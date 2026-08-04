import json
import logging
from typing import TypedDict, List, Optional, Literal

from langgraph.graph import StateGraph, END
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.agent.retrieval import retrieve_news_chunks, get_latest_fundamentals, RetrievedChunk
from app.agent.scoring import rank_followed_stocks
from app.agent.persona import get_or_create_persona, update_persona_from_message
from app.db.models import InvestorPersona

logger = logging.getLogger(__name__)

_HTTP_OPTIONS = types.HttpOptions(timeout=15_000)  # milliseconds — fail fast, don't hang the request
_client = (
    genai.Client(api_key=settings.GEMINI_API_KEY, http_options=_HTTP_OPTIONS)
    if settings.GEMINI_API_KEY
    else None
)


class AgentState(TypedDict):
    db: Session               # not serialized; passed through in-process
    user_id: str
    message: str
    intent: Optional[Literal["recommend", "qa"]]
    stock_symbols: List[str]
    retrieved: List[RetrievedChunk]
    persona: Optional[InvestorPersona]
    persona_updated: bool
    answer: str
    citations: List[dict]


def node_update_memory(state: AgentState) -> AgentState:
    """From Chat: extract and persist any investor-persona facts in this turn's message."""
    updated_persona = update_persona_from_message(state["db"], state["user_id"], state["message"])
    state["persona"] = updated_persona or get_or_create_persona(state["db"], state["user_id"])
    # Distinguishes "this message actually contained new persona info" from
    # "no facts here" — used downstream so a pure persona statement (no stock
    # question) gets a confirmation instead of a QA-style "no data" refusal.
    state["persona_updated"] = updated_persona is not None
    return state


def node_classify_intent(state: AgentState) -> AgentState:
    """Cheap keyword routing first; falls back to a small LLM call only if ambiguous."""
    msg = state["message"].lower()
    if any(kw in msg for kw in ["recommend", "should i buy", "what to buy", "suggest stocks", "pick for me"]):
        state["intent"] = "recommend"
    else:
        state["intent"] = "qa"
    return state


def node_extract_tickers(state: AgentState) -> AgentState:
    """Extract mentioned NSE tickers heuristically (uppercase tokens); falls back to all followed stocks downstream."""
    import re
    candidates = re.findall(r"\b[A-Z]{2,15}\b", state["message"])
    noise = {"I", "A", "NSE", "BSE", "INR", "RS"}
    state["stock_symbols"] = [c for c in candidates if c not in noise]
    return state


def node_retrieve(state: AgentState) -> AgentState:
    symbols = state["stock_symbols"] or None
    try:
        state["retrieved"] = retrieve_news_chunks(state["db"], state["message"], stock_symbols=symbols, k=8)
    except RuntimeError as e:
        # Embedding call failed (bad/misconfigured key, transient outage, etc.) — degrade to
        # "no grounded data" rather than raising and killing the whole request/connection.
        logger.warning(f"Retrieval failed, answering ungrounded-refusal instead: {e}")
        state["retrieved"] = []
    return state


def node_answer_qa(state: AgentState) -> AgentState:
    """Grounded QA: only asserts what's in retrieved chunks + fundamentals; refuses to invent numbers."""
    chunks = state["retrieved"]
    fundamentals_ctx = []
    for sym in (state["stock_symbols"] or []):
        f = get_latest_fundamentals(state["db"], sym)
        if f:
            fundamentals_ctx.append(
                f"{sym}: P/E {f.pe_ratio}, D/E {f.debt_to_equity}, ROE {f.roe_pct}%, "
                f"Div Yield {f.dividend_yield_pct}%, Price Rs.{f.current_price_inr} (as of {f.fetched_at})"
            )

    if not chunks and not fundamentals_ctx:
        if not state["stock_symbols"] and state.get("persona_updated"):
            persona = state["persona"]
            tags = ", ".join(persona.style_tags or []) or "no specific style tags yet"
            state["answer"] = (
                f"Got it — I've updated your investor profile "
                f"(risk profile: {persona.risk_profile or 'not set'}; style: {tags}). "
                f"Ask me for picks any time, or follow a stock to get grounded, cited analysis on it."
            )
            state["citations"] = []
            return state
        state["answer"] = "I don't have that in the ingested data yet — try following the stock first so I can pull its fundamentals and news."
        state["citations"] = []
        return state

    context_blocks = [f"[{i+1}] ({c.stock_symbol}, {c.sentiment}) {c.text}" for i, c in enumerate(chunks)]
    system = (
        "You are an Indian equity research assistant. Answer ONLY using the numbered context below "
        "and the fundamentals snapshot. All figures must be in INR (Rs.). Cite claims using [n] referring "
        "to the context items. If the answer isn't supported by the context, say so explicitly — never invent numbers."
    )
    user_msg = (
        f"Question: {state['message']}\n\n"
        f"Fundamentals:\n" + "\n".join(fundamentals_ctx) + "\n\n"
        f"News context:\n" + "\n".join(context_blocks)
    )

    if _client:
        try:
            resp = _client.models.generate_content(
                model=settings.CHAT_MODEL,
                contents=user_msg,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
            )
            state["answer"] = resp.text
        except Exception as e:
            logger.warning(f"Chat generation failed: {e}")
            state["answer"] = (
                "I retrieved relevant sources but couldn't reach the language model to summarize them "
                "(provider error). Here's what's in the data: "
                + "; ".join(context_blocks[:3])
            )
    else:
        state["answer"] = "LLM not configured."

    state["citations"] = [
        {"type": "news", "id": c.chunk_id, "label": c.source_title, "url": c.source_url, "stock": c.stock_symbol}
        for c in chunks
    ] + [
        {"type": "fundamentals", "label": line} for line in fundamentals_ctx
    ]
    return state


def node_recommend(state: AgentState) -> AgentState:
    """
    Recommendation flow: scores every FOLLOWED stock against the persona using
    pure algorithmic scoring (app.agent.scoring) — no LLM call per stock. The LLM
    is only used once, at the end, to phrase the final cited summary.
    """
    persona = state["persona"] or get_or_create_persona(state["db"], state["user_id"])
    ranked = rank_followed_stocks(state["db"], state["user_id"], persona)
    top = [r for r in ranked if not r.debt_flag or persona.risk_profile != "conservative"][:5]

    if not top:
        state["answer"] = "You aren't following any stocks yet, or none have enough ingested data. Follow a few NSE tickers first."
        state["citations"] = []
        return state

    lines = [f"- {r.symbol} ({r.name}): score {r.score}, {r.reason}" for r in top]
    prompt_ctx = "\n".join(lines)

    system = (
        "You are an Indian equity research assistant writing a short, cited recommendation summary. "
        "Use ONLY the ranked list given — do not invent numbers or stocks not listed. All prices/figures in INR."
    )
    user_msg = f"Investor persona: {persona.risk_profile}, tags: {persona.style_tags}\n\nRanked candidates:\n{prompt_ctx}"

    if _client:
        try:
            resp = _client.models.generate_content(
                model=settings.CHAT_MODEL,
                contents=user_msg,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.3),
            )
            state["answer"] = resp.text
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {e}")
            state["answer"] = "Couldn't reach the language model to phrase this, but here are your ranked picks:\n" + prompt_ctx
    else:
        state["answer"] = prompt_ctx

    state["citations"] = [{"type": "score", "label": f"{r.symbol}: {r.reason}", "stock": r.symbol} for r in top]
    return state


def route_intent(state: AgentState) -> str:
    return "recommend" if state["intent"] == "recommend" else "qa"


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("update_memory", node_update_memory)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("extract_tickers", node_extract_tickers)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("answer_qa", node_answer_qa)
    graph.add_node("recommend", node_recommend)

    graph.set_entry_point("update_memory")
    graph.add_edge("update_memory", "classify_intent")
    graph.add_edge("classify_intent", "extract_tickers")
    graph.add_conditional_edges("extract_tickers", route_intent, {"recommend": "recommend", "qa": "retrieve"})
    graph.add_edge("retrieve", "answer_qa")
    graph.add_edge("answer_qa", END)
    graph.add_edge("recommend", END)

    return graph.compile()


_compiled_graph = None


def get_agent_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph


def run_agent(db: Session, user_id: str, message: str) -> dict:
    graph = get_agent_graph()
    initial_state: AgentState = {
        "db": db, "user_id": user_id, "message": message,
        "intent": None, "stock_symbols": [], "retrieved": [],
        "persona": None, "persona_updated": False, "answer": "", "citations": [],
    }
    final_state = graph.invoke(initial_state)
    return {"answer": final_state["answer"], "citations": final_state["citations"]}

import json
from typing import Optional

from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.core.config import settings
from app.db.models import InvestorPersona, PersonaFact
from app.ingestion.embeddings import embed_text

_HTTP_OPTIONS = types.HttpOptions(timeout=15_000)
_client = (
    genai.Client(api_key=settings.GEMINI_API_KEY, http_options=_HTTP_OPTIONS)
    if settings.GEMINI_API_KEY
    else None
)

_EXTRACT_PROMPT = """Extract investor-preference facts from this message, if any (risk tolerance, sector
preferences, style like dividend/growth/value, things to avoid like high debt). Return ONLY JSON:
{"has_facts": bool, "facts": ["..."], "risk_profile": "conservative"|"moderate"|"aggressive"|null, "style_tags": ["..."]}
If the message has no investor-preference content, return has_facts: false and empty lists."""


def extract_persona_facts(message: str) -> dict:
    if not _client:
        return {"has_facts": False, "facts": [], "risk_profile": None, "style_tags": []}
    try:
        resp = _client.models.generate_content(
            model=settings.CHAT_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_PROMPT,
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        return json.loads(resp.text)
    except Exception:
        return {"has_facts": False, "facts": [], "risk_profile": None, "style_tags": []}


def update_persona_from_message(db: Session, user_id: str, message: str) -> Optional[InvestorPersona]:
    """
    Called on every user chat turn. Only writes when the extractor actually finds
    persona-relevant content — most turns are a no-op here.
    """
    extracted = extract_persona_facts(message)
    if not extracted.get("has_facts"):
        return None

    for fact in extracted.get("facts", []):
        db.add(PersonaFact(user_id=user_id, fact_text=fact, source="chat"))

    persona = db.query(InvestorPersona).filter(InvestorPersona.user_id == user_id).first()
    if not persona:
        persona = InvestorPersona(user_id=user_id, style_tags=[], summary_text="")
        db.add(persona)
        db.flush()

    if extracted.get("risk_profile"):
        persona.risk_profile = extracted["risk_profile"]

    existing_tags = set((persona.style_tags or []))
    existing_tags.update(extracted.get("style_tags", []))
    persona.style_tags = list(existing_tags)

    facts_text = " ".join(extracted.get("facts", []))
    persona.summary_text = f"{persona.summary_text or ''} {facts_text}".strip()

    try:
        persona.embedding = embed_text(persona.summary_text) if persona.summary_text else None
    except RuntimeError:
        pass

    db.commit()
    db.refresh(persona)
    return persona


def get_or_create_persona(db: Session, user_id: str) -> InvestorPersona:
    persona = db.query(InvestorPersona).filter(InvestorPersona.user_id == user_id).first()
    if not persona:
        persona = InvestorPersona(user_id=user_id, style_tags=[], risk_profile="moderate", summary_text="")
        db.add(persona)
        db.commit()
        db.refresh(persona)
    return persona

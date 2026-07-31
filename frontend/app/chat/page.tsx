"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, getToken } from "@/lib/api";
import ChatMessageBubble, { Message } from "@/components/ChatMessageBubble";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!getToken()) {
      router.push("/");
      return;
    }
    api
      .chatHistory()
      .then((history) => setMessages(history))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    try {
      const res = await api.chat(text);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, citations: res.citations }]);
    } catch (err: any) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${err.message}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col max-w-3xl mx-auto px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white">
          ← Dashboard
        </Link>
        <h1 className="text-lg font-semibold">Equity Research Chat</h1>
        <div className="w-16" />
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {messages.length === 0 && (
          <p className="text-gray-500 text-sm text-center mt-12">
            Ask something like "What's the sentiment on TCS this week?" or "Recommend stocks for my profile."
          </p>
        )}
        {messages.map((m, i) => (
          <ChatMessageBubble key={i} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex gap-2 pt-4 border-t border-white/10">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a stock, sentiment, or get recommendations…"
          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={sending}
          className="bg-accent text-ink font-medium px-5 py-3 rounded-lg text-sm disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </form>
    </main>
  );
}

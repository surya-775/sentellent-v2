"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function FollowTickerForm({ onFollowed }: { onFollowed: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.followStock(symbol.trim().toUpperCase());
      setSymbol("");
      onFollowed();
    } catch (err: any) {
      setError(err.message || "Failed to follow stock");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        placeholder="e.g. RELIANCE, TCS, HDFCBANK"
        className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
      />
      <button
        type="submit"
        disabled={loading}
        className="bg-accent text-ink font-medium px-4 py-2 rounded-lg text-sm disabled:opacity-50"
      >
        {loading ? "Following…" : "Follow"}
      </button>
      {error && <p className="text-red-400 text-xs self-center">{error}</p>}
    </form>
  );
}

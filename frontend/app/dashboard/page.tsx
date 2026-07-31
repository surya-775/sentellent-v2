"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, getToken, clearToken } from "@/lib/api";
import FollowTickerForm from "@/components/FollowTickerForm";

interface Stock {
  nse_symbol: string;
  name: string;
  sector: string | null;
}

export default function Dashboard() {
  const router = useRouter();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadStocks() {
    try {
      const data = await api.listFollowed();
      setStocks(data);
    } catch {
      router.push("/");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/");
      return;
    }
    loadStocks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="min-h-screen px-6 py-10 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">Your Watchlist</h1>
        <div className="flex gap-3">
          <Link href="/chat" className="text-sm bg-accent text-ink px-4 py-2 rounded-lg font-medium">
            Open Chat
          </Link>
          <button
            onClick={() => {
              clearToken();
              router.push("/");
            }}
            className="text-sm text-gray-400 hover:text-white px-4 py-2"
          >
            Sign out
          </button>
        </div>
      </div>

      <div className="mb-8">
        <FollowTickerForm onFollowed={loadStocks} />
        <p className="text-xs text-gray-500 mt-2">
          Following a ticker queues fundamentals + news ingestion in the background — it may take a minute to show up in chat.
        </p>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : stocks.length === 0 ? (
        <p className="text-gray-500 text-sm">No stocks followed yet. Add an NSE ticker above to get started.</p>
      ) : (
        <ul className="space-y-2">
          {stocks.map((s) => (
            <li key={s.nse_symbol} className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 flex justify-between">
              <span className="font-medium">{s.nse_symbol}</span>
              <span className="text-gray-400 text-sm">{s.name}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

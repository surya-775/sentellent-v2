"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken, googleLoginUrl } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (getToken()) router.push("/dashboard");
  }, [router]);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <p className="text-sm uppercase tracking-widest text-accent mb-3">Sentellent</p>
      <h1 className="text-4xl md:text-5xl font-semibold max-w-2xl">
        Your Agentic AI Indian Equity Research Chief of Staff
      </h1>
      <p className="mt-4 text-gray-400 max-w-xl">
        Follow NSE/BSE tickers, get cited answers grounded in real fundamentals and news, all in INR.
      </p>
      <a
        href={googleLoginUrl()}
        className="mt-8 bg-accent text-ink font-medium px-6 py-3 rounded-lg hover:opacity-90 transition"
      >
        Sign in with Google
      </a>
    </main>
  );
}

"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setToken } from "@/lib/api";

function AuthCallbackInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");

    console.log("Callback token:", token);

    if (token) {
      setToken(token);

      console.log(
        "Stored token after setToken:",
        localStorage.getItem("token")
      );

      router.push("/dashboard");
    } else {
      console.log("No token found");
      router.push("/");
    }
  }, [params, router]);

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-400">Signing you in…</p>
    </main>
  );
}

export default function AuthCallback() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen flex items-center justify-center">
          <p className="text-gray-400">Signing you in…</p>
        </main>
      }
    >
      <AuthCallbackInner />
    </Suspense>
  );
}
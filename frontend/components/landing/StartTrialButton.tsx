"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { startSession } from "@/lib/api";

export function StartTrialButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      const session = await startSession();
      router.push(`/session/${session.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "체험 세션을 시작하지 못했습니다.");
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        className="primaryButton"
        type="button"
        onClick={handleStart}
        disabled={loading}
      >
        {loading ? "추천 준비 중..." : "추천 시작하기"}
      </button>
      {error ? (
        <div className="statusBanner" style={{ marginTop: 14 }}>
          {error}
        </div>
      ) : null}
    </div>
  );
}

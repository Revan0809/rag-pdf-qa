"use client";

import { useEffect, useState } from "react";

import { pingHealth } from "@/lib/api";

type Status = "checking" | "slow" | "ready" | "down";

export default function ColdStartBanner() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const slowTimer = window.setTimeout(() => {
      if (!cancelled) setStatus((current) => (current === "checking" ? "slow" : current));
    }, 1500);

    pingHealth().then((ok) => {
      if (cancelled) return;
      window.clearTimeout(slowTimer);
      setStatus(ok ? "ready" : "down");
    });

    return () => {
      cancelled = true;
      window.clearTimeout(slowTimer);
    };
  }, []);

  if (status !== "slow" && status !== "down") return null;

  return (
    <div
      role="status"
      className="w-full border-b border-border bg-warning/10 px-4 py-2 text-center text-sm text-warning"
    >
      {status === "slow"
        ? "Waking up the agents… the backend sleeps when idle on its free tier, so the first request can take up to a minute."
        : "Couldn't reach the backend. It may still be waking up — try again in a moment."}
    </div>
  );
}

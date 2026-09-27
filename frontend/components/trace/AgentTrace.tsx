"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Compass, FileSearch, Loader2, PenLine, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { AgentName, TraceEvent } from "@/types";

interface AgentTraceProps {
  events: TraceEvent[];
  isStreaming: boolean;
}

const AGENT_ICON: Record<AgentName, typeof Compass> = {
  planner: Compass,
  retriever: FileSearch,
  analyst: PenLine,
  verifier: ShieldCheck,
};

const AGENT_LABEL: Record<AgentName, string> = {
  planner: "Planner",
  retriever: "Retriever",
  analyst: "Analyst",
  verifier: "Verifier",
};

export default function AgentTrace({ events, isStreaming }: AgentTraceProps) {
  const [isOpen, setIsOpen] = useState(true);

  if (events.length === 0 && !isStreaming) return null;

  return (
    <div className="rounded-xl border border-border bg-surface/60">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-from"
      >
        <span>Agent trace</span>
        <span aria-hidden="true">{isOpen ? "−" : "+"}</span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <ol className="flex flex-col gap-1.5 px-3 pb-3">
              <AnimatePresence initial={false}>
                {events.map((event, index) => {
                  const Icon = AGENT_ICON[event.agent];
                  return (
                    <motion.li
                      key={`${event.agent}-${index}`}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-start gap-2 text-xs"
                    >
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success/15 text-success">
                        <Icon size={12} aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="font-medium text-text">{AGENT_LABEL[event.agent]}</span>
                        <span className="text-text-muted"> · {event.summary}</span>
                      </span>
                      <span className="shrink-0 text-text-muted">{event.duration_ms}ms</span>
                    </motion.li>
                  );
                })}
              </AnimatePresence>

              {isStreaming && (
                <motion.li
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 text-xs text-text-muted"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-from/15 text-accent-from">
                    <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                  </span>
                  <span>Working…</span>
                </motion.li>
              )}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

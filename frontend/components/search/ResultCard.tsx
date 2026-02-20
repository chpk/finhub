"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, FileText, Hash } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { SearchResult } from "@/lib/types";

interface ResultCardProps {
  result: SearchResult;
  queryTerms?: string[];
}

function highlightText(text: string, terms: string[]): React.ReactNode {
  if (terms.length === 0) return text;
  const regex = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|")})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="rounded bg-yellow-100 px-0.5 text-foreground">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

export function ResultCard({ result, queryTerms = [] }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false);
  const meta = result.metadata || {};

  const scorePercent = Math.max(0, Math.min(100, (1 - (result.score || 0)) * 100));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border bg-card transition-shadow hover:shadow-sm overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 p-5 text-left"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 mt-0.5">
          <FileText className="h-4 w-4 text-primary" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold">
              {(meta.source_file as string) || result.collection || "Document"}
            </p>
            {meta.page_number != null && (
              <span className="text-xs text-muted-foreground">
                p.{String(meta.page_number)}
              </span>
            )}
            {meta.framework != null && (
              <Badge variant="secondary" className="text-[10px]">
                {String(meta.framework)}
              </Badge>
            )}
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground line-clamp-3">
            {highlightText(result.text, queryTerms)}
          </p>
          {meta.section_path != null && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Hash className="h-3 w-3" />
              {String(meta.section_path)}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 mt-1">
          <Badge variant="default" className="tabular-nums">
            {scorePercent.toFixed(0)}%
          </Badge>
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </motion.div>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="border-t px-5 py-4">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Full Content
              </p>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {highlightText(result.text, queryTerms)}
              </p>
              {Object.keys(meta).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Metadata
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(meta).map(([key, value]) => (
                      <span
                        key={key}
                        className="rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground"
                      >
                        {key}: {String(value)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

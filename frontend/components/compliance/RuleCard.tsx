"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  MinusCircle,
  HelpCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ComplianceCheckResult, ComplianceStatus } from "@/lib/types";

const statusConfig: Record<
  ComplianceStatus,
  { label: string; icon: React.ElementType; variant: "success" | "danger" | "warning" | "muted" }
> = {
  compliant: { label: "Compliant", icon: CheckCircle2, variant: "success" },
  non_compliant: { label: "Non-Compliant", icon: XCircle, variant: "danger" },
  partially_compliant: { label: "Partial", icon: AlertTriangle, variant: "warning" },
  not_applicable: { label: "N/A", icon: MinusCircle, variant: "muted" },
  unable_to_determine: { label: "Uncertain", icon: HelpCircle, variant: "muted" },
};

interface RuleCardProps {
  result: ComplianceCheckResult;
}

export function RuleCard({ result }: RuleCardProps) {
  const [expanded, setExpanded] = useState(false);
  const cfg = statusConfig[result.status] || statusConfig.unable_to_determine;
  const Icon = cfg.icon;

  return (
    <motion.div
      layout
      className="rounded-xl border bg-card transition-shadow hover:shadow-sm overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <Icon className={`h-4.5 w-4.5 shrink-0 ${
          cfg.variant === "success" ? "text-emerald-500" :
          cfg.variant === "danger" ? "text-red-500" :
          cfg.variant === "warning" ? "text-amber-500" :
          "text-gray-400"
        }`} />

        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug">{result.rule_source}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {result.rule_text}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
          <span className="text-xs text-muted-foreground tabular-nums">
            {Math.round(result.confidence * 100)}%
          </span>
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
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t px-4 py-4 space-y-4">
              {/* Rule text */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Regulatory Requirement
                </p>
                <p className="mt-1 text-sm leading-relaxed">{result.rule_text}</p>
              </div>

              {/* Evidence */}
              {result.evidence && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Evidence
                  </p>
                  <p className="mt-1 rounded-lg bg-muted/50 p-3 text-sm italic leading-relaxed text-muted-foreground">
                    &ldquo;{result.evidence}&rdquo;
                  </p>
                </div>
              )}

              {/* Explanation */}
              {result.explanation && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Explanation
                  </p>
                  <p className="mt-1 text-sm leading-relaxed">{result.explanation}</p>
                </div>
              )}

              {/* Recommendations */}
              {result.recommendations && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Recommendations
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-primary">
                    {result.recommendations}
                  </p>
                </div>
              )}

              {/* Confidence bar */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Confidence
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-primary"
                      initial={{ width: 0 }}
                      animate={{ width: `${result.confidence * 100}%` }}
                      transition={{ duration: 0.6, ease: "easeOut" }}
                    />
                  </div>
                  <span className="text-xs font-medium tabular-nums">
                    {Math.round(result.confidence * 100)}%
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

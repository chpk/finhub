"use client";

import { motion } from "framer-motion";
import { CircularProgress } from "@/components/ui/circular-progress";
import { Badge } from "@/components/ui/badge";
import type { ComplianceReport } from "@/lib/types";

interface ComplianceMatrixProps {
  report: ComplianceReport | null;
  loading?: boolean;
}

export function ComplianceMatrix({ report, loading }: ComplianceMatrixProps) {
  if (loading) {
    return (
      <div className="rounded-2xl border bg-card p-6">
        <div className="skeleton h-6 w-48 rounded-lg" />
        <div className="mt-6 flex items-center justify-center py-12">
          <div className="skeleton h-40 w-40 rounded-full" />
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="rounded-2xl border bg-card p-6">
        <h2 className="text-lg font-semibold">Compliance Results</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Run a compliance check to see results.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <div className="h-32 w-32 rounded-full bg-muted/40 flex items-center justify-center">
            <span className="text-3xl font-bold text-muted-foreground/30">—</span>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Select a document and frameworks, then run validation.
          </p>
        </div>
      </div>
    );
  }

  const breakdowns = [
    {
      label: "Compliant",
      value: report.compliant_count,
      color: "bg-emerald-500",
      textColor: "text-emerald-700",
    },
    {
      label: "Non-Compliant",
      value: report.non_compliant_count,
      color: "bg-red-500",
      textColor: "text-red-700",
    },
    {
      label: "Partial",
      value: report.partially_compliant_count,
      color: "bg-amber-500",
      textColor: "text-amber-700",
    },
    {
      label: "N/A",
      value: report.not_applicable_count,
      color: "bg-gray-300",
      textColor: "text-gray-500",
    },
  ];

  return (
    <div className="rounded-2xl border bg-card p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Compliance Results</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {report.document_name}
            {report.company_name && ` — ${report.company_name}`}
          </p>
        </div>
        <div className="flex gap-2">
          {report.frameworks_tested.map((fw) => (
            <Badge key={fw} variant="secondary">{fw}</Badge>
          ))}
        </div>
      </div>

      <div className="mt-8 flex flex-col items-center gap-8 sm:flex-row sm:justify-around">
        {/* Circular score */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          <CircularProgress value={report.overall_compliance_score} size={180} strokeWidth={14} />
        </motion.div>

        {/* Breakdown */}
        <div className="grid grid-cols-2 gap-x-8 gap-y-4">
          {breakdowns.map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              <div className={`h-3 w-3 rounded-full ${item.color}`} />
              <div>
                <p className="text-2xl font-semibold tabular-nums">{item.value}</p>
                <p className="text-xs text-muted-foreground">{item.label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Summary */}
      {report.summary && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mt-8 rounded-xl bg-muted/40 p-5"
        >
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
            Executive Summary
          </p>
          <p className="text-sm leading-relaxed">{report.summary}</p>
        </motion.div>
      )}
    </div>
  );
}

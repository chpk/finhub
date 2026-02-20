"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Filter, Download } from "lucide-react";
import { RuleCard } from "./RuleCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ComplianceReport as ReportType, ComplianceStatus } from "@/lib/types";

interface ComplianceReportViewProps {
  report: ReportType | null;
}

const filterOptions: { label: string; value: ComplianceStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Non-Compliant", value: "non_compliant" },
  { label: "Partial", value: "partially_compliant" },
  { label: "Compliant", value: "compliant" },
  { label: "N/A", value: "not_applicable" },
];

export function ComplianceReport({ report }: ComplianceReportViewProps) {
  const [filter, setFilter] = useState<ComplianceStatus | "all">("all");

  const filteredResults = useMemo(() => {
    if (!report) return [];
    if (filter === "all") return report.results;
    return report.results.filter((r) => r.status === filter);
  }, [report, filter]);

  if (!report) {
    return (
      <div className="rounded-2xl border bg-card p-6">
        <h2 className="text-lg font-semibold">Detailed Results</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Individual rule assessments will appear here after validation.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <p className="text-sm text-muted-foreground">
            Run a compliance check to see detailed rule-by-rule analysis.
          </p>
        </div>
      </div>
    );
  }

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance-report-${report.report_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-2xl border bg-card p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Detailed Results</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {report.total_rules_checked} rules checked
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleDownload}>
          <Download className="mr-1.5 h-3.5 w-3.5" />
          Download JSON
        </Button>
      </div>

      {/* Filter pills */}
      <div className="mt-5 flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        {filterOptions.map((opt) => {
          const count =
            opt.value === "all"
              ? report.results.length
              : report.results.filter((r) => r.status === opt.value).length;
          return (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                filter === opt.value
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {opt.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Results list */}
      <div className="mt-5 space-y-2">
        {filteredResults.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No results matching this filter.
          </p>
        ) : (
          filteredResults.map((result, i) => (
            <motion.div
              key={result.rule_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <RuleCard result={result} />
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}

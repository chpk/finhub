"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Download,
  Eye,
  Clock,
  ShieldCheck,
  ChevronRight,
  FileJson,
  FileSpreadsheet,
  FileDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getComplianceReports,
  downloadReportJson,
  downloadReportPdf,
  downloadReportExcel,
} from "@/lib/api";
import type { ComplianceReport } from "@/lib/types";

export default function ReportsPage() {
  const [reports, setReports] = useState<ComplianceReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ComplianceReport | null>(null);

  useEffect(() => {
    getComplianceReports(0, 50)
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDownloadJson = async (report: ComplianceReport) => {
    try {
      await downloadReportJson(report.report_id);
    } catch {
      // Fallback: download from local state
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${report.report_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleDownloadPdf = async (report: ComplianceReport) => {
    try {
      await downloadReportPdf(report.report_id);
    } catch (err) {
      alert("PDF download failed. WeasyPrint may not be installed on the server.");
    }
  };

  const handleDownloadExcel = async (report: ComplianceReport) => {
    try {
      await downloadReportExcel(report.report_id);
    } catch (err) {
      alert("Excel download failed.");
    }
  };

  const scoreColor = (score: number) =>
    score >= 80 ? "text-emerald-600" : score >= 60 ? "text-amber-600" : "text-red-600";

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <h1 className="text-4xl font-semibold tracking-tight">
          Compliance Reports
        </h1>
        <p className="mt-3 text-muted-foreground">
          View, download, and manage generated compliance validation reports.
        </p>
      </motion.div>

      <motion.div
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15 }}
      >
        <div className="rounded-2xl border bg-card">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-6 py-4">
            <h2 className="text-lg font-semibold">Generated Reports</h2>
            <span className="text-sm text-muted-foreground">
              {reports.length} report{reports.length !== 1 ? "s" : ""}
            </span>
          </div>

          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton h-16 w-full rounded-xl" />
              ))}
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted/50">
                <FileText className="h-7 w-7 text-muted-foreground/30" />
              </div>
              <p className="mt-4 text-muted-foreground">
                No reports generated yet.
              </p>
              <p className="mt-1 text-sm text-muted-foreground/70">
                Run a compliance check to generate your first report.
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {reports.map((report, i) => (
                <motion.div
                  key={report.report_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-muted/30"
                >
                  {/* Score */}
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted/50">
                    <span
                      className={`text-lg font-bold tabular-nums ${scoreColor(report.overall_compliance_score)}`}
                    >
                      {Math.round(report.overall_compliance_score)}%
                    </span>
                  </div>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold">
                        {report.document_name}
                      </p>
                      {report.company_name && (
                        <span className="text-xs text-muted-foreground">
                          — {report.company_name}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <ShieldCheck className="h-3 w-3" />
                        {report.total_rules_checked} rules
                      </span>
                      <span>{report.frameworks_tested.join(", ")}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {report.generated_at
                          ? new Date(report.generated_at).toLocaleDateString()
                          : "—"}
                      </span>
                    </div>
                  </div>

                  {/* Status badges */}
                  <div className="hidden gap-1.5 sm:flex">
                    <Badge variant="success">{report.compliant_count}</Badge>
                    <Badge variant="danger">{report.non_compliant_count}</Badge>
                    <Badge variant="warning">{report.partially_compliant_count}</Badge>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      title="View details"
                      onClick={() => setSelected(report)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Download JSON"
                      onClick={() => handleDownloadJson(report)}
                    >
                      <FileJson className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Download PDF"
                      onClick={() => handleDownloadPdf(report)}
                    >
                      <FileDown className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Download Excel"
                      onClick={() => handleDownloadExcel(report)}
                    >
                      <FileSpreadsheet className="h-4 w-4" />
                    </Button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Detail panel */}
      {selected && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 rounded-2xl border bg-card p-6"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              {selected.document_name}
            </h3>
            <button
              onClick={() => setSelected(null)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>

          {selected.summary && (
            <div className="mt-4 rounded-xl bg-muted/40 p-4">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
                Executive Summary
              </p>
              <p className="text-sm leading-relaxed">{selected.summary}</p>
            </div>
          )}

          <div className="mt-4 space-y-2 max-h-[400px] overflow-y-auto">
            {selected.results.map((r) => (
              <div
                key={r.rule_id}
                className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm"
              >
                <Badge
                  variant={
                    r.status === "compliant"
                      ? "success"
                      : r.status === "non_compliant"
                        ? "danger"
                        : r.status === "partially_compliant"
                          ? "warning"
                          : "muted"
                  }
                >
                  {r.status.replace("_", " ")}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{r.rule_source}</p>
                  <p className="text-xs text-muted-foreground truncate">
                    {r.rule_text}
                  </p>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {Math.round(r.confidence * 100)}%
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}

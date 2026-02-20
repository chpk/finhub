"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Search,
  AlertTriangle,
  Clock,
  FileText,
  ChevronRight,
  Loader2,
  Send,
  Building2,
  Activity,
  TrendingDown,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Info,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import {
  getRiskDashboard,
  getComplianceTimeline,
  examineCompany,
} from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";
import type { RiskDashboard, TimelineEvent, ExaminationAnalysis } from "@/lib/types";

const SEVERITY_COLORS: Record<string, string> = {
  high: "#ff3b30",
  medium: "#ff9f0a",
  low: "#30d158",
  critical: "#ff3b30",
  minimal: "#30d158",
  unknown: "#86868b",
};

const SEVERITY_BG: Record<string, string> = {
  high: "bg-red-50 border-red-200 text-red-700",
  medium: "bg-amber-50 border-amber-200 text-amber-700",
  low: "bg-emerald-50 border-emerald-200 text-emerald-700",
};

const EVENT_ICONS: Record<string, React.ReactNode> = {
  document_ingested: <FileText className="h-4 w-4" />,
  compliance_check: <Shield className="h-4 w-4" />,
};

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  warning: <AlertCircle className="h-4 w-4 text-amber-500" />,
  danger: <XCircle className="h-4 w-4 text-red-500" />,
  info: <Info className="h-4 w-4 text-blue-500" />,
};

export default function ExaminationPage() {
  const [risk, setRisk] = useState<RiskDashboard | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [riskLoading, setRiskLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(true);

  const [companyName, setCompanyName] = useState("");
  const [examQuestion, setExamQuestion] = useState("");
  const [examResult, setExamResult] = useState<ExaminationAnalysis | null>(null);
  const [examLoading, setExamLoading] = useState(false);

  const { toast } = useToast();

  useEffect(() => {
    getRiskDashboard()
      .then(setRisk)
      .catch(() => toast("Failed to load risk dashboard.", "error"))
      .finally(() => setRiskLoading(false));

    getComplianceTimeline()
      .then(setTimeline)
      .catch(() => toast("Failed to load timeline.", "error"))
      .finally(() => setTimelineLoading(false));
  }, []);

  const handleExamine = useCallback(async () => {
    if (!companyName.trim() || !examQuestion.trim()) {
      toast("Enter both company name and question.", "error");
      return;
    }
    setExamLoading(true);
    setExamResult(null);
    try {
      const res = await examineCompany(companyName, examQuestion);
      setExamResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Examination failed";
      toast(msg, "error");
    } finally {
      setExamLoading(false);
    }
  }, [companyName, examQuestion, toast]);

  const riskPieData = risk
    ? [
        { name: "Score", value: risk.risk_score },
        { name: "Remaining", value: 100 - risk.risk_score },
      ]
    : [];

  const riskColor =
    SEVERITY_COLORS[risk?.overall_risk || "unknown"] || "#86868b";

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#ff3b30] to-[#ff9f0a]">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Preliminary Examination
            </h1>
            <p className="text-sm text-muted-foreground">
              Risk assessment, compliance timeline & company investigation
            </p>
          </div>
        </div>
      </motion.div>

      {/* Top Row: Risk + Company Search */}
      <div className="grid gap-6 lg:grid-cols-2 mb-6">
        {/* Risk Dashboard */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl border bg-card p-6 shadow-sm"
        >
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            Risk Dashboard
          </h2>

          {riskLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : risk ? (
            <div className="flex items-start gap-6">
              {/* Risk Score Gauge */}
              <div className="w-32 shrink-0">
                <ResponsiveContainer width="100%" height={130}>
                  <PieChart>
                    <Pie
                      data={riskPieData}
                      startAngle={180}
                      endAngle={0}
                      innerRadius={40}
                      outerRadius={55}
                      dataKey="value"
                    >
                      <Cell fill={riskColor} />
                      <Cell fill="#e5e5e5" />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="text-center -mt-10">
                  <p className="text-2xl font-bold" style={{ color: riskColor }}>
                    {risk.risk_score}
                  </p>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">
                    {risk.overall_risk} risk
                  </p>
                </div>
              </div>

              {/* Risk Metrics */}
              <div className="flex-1 space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-lg bg-muted/30 p-2.5">
                    <p className="text-xs text-muted-foreground">Docs Analysed</p>
                    <p className="font-semibold">{risk.documents_analysed}</p>
                  </div>
                  <div className="rounded-lg bg-muted/30 p-2.5">
                    <p className="text-xs text-muted-foreground">Reports</p>
                    <p className="font-semibold">{risk.reports_analysed}</p>
                  </div>
                </div>

                <div className="space-y-1.5">
                  {risk.flags.slice(0, 4).map((f, i) => (
                    <div
                      key={i}
                      className={`flex items-start gap-2 rounded-lg border px-2.5 py-2 text-xs ${
                        SEVERITY_BG[f.severity] || "bg-muted/30"
                      }`}
                    >
                      <div
                        className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full`}
                        style={{
                          backgroundColor:
                            SEVERITY_COLORS[f.severity] || "#86868b",
                        }}
                      />
                      <p className="line-clamp-2">{f.description}</p>
                    </div>
                  ))}
                  {risk.flags.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      No risk flags detected.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No risk data available.
            </p>
          )}
        </motion.div>

        {/* Company Investigation */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl border bg-card p-6 shadow-sm"
        >
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            Company Investigation
          </h2>

          <div className="space-y-3">
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Enter company name..."
              className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            <input
              type="text"
              value={examQuestion}
              onChange={(e) => setExamQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleExamine()}
              placeholder="What would you like to investigate?"
              className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            <button
              onClick={handleExamine}
              disabled={examLoading || !companyName.trim() || !examQuestion.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {examLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Investigate
            </button>
          </div>

          <AnimatePresence>
            {examResult && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 overflow-hidden"
              >
                <div className="rounded-xl border bg-muted/20 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="h-4 w-4 text-primary" />
                    <span className="text-xs font-semibold">
                      Analysis: {examResult.company}
                    </span>
                  </div>
                  <div className="prose prose-sm max-w-none text-sm text-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">
                    {examResult.answer}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* Timeline */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="rounded-2xl border bg-card p-6 shadow-sm"
      >
        <h2 className="text-sm font-semibold mb-5 flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          Compliance Timeline
        </h2>

        {timelineLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : timeline.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <Clock className="h-8 w-8 text-muted-foreground/30 mb-2" />
            <p className="text-sm text-muted-foreground">
              No events yet. Ingest documents and run compliance checks to build
              the timeline.
            </p>
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />
            <div className="space-y-4">
              {timeline.slice(0, 20).map((event, i) => (
                <motion.div
                  key={`${event.type}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="relative flex gap-4 pl-3"
                >
                  {/* Dot */}
                  <div
                    className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border bg-card"
                    style={{
                      borderColor:
                        SEVERITY_COLORS[event.severity] || "#d2d2d7",
                    }}
                  >
                    {SEVERITY_ICONS[event.severity] ||
                      EVENT_ICONS[event.type] || (
                        <Info className="h-4 w-4 text-muted-foreground" />
                      )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 rounded-xl border bg-card/50 p-4 hover:bg-muted/20 transition-colors">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">
                          {event.title}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {event.description}
                        </p>
                      </div>
                      {event.score !== undefined && (
                        <span
                          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                            event.score >= 80
                              ? "bg-emerald-50 text-emerald-700"
                              : event.score >= 50
                              ? "bg-amber-50 text-amber-700"
                              : "bg-red-50 text-red-700"
                          }`}
                        >
                          {event.score.toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground/60 mt-2">
                      {new Date(event.timestamp).toLocaleString()}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}

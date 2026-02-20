"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  TrendingUp,
  FileText,
  Send,
  Loader2,
  Table2,
  AlertTriangle,
  ChevronDown,
  X,
  Image as ImageIcon,
  Activity,
  Database,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  getAnalyticsDocuments,
  analyseData,
  getFinancialMetrics,
  getRiskIndicators,
} from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";
import type { AnalyticsDocument, AnalyseResponse } from "@/lib/types";

const CHART_COLORS = [
  "#0071e3",
  "#30d158",
  "#ff9f0a",
  "#ff3b30",
  "#bf5af2",
  "#64d2ff",
  "#ff375f",
  "#ffd60a",
];

export default function AnalyticsPage() {
  const [documents, setDocuments] = useState<AnalyticsDocument[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [docsLoading, setDocsLoading] = useState(true);
  const [result, setResult] = useState<AnalyseResponse | null>(null);
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [riskIndicators, setRiskIndicators] = useState<
    Array<Record<string, unknown>>
  >([]);
  const [docSelectorOpen, setDocSelectorOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    getAnalyticsDocuments()
      .then(setDocuments)
      .catch(() => toast("Failed to load documents.", "error"))
      .finally(() => setDocsLoading(false));
  }, []);

  useEffect(() => {
    if (selectedDocs.length > 0) {
      getFinancialMetrics(selectedDocs)
        .then(setMetrics)
        .catch(() => {});

      getRiskIndicators(selectedDocs[0])
        .then(setRiskIndicators)
        .catch(() => {});
    } else {
      setMetrics({});
      setRiskIndicators([]);
    }
  }, [selectedDocs]);

  const handleAnalyse = useCallback(async () => {
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await analyseData(
        question,
        selectedDocs.length > 0 ? selectedDocs : undefined
      );
      setResult(res);
      if (res.metrics && Object.keys(res.metrics).length > 0) {
        setMetrics((prev) => ({ ...prev, ...res.metrics }));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Analysis failed";
      toast(msg, "error");
    } finally {
      setLoading(false);
    }
  }, [question, selectedDocs, toast]);

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  const metricsData = Object.entries(metrics).map(([key, val]) => ({
    name: key,
    value: typeof val === "number" ? val : 0,
  }));

  const riskData = riskIndicators.map((r, i) => ({
    name: String(r.indicator || `Risk ${i + 1}`),
    severity:
      r.severity === "high" ? 3 : r.severity === "medium" ? 2 : 1,
    description: String(r.description || ""),
  }));

  const suggestedQuestions = [
    "What is the total revenue and net profit from the loaded documents?",
    "Show me the key financial ratios and generate a bar chart",
    "Are there any going concern qualifications in the audit reports?",
    "Compare EBITDA across all loaded documents",
    "What are the major risk indicators in these financial statements?",
    "Generate a pie chart showing the breakdown of expenses",
  ];

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#0071e3] to-[#bf5af2]">
            <BarChart3 className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Interactive Analytics Engine
            </h1>
            <p className="text-sm text-muted-foreground">
              AI-powered financial analysis with agentic tool calls
            </p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* Main Column */}
        <div className="space-y-6">
          {/* Document Selector */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Data Sources</h2>
              </div>
              <button
                onClick={() => setDocSelectorOpen(!docSelectorOpen)}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
              >
                {selectedDocs.length > 0
                  ? `${selectedDocs.length} selected`
                  : "Select documents"}
                <ChevronDown
                  className={`h-3.5 w-3.5 transition-transform ${
                    docSelectorOpen ? "rotate-180" : ""
                  }`}
                />
              </button>
            </div>

            <AnimatePresence>
              {docSelectorOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  {docsLoading ? (
                    <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading documents...
                    </div>
                  ) : documents.length === 0 ? (
                    <p className="py-4 text-sm text-muted-foreground">
                      No documents available. Ingest documents first.
                    </p>
                  ) : (
                    <div className="max-h-48 overflow-y-auto space-y-1 border-t pt-3">
                      {documents.map((doc) => (
                        <button
                          key={doc.document_id}
                          onClick={() => toggleDoc(doc.document_id)}
                          className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                            selectedDocs.includes(doc.document_id)
                              ? "bg-primary/10 text-primary"
                              : "hover:bg-muted/50 text-muted-foreground"
                          }`}
                        >
                          <FileText className="h-4 w-4 shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-medium text-foreground">
                              {doc.filename}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {doc.total_pages} pages &middot;{" "}
                              {doc.tables_count} tables
                            </p>
                          </div>
                          {selectedDocs.includes(doc.document_id) && (
                            <div className="h-2 w-2 rounded-full bg-primary" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {selectedDocs.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {selectedDocs.map((id) => {
                  const doc = documents.find((d) => d.document_id === id);
                  return (
                    <span
                      key={id}
                      className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                    >
                      {doc?.filename?.slice(0, 20) || id.slice(0, 8)}
                      <button onClick={() => toggleDoc(id)}>
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </motion.div>

          {/* Question Input */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              Ask a Question
            </h2>
            <div className="flex gap-3">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyse()}
                placeholder="e.g. What is the revenue trend? Generate a bar chart of expenses..."
                className="flex-1 rounded-xl border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 transition-shadow"
                disabled={loading}
              />
              <button
                onClick={handleAnalyse}
                disabled={loading || !question.trim()}
                className="flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-medium text-white transition-all hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Analyse
              </button>
            </div>

            {/* Suggested questions */}
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestedQuestions.slice(0, 4).map((q, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQuestion(q);
                  }}
                  className="rounded-lg border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
                >
                  {q.slice(0, 50)}...
                </button>
              ))}
            </div>
          </motion.div>

          {/* Results */}
          <AnimatePresence mode="wait">
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-2xl border bg-card p-8 shadow-sm"
              >
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <p className="text-sm text-muted-foreground">
                    Agent is analysing your data...
                  </p>
                  <p className="text-xs text-muted-foreground/70">
                    Loading tables, running queries, and generating insights
                  </p>
                </div>
              </motion.div>
            )}

            {!loading && result && (
              <motion.div
                key="result"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-5"
              >
                {/* Answer */}
                <div className="rounded-2xl border bg-card p-6 shadow-sm">
                  <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-primary" />
                    Analysis Result
                    <span className="ml-auto text-xs font-normal text-muted-foreground">
                      {result.tables_loaded} tables loaded
                    </span>
                  </h3>
                  <div className="prose prose-sm max-w-none text-foreground whitespace-pre-wrap">
                    {result.answer}
                  </div>
                </div>

                {/* Charts from agent */}
                {result.charts.length > 0 && (
                  <div className="rounded-2xl border bg-card p-6 shadow-sm">
                    <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                      <ImageIcon className="h-4 w-4 text-muted-foreground" />
                      Generated Charts
                    </h3>
                    <div className="grid gap-4 md:grid-cols-2">
                      {result.charts.map((chart, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.1 }}
                          className="overflow-hidden rounded-xl border"
                        >
                          <img
                            src={`data:image/png;base64,${chart}`}
                            alt={`Chart ${i + 1}`}
                            className="w-full"
                          />
                        </motion.div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-5">
          {/* Financial Metrics */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              Financial Metrics
            </h3>
            {metricsData.length > 0 ? (
              <>
                <div className="space-y-2 mb-4">
                  {metricsData.slice(0, 8).map((m, i) => (
                    <div
                      key={m.name}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-muted-foreground truncate mr-2">
                        {m.name}
                      </span>
                      <span className="font-medium tabular-nums">
                        {typeof m.value === "number"
                          ? m.value.toLocaleString()
                          : "—"}
                      </span>
                    </div>
                  ))}
                </div>
                {metricsData.length > 0 && (
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={metricsData.slice(0, 6)}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                        <XAxis
                          dataKey="name"
                          tick={{ fontSize: 10 }}
                          angle={-20}
                          textAnchor="end"
                          height={50}
                        />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                          {metricsData.slice(0, 6).map((_, i) => (
                            <Cell
                              key={i}
                              fill={CHART_COLORS[i % CHART_COLORS.length]}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-muted-foreground">
                Select documents and run an analysis to see metrics.
              </p>
            )}
          </motion.div>

          {/* Risk Indicators */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              Risk Indicators
            </h3>
            {riskData.length > 0 ? (
              <div className="space-y-2">
                {riskData.slice(0, 6).map((r, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg border p-2.5"
                  >
                    <div
                      className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                        r.severity >= 3
                          ? "bg-red-500"
                          : r.severity >= 2
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                      }`}
                    />
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate">{r.name}</p>
                      <p className="text-[11px] text-muted-foreground line-clamp-2">
                        {r.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Select a document to view risk indicators.
              </p>
            )}
          </motion.div>

          {/* Quick Stats */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.25 }}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Table2 className="h-4 w-4 text-muted-foreground" />
              Analysis Summary
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-muted/30 p-3 text-center">
                <p className="text-lg font-semibold text-primary">
                  {documents.length}
                </p>
                <p className="text-[11px] text-muted-foreground">Documents</p>
              </div>
              <div className="rounded-xl bg-muted/30 p-3 text-center">
                <p className="text-lg font-semibold text-primary">
                  {selectedDocs.length}
                </p>
                <p className="text-[11px] text-muted-foreground">Selected</p>
              </div>
              <div className="rounded-xl bg-muted/30 p-3 text-center">
                <p className="text-lg font-semibold text-primary">
                  {Object.keys(metrics).length}
                </p>
                <p className="text-[11px] text-muted-foreground">Metrics</p>
              </div>
              <div className="rounded-xl bg-muted/30 p-3 text-center">
                <p className="text-lg font-semibold text-primary">
                  {result?.charts.length || 0}
                </p>
                <p className="text-[11px] text-muted-foreground">Charts</p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

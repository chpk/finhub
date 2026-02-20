"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck,
  Loader2,
  FileText,
  ChevronDown,
  CheckCircle2,
  Circle,
  AlertCircle,
} from "lucide-react";
import { FrameworkSelector } from "@/components/compliance/FrameworkSelector";
import { ComplianceMatrix } from "@/components/compliance/ComplianceMatrix";
import { ComplianceReport as ComplianceReportView } from "@/components/compliance/ComplianceReport";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast-provider";
import {
  getDocuments,
  runComplianceCheckAsync,
  getComplianceProgress,
  getComplianceReport,
} from "@/lib/api";
import type { DocumentRecord, ComplianceReport } from "@/lib/types";
import type { ComplianceProgress } from "@/lib/api";

interface ProgressStep {
  step: string;
  pct: number;
  timestamp: string;
}

export default function CompliancePage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>([
    "IndAS",
    "Schedule_III",
  ]);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [docDropdownOpen, setDocDropdownOpen] = useState(false);
  const [progress, setProgress] = useState<ComplianceProgress | null>(null);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    getDocuments(0, 100)
      .then(setDocuments)
      .catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const toggleFramework = (id: string) => {
    setSelectedFrameworks((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const handleRun = async () => {
    if (!selectedDocId) {
      toast("Please select a document first.", "error");
      return;
    }
    if (selectedFrameworks.length === 0) {
      toast("Please select at least one framework.", "error");
      return;
    }

    setLoading(true);
    setReport(null);
    setProgress(null);
    setProgressSteps([]);

    try {
      const { job_id } = await runComplianceCheckAsync(
        selectedDocId,
        selectedFrameworks
      );

      pollRef.current = setInterval(async () => {
        try {
          const prog = await getComplianceProgress(job_id);
          setProgress(prog);
          setProgressSteps(prog.steps || []);

          if (prog.status === "completed" && prog.report_id) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            const fullReport = await getComplianceReport(prog.report_id);
            setReport(fullReport);
            setLoading(false);
            toast("Compliance check completed!", "success");
          } else if (prog.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setLoading(false);
            toast(prog.error || "Compliance check failed", "error");
          }
        } catch {
          // Keep polling
        }
      }, 2000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Check failed";
      toast(msg, "error");
      setLoading(false);
    }
  };

  const selectedDoc = documents.find((d) => (d._id || d.id) === selectedDocId);

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <h1 className="text-4xl font-semibold tracking-tight">
          Compliance Validation
        </h1>
        <p className="mt-3 text-muted-foreground">
          Validate financial documents against Indian regulatory frameworks with
          AI-powered analysis.
        </p>
      </motion.div>

      {/* Step 1: Document Selector */}
      <motion.div
        className="mt-10"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1 }}
      >
        <div className="rounded-2xl border bg-card p-6">
          <h2 className="text-lg font-semibold">Step 1: Select Document</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose a processed document to validate.
          </p>
          <div className="relative mt-4">
            <button
              onClick={() => setDocDropdownOpen(!docDropdownOpen)}
              className="flex w-full items-center justify-between rounded-xl border bg-background px-4 py-3 text-left text-sm transition-shadow hover:shadow-sm focus:ring-2 focus:ring-primary/20 focus:outline-none"
            >
              {selectedDoc ? (
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{selectedDoc.filename}</span>
                  <span className="text-xs text-muted-foreground">
                    ({selectedDoc.total_pages} pages,{" "}
                    {selectedDoc.elements_count} elements)
                  </span>
                </div>
              ) : (
                <span className="text-muted-foreground">
                  {documents.length === 0
                    ? "No documents available — upload one first"
                    : "Select a document..."}
                </span>
              )}
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </button>

            {docDropdownOpen && documents.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border bg-card shadow-lg"
              >
                {documents.map((doc) => {
                  const docId = doc._id || doc.id || "";
                  return (
                    <button
                      key={docId}
                      onClick={() => {
                        setSelectedDocId(docId);
                        setDocDropdownOpen(false);
                      }}
                      className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-muted/50 ${
                        selectedDocId === docId ? "bg-primary/5" : ""
                      }`}
                    >
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{doc.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {doc.total_pages} pages &middot;{" "}
                          {doc.elements_count} elements &middot;{" "}
                          {doc.tables_count} tables
                        </p>
                      </div>
                    </button>
                  );
                })}
              </motion.div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Step 2: Framework Selector */}
      <motion.div
        className="mt-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
      >
        <FrameworkSelector
          selected={selectedFrameworks}
          onToggle={toggleFramework}
        />
      </motion.div>

      {/* Step 3: Run button */}
      <motion.div
        className="mt-6 flex justify-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <Button
          size="lg"
          onClick={handleRun}
          disabled={
            loading || !selectedDocId || selectedFrameworks.length === 0
          }
          className="rounded-full px-10 py-6 text-base font-semibold shadow-lg shadow-primary/20 transition-all hover:shadow-xl hover:shadow-primary/30"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Running Compliance Check...
            </>
          ) : (
            <>
              <ShieldCheck className="mr-2 h-5 w-5" />
              Run Compliance Check
            </>
          )}
        </Button>
      </motion.div>

      {/* Progress Visualization */}
      <AnimatePresence>
        {loading && progress && (
          <motion.div
            className="mt-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <div className="rounded-2xl border bg-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  Compliance Analysis in Progress
                </h2>
                <span className="text-sm font-medium text-primary">
                  {progress.progress_pct}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-2 w-full rounded-full bg-muted overflow-hidden mb-4">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-primary to-blue-400"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress.progress_pct}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>

              {/* Current step */}
              <p className="text-sm font-medium text-foreground mb-4">
                {progress.current_step}
              </p>

              {/* Step history */}
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {progressSteps.map((step, i) => {
                  const isLast = i === progressSteps.length - 1;
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-3"
                    >
                      {isLast ? (
                        <Loader2 className="h-4 w-4 mt-0.5 shrink-0 animate-spin text-primary" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-500" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p
                          className={`text-xs ${
                            isLast
                              ? "font-medium text-foreground"
                              : "text-muted-foreground"
                          }`}
                        >
                          {step.step}
                        </p>
                      </div>
                      <span className="text-[10px] text-muted-foreground/50 shrink-0 tabular-nums">
                        {step.pct}%
                      </span>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      {report && (
        <>
          <motion.div
            className="mt-10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <ComplianceMatrix report={report} loading={false} />
          </motion.div>

          <motion.div
            className="mt-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <ComplianceReportView report={report} />
          </motion.div>
        </>
      )}
    </div>
  );
}

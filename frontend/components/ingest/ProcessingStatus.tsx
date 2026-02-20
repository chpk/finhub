"use client";

import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import { getDocumentStatus } from "@/lib/api";

interface ProcessingStatusProps {
  activeDocumentId?: string | null;
}

interface Stage {
  id: string;
  label: string;
}

const stages: Stage[] = [
  { id: "uploaded", label: "File Uploaded" },
  { id: "processing", label: "Extracting Text & Tables" },
  { id: "processed", label: "Chunking & Embedding" },
  { id: "indexed", label: "Indexed in Vector DB" },
];

function getStageIndex(status: string): number {
  if (status === "uploaded") return 0;
  if (status === "processing") return 1;
  if (status === "processed") return 3;
  if (status === "failed") return -1;
  return -1;
}

export function ProcessingStatus({ activeDocumentId }: ProcessingStatusProps) {
  const [status, setStatus] = useState<string>("");
  const [docInfo, setDocInfo] = useState<{
    elements: number;
    tables: number;
    pages: number;
  } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    if (!activeDocumentId) {
      setStatus("");
      setDocInfo(null);
      return;
    }

    setStatus("uploaded");

    const poll = async () => {
      try {
        const doc = await getDocumentStatus(activeDocumentId);
        setStatus(doc.status);
        setDocInfo({
          elements: doc.elements_count || 0,
          tables: doc.tables_count || 0,
          pages: doc.total_pages || 0,
        });
        if (doc.status === "processed" || doc.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        // Keep polling
      }
    };

    poll();
    pollRef.current = setInterval(poll, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeDocumentId]);

  const activeStageIdx = getStageIndex(status);
  const isFailed = status === "failed";

  return (
    <div className="rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">Processing Pipeline</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {activeDocumentId
          ? "Tracking document processing stages."
          : "Upload a document to see processing status."}
      </p>

      <div className="mt-6 space-y-1">
        {stages.map((stage, i) => {
          const isDone = activeStageIdx > i;
          const isActive = activeStageIdx === i && !isFailed;

          return (
            <div
              key={stage.id}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5"
            >
              {isDone ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              ) : isActive ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
              ) : (
                <Circle className="h-4 w-4 text-muted-foreground/30 shrink-0" />
              )}
              <span
                className={`text-sm ${
                  isActive
                    ? "font-medium text-foreground"
                    : isDone
                      ? "text-emerald-600"
                      : "text-muted-foreground/50"
                }`}
              >
                {stage.label}
              </span>
              {isActive && (
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: "100%" }}
                  className="ml-auto h-1 max-w-[80px] rounded-full bg-primary/20 overflow-hidden"
                >
                  <motion.div
                    animate={{ x: ["-100%", "100%"] }}
                    transition={{
                      repeat: Infinity,
                      duration: 1.5,
                      ease: "easeInOut",
                    }}
                    className="h-full w-1/2 rounded-full bg-primary"
                  />
                </motion.div>
              )}
            </div>
          );
        })}

        {isFailed && (
          <div className="flex items-center gap-3 rounded-xl bg-red-50 px-3 py-2.5">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            <span className="text-sm font-medium text-red-700">
              Processing failed. Please try again.
            </span>
          </div>
        )}
      </div>

      {docInfo && activeStageIdx >= 3 && (
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-xl bg-emerald-50 px-4 py-3"
        >
          <p className="text-xs font-medium text-emerald-700">
            {docInfo.elements} elements &middot; {docInfo.tables} tables
            &middot; {docInfo.pages} pages extracted and indexed
          </p>
        </motion.div>
      )}

      {!activeDocumentId && (
        <div className="mt-6 rounded-xl bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            Upload a document to see processing status.
          </p>
        </div>
      )}
    </div>
  );
}

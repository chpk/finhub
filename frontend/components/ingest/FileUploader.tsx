"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, X, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/toast-provider";
import { uploadDocument } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

interface FileUploaderProps {
  onUploadComplete?: (result: UploadResponse) => void;
}

type DocType = "auto" | "financial_statement" | "audit_report" | "annual_report" | "regulatory";

const docTypes: { value: DocType; label: string }[] = [
  { value: "auto", label: "Auto-Detect" },
  { value: "financial_statement", label: "Financial Statement" },
  { value: "audit_report", label: "Audit Report" },
  { value: "annual_report", label: "Annual Report" },
  { value: "regulatory", label: "Regulatory Document" },
];

interface UploadingFile {
  file: File;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
  result?: UploadResponse;
  error?: string;
}

export function FileUploader({ onUploadComplete }: FileUploaderProps) {
  const [files, setFiles] = useState<UploadingFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [docType, setDocType] = useState<DocType>("auto");
  const [isUploading, setIsUploading] = useState(false);
  const { toast } = useToast();

  const addFiles = useCallback((newFiles: File[]) => {
    const pdfs = newFiles.filter(
      (f) =>
        f.type === "application/pdf" ||
        f.name.toLowerCase().endsWith(".pdf") ||
        f.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
        f.name.toLowerCase().endsWith(".docx")
    );
    if (pdfs.length === 0) {
      toast("Please upload PDF or DOCX files.", "error");
      return;
    }
    setFiles((prev) => [
      ...prev,
      ...pdfs.map((file) => ({ file, progress: 0, status: "pending" as const })),
    ]);
  }, [toast]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      addFiles(Array.from(e.dataTransfer.files));
    },
    [addFiles]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) addFiles(Array.from(e.target.files));
      e.target.value = "";
    },
    [addFiles]
  );

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0 || isUploading) return;
    setIsUploading(true);

    for (let i = 0; i < files.length; i++) {
      if (files[i].status === "done") continue;

      setFiles((prev) => {
        const next = [...prev];
        next[i] = { ...next[i], status: "uploading", progress: 30 };
        return next;
      });

      try {
        const result = await uploadDocument(files[i].file, docType);
        setFiles((prev) => {
          const next = [...prev];
          next[i] = { ...next[i], status: "done", progress: 100, result };
          return next;
        });
        onUploadComplete?.(result);
        toast(`${files[i].file.name} processed successfully.`, "success");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setFiles((prev) => {
          const next = [...prev];
          next[i] = { ...next[i], status: "error", progress: 0, error: msg };
          return next;
        });
        toast(`Failed to upload ${files[i].file.name}.`, "error");
      }
    }

    setIsUploading(false);
  };

  const pendingCount = files.filter((f) => f.status !== "done").length;

  return (
    <div className="rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">Upload Documents</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Drag & drop PDF or DOCX files for processing.
      </p>

      {/* Document type selector */}
      <div className="mt-4 flex flex-wrap gap-2">
        {docTypes.map((dt) => (
          <button
            key={dt.value}
            onClick={() => setDocType(dt.value)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
              docType === dt.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {dt.label}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        className={`mt-4 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 transition-all ${
          isDragOver
            ? "border-primary bg-primary/5 scale-[1.01]"
            : "border-muted-foreground/20 hover:border-primary/40"
        }`}
      >
        <motion.div
          animate={isDragOver ? { scale: 1.1, y: -4 } : { scale: 1, y: 0 }}
          transition={{ type: "spring", bounce: 0.3 }}
        >
          <Upload className="h-8 w-8 text-muted-foreground/40" />
        </motion.div>
        <p className="mt-3 text-sm text-muted-foreground">
          Drop files here, or{" "}
          <label className="cursor-pointer font-medium text-primary hover:underline">
            browse
            <input
              type="file"
              multiple
              accept=".pdf,.docx"
              onChange={handleFileInput}
              className="hidden"
            />
          </label>
        </p>
        <p className="mt-1 text-xs text-muted-foreground/60">
          PDF, DOCX up to 50MB each
        </p>
      </div>

      {/* File list */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-4 space-y-2 overflow-hidden"
          >
            {files.map((f, i) => (
              <motion.div
                key={`${f.file.name}-${i}`}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="rounded-xl border bg-muted/30 px-4 py-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5 min-w-0">
                    {f.status === "done" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    ) : f.status === "uploading" ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                    ) : (
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="truncate text-sm font-medium">{f.file.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {(f.file.size / 1024 / 1024).toFixed(1)} MB
                    </span>
                  </div>
                  {f.status !== "uploading" && (
                    <button onClick={() => removeFile(i)} className="ml-2 shrink-0">
                      <X className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive transition-colors" />
                    </button>
                  )}
                </div>
                {f.status === "uploading" && (
                  <div className="mt-2">
                    <Progress value={f.progress} className="h-1.5" />
                  </div>
                )}
                {f.status === "done" && f.result && (
                  <p className="mt-1 text-xs text-emerald-600">
                    {f.result.elements_count} elements &middot; {f.result.tables_count} tables &middot;{" "}
                    {f.result.pages} pages
                  </p>
                )}
                {f.status === "error" && (
                  <p className="mt-1 text-xs text-red-600">{f.error}</p>
                )}
              </motion.div>
            ))}

            <Button
              onClick={handleUpload}
              disabled={isUploading || pendingCount === 0}
              className="mt-3 w-full rounded-xl"
              size="lg"
            >
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                `Upload ${pendingCount} file${pendingCount !== 1 ? "s" : ""}`
              )}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

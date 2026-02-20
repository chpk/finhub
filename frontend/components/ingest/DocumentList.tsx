"use client";

import { motion } from "framer-motion";
import {
  FileText,
  Table2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DocumentRecord } from "@/lib/types";

interface DocumentListProps {
  documents: DocumentRecord[];
  loading?: boolean;
}

const statusIcon: Record<string, React.ReactNode> = {
  processed: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />,
  uploaded: <CheckCircle2 className="h-3.5 w-3.5 text-blue-500" />,
  validated: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />,
  partial: <AlertCircle className="h-3.5 w-3.5 text-amber-500" />,
  failed: <AlertCircle className="h-3.5 w-3.5 text-red-500" />,
  processing: <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />,
  validating: <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />,
};

const statusBadge: Record<string, "success" | "warning" | "danger" | "muted"> = {
  processed: "success",
  uploaded: "muted",
  validated: "success",
  partial: "warning",
  failed: "danger",
  processing: "muted",
  validating: "muted",
};

export function DocumentList({ documents, loading }: DocumentListProps) {
  return (
    <div className="rounded-2xl border bg-card p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Uploaded Documents</h2>
        <span className="text-sm text-muted-foreground">
          {documents.length} document{documents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {loading ? (
        <div className="mt-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <FileText className="h-10 w-10 text-muted-foreground/25" />
          <p className="mt-3 text-sm text-muted-foreground">
            No documents uploaded yet.
          </p>
        </div>
      ) : (
        <div className="mt-4 overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-12 gap-3 border-b px-4 py-2 text-xs font-medium text-muted-foreground">
            <div className="col-span-4">Filename</div>
            <div className="col-span-2">Type</div>
            <div className="col-span-1 text-center">Pages</div>
            <div className="col-span-1 text-center">Elements</div>
            <div className="col-span-1 text-center">Tables</div>
            <div className="col-span-2">Date</div>
            <div className="col-span-1 text-center">Status</div>
          </div>

          {/* Rows */}
          <div className="divide-y">
            {documents.map((doc, i) => (
              <motion.div
                key={doc._id || doc.id || doc.filename}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="grid grid-cols-12 gap-3 px-4 py-3 text-sm transition-colors hover:bg-muted/30 items-center"
              >
                <div className="col-span-4 flex items-center gap-2 min-w-0">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate font-medium">{doc.filename}</span>
                </div>
                <div className="col-span-2">
                  <Badge variant="secondary" className="text-[11px]">
                    {doc.metadata?.content_type === "application/pdf" ? "PDF" : "Document"}
                  </Badge>
                </div>
                <div className="col-span-1 text-center tabular-nums">
                  {doc.total_pages}
                </div>
                <div className="col-span-1 text-center tabular-nums">
                  {doc.elements_count}
                </div>
                <div className="col-span-1 text-center tabular-nums">
                  {doc.tables_count}
                </div>
                <div className="col-span-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {doc.created_at
                    ? new Date(doc.created_at).toLocaleDateString()
                    : "—"}
                </div>
                <div className="col-span-1 flex justify-center">
                  <Badge variant={statusBadge[doc.status] || "muted"}>
                    {statusIcon[doc.status]}
                    <span className="ml-1">
                      {doc.status}
                    </span>
                  </Badge>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { FileUploader } from "@/components/ingest/FileUploader";
import { ProcessingStatus } from "@/components/ingest/ProcessingStatus";
import { DocumentList } from "@/components/ingest/DocumentList";
import { getDocuments, invalidateCache } from "@/lib/api";
import type { DocumentRecord, UploadResponse } from "@/lib/types";

export default function IngestPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await getDocuments(0, 50);
      setDocuments(docs);
    } catch {
      // API may not be running
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUploadComplete = (result: UploadResponse) => {
    setActiveDocId(result.document_id);
    invalidateCache("/api/ingest");
    invalidateCache("/api/dashboard");
    setTimeout(() => loadDocuments(), 2000);
    setTimeout(() => loadDocuments(), 8000);
    setTimeout(() => loadDocuments(), 20000);
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <h1 className="text-4xl font-semibold tracking-tight">
          Document Ingestion
        </h1>
        <p className="mt-3 text-muted-foreground">
          Upload regulatory PDFs and financial statements for processing and
          compliance analysis.
        </p>
      </motion.div>

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
        >
          <FileUploader onUploadComplete={handleUploadComplete} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25 }}
        >
          <ProcessingStatus activeDocumentId={activeDocId} />
        </motion.div>
      </div>

      <motion.div
        className="mt-12"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.35 }}
      >
        <DocumentList documents={documents} loading={loading} />
      </motion.div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageCircle,
  Plus,
  Trash2,
  Settings2,
  FileText,
  ChevronDown,
  X,
} from "lucide-react";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { getChatSessions, deleteChatSession, getDocuments } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";
import type { DocumentRecord } from "@/lib/types";

interface SessionInfo {
  session_id: string;
  title: string;
  created_at?: string;
  message_count?: number;
}

type ChatMode = "auto" | "compliance_matrix" | "analytics" | "comparison";

const MODE_OPTIONS: { value: ChatMode; label: string; desc: string }[] = [
  { value: "auto", label: "Auto", desc: "Intelligent auto-detection" },
  { value: "compliance_matrix", label: "Compliance Matrix", desc: "Step-by-step rule walkthrough" },
  { value: "analytics", label: "Analytics", desc: "Data-driven with metrics" },
  { value: "comparison", label: "Comparison", desc: "Compare companies / scores" },
];

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatMode, setChatMode] = useState<ChatMode>("auto");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [showModeSelect, setShowModeSelect] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    getChatSessions()
      .then((data) => {
        const mapped = data.map((s) => ({
          session_id: s.session_id || "",
          title: s.title || "Chat Session",
          created_at: s.created_at,
          message_count: s.messages?.length,
        }));
        setSessions(mapped);
      })
      .catch(() => {});

    getDocuments(0, 50)
      .then(setDocuments)
      .catch(() => {});
  }, []);

  const handleNewChat = () => {
    setCurrentSession(null);
    setSelectedDocIds([]);
    setChatMode("auto");
  };

  const handleSessionChange = (sessionId: string) => {
    setCurrentSession(sessionId);
    getChatSessions()
      .then((data) => {
        const mapped = data.map((s) => ({
          session_id: s.session_id || "",
          title: s.title || "Chat Session",
          created_at: s.created_at,
          message_count: s.messages?.length,
        }));
        setSessions(mapped);
      })
      .catch(() => {});
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (currentSession === id) setCurrentSession(null);
      toast("Session deleted.", "info");
    } catch {
      toast("Failed to delete session.", "error");
    }
  };

  const toggleDocId = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  return (
    <div className="flex h-[calc(100vh-7.5rem)]">
      {/* Sidebar */}
      {sidebarOpen && (
        <motion.aside
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          className="hidden w-72 flex-col border-r bg-card/50 p-4 lg:flex"
        >
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>

          {/* Mode Selector */}
          <div className="mt-4">
            <button
              onClick={() => setShowModeSelect(!showModeSelect)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs text-muted-foreground hover:bg-muted transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Settings2 className="h-3.5 w-3.5" />
                Mode: {MODE_OPTIONS.find((m) => m.value === chatMode)?.label}
              </span>
              <ChevronDown
                className={`h-3 w-3 transition-transform ${showModeSelect ? "rotate-180" : ""}`}
              />
            </button>
            <AnimatePresence>
              {showModeSelect && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  {MODE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => {
                        setChatMode(opt.value);
                        setShowModeSelect(false);
                      }}
                      className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors ${
                        chatMode === opt.value
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-muted"
                      }`}
                    >
                      <div>
                        <p className="font-medium">{opt.label}</p>
                        <p className="text-[10px] opacity-70">{opt.desc}</p>
                      </div>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Document Context */}
          <div className="mt-3">
            <button
              onClick={() => setShowDocPicker(!showDocPicker)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs text-muted-foreground hover:bg-muted transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                Documents ({selectedDocIds.length})
              </span>
              <ChevronDown
                className={`h-3 w-3 transition-transform ${showDocPicker ? "rotate-180" : ""}`}
              />
            </button>
            <AnimatePresence>
              {showDocPicker && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="max-h-32 overflow-y-auto space-y-0.5 mt-1">
                    {documents.map((doc) => {
                      const docId = doc._id || doc.id || "";
                      return (
                        <button
                          key={docId}
                          onClick={() => toggleDocId(docId)}
                          className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                            selectedDocIds.includes(docId)
                              ? "bg-primary/10 text-primary"
                              : "text-muted-foreground hover:bg-muted"
                          }`}
                        >
                          <span className="truncate">{doc.filename}</span>
                          {selectedDocIds.includes(docId) && (
                            <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                          )}
                        </button>
                      );
                    })}
                    {documents.length === 0 && (
                      <p className="px-3 py-2 text-[10px] text-muted-foreground">
                        No documents ingested.
                      </p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            {selectedDocIds.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1 px-1">
                {selectedDocIds.map((id) => {
                  const doc = documents.find((d) => (d._id || d.id) === id);
                  return (
                    <span
                      key={id}
                      className="inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary"
                    >
                      {doc?.filename?.slice(0, 15) || id.slice(0, 6)}
                      <button onClick={() => toggleDocId(id)}>
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </div>

          {/* Sessions */}
          <div className="mt-4 flex-1 overflow-y-auto space-y-1">
            {sessions.length === 0 ? (
              <div className="flex flex-col items-center py-8 text-center">
                <MessageCircle className="h-6 w-6 text-muted-foreground/30" />
                <p className="mt-2 text-xs text-muted-foreground">
                  No past sessions.
                </p>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.session_id}
                  className={`group flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors cursor-pointer ${
                    currentSession === session.session_id
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                  onClick={() => setCurrentSession(session.session_id)}
                >
                  <MessageCircle className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate flex-1">{session.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(session.session_id);
                    }}
                    className="hidden shrink-0 text-muted-foreground hover:text-destructive group-hover:block"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </motion.aside>
      )}

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center gap-3 border-b bg-card/50 px-6 py-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="hidden rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors lg:block"
          >
            <MessageCircle className="h-4 w-4" />
          </button>
          <div className="flex-1">
            <h1 className="text-base font-semibold">NFRA Insight Bot</h1>
            <p className="text-xs text-muted-foreground">
              Enhanced — {MODE_OPTIONS.find((m) => m.value === chatMode)?.desc}
              {selectedDocIds.length > 0 &&
                ` · ${selectedDocIds.length} doc(s) loaded`}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {MODE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setChatMode(opt.value)}
                className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                  chatMode === opt.value
                    ? "bg-primary text-white"
                    : "bg-muted/50 text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow
            mode={chatMode}
            documentIds={selectedDocIds}
            sessionId={currentSession}
            onSessionChange={handleSessionChange}
          />
        </div>
      </div>
    </div>
  );
}

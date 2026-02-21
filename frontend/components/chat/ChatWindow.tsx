"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import {
  sendChatMessage,
  sendAnalyticsChatMessage,
} from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";
import type { ChatSource } from "@/lib/types";
import { Loader2, Sparkles } from "lucide-react";

interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

interface ChatWindowProps {
  mode?: string;
  documentIds?: string[];
  sessionId?: string | null;
  onSessionChange?: (sessionId: string) => void;
}

const SUGGESTED_QUESTIONS = [
  "Show me all companies non-compliant with Ind AS 24",
  "What are common non-compliance patterns in banking sector?",
  "Explain Schedule III balance sheet requirements step by step",
  "Compare compliance scores across all documents",
  "What are the key SEBI LODR disclosure requirements?",
  "Summarise the audit report findings",
];

const WELCOME_MESSAGE: LocalMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hello! I'm the enhanced NFRA Insight Bot. I can help you with:\n\n" +
    "- **Compliance Matrix**: Walk through regulatory requirements step-by-step\n" +
    "- **Analytics**: Data-driven answers referencing financial metrics\n" +
    "- **Comparison**: Compare companies and compliance scores\n" +
    "- **General Q&A**: Ask about Ind AS, SEBI, RBI, BRSR, or any regulation\n\n" +
    "Select documents in the sidebar to scope my answers, or ask freely!",
};

export function ChatWindow({
  mode = "auto",
  documentIds = [],
  sessionId: externalSessionId,
  onSessionChange,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<LocalMessage[]>([WELCOME_MESSAGE]);
  const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const prevSessionRef = useRef<string | null | undefined>(undefined);

  const activeSessionId = externalSessionId ?? internalSessionId;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (prevSessionRef.current === externalSessionId) return;
    prevSessionRef.current = externalSessionId;

    if (externalSessionId === null) {
      setMessages([WELCOME_MESSAGE]);
      setInternalSessionId(null);
      return;
    }

    if (externalSessionId) {
      setLoadingHistory(true);
      import("@/lib/api")
        .then(({ getChatHistory }) => getChatHistory(externalSessionId))
        .then((session) => {
          const history: LocalMessage[] = (session.messages || []).map(
            (m: any, i: number) => ({
              id: `hist_${i}`,
              role: m.role as "user" | "assistant",
              content: m.content,
              sources: m.sources,
            })
          );
          setMessages(
            history.length > 0 ? history : [WELCOME_MESSAGE]
          );
          setInternalSessionId(externalSessionId);
        })
        .catch(() => {
          setMessages([WELCOME_MESSAGE]);
        })
        .finally(() => setLoadingHistory(false));
    }
  }, [externalSessionId]);

  const handleSend = async (content: string) => {
    const userMsg: LocalMessage = {
      id: Date.now().toString(),
      role: "user",
      content,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const useAnalytics =
        mode !== "auto" ||
        documentIds.length > 0 ||
        content.toLowerCase().includes("compare") ||
        content.toLowerCase().includes("compliance matrix") ||
        content.toLowerCase().includes("analytics");

      let res;
      if (useAnalytics) {
        res = await sendAnalyticsChatMessage(
          content,
          activeSessionId,
          documentIds,
          mode
        );
      } else {
        res = await sendChatMessage(content, activeSessionId, documentIds);
      }

      if (res.session_id) {
        setInternalSessionId(res.session_id);
        onSessionChange?.(res.session_id);
      }

      const botMsg: LocalMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: res.response,
        sources: res.sources,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to get response";
      toast(msg, "error");
      const errorMsg: LocalMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content:
          "I'm sorry, I couldn't process your request. Please make sure the backend is running and try again.",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
        <div className="space-y-5">
          {loadingHistory ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading conversation...</span>
            </motion.div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  sources={msg.sources}
                />
              ))}
              {loading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Thinking...</span>
                </motion.div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="border-t bg-card/30 px-6 py-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="h-3.5 w-3.5 text-primary/50" />
            <span className="text-[11px] text-muted-foreground font-medium">
              Try asking:
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.slice(0, 4).map((q, i) => (
              <button
                key={i}
                onClick={() => handleSend(q)}
                className="rounded-lg border bg-background px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t bg-card/50 p-4">
        <ChatInput onSend={handleSend} disabled={loading} loading={loading} />
      </div>
    </div>
  );
}

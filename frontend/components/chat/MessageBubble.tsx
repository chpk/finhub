"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, FileText, Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatSource } from "@/lib/types";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

export function MessageBubble({ role, content, sources }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);
  const isUser = role === "user";
  const hasSources = sources && sources.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message */}
      <div className={`max-w-[75%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-md"
              : "bg-muted text-foreground rounded-tl-md"
          }`}
        >
          {isUser ? (
            content.split("\n").map((line, i) => (
              <span key={i}>
                {line}
                {i < content.split("\n").length - 1 && <br />}
              </span>
            ))
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2 prose-pre:my-2 prose-code:text-xs prose-code:bg-black/10 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-table:text-xs [&_table]:border-collapse [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-black/5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Sources toggle */}
        {hasSources && (
          <div className="mt-1.5">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <FileText className="h-3 w-3" />
              {sources.length} source{sources.length !== 1 ? "s" : ""}
              <motion.div
                animate={{ rotate: showSources ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3 w-3" />
              </motion.div>
            </button>

            <AnimatePresence>
              {showSources && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-2 space-y-1.5 overflow-hidden"
                >
                  {sources.map((src, i) => (
                    <div
                      key={i}
                      className="rounded-lg border bg-card px-3 py-2 text-left"
                    >
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <FileText className="h-3 w-3" />
                        <span className="font-medium">{src.source}</span>
                        {src.page && <span>p.{src.page}</span>}
                        {src.section && (
                          <span className="truncate">{src.section}</span>
                        )}
                        {src.score > 0 && (
                          <span className="ml-auto text-[10px] opacity-60">
                            {(src.score * 100).toFixed(0)}% match
                          </span>
                        )}
                      </div>
                      {src.text && (
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2 italic">
                          &ldquo;{src.text}&rdquo;
                        </p>
                      )}
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
}

"use client";

import { useState } from "react";
import { Send, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

const suggestions = [
  "What is Ind AS 1 about?",
  "Explain Schedule III requirements",
  "SEBI LODR disclosure obligations",
  "What is BRSR reporting?",
];

export function ChatInput({ onSend, disabled, loading }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue("");
    }
  };

  return (
    <div>
      {/* Quick suggestions */}
      <div className="mb-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => {
              if (!disabled) {
                onSend(s);
              }
            }}
            className="rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {s}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask about Ind AS, SEBI, or any regulation..."
          disabled={disabled}
          className="flex-1 rounded-xl border bg-background px-4 py-3 text-sm outline-none transition-shadow placeholder:text-muted-foreground/50 focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!value.trim() || disabled}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </form>
    </div>
  );
}

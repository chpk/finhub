"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { SearchBar } from "@/components/search/SearchBar";
import { ResultCard } from "@/components/search/ResultCard";
import { useToast } from "@/components/ui/toast-provider";
import { searchDocuments } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

const collectionFilters = [
  { label: "All", value: "" },
  { label: "Ind AS", value: "regulatory_frameworks" },
  { label: "Financial Docs", value: "financial_documents" },
  { label: "Checklists", value: "disclosure_checklists" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [activeFilter, setActiveFilter] = useState("");
  const { toast } = useToast();

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const collections = activeFilter ? [activeFilter] : [];
      const data = await searchDocuments(query, collections, 15);
      setResults(data);
      if (data.length === 0) {
        toast("No results found. Try a different query.", "info");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Search failed";
      toast(msg, "error");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const queryTerms = query
    .trim()
    .split(/\s+/)
    .filter((t) => t.length > 2);

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center"
      >
        <h1 className="text-4xl font-semibold tracking-tight">
          Semantic Search
        </h1>
        <p className="mt-3 text-muted-foreground">
          Search across regulatory documents and financial standards using
          natural language.
        </p>
      </motion.div>

      <motion.div
        className="mx-auto mt-10 max-w-3xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15 }}
      >
        <SearchBar
          query={query}
          onQueryChange={setQuery}
          onSearch={handleSearch}
          loading={loading}
        />

        {/* Filter pills */}
        <div className="mt-4 flex justify-center gap-2">
          {collectionFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setActiveFilter(f.value)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-all ${
                activeFilter === f.value
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </motion.div>

      <motion.div
        className="mx-auto mt-10 max-w-4xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.25 }}
      >
        {!searched ? (
          <div className="flex flex-col items-center py-16 text-center">
            <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center">
              <span className="text-2xl">🔍</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Enter a query to search across ingested regulatory documents.
            </p>
          </div>
        ) : loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-center">
            <p className="text-sm text-muted-foreground">
              No results found for &ldquo;{query}&rdquo;. Try a broader query.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              {results.length} result{results.length !== 1 ? "s" : ""} found
            </p>
            {results.map((result, idx) => (
              <ResultCard
                key={`${result.collection}-${idx}`}
                result={result}
                queryTerms={queryTerms}
              />
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}

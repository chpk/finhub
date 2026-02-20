"use client";

import { Search, Loader2 } from "lucide-react";

interface SearchBarProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSearch: () => void;
  loading?: boolean;
}

export function SearchBar({ query, onQueryChange, onSearch, loading }: SearchBarProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative">
        {loading ? (
          <Loader2 className="absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-primary" />
        ) : (
          <Search className="absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        )}
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search regulations, standards, and compliance rules..."
          className="w-full rounded-2xl border bg-card py-4.5 pl-14 pr-5 text-base outline-none transition-all placeholder:text-muted-foreground/50 focus:shadow-lg focus:shadow-primary/5 focus:ring-2 focus:ring-primary/20"
        />
      </div>
    </form>
  );
}

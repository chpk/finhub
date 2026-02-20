"use client";

import { motion } from "framer-motion";
import { FileText, ShieldCheck, TrendingUp, Layers } from "lucide-react";
import type { DashboardStats } from "@/lib/types";

interface StatsCardsProps {
  stats: DashboardStats;
  loading?: boolean;
}

const cards = [
  {
    key: "documents_ingested" as const,
    label: "Documents Ingested",
    icon: FileText,
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-100",
  },
  {
    key: "compliance_checks" as const,
    label: "Compliance Checks",
    icon: ShieldCheck,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-100",
  },
  {
    key: "average_score" as const,
    label: "Average Score",
    icon: TrendingUp,
    color: "text-violet-600",
    bg: "bg-violet-50",
    border: "border-violet-100",
    suffix: "%",
  },
  {
    key: "active_frameworks" as const,
    label: "Active Frameworks",
    icon: Layers,
    color: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-100",
  },
];

export function StatsCards({ stats, loading }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, i) => {
        const Icon = card.icon;
        const value = stats[card.key];
        return (
          <motion.div
            key={card.key}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.08 }}
            whileHover={{ y: -2, boxShadow: "0 8px 30px rgba(0,0,0,0.08)" }}
            className={`group relative overflow-hidden rounded-2xl border ${card.border} bg-card p-6 transition-all`}
          >
            {loading ? (
              <div className="space-y-3">
                <div className="skeleton h-10 w-10 rounded-xl" />
                <div className="skeleton h-7 w-16 rounded-lg" />
                <div className="skeleton h-4 w-24 rounded" />
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <div className={`rounded-xl ${card.bg} p-3`}>
                  <Icon className={`h-5 w-5 ${card.color}`} />
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums">
                    {value === 0 ? "—" : value}
                    {value !== 0 && card.suffix ? card.suffix : ""}
                  </p>
                  <p className="text-sm text-muted-foreground">{card.label}</p>
                </div>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

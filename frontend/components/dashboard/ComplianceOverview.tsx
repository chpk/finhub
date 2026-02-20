"use client";

import { motion } from "framer-motion";
import { ShieldCheck, AlertTriangle, MinusCircle, HelpCircle } from "lucide-react";
import type { ComplianceReport } from "@/lib/types";

interface ComplianceOverviewProps {
  reports: ComplianceReport[];
  loading?: boolean;
}

export function ComplianceOverview({ reports, loading }: ComplianceOverviewProps) {
  const totals = reports.reduce(
    (acc, r) => ({
      compliant: acc.compliant + r.compliant_count,
      nonCompliant: acc.nonCompliant + r.non_compliant_count,
      partial: acc.partial + r.partially_compliant_count,
      na: acc.na + r.not_applicable_count,
    }),
    { compliant: 0, nonCompliant: 0, partial: 0, na: 0 }
  );

  const total = totals.compliant + totals.nonCompliant + totals.partial + totals.na;

  const bars = [
    {
      label: "Compliant",
      value: totals.compliant,
      color: "bg-emerald-500",
      textColor: "text-emerald-600",
      icon: ShieldCheck,
    },
    {
      label: "Non-Compliant",
      value: totals.nonCompliant,
      color: "bg-red-500",
      textColor: "text-red-600",
      icon: AlertTriangle,
    },
    {
      label: "Partial",
      value: totals.partial,
      color: "bg-amber-500",
      textColor: "text-amber-600",
      icon: MinusCircle,
    },
    {
      label: "N/A",
      value: totals.na,
      color: "bg-gray-300",
      textColor: "text-gray-500",
      icon: HelpCircle,
    },
  ];

  return (
    <div className="rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">Compliance Overview</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Aggregated results across all reports.
      </p>

      {loading ? (
        <div className="mt-8 space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <div className="skeleton h-4 w-24 rounded" />
              <div className="skeleton h-3 w-full rounded-full" />
            </div>
          ))}
        </div>
      ) : total === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <div className="h-20 w-20 rounded-full bg-muted/50 flex items-center justify-center">
            <ShieldCheck className="h-8 w-8 text-muted-foreground/30" />
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            No compliance data yet. Upload documents and run validation.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          {/* Stacked bar */}
          <div className="flex h-3 overflow-hidden rounded-full bg-muted">
            {bars.map((bar) =>
              bar.value > 0 ? (
                <motion.div
                  key={bar.label}
                  className={`${bar.color} h-full`}
                  initial={{ width: 0 }}
                  animate={{ width: `${(bar.value / total) * 100}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              ) : null
            )}
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-4">
            {bars.map((bar) => {
              const Icon = bar.icon;
              return (
                <div key={bar.label} className="flex items-center gap-2.5">
                  <Icon className={`h-4 w-4 ${bar.textColor}`} />
                  <div>
                    <p className="text-sm font-medium">{bar.value}</p>
                    <p className="text-xs text-muted-foreground">{bar.label}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { Clock, FileText, ShieldCheck, CheckCircle2 } from "lucide-react";
import type { ComplianceReport } from "@/lib/types";

interface RecentActivityProps {
  reports: ComplianceReport[];
  loading?: boolean;
}

export function RecentActivity({ reports, loading }: RecentActivityProps) {
  const recent = reports.slice(0, 8);

  return (
    <div className="rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">Recent Activity</h2>
      <p className="mt-1 text-sm text-muted-foreground">Latest compliance checks.</p>

      {loading ? (
        <div className="mt-5 space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="skeleton h-8 w-8 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <div className="skeleton h-3.5 w-3/4 rounded" />
                <div className="skeleton h-3 w-1/2 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : recent.length === 0 ? (
        <div className="mt-6 flex flex-col items-center justify-center py-8 text-center">
          <Clock className="h-8 w-8 text-muted-foreground/30" />
          <p className="mt-3 text-sm text-muted-foreground">No recent activity.</p>
        </div>
      ) : (
        <div className="mt-4 space-y-1">
          {recent.map((report) => (
            <div
              key={report.report_id}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-muted/50"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                {report.overall_compliance_score >= 80 ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : report.overall_compliance_score >= 50 ? (
                  <ShieldCheck className="h-4 w-4 text-amber-600" />
                ) : (
                  <FileText className="h-4 w-4 text-red-600" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {report.document_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {Math.round(report.overall_compliance_score)}% &middot;{" "}
                  {report.frameworks_tested.join(", ")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { Upload, ShieldCheck, Search, ArrowRight } from "lucide-react";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { ComplianceOverview } from "@/components/dashboard/ComplianceOverview";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { Button } from "@/components/ui/button";
import { getDashboardStats, getComplianceReports } from "@/lib/api";
import type { DashboardStats, ComplianceReport } from "@/lib/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [reports, setReports] = useState<ComplianceReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load(attempt = 0) {
      try {
        const [s, r] = await Promise.all([
          getDashboardStats(),
          getComplianceReports(0, 10).catch(() => []),
        ]);
        if (!cancelled) {
          setStats(s);
          setReports(r);
          setLoading(false);
        }
      } catch {
        if (!cancelled && attempt < 2) {
          setTimeout(() => load(attempt + 1), 1500);
        } else if (!cancelled) {
          setStats({
            documents_ingested: 0,
            compliance_checks: 0,
            average_score: 0,
            active_frameworks: 0,
          });
          setLoading(false);
        }
      }
    }
    load();

    return () => { cancelled = true; };
  }, []);

  const quickActions = [
    {
      label: "Upload Document",
      href: "/ingest",
      icon: Upload,
      description: "Process PDFs for compliance analysis",
    },
    {
      label: "Run Compliance Check",
      href: "/compliance",
      icon: ShieldCheck,
      description: "Validate against regulatory frameworks",
    },
    {
      label: "Search Standards",
      href: "/search",
      icon: Search,
      description: "Query Ind AS, SEBI, RBI regulations",
    },
  ];

  return (
    <div className="mx-auto max-w-7xl px-6 py-16">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="mb-16 text-center"
      >
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">
          <span className="gradient-text">NFRA Compliance</span>
          <br />
          <span className="text-foreground">Engine</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
          AI-powered validation of financial statements against Indian
          regulatory frameworks — Ind AS, SEBI LODR, Schedule III, and more.
        </p>
      </motion.div>

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15 }}
      >
        <StatsCards stats={stats ?? { documents_ingested: 0, compliance_checks: 0, average_score: 0, active_frameworks: 0 }} loading={loading} />
      </motion.div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.25 }}
        className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-3"
      >
        {quickActions.map((action) => {
          const Icon = action.icon;
          return (
            <Link key={action.href} href={action.href}>
              <motion.div
                whileHover={{ y: -2 }}
                className="group flex items-center gap-4 rounded-2xl border bg-card p-5 transition-shadow hover:shadow-md"
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{action.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {action.description}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
              </motion.div>
            </Link>
          );
        })}
      </motion.div>

      {/* Main Grid */}
      <div className="mt-12 grid grid-cols-1 gap-8 lg:grid-cols-3">
        <motion.div
          className="lg:col-span-2"
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
        >
          <ComplianceOverview reports={reports} loading={loading} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
        >
          <RecentActivity reports={reports} loading={loading} />
        </motion.div>
      </div>
    </div>
  );
}

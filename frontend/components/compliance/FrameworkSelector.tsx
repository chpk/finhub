"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  FileSpreadsheet,
  Building2,
  Landmark,
  Leaf,
  ClipboardCheck,
} from "lucide-react";

const frameworks = [
  {
    id: "IndAS",
    name: "Ind AS",
    description: "Indian Accounting Standards (Ind AS 1–41)",
    icon: BookOpen,
    color: "text-blue-600",
    activeBg: "bg-blue-50 border-blue-200",
  },
  {
    id: "Schedule_III",
    name: "Schedule III",
    description: "Companies Act 2013 — Balance Sheet Format",
    icon: FileSpreadsheet,
    color: "text-violet-600",
    activeBg: "bg-violet-50 border-violet-200",
  },
  {
    id: "SEBI_LODR",
    name: "SEBI LODR",
    description: "Listing Obligations & Disclosure Requirements",
    icon: Building2,
    color: "text-emerald-600",
    activeBg: "bg-emerald-50 border-emerald-200",
  },
  {
    id: "RBI_Norms",
    name: "RBI Norms",
    description: "Reserve Bank Disclosure Norms",
    icon: Landmark,
    color: "text-amber-600",
    activeBg: "bg-amber-50 border-amber-200",
  },
  {
    id: "ESG_BRSR",
    name: "ESG / BRSR",
    description: "Business Responsibility & Sustainability Reporting",
    icon: Leaf,
    color: "text-green-600",
    activeBg: "bg-green-50 border-green-200",
  },
  {
    id: "Auditing_Standards",
    name: "Auditing Standards",
    description: "SA 700–720 by ICAI",
    icon: ClipboardCheck,
    color: "text-rose-600",
    activeBg: "bg-rose-50 border-rose-200",
  },
];

interface FrameworkSelectorProps {
  selected: string[];
  onToggle: (id: string) => void;
}

export function FrameworkSelector({ selected, onToggle }: FrameworkSelectorProps) {
  return (
    <div className="rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">Select Frameworks</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Choose regulatory frameworks to validate against.
      </p>
      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {frameworks.map((fw, i) => {
          const isActive = selected.includes(fw.id);
          const Icon = fw.icon;
          return (
            <motion.button
              key={fw.id}
              onClick={() => onToggle(fw.id)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                isActive
                  ? `${fw.activeBg} shadow-sm`
                  : "border-transparent bg-muted/40 hover:bg-muted/70"
              }`}
            >
              <div
                className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                  isActive ? "bg-white shadow-sm" : "bg-white/60"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? fw.color : "text-muted-foreground"}`} />
              </div>
              <div>
                <p className={`text-sm font-semibold ${isActive ? "text-foreground" : ""}`}>
                  {fw.name}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">{fw.description}</p>
              </div>
              {/* Checkbox indicator */}
              <div
                className={`ml-auto mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-all ${
                  isActive
                    ? "border-primary bg-primary text-white"
                    : "border-muted-foreground/30"
                }`}
              >
                {isActive && (
                  <motion.svg
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    className="h-3 w-3"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <motion.polyline points="20 6 9 17 4 12" />
                  </motion.svg>
                )}
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

export { frameworks };

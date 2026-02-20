"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FileText,
  ShieldCheck,
  Search,
  BarChart3,
  MessageCircle,
  Home,
} from "lucide-react";

const sidebarItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/ingest", label: "Ingest Documents", icon: FileText },
  { href: "/compliance", label: "Compliance Check", icon: ShieldCheck },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/search", label: "Semantic Search", icon: Search },
  { href: "/chat", label: "NFRA Bot", icon: MessageCircle },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 border-r bg-card/50 p-6 lg:block">
      <nav className="flex flex-col gap-1">
        {sidebarItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

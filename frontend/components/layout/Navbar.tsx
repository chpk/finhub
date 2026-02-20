"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  FileText,
  ShieldCheck,
  Search,
  BarChart3,
  MessageCircle,
  Home,
  Activity,
  Shield,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/ingest", label: "Ingest", icon: FileText },
  { href: "/compliance", label: "Compliance", icon: ShieldCheck },
  { href: "/analytics", label: "Analytics", icon: Activity },
  { href: "/examination", label: "Examination", icon: Shield },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/search", label: "Search", icon: Search },
  { href: "/chat", label: "Chat", icon: MessageCircle },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-white/20 bg-white/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#0071e3] to-[#6e56cf] transition-transform group-hover:scale-105">
            <ShieldCheck className="h-4.5 w-4.5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-foreground leading-tight">
              NFRA
            </span>
            <span className="text-[10px] leading-tight text-muted-foreground">
              Compliance Engine
            </span>
          </div>
        </Link>

        {/* Navigation links */}
        <div className="flex items-center gap-0.5">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="navbar-pill"
                    className="absolute inset-0 rounded-full bg-primary/[0.08]"
                    transition={{
                      type: "spring",
                      bounce: 0.15,
                      duration: 0.5,
                    }}
                  />
                )}
                <Icon className="relative h-3.5 w-3.5" />
                <span className="relative hidden md:inline">{item.label}</span>
              </Link>
            );
          })}
        </div>

        {/* Right side - status */}
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-1.5 sm:flex">
            <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-muted-foreground">Online</span>
          </div>
        </div>
      </div>
    </nav>
  );
}

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface CardProps {
  className?: string;
  children: ReactNode;
  hover?: boolean;
  onClick?: () => void;
}

export function Card({ className, children, hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "bg-white rounded-xl border border-zinc-200 shadow-card overflow-hidden",
        hover && "transition-all duration-200 hover:shadow-card-hover hover:border-zinc-300 cursor-pointer",
        className
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  className?: string;
  children: ReactNode;
}

export function CardHeader({ className, children }: CardHeaderProps) {
  return (
    <div className={cn("px-5 py-4 border-b border-zinc-100 flex items-center gap-3", className)}>
      {children}
    </div>
  );
}

export function CardBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("p-5", className)}>{children}</div>;
}

// ─── Summary Stat Card ────────────────────────────────────────────────────────

interface SummaryCardProps {
  label: string;
  value: number | string;
  sub?: string;
  accent: "blue" | "green" | "red" | "amber" | "zinc";
}

const ACCENT_MAP = {
  blue:  { bar: "bg-blue-500",    num: "text-blue-700" },
  green: { bar: "bg-emerald-500", num: "text-emerald-700" },
  red:   { bar: "bg-red-500",     num: "text-red-600" },
  amber: { bar: "bg-amber-400",   num: "text-amber-600" },
  zinc:  { bar: "bg-zinc-400",    num: "text-zinc-600" },
};

export function SummaryCard({ label, value, sub, accent }: SummaryCardProps) {
  const a = ACCENT_MAP[accent];
  return (
    <div className="relative bg-white rounded-xl border border-zinc-200 shadow-card px-5 py-4 overflow-hidden animate-fade-in">
      <div className={cn("absolute top-0 left-0 w-1 h-full rounded-l-xl", a.bar)} />
      <div className="pl-1">
        <div className="text-xs text-zinc-500 font-medium mb-1">{label}</div>
        <div className={cn("text-3xl font-bold tracking-tight", a.num)}>{value}</div>
        {sub && <div className="text-xs text-zinc-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

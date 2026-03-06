import { cn, getStatusColors, getSeverityColors } from "@/lib/utils";
import type { ValidationStatus, LayerStatus, DiffSeverity } from "@/types";

// ─── Status Badge ─────────────────────────────────────────────────────────────

interface StatusBadgeProps {
  status: ValidationStatus | LayerStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const c = getStatusColors(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold tracking-wide border",
        c.badge,
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", c.dot)} />
      {status.toUpperCase()}
    </span>
  );
}

// ─── Layer Dot ────────────────────────────────────────────────────────────────

interface LayerDotProps {
  status: LayerStatus;
  label?: string;
  className?: string;
}

export function LayerDot({ status, label, className }: LayerDotProps) {
  const c = getStatusColors(status);
  return (
    <span
      className={cn("relative inline-flex items-center gap-1", className)}
      title={label ?? status}
    >
      <span className={cn("w-2 h-2 rounded-full", c.dot)} />
      {label && <span className="text-[10px] text-zinc-500">{label}</span>}
    </span>
  );
}

// ─── Severity Badge ───────────────────────────────────────────────────────────

interface SeverityBadgeProps {
  severity: DiffSeverity;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const c = getSeverityColors(severity);
  return (
    <span
      className={cn(
        "px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide",
        c.badge,
        className
      )}
    >
      {severity}
    </span>
  );
}

// ─── Run Status Chip ──────────────────────────────────────────────────────────

export function RunStatusChip({ status }: { status: ValidationStatus }) {
  const c = getStatusColors(status);
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border", c.badge)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", c.dot, status === "RUNNING" ? "animate-pulse" : "")} />
      {status}
    </span>
  );
}

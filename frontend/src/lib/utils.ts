// src/lib/utils.ts

// Utility to combine class names (similar to clsx)
export function cn(...inputs: (string | undefined | null | false)[]) {
  return inputs.filter(Boolean).join(" ");
}

// Format bytes into human readable format
export function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;

  const sizes = [
    "Bytes",
    "KB",
    "MB",
    "GB",
    "TB"
  ];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat(
    (bytes / Math.pow(k, i)).toFixed(dm)
  ) + " " + sizes[i];
}

// Helper to handle naive ISO strings (Python) and ensure they're treated as UTC
function parseUTC(date: string | Date): Date {
  if (typeof date === "string") {
    // Replace space with T for valid ISO format, and ensure Z suffix
    const utcDate = (date.includes("Z") || date.includes("+")) ? date : `${date.replace(" ", "T")}Z`;
    return new Date(utcDate);
  }
  return date;
}

// Format a date into readable string (IST)
export function formatDate(date: string | Date) {
  const d = parseUTC(date);

  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true
  });
}

// Format duration (seconds → human readable)
export function formatDuration(startedAt: string, completedAt: string) {
  const start = parseUTC(startedAt).getTime();
  const end = parseUTC(completedAt).getTime();
  const seconds = Math.floor((end - start) / 1000);

  if (!seconds || seconds < 0) return "1s";

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;

  if (mins === 0) return `${secs}s`;

  return `${mins}m ${secs}s`;
}

// Compute validation stats for dashboard
export function computeStats(results: any[]) {
  const total = results.length;

  const passed = results.filter(r => r.overallStatus === "PASS").length;
  const failed = results.filter(r => r.overallStatus === "FAIL").length;

  const passRate = total ? Math.round((passed / total) * 100) : 0;

  return {
    totalReports: total,
    passed,
    failed,
    pending: total - passed - failed,
    passRate
  };
}

// Status → color helper for UI badges
export function getStatusColors(status: string) {
  switch (status) {
    case "PASS":
    case "pass":
      return {
        badge: "bg-emerald-100 text-emerald-700 border-emerald-200",
        dot: "bg-emerald-500"
      };
    case "FAIL":
    case "fail":
      return {
        badge: "bg-red-100 text-red-700 border-red-200",
        dot: "bg-red-500"
      };
    case "RUNNING":
    case "running":
      return {
        badge: "bg-blue-100 text-blue-700 border-blue-200",
        dot: "bg-blue-500"
      };
    case "PENDING":
    case "pending":
      return {
        badge: "bg-zinc-100 text-zinc-600 border-zinc-200",
        dot: "bg-zinc-400"
      };
    case "ERROR":
    case "error":
      return {
        badge: "bg-orange-100 text-orange-700 border-orange-200",
        dot: "bg-orange-500"
      };
    case "REVIEW":
    case "review":
      return {
        badge: "bg-amber-100 text-amber-700 border-amber-200",
        dot: "bg-amber-500"
      };
    case "skipped":
      return {
        badge: "bg-slate-100 text-slate-500 border-slate-200",
        dot: "bg-slate-300"
      };
    default:
      return {
        badge: "bg-zinc-100 text-zinc-600 border-zinc-200",
        dot: "bg-zinc-400"
      };
  }
}

// Severity → color helper for UI badges
export function getSeverityColors(severity: string) {
  switch (severity) {
    case "high":
      return {
        bg: "bg-red-50",
        border: "border-red-200",
        text: "text-red-700",
        badge: "bg-red-100 text-red-700 border-red-200",
        dot: "bg-red-500"
      };
    case "medium":
      return {
        bg: "bg-amber-50",
        border: "border-amber-200",
        text: "text-amber-700",
        badge: "bg-amber-100 text-amber-700 border-amber-200",
        dot: "bg-amber-500"
      };
    case "low":
      return {
        bg: "bg-zinc-50",
        border: "border-zinc-200",
        text: "text-zinc-600",
        badge: "bg-zinc-100 text-zinc-600 border-zinc-200",
        dot: "bg-zinc-400"
      };
    default:
      return {
        bg: "bg-zinc-50",
        border: "border-zinc-200",
        text: "text-zinc-600",
        badge: "bg-zinc-100 text-zinc-600 border-zinc-200",
        dot: "bg-zinc-400"
      };
  }
}
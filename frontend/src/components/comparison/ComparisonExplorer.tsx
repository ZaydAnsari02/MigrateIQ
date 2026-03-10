"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair, Difference } from "@/types";

const resolvePath = (path: string | undefined | null) => {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${baseUrl}${path.startsWith("/") ? "" : "/"}${path}`;
};

function getDiffLabel(type: string, detail: string): string {
  const normalized = type.toLowerCase().replace(/\s/g, "");
  if (["visualdismatch", "visualmismatch", "visualdifference"].includes(normalized)) {
    const d = detail.toLowerCase();
    if (/chart type|bar chart|pie chart|line chart|stacked bar|donut|scatter/.test(d)) return "Chart Type Difference";
    if (/color scheme|colour scheme|color differ|palette|shade of/.test(d)) return "Color Scheme Difference";
    if (/legend/.test(d)) return "Legend Difference";
    if (/\btitle\b/.test(d)) return "Title Difference";
    if (/data label/.test(d)) return "Data Labels Difference";
    if (/axis|x-axis|y-axis/.test(d)) return "Axis Labels Difference";
    if (/filter|slicer/.test(d)) return "Filter Difference";
    if (/layout|position|alignment/.test(d)) return "Layout Difference";
    if (/missing|absent|not present|not found/.test(d)) return "Missing Element";
    if (/tooltip|hover/.test(d)) return "Tooltip Difference";
    if (/font|text size/.test(d)) return "Text Style Difference";
    return "Visual Difference";
  }
  return type;
}

const LAYER_META = {
  L1: { bg: "bg-blue-50", border: "border-blue-200", dot: "bg-blue-500", pill: "bg-blue-100 text-blue-700", name: "Visual" },
  L2: { bg: "bg-violet-50", border: "border-violet-200", dot: "bg-violet-500", pill: "bg-violet-100 text-violet-700", name: "Semantic" },
  L3: { bg: "bg-rose-50", border: "border-rose-200", dot: "bg-rose-500", pill: "bg-rose-100 text-rose-700", name: "Data" },
} as const;

interface ComparisonExplorerProps {
  pairs: ReportPair[];
  initialLeftId?: string;
}

export function ComparisonExplorer({ pairs, initialLeftId }: ComparisonExplorerProps) {
  const [selectedId, setSelectedId] = useState<string>(initialLeftId ?? pairs[0]?.id ?? "");

  useEffect(() => { if (initialLeftId) setSelectedId(initialLeftId); }, [initialLeftId]);
  useEffect(() => {
    if (pairs.length > 0 && (!selectedId || !pairs.find(p => p.id === selectedId))) {
      setSelectedId(pairs[0].id);
    }
  }, [pairs, selectedId]);

  const pair = pairs.find(p => p.id === selectedId);

  if (pairs.length === 0) {
    return (
      <div className="bg-white border border-zinc-200 rounded-2xl p-16 text-center shadow-sm">
        <div className="text-5xl mb-4 opacity-30">🔍</div>
        <h3 className="text-sm font-semibold text-zinc-600 mb-1">No reports to compare</h3>
        <p className="text-xs text-zinc-400">Run a validation first to see detailed comparison results here.</p>
      </div>
    );
  }

  const vis = pair?.visualResult ?? null;
  let keyDiffs: string[] = [];
  if (vis?.aiKeyDifferences) {
    try {
      const parsed = JSON.parse(vis.aiKeyDifferences);
      keyDiffs = Array.isArray(parsed) ? parsed : [String(parsed)];
    } catch { keyDiffs = [vis.aiKeyDifferences]; }
  }

  const statusColor = (s: string) => {
    switch (s.toUpperCase()) {
      case "PASS": return "text-emerald-600 bg-emerald-50 border-emerald-200";
      case "FAIL": return "text-red-600 bg-red-50 border-red-200";
      case "REVIEW": return "text-amber-600 bg-amber-50 border-amber-200";
      default: return "text-zinc-500 bg-zinc-50 border-zinc-200";
    }
  };

  return (
    <div className="flex gap-5 items-start">

      {/* ── LEFT SIDEBAR ─────────────────────────────────────────────────── */}
      <div className="w-64 shrink-0">
        <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
          {/* Sidebar header */}
          <div className="px-4 py-3.5 border-b border-zinc-100">
            <h3 className="text-xs font-bold text-zinc-800">Report Pairs</h3>
            <p className="text-[10px] text-zinc-400 mt-0.5">{pairs.length} validation result{pairs.length !== 1 ? "s" : ""}</p>
          </div>

          {/* Report list */}
          <div className="py-1.5 max-h-[calc(100vh-220px)] overflow-y-auto">
            {pairs.map(p => {
              const isSelected = p.id === selectedId;
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  className={cn(
                    "w-full text-left px-4 py-3 transition-all border-l-2 flex items-start justify-between gap-2",
                    isSelected
                      ? "border-l-blue-600 bg-blue-50/60"
                      : "border-l-transparent hover:bg-zinc-50"
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className={cn(
                      "text-[11px] font-medium truncate leading-snug",
                      isSelected ? "text-blue-700" : "text-zinc-700"
                    )}>
                      {p.reportName}
                    </p>
                    <p className="text-[9px] text-zinc-400 mt-0.5">
                      {new Date(p.createdAt).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                    </p>
                  </div>
                  <span className={cn(
                    "shrink-0 text-[8px] font-bold px-1.5 py-0.5 rounded-full border uppercase tracking-wide mt-0.5",
                    statusColor(p.overallStatus)
                  )}>
                    {p.overallStatus}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── MAIN PANEL ───────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 space-y-4">
        {!pair ? (
          <div className="bg-white border-2 border-dashed border-zinc-200 rounded-2xl h-48 flex items-center justify-center text-zinc-400 text-xs">
            Select a report from the sidebar
          </div>
        ) : (
          <>
            {/* ── Report header ───────────────────────────────────────────── */}
            <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm px-5 py-4 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-zinc-900 truncate">{pair.reportName}</h2>
                <p className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">{pair.id}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {/* Layer pills */}
                <div className="flex items-center gap-1.5">
                  {[
                    { key: "L1", status: pair.layer1Status },
                    { key: "L2", status: pair.layer2Status },
                    { key: "L3", status: pair.layer3Status },
                  ].map(l => {
                    const lc = LAYER_META[l.key as keyof typeof LAYER_META];
                    return (
                      <div key={l.key} className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-lg border text-[9px] font-bold uppercase",
                        l.status === "skipped" ? "bg-zinc-50 border-zinc-200 text-zinc-400" : cn(lc.bg, lc.border, lc.pill)
                      )}>
                        <span>{l.key}</span>
                        <span>·</span>
                        <LayerDot status={l.status} />
                      </div>
                    );
                  })}
                </div>
                <StatusBadge status={pair.overallStatus} />
              </div>
            </div>

            {/* ── Visual Comparison ───────────────────────────────────────── */}
            {vis ? (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-900">Visual Comparison</h4>
                    <p className="text-[10px] text-zinc-400 mt-0.5">Side-by-side screenshot comparison</p>
                  </div>
                  {vis.pixelSimilarityPct !== undefined && (
                    <div className="text-right">
                      <p className="text-[10px] text-zinc-400">Pixel Similarity</p>
                      <p className={cn(
                        "text-xl font-bold tabular-nums mt-0.5",
                        vis.pixelSimilarityPct > 95 ? "text-emerald-600" :
                        vis.pixelSimilarityPct > 75 ? "text-amber-500" : "text-red-500"
                      )}>
                        {vis.pixelSimilarityPct.toFixed(1)}%
                      </p>
                    </div>
                  )}
                </div>

                <div className="p-5 space-y-5">
                  {/* Screenshots */}
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: "Tableau", tag: "Source", src: resolvePath(pair.tableauScreenshot), tagColor: "bg-blue-100 text-blue-700" },
                      { label: "Power BI", tag: "Migrated", src: resolvePath(pair.powerBiScreenshot), tagColor: "bg-violet-100 text-violet-700" },
                    ].map(side => (
                      <div key={side.label}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[11px] font-semibold text-zinc-700">{side.label}</span>
                          <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full", side.tagColor)}>{side.tag}</span>
                        </div>
                        <div className="rounded-xl border border-zinc-200 bg-zinc-50 overflow-hidden flex items-center justify-center min-h-[180px]">
                          {side.src ? (
                            <img src={side.src} alt={side.label} className="w-full h-full object-contain" />
                          ) : (
                            <div className="py-10 text-center text-zinc-300">
                              <div className="text-3xl opacity-40 mb-1">🖼️</div>
                              <div className="text-[10px]">No screenshot uploaded</div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* AI Summary */}
                  {vis.aiSummary && (
                    <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                          <span className="text-[8px] text-white font-bold">AI</span>
                        </span>
                        <span className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Analysis Summary</span>
                      </div>
                      <p className="text-xs text-zinc-700 leading-relaxed">{vis.aiSummary}</p>
                    </div>
                  )}

                  {/* Numbered differences */}
                  {keyDiffs.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Identified Differences</span>
                        <span className="text-[9px] font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{keyDiffs.length}</span>
                      </div>
                      <div className="space-y-2">
                        {keyDiffs.map((diff, i) => (
                          <div key={i} className="flex gap-3 items-start bg-zinc-50 border border-zinc-200 rounded-xl p-3.5">
                            <span className="shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white text-[9px] font-bold flex items-center justify-center mt-0.5">
                              {i + 1}
                            </span>
                            <p className="text-[11px] text-zinc-700 leading-relaxed">{diff}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {keyDiffs.length === 0 && vis.aiSummary && (
                    <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-3">
                      <span>✅</span>
                      <span className="text-xs text-emerald-700 font-medium">No visual differences identified by AI analysis.</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xl shrink-0">🖼️</div>
                <div>
                  <p className="text-xs font-semibold text-slate-600">Visual Layer Not Validated</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Upload Tableau and Power BI screenshots to enable visual comparison.</p>
                </div>
              </div>
            )}

            {/* ── Regression Log ──────────────────────────────────────────── */}
            <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-zinc-900">Regression Log</h4>
                  <p className="text-[10px] text-zinc-400 mt-0.5">All detected issues across validation layers</p>
                </div>
                <span className={cn(
                  "text-[10px] font-bold px-2.5 py-1 rounded-full border",
                  pair.differences.length === 0
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-red-50 text-red-600 border-red-200"
                )}>
                  {pair.differences.length === 0 ? "All Passed" : `${pair.differences.length} Issue${pair.differences.length !== 1 ? "s" : ""}`}
                </span>
              </div>

              <div className="p-5">
                {pair.differences.length === 0 ? (
                  <div className="flex items-center gap-4 bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                    <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center text-lg shrink-0">✅</div>
                    <div>
                      <p className="text-xs font-semibold text-emerald-700">No regressions detected</p>
                      <p className="text-[11px] text-emerald-600 mt-0.5">All checks passed across L1 Visual, L2 Semantic, and L3 Data layers.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {pair.differences.map((d: Difference, i: number) => {
                      const lc = LAYER_META[d.layer as keyof typeof LAYER_META] ?? LAYER_META.L3;
                      const label = getDiffLabel(d.type, d.detail);
                      return (
                        <div key={i} className={cn("rounded-xl border p-4 flex gap-3 items-start", lc.bg, lc.border)}>
                          <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", lc.dot)} />
                          <div className="flex-1 min-w-0 space-y-1.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[11px] font-bold text-zinc-800">{label}</span>
                              <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide", lc.pill)}>
                                {d.layer} · {lc.name}
                              </span>
                              {d.severity === "high" && (
                                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 uppercase tracking-wide">High</span>
                              )}
                            </div>
                            <p className="text-[11px] text-zinc-600 leading-snug">{d.detail}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

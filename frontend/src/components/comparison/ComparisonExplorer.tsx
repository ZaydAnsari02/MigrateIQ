"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type {
  ReportPair,
  Difference,
  ExcludedParameters,
  CardVisibility,
  LayerStatus,
} from "@/types";
import {
  DEFAULT_EXCLUDED_PARAMS,
  DEFAULT_CARD_VISIBILITY,
  excludedToEnabled,
} from "@/types";

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

// ── Parameter exclusion config ────────────────────────────────────────────────
const EXCLUSION_OPTIONS: { key: keyof ExcludedParameters; label: string }[] = [
  { key: "chart_type",   label: "Ignore Chart Type" },
  { key: "color",        label: "Ignore Color Differences" },
  { key: "legend",       label: "Ignore Legend Differences" },
  { key: "axis_labels",  label: "Ignore Axis Labels" },
  { key: "axis_scale",   label: "Ignore Axis Scale" },
  { key: "title",        label: "Ignore Chart Title" },
  { key: "data_labels",  label: "Ignore Data Labels" },
  { key: "layout",       label: "Ignore Layout Differences" },
  { key: "text_content", label: "Ignore Text Content" },
  { key: "text_case",    label: "Ignore Text Case Differences" },
];

// Maps API parameterResults keys → display labels (ordered as shown in UI)
const PARAM_RESULT_LABELS: Record<string, string> = {
  chart_type:   "Chart Type Consistency",
  color:        "Color Consistency",
  legend:       "Legend Validation",
  axis_labels:  "Axis Labels",
  axis_scale:   "Axis Scale Consistency",
  title:        "Chart Title",
  data_labels:  "Data Labels",
  layout:       "Layout / Alignment",
  text_content: "Text Content",
};

const LAYER_META = {
  L1: { bg: "bg-blue-50",   border: "border-blue-200",   dot: "bg-blue-500",   pill: "bg-blue-100 text-blue-700",     name: "Visual"   },
  L2: { bg: "bg-violet-50", border: "border-violet-200", dot: "bg-violet-500", pill: "bg-violet-100 text-violet-700", name: "Semantic" },
  L3: { bg: "bg-rose-50",   border: "border-rose-200",   dot: "bg-rose-500",   pill: "bg-rose-100 text-rose-700",     name: "Data"     },
} as const;

/**
 * Derive per-parameter statuses from GPT-structured results or legacy booleans.
 *
 * Priority:
 *  1. vis.parameterResults  — "pass"/"fail"/"ignored" strings from GPT (new format)
 *  2. vis boolean match fields — legacy fallback
 *
 * User exclusion overrides are applied on top in both cases.
 */
function deriveParamResults(
  vis: ReportPair["visualResult"] | null,
  excluded: ExcludedParameters,
): Record<string, string> | null {
  if (!vis || !vis.gpt4oCalled) return null;

  // New format: use pre-computed parameterResults from the backend
  if (vis.parameterResults) {
    const base: Record<string, string> = { ...(vis.parameterResults as Record<string, string>) };
    // Apply user exclusion overrides on top
    for (const key of Object.keys(excluded) as (keyof ExcludedParameters)[]) {
      if (excluded[key] && key in base) base[key as string] = "ignored";
    }
    return base;
  }

  // Legacy fallback: derive from individual boolean match properties
  const s = (match: boolean | undefined | null, key: keyof ExcludedParameters): string => {
    if (excluded[key]) return "ignored";
    if (match === undefined || match === null) return "skipped";
    return match ? "pass" : "fail";
  };
  return {
    chart_type:   s(vis.chartTypeMatch,    "chart_type"),
    color:        s(vis.colorSchemeMatch,  "color"),
    legend:       s(vis.legendMatch,       "legend"),
    axis_labels:  s(vis.axisLabelsMatch,   "axis_labels"),
    axis_scale:   s(vis.axisScaleMatch,    "axis_scale"),
    title:        s(vis.titleMatch,        "title"),
    data_labels:  s(vis.dataLabelsMatch,   "data_labels"),
    layout:       s(vis.layoutMatch,       "layout"),
    text_content: s(vis.textContentMatch,  "text_content"),
  };
}

interface ComparisonExplorerProps {
  pairs: ReportPair[];
  initialLeftId?: string;
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function Checkbox({
  checked,
  onChange,
  label,
  activeColor = "bg-blue-600 border-blue-600",
  labelActive = "text-zinc-800",
  labelInactive = "text-zinc-500",
  disabled = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  activeColor?: string;
  labelActive?: string;
  labelInactive?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={cn("flex items-center gap-2 select-none", disabled ? "cursor-default opacity-50" : "cursor-pointer group")}
      onClick={() => !disabled && onChange(!checked)}
    >
      <div
        className={cn(
          "w-4 h-4 rounded border-2 flex items-center justify-center transition-colors shrink-0",
          checked ? activeColor : "bg-white border-zinc-300",
          !disabled && "group-hover:border-zinc-400"
        )}
      >
        {checked && (
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 12 12">
            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </div>
      <span className={cn("text-[11px] font-medium", checked ? labelActive : labelInactive)}>{label}</span>
    </label>
  );
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pass:    "text-emerald-700 bg-emerald-50 border-emerald-200",
    fail:    "text-red-600 bg-red-50 border-red-200",
    ignored: "text-zinc-400 bg-zinc-50 border-zinc-200",
    skipped: "text-amber-600 bg-amber-50 border-amber-200",
  };
  return (
    <span className={cn(
      "inline-flex items-center px-2 py-0.5 rounded-full border text-[9px] font-bold uppercase tracking-wide",
      styles[status] ?? styles.skipped
    )}>
      {status}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ComparisonExplorer({ pairs, initialLeftId }: ComparisonExplorerProps) {
  const [selectedId, setSelectedId]       = useState<string>(initialLeftId ?? pairs[0]?.id ?? "");
  const [excluded, setExcluded]           = useState<ExcludedParameters>({ ...DEFAULT_EXCLUDED_PARAMS });
  const [cards, setCards]                 = useState<CardVisibility>({ ...DEFAULT_CARD_VISIBILITY });
  const [isRunning, setIsRunning]         = useState(false);
  const [liveResult, setLiveResult]       = useState<Record<string, any> | null>(null);
  const [filtersOpen, setFiltersOpen]     = useState(false);
  const [cardsOpen, setCardsOpen]         = useState(false);
  const [search, setSearch]               = useState("");

  // Result visibility filters
  const [showPass,    setShowPass]    = useState(true);
  const [showFail,    setShowFail]    = useState(true);
  const [showIgnored, setShowIgnored] = useState(true);

  useEffect(() => { if (initialLeftId) setSelectedId(initialLeftId); }, [initialLeftId]);
  useEffect(() => {
    if (pairs.length > 0 && (!selectedId || !pairs.find(p => p.id === selectedId))) {
      setSelectedId(pairs[0].id);
    }
  }, [pairs, selectedId]);

  // Reset live result & filters when switching pairs
  useEffect(() => {
    setLiveResult(null);
    setExcluded({ ...DEFAULT_EXCLUDED_PARAMS });
  }, [selectedId]);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  async function handleRunValidation() {
    if (!pair?.id) return;
    setIsRunning(true);
    setLiveResult(null);
    try {
      const parameters = excludedToEnabled(excluded);
      const res = await fetch(`${baseUrl}/report-pairs/${pair.id}/visual-validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parameters }),
      });
      if (!res.ok) throw new Error(await res.text());
      setLiveResult(await res.json());
    } catch (e: any) {
      setLiveResult({ error: e.message ?? "Validation failed" });
    } finally {
      setIsRunning(false);
    }
  }

  const filteredPairs = pairs.filter(p =>
    p.reportName.toLowerCase().includes(search.toLowerCase())
  );

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
    if (Array.isArray(vis.aiKeyDifferences)) {
      keyDiffs = vis.aiKeyDifferences;
    } else {
      try {
        const parsed = JSON.parse(vis.aiKeyDifferences);
        keyDiffs = Array.isArray(parsed) ? parsed : [String(parsed)];
      } catch { keyDiffs = [vis.aiKeyDifferences as string]; }
    }
  }

  const statusColor = (s: string) => {
    switch (s.toUpperCase()) {
      case "PASS":   return "text-emerald-600 bg-emerald-50 border-emerald-200";
      case "FAIL":   return "text-red-600 bg-red-50 border-red-200";
      case "REVIEW": return "text-amber-600 bg-amber-50 border-amber-200";
      default:       return "text-zinc-500 bg-zinc-50 border-zinc-200";
    }
  };

  const activeExclusionCount  = Object.values(excluded).filter(Boolean).length;
  const toggleCard = (key: keyof CardVisibility) =>
    setCards(prev => ({ ...prev, [key]: !prev[key] }));

  // Parameter results: prefer live run, fall back to client-side derivation from
  // stored vis match booleans + current exclusion map. This means toggling
  // exclusions immediately updates the breakdown table without a re-run.
  const paramResults: Record<string, string> | null =
    liveResult?.parameterResults ?? deriveParamResults(vis, excluded);

  // Derive overall breakdown status: fail if any enabled field failed, else pass.
  const breakdownStatus: string =
    liveResult?.status ??
    (paramResults
      ? Object.values(paramResults).some(s => s === "fail") ? "fail" : "pass"
      : "");

  // Effective L1 status for the header dot — derived from paramResults so that
  // "ignored"-only runs still show PASS instead of "—".
  // Rules: any fail → fail | any pass → pass | all ignored/skipped → skipped ("—")
  const effectiveL1Status: LayerStatus = (() => {
    if (!paramResults) return pair?.layer1Status ?? "skipped";
    const vals = Object.values(paramResults);
    if (vals.some(s => s === "fail"))  return "fail";
    if (vals.some(s => s === "pass"))  return "pass";
    return "skipped";
  })();

  const filteredParamEntries = paramResults
    ? Object.entries(PARAM_RESULT_LABELS).filter(([key]) => {
        const st = paramResults[key] ?? "skipped";
        if (st === "pass"    && !showPass)    return false;
        if (st === "fail"    && !showFail)    return false;
        if (st === "ignored" && !showIgnored) return false;
        return true;
      })
    : null;

  return (
    <div className="flex gap-5 items-start">

      {/* ── LEFT SIDEBAR ─────────────────────────────────────────────────── */}
      <div className="w-64 shrink-0">
        <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
          <div className="px-4 py-3.5 border-b border-zinc-100">
            <h3 className="text-xs font-bold text-zinc-800">Report Pairs</h3>
            <p className="text-[10px] text-zinc-400 mt-0.5">{pairs.length} validation result{pairs.length !== 1 ? "s" : ""}</p>
          </div>

          {/* Search */}
          <div className="px-3 py-2.5 border-b border-zinc-100">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search reports…"
                className="w-full pl-7 pr-2 py-1.5 text-[11px] bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:border-blue-400 focus:bg-white transition-colors placeholder:text-zinc-400"
              />
            </div>
          </div>

          {/* Report list */}
          <div className="py-1.5 max-h-[calc(100vh-265px)] overflow-y-auto">
            {filteredPairs.length === 0 ? (
              <p className="text-[11px] text-zinc-400 text-center py-6">No reports match &ldquo;{search}&rdquo;</p>
            ) : null}
            {filteredPairs.map(p => {
              const isSelected = p.id === selectedId;
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  className={cn(
                    "w-full text-left px-4 py-3 transition-all border-l-2 flex items-start justify-between gap-2",
                    isSelected ? "border-l-blue-600 bg-blue-50/60" : "border-l-transparent hover:bg-zinc-50"
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className={cn("text-[11px] font-medium truncate leading-snug", isSelected ? "text-blue-700" : "text-zinc-700")}>
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
            {/* ── Report header ─────────────────────────────────────────── */}
            <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm px-5 py-4 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-zinc-900 truncate">{pair.reportName}</h2>
                <p className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">{pair.id}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <div className="flex items-center gap-1.5">
                  {[
                    { key: "L1", status: effectiveL1Status },
                    { key: "L2", status: pair.layer2Status },
                    { key: "L3", status: pair.layer3Status },
                  ].map(l => {
                    const pillStyle =
                      l.status === "skipped"
                        ? "bg-zinc-50 border-zinc-200 text-zinc-400"
                        : l.status?.toUpperCase() === "PASS"
                        ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                        : "bg-red-50 border-red-200 text-red-600";
                    return (
                      <div key={l.key} className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-lg border text-[9px] font-bold uppercase",
                        pillStyle
                      )}>
                        <span>{l.key}</span><span>·</span><LayerDot status={l.status} />
                      </div>
                    );
                  })}
                </div>
                <StatusBadge status={pair.overallStatus} />
              </div>
            </div>

            {/* ── Advanced Filters ──────────────────────────────────────── */}
            <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 flex items-center justify-between">
                <button
                  onClick={() => setFiltersOpen(o => !o)}
                  className="flex items-center gap-2 text-xs font-semibold text-zinc-700 hover:text-zinc-900 transition-colors"
                >
                  <svg className={cn("w-3.5 h-3.5 text-zinc-400 transition-transform", filtersOpen && "rotate-180")}
                    viewBox="0 0 12 12" fill="none">
                    <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Advanced Filters
                  {activeExclusionCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[9px] font-bold">
                      {activeExclusionCount} excluded
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setCardsOpen(o => !o)}
                  className="flex items-center gap-1.5 text-[10px] font-medium text-zinc-400 hover:text-zinc-600 transition-colors"
                >
                  <svg className={cn("w-3 h-3 transition-transform", cardsOpen && "rotate-180")}
                    viewBox="0 0 12 12" fill="none">
                    <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Toggle Cards
                </button>
              </div>

              {/* Card visibility toggles */}
              {cardsOpen && (
                <div className="px-5 pb-4 border-t border-zinc-100">
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wider font-medium mt-3 mb-2">
                    Toggle Result Cards
                  </p>
                  <div className="flex flex-wrap gap-4">
                    <Checkbox checked disabled label="Screenshot Comparison" labelActive="text-zinc-400" labelInactive="text-zinc-400"
                      onChange={() => {}} activeColor="bg-zinc-300 border-zinc-300" />
                    <Checkbox checked disabled label="AI Summary" labelActive="text-zinc-400" labelInactive="text-zinc-400"
                      onChange={() => {}} activeColor="bg-zinc-300 border-zinc-300" />
                    <Checkbox
                      checked={cards.visualBreakdown}
                      onChange={() => toggleCard("visualBreakdown")}
                      label="Visual Comparison Breakdown"
                    />
                    <Checkbox
                      checked={cards.regressionLog}
                      onChange={() => toggleCard("regressionLog")}
                      label="Regression Log"
                    />
                  </div>
                </div>
              )}

              {/* Advanced Filters content */}
              {filtersOpen && (
                <div className="border-t border-zinc-100 px-5 py-4 space-y-5">
                  {/* A — Parameter exclusion */}
                  <div>
                    <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-1">
                      Exclude Parameters
                    </p>
                    <p className="text-[10px] text-zinc-400 mb-3">
                      Checked parameters will be ignored — their mismatches will not cause FAIL.
                    </p>
                    <div className="grid grid-cols-3 gap-x-6 gap-y-2.5">
                      {EXCLUSION_OPTIONS.map(({ key, label }) => (
                        <Checkbox
                          key={key}
                          checked={excluded[key]}
                          onChange={v => setExcluded(prev => ({ ...prev, [key]: v }))}
                          label={label}
                          activeColor="bg-amber-500 border-amber-500"
                          labelActive="text-amber-700"
                          labelInactive="text-zinc-600"
                        />
                      ))}
                    </div>
                    {activeExclusionCount > 0 && (
                      <button
                        onClick={() => setExcluded({ ...DEFAULT_EXCLUDED_PARAMS })}
                        className="mt-2 text-[10px] text-zinc-400 hover:text-zinc-600 underline"
                      >
                        Clear all exclusions
                      </button>
                    )}
                  </div>

                  {/* B — Result filters (when any parameter results are available) */}
                  {paramResults && (
                    <div>
                      <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-3">
                        Result Filters
                      </p>
                      <div className="flex flex-wrap gap-4">
                        <Checkbox checked={showPass}    onChange={setShowPass}    label="Show Pass"
                          activeColor="bg-emerald-600 border-emerald-600" labelActive="text-emerald-700" />
                        <Checkbox checked={showFail}    onChange={setShowFail}    label="Show Fail"
                          activeColor="bg-red-600 border-red-600" labelActive="text-red-700" />
                        <Checkbox checked={showIgnored} onChange={setShowIgnored} label="Show Ignored"
                          activeColor="bg-zinc-500 border-zinc-500" labelActive="text-zinc-600" />
                      </div>
                    </div>
                  )}

                  {/* Run button */}
                  <div className="flex items-center gap-3 pt-1">
                    <button
                      onClick={handleRunValidation}
                      disabled={isRunning || !pair?.tableauScreenshot || !pair?.powerBiScreenshot}
                      className={cn(
                        "px-4 py-2 rounded-lg text-[11px] font-bold transition-all",
                        isRunning || !pair?.tableauScreenshot || !pair?.powerBiScreenshot
                          ? "bg-zinc-100 text-zinc-400 cursor-not-allowed"
                          : "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                      )}
                    >
                      {isRunning ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                          </svg>
                          Running…
                        </span>
                      ) : "Start Validation"}
                    </button>
                    {!pair?.tableauScreenshot || !pair?.powerBiScreenshot
                      ? <span className="text-[10px] text-amber-500 font-medium">Upload both screenshots to enable</span>
                      : null}
                  </div>
                </div>
              )}

              {/* Error banner */}
              {liveResult?.error && (
                <div className="border-t border-zinc-100 px-5 py-4">
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
                    Validation error: {liveResult.error}
                  </div>
                </div>
              )}
            </div>

            {/* ── Visual Comparison Breakdown (toggleable) ──────────────── */}
            {cards.visualBreakdown && paramResults && (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-900">Visual Comparison Breakdown</h4>
                    <p className="text-[10px] text-zinc-400 mt-0.5">
                      {liveResult ? "Parameter-level results from last validation run" : "Parameter-level results — adjust exclusions to recalculate"}
                    </p>
                  </div>
                  {breakdownStatus && (
                    <span className={cn(
                      "text-[9px] font-bold px-2 py-1 rounded-full border uppercase",
                      breakdownStatus === "pass"   ? "text-emerald-700 bg-emerald-50 border-emerald-200" :
                      breakdownStatus === "fail"   ? "text-red-600 bg-red-50 border-red-200" :
                      breakdownStatus === "review" ? "text-amber-600 bg-amber-50 border-amber-200" :
                      "text-zinc-500 bg-zinc-50 border-zinc-200"
                    )}>
                      {breakdownStatus}
                    </span>
                  )}
                </div>
                <div className="p-5">
                  {/* Parameter results table only — AI summary/diffs shown in Visual Comparison card */}
                  <div className="rounded-xl border border-zinc-200 overflow-hidden">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="bg-zinc-50 border-b border-zinc-200">
                          <th className="text-left px-4 py-2.5 font-semibold text-zinc-600">Parameter</th>
                          <th className="text-left px-4 py-2.5 font-semibold text-zinc-600">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredParamEntries && filteredParamEntries.length > 0
                          ? filteredParamEntries.map(([key, label]) => (
                              <tr key={key} className="border-b border-zinc-100 last:border-0">
                                <td className="px-4 py-2.5 text-zinc-700 font-medium">{label}</td>
                                <td className="px-4 py-2.5">
                                  <StatusPill status={paramResults![key] ?? "skipped"} />
                                </td>
                              </tr>
                            ))
                          : (
                              <tr>
                                <td colSpan={2} className="px-4 py-4 text-center text-[10px] text-zinc-400">
                                  No results match current filters.
                                </td>
                              </tr>
                            )
                        }
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* ── Visual Comparison (always visible — screenshots + AI analysis) ── */}
            {(vis || pair.tableauScreenshot || pair.powerBiScreenshot) && (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-900">Visual Comparison</h4>
                    <p className="text-[10px] text-zinc-400 mt-0.5">Side-by-side screenshot comparison with AI analysis</p>
                  </div>
                  {/* Risk level badge */}
                  {(liveResult?.gpt4oRiskLevel ?? vis?.gpt4oRiskLevel) && (
                    <span className={cn(
                      "text-[8px] font-bold px-2 py-1 rounded-full border uppercase",
                      (liveResult?.gpt4oRiskLevel ?? vis?.gpt4oRiskLevel) === "high"   ? "text-red-600 bg-red-50 border-red-200" :
                      (liveResult?.gpt4oRiskLevel ?? vis?.gpt4oRiskLevel) === "medium" ? "text-amber-600 bg-amber-50 border-amber-200" :
                      "text-emerald-600 bg-emerald-50 border-emerald-200"
                    )}>
                      {liveResult?.gpt4oRiskLevel ?? vis?.gpt4oRiskLevel} risk
                    </span>
                  )}
                </div>

                <div className="p-5 space-y-5">
                  {/* Screenshots */}
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: "Tableau", tag: "Source",   src: resolvePath(pair.tableauScreenshot), tagColor: "bg-blue-100 text-blue-700" },
                      { label: "Power BI", tag: "Migrated", src: resolvePath(pair.powerBiScreenshot), tagColor: "bg-violet-100 text-violet-700" },
                    ].map(side => (
                      <div key={side.label}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[11px] font-semibold text-zinc-700">{side.label}</span>
                          <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full", side.tagColor)}>{side.tag}</span>
                        </div>
                        <div className="rounded-xl border border-zinc-200 bg-zinc-50 overflow-hidden flex items-center justify-center min-h-[180px]">
                          {side.src
                            ? <img src={side.src} alt={side.label} className="w-full h-full object-contain" />
                            : <div className="py-10 text-center text-zinc-300">
                                <div className="text-3xl opacity-40 mb-1">🖼️</div>
                                <div className="text-[10px]">No screenshot uploaded</div>
                              </div>
                          }
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* AI Summary — prefer live result, fall back to stored */}
                  {(liveResult?.aiSummary ?? (vis?.aiSummary)) && (
                    <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                          <span className="text-[8px] text-white font-bold">AI</span>
                        </span>
                        <span className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Analysis Summary</span>
                      </div>
                      <p className="text-xs text-zinc-700 leading-relaxed">
                        {liveResult?.aiSummary ?? vis?.aiSummary}
                      </p>
                    </div>
                  )}

                  {/* Identified Differences — prefer live result, fall back to stored */}
                  {(() => {
                    const activeDiffs: string[] = (() => {
                      if (liveResult && Array.isArray(liveResult.aiKeyDifferences) && liveResult.aiKeyDifferences.length > 0) {
                        return liveResult.aiKeyDifferences;
                      }
                      return keyDiffs;
                    })();
                    if (activeDiffs.length === 0) {
                      const hasSummary = liveResult?.aiSummary ?? vis?.aiSummary;
                      if (hasSummary) {
                        return (
                          <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-3">
                            <span>✅</span>
                            <span className="text-xs text-emerald-700 font-medium">No visual differences identified by AI analysis.</span>
                          </div>
                        );
                      }
                      return null;
                    }
                    return (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Identified Differences</span>
                          <span className="text-[9px] font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                            {activeDiffs.length}
                          </span>
                        </div>
                        {activeDiffs.map((diff, i) => (
                          <div key={i} className="flex gap-3 items-start bg-zinc-50 border border-zinc-200 rounded-xl p-3.5">
                            <span className="shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white text-[9px] font-bold flex items-center justify-center mt-0.5">
                              {i + 1}
                            </span>
                            <p className="text-[11px] text-zinc-700 leading-relaxed">{diff}</p>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}

            {!vis && !pair.tableauScreenshot && !pair.powerBiScreenshot && (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xl shrink-0">🖼️</div>
                <div>
                  <p className="text-xs font-semibold text-slate-600">Visual Layer Not Validated</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Upload Tableau and Power BI screenshots to enable visual comparison.</p>
                </div>
              </div>
            )}

            {/* ── Regression Log (toggleable) ───────────────────────────── */}
            {cards.regressionLog && (
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
            )}
          </>
        )}
      </div>
    </div>
  );
}

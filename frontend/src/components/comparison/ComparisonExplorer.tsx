"use client";

import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair, Difference, TableDetail, TableTypeMismatch, TableColumnValueDetail, ColumnValueAnalysis, LayerStatus, ValidationStatus, ExcludedParameters, CardVisibility, Layer2Details } from "@/types";
import { DEFAULT_EXCLUDED_PARAMS, excludedToEnabled, DEFAULT_CARD_VISIBILITY } from "@/types";

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

// ── Helper functions ──────────────────────────────────────────────────────────

function deriveParamResults(
  vis: ReportPair["visualResult"] | null,
  excluded: ExcludedParameters,
): Record<string, string> | null {
  if (!vis) return null;
  const matchMap: Record<string, boolean | undefined> = {
    chart_type:   vis.chartTypeMatch,
    color:        vis.colorSchemeMatch,
    legend:       vis.legendMatch,
    axis_labels:  vis.axisLabelsMatch,
    axis_scale:   undefined,
    title:        vis.titleMatch,
    data_labels:  vis.dataLabelsMatch,
    layout:       vis.layoutMatch,
    text_content: undefined,
  };
  const result: Record<string, string> = {};
  for (const key of Object.keys(PARAM_RESULT_LABELS)) {
    if (excluded[key as keyof ExcludedParameters]) {
      result[key] = "ignored";
    } else if (matchMap[key] === true) {
      result[key] = "pass";
    } else if (matchMap[key] === false) {
      result[key] = "fail";
    } else {
      result[key] = "skipped";
    }
  }
  return result;
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
  L1: { bg: "bg-blue-50", border: "border-blue-200", dot: "bg-blue-500", pill: "bg-blue-100 text-blue-700", name: "Visual" },
  L2: { bg: "bg-violet-50", border: "border-violet-200", dot: "bg-violet-500", pill: "bg-violet-100 text-violet-700", name: "Semantic & Data" },
  L3: { bg: "bg-rose-50", border: "border-rose-200", dot: "bg-rose-500", pill: "bg-rose-100 text-rose-700", name: "Deep Analysis" },
} as const;

interface ComparisonExplorerProps {
  pairs: ReportPair[];
  initialLeftId?: string;
  onRefresh?: () => Promise<void>;
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

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded border text-[9px] font-medium", color)}>
      {label}
    </span>
  );
}

function OverlapBar({ pct }: { pct: number }) {
  const color = pct >= 100 ? "bg-emerald-500" : pct >= 80 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className={cn(
        "text-[10px] font-bold tabular-nums shrink-0 w-10 text-right",
        pct >= 100 ? "text-emerald-600" : pct >= 80 ? "text-amber-600" : "text-red-600"
      )}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

// ── L3 Measure Results Component ──────────────────────────────────────────────

interface L3Result {
  layer: string;
  status: string;
  description?: string;
  summary: {
    total_measures: number;
    passed: number;
    failed: number;
    unknown: number;
    missing_in_pbit: string[];
    missing_in_twbx: string[];
  };
  measure_results: {
    measure: string;
    verdict: string;
    confidence: string;
    reason: string;
    tableau_formula: string;
    dax_formula: string;
  }[];
  error?: string;
}

function L3MeasureResults({ l3 }: { l3: L3Result }) {
  if (l3.status === "ERROR") {
    return (
      <div className="bg-white border border-red-200 rounded-2xl shadow-sm p-5">
        <p className="text-xs font-semibold text-red-600">L3 Validation Error</p>
        <p className="text-[11px] text-zinc-500 mt-1">{l3.error}</p>
      </div>
    );
  }

  const { summary, measure_results } = l3;

  return (
    <div className="bg-white border border-rose-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-rose-100 bg-rose-50/40">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-zinc-900">Measure Equivalence</h4>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-700 uppercase tracking-wide">
                L3 · Semantic
              </span>
            </div>
            <p className="text-[10px] text-zinc-400 mt-0.5">
              LLM-judged formula equivalence between Tableau calculated fields and DAX measures
            </p>
            {l3.description && (
              <p className="text-[11px] text-zinc-600 mt-1">{l3.description}</p>
            )}
          </div>
          <span className={cn(
            "text-[10px] font-bold px-3 py-1 rounded-full border uppercase",
            l3.status === "PASS"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : "bg-red-50 text-red-600 border-red-200"
          )}>
            {l3.status}
          </span>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "Total Measures", value: summary.total_measures, color: "text-zinc-800" },
            { label: "Passed",         value: summary.passed,         color: "text-emerald-600" },
            { label: "Failed",         value: summary.failed,         color: summary.failed > 0 ? "text-red-600" : "text-emerald-600" },
            { label: "Unknown",        value: summary.unknown,        color: summary.unknown > 0 ? "text-amber-600" : "text-zinc-400" },
          ].map(s => (
            <div key={s.label} className="bg-white border border-rose-100 rounded-xl px-3 py-2.5">
              <p className="text-[9px] text-zinc-400 uppercase tracking-wide">{s.label}</p>
              <p className={cn("text-sm font-bold mt-0.5 tabular-nums", s.color)}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Missing measures warnings */}
        {(summary.missing_in_pbit?.length > 0 || summary.missing_in_twbx?.length > 0) && (
          <div className="mt-3 grid grid-cols-2 gap-2">
            {summary.missing_in_pbit?.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                <p className="text-[9px] font-bold text-amber-700 uppercase mb-1">Missing in Power BI</p>
                <div className="flex flex-wrap gap-1">
                  {summary.missing_in_pbit.map(m => (
                    <span key={m} className="text-[9px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded border border-amber-200">{m}</span>
                  ))}
                </div>
              </div>
            )}
            {summary.missing_in_twbx?.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                <p className="text-[9px] font-bold text-amber-700 uppercase mb-1">Missing in Tableau</p>
                <div className="flex flex-wrap gap-1">
                  {summary.missing_in_twbx.map(m => (
                    <span key={m} className="text-[9px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded border border-amber-200">{m}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Measure results table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-200">
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500">Measure</th>
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500">Tableau Formula</th>
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500">DAX Formula</th>
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500">Reason</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500 w-20">Confidence</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500 w-20">Verdict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {measure_results.map((m) => (
              <tr key={m.measure} className={cn(
                "transition-colors",
                m.verdict === "FAIL"    ? "bg-red-50/20 hover:bg-red-50/40" :
                m.verdict === "UNKNOWN" ? "bg-amber-50/20 hover:bg-amber-50/40" :
                "bg-white hover:bg-zinc-50/60"
              )}>
                <td className="px-4 py-3 font-semibold text-zinc-800">{m.measure}</td>
                <td className="px-4 py-3 font-mono text-zinc-500 max-w-[160px] truncate" title={m.tableau_formula}>
                  {m.tableau_formula || <span className="text-zinc-300 italic">—</span>}
                </td>
                <td className="px-4 py-3 font-mono text-zinc-500 max-w-[160px] truncate" title={m.dax_formula}>
                  {m.dax_formula || <span className="text-zinc-300 italic">—</span>}
                </td>
                <td className="px-4 py-3 text-zinc-500 italic max-w-[200px]">{m.reason}</td>
                <td className="px-4 py-3 text-center">
                  <span className={cn(
                    "text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase",
                    m.confidence === "high"   ? "bg-zinc-100 text-zinc-600" :
                    m.confidence === "medium" ? "bg-amber-50 text-amber-600" :
                    "bg-zinc-50 text-zinc-400"
                  )}>
                    {m.confidence}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={cn(
                    "text-[9px] font-bold px-2 py-0.5 rounded-full border uppercase",
                    m.verdict === "PASS"    ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                    m.verdict === "FAIL"    ? "bg-red-50 text-red-600 border-red-200" :
                    "bg-amber-50 text-amber-600 border-amber-200"
                  )}>
                    {m.verdict}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Unified Column Analysis Component (L2/L3) ────────────────────────────────

function UnifiedColumnAnalysis({
  layer2Details,
  layer3Details,
}: {
  layer2Details?: Layer2Details | null;
  layer3Details?: TableDetail[];
}) {
  const [openTables, setOpenTables] = useState<Set<string>>(new Set());
  const [openColumns, setOpenColumns] = useState<Set<string>>(new Set());

  const toggleTable = (name: string) =>
    setOpenTables((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const toggleColumn = (key: string) =>
    setOpenColumns((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const valDetails = layer2Details?.columnValueDetails ?? [];
  const schemaDetails = layer3Details ?? [];

  const matchedTableNames = new Set(valDetails.filter(v => v.result !== "SKIPPED").map(v => v.tableName));
  const schemaTableNames = new Set(schemaDetails.map(s => s.tableName));
  const allTableNames = Array.from(new Set([...matchedTableNames, ...schemaTableNames])).sort();

  const tablesAnalyzed = allTableNames.length;
  const columnsAnalyzed = valDetails.reduce((s, v) => s + (v.columnsAnalyzed ?? 0), 0);
  const mismatchedColumns = valDetails.reduce((s, v) => s + (v.mismatchedColumns ?? 0), 0);
  const schemaFailures = schemaDetails.filter((s) => s.result === "FAIL").length;
  const typeMismatches = schemaDetails.reduce((s, t) => s + (t.columnTypeMismatches?.length ?? 0), 0);

  const matchRate = columnsAnalyzed > 0
    ? (((columnsAnalyzed - mismatchedColumns) / columnsAnalyzed) * 100).toFixed(1)
    : "--";

  const stats = [
    { label: "Tables Analyzed",    value: String(tablesAnalyzed),     color: "text-zinc-800" },
    { label: "Columns Analyzed",   value: String(columnsAnalyzed),    color: "text-zinc-800" },
    { label: "Value Mismatches",   value: String(mismatchedColumns),  color: mismatchedColumns > 0 ? "text-red-600" : "text-emerald-600" },
    { label: "Schema Failures",    value: String(schemaFailures),     color: schemaFailures > 0 ? "text-red-600" : "text-emerald-600" },
    { label: "Type Mismatches",    value: String(typeMismatches),     color: typeMismatches > 0 ? "text-amber-600" : "text-emerald-600" },
    { label: "Overall Match Rate", value: matchRate === "--" ? "--%" : `${matchRate}%`, color: mismatchedColumns === 0 && columnsAnalyzed > 0 ? "text-emerald-600" : "text-amber-600" },
  ];

  if (tablesAnalyzed === 0) {
    return (
      <div className="bg-white border border-violet-200 rounded-2xl shadow-sm p-8 text-center">
        <div className="text-3xl mb-3 opacity-30">📊</div>
        <p className="text-xs font-semibold text-zinc-900">No column-level data available</p>
        <p className="text-[11px] text-zinc-400 mt-1">Run a new validation to see column-level schema and data results.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-violet-200 rounded-2xl shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-violet-100 bg-violet-50/40">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-zinc-900">Column Analysis</h4>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 uppercase tracking-wide">
                L2 · Semantic
              </span>
            </div>
            <p className="text-[10px] text-zinc-400 mt-0.5">Comprehensive schema, row count, and data value validation</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {stats.map((s) => (
            <div key={s.label} className="bg-white border border-violet-100 rounded-xl px-3 py-2.5">
              <p className="text-[9px] text-zinc-400 uppercase tracking-wide">{s.label}</p>
              <p className={cn("text-sm font-bold mt-0.5 tabular-nums", s.color)}>{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-200">
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500 w-48">Table / Column</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500">Tableau</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500">Power BI</th>
              <th className="px-4 py-2.5 text-left font-semibold text-zinc-500 whitespace-nowrap min-w-[200px]">Summary / Difference</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500 w-32">Overlap</th>
              <th className="px-4 py-2.5 text-center font-semibold text-zinc-500">Match</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {allTableNames.map((tableName) => {
              const tableVal = valDetails.find((v) => v.tableName.toLowerCase().trim() === tableName.toLowerCase().trim());
              const tableSchema = schemaDetails.find((s) => s.tableName.toLowerCase().trim() === tableName.toLowerCase().trim());

              const isOpen = openTables.has(tableName);
              const isUnmatched = tableVal?.result === "SKIPPED";
              const isFail = tableSchema?.result === "FAIL" || (tableVal && tableVal.result === "FAIL");

              let summary = "";
              if (isUnmatched) {
                const side = tableVal?.twbxColumns?.length ? "Tableau only" : "Power BI only";
                summary = `Table found in ${side}. No match in other source.`;
              } else if (tableSchema?.result === "FAIL") {
                const parts = [];
                if (tableSchema.columnsMissingInPbi.length) parts.push(`${tableSchema.columnsMissingInPbi.length} col missing in PBI`);
                if (tableSchema.columnsMissingInTwbx.length) parts.push(`${tableSchema.columnsMissingInTwbx.length} col missing in Tableau`);
                if (tableSchema.columnTypeMismatches.length) parts.push(`${tableSchema.columnTypeMismatches.length} type mismatch`);
                summary = parts.join(", ") || tableSchema.failureReasons[0] || "Schema mismatch identified";
              } else if (tableVal?.mismatchedColumns) {
                summary = `${tableVal.mismatchedColumns} column${tableVal.mismatchedColumns !== 1 ? "s" : ""} have data mismatches`;
              } else {
                summary = "Schema and counts match perfectly.";
              }

              return (
                <React.Fragment key={tableName}>
                  <tr className={cn(
                    "transition-colors group",
                    isFail ? "bg-red-50/20 hover:bg-red-50/40" : isUnmatched ? "bg-amber-50/20 hover:bg-amber-50/40" : "bg-white hover:bg-zinc-50/60"
                  )}>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleTable(tableName)}
                        className="flex items-center gap-2 text-left min-w-0"
                      >
                        <svg className={cn("w-3 h-3 text-zinc-400 shrink-0 transition-transform", isOpen && "rotate-90")}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                        </svg>
                        <span className="font-bold text-zinc-900 truncate" title={tableName}>{tableName}</span>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-zinc-600">
                      {(() => {
                        const count = tableVal?.rowCountTableau ?? tableSchema?.rowCountTableau;
                        return count != null ? `${count.toLocaleString()} rows` : "--";
                      })()}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-zinc-600">
                      {(() => {
                        const count = tableVal?.rowCountPowerBi ?? tableSchema?.rowCountPowerBi;
                        return count != null ? `${count.toLocaleString()} rows` : "--";
                      })()}
                    </td>
                    <td className={cn("px-4 py-3 text-[10px] italic", isFail ? "text-red-600 font-medium" : isUnmatched ? "text-amber-700" : "text-zinc-400")}>
                      {summary}
                    </td>
                    <td className="px-4 py-3">
                      {tableVal?.columnsAnalyzed ? (
                        <OverlapBar pct={((tableVal.columnsAnalyzed - tableVal.mismatchedColumns) / tableVal.columnsAnalyzed) * 100} />
                      ) : <div className="text-center text-zinc-300">--%</div>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isFail ? (
                        <span className="text-[9px] font-bold text-red-600 px-1.5 py-0.5 rounded-full bg-red-50 border border-red-200">FAIL</span>
                      ) : isUnmatched ? (
                        <span className="text-[9px] font-bold text-amber-600 px-1.5 py-0.5 rounded-full bg-amber-50 border border-amber-200">UNMATCHED</span>
                      ) : (
                        <span className="text-[9px] font-bold text-emerald-600 px-1.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200">PASS</span>
                      )}
                    </td>
                  </tr>

                  {isOpen && (
                    <tr>
                      <td colSpan={6} className="px-8 pb-6 bg-zinc-50/30 border-b border-zinc-100">
                        <div className="space-y-4 py-3">
                          {isUnmatched && (
                            <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl">
                              <p className="text-[11px] text-amber-800 leading-relaxed">
                                <strong>Comparison Skipped:</strong> No matching table was found in the other environment for <code>{tableName}</code>.
                                This usually happens when table names differ or a table was only uploaded in one report.
                              </p>
                            </div>
                          )}

                          {tableSchema && (tableSchema.columnsMissingInPbi.length > 0 || tableSchema.columnsMissingInTwbx.length > 0) && (
                            <div className="grid grid-cols-2 gap-4">
                              <div className={cn("p-3 rounded-xl border bg-white shadow-sm", tableSchema.columnsMissingInPbi.length ? "border-red-100" : "border-zinc-100")}>
                                <p className="text-[9px] font-bold text-zinc-400 uppercase tracking-wide mb-2">Missing in Power BI</p>
                                {tableSchema.columnsMissingInPbi.length ? (
                                  <div className="flex flex-wrap gap-1">
                                    {tableSchema.columnsMissingInPbi.map(c => <Chip key={c} label={c} color="bg-red-50 text-red-700 border-red-200" />)}
                                  </div>
                                ) : <p className="text-[10px] text-emerald-600 italic">None</p>}
                              </div>
                              <div className={cn("p-3 rounded-xl border bg-white shadow-sm", tableSchema.columnsMissingInTwbx.length ? "border-red-100" : "border-zinc-100")}>
                                <p className="text-[9px] font-bold text-zinc-400 uppercase tracking-wide mb-2">Missing in Tableau</p>
                                {tableSchema.columnsMissingInTwbx.length ? (
                                  <div className="flex flex-wrap gap-1">
                                    {tableSchema.columnsMissingInTwbx.map(c => <Chip key={c} label={c} color="bg-red-50 text-red-700 border-red-200" />)}
                                  </div>
                                ) : <p className="text-[10px] text-emerald-600 italic">None</p>}
                              </div>
                            </div>
                          )}

                          {tableSchema && tableSchema.columnTypeMismatches.length > 0 && (
                            <div className="rounded-xl border border-amber-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-200 text-[10px] font-bold text-amber-800 uppercase">Schema Type Mismatches</div>
                              <table className="w-full text-[10px]">
                                <thead>
                                  <tr className="bg-zinc-50 border-b border-zinc-100 text-zinc-400">
                                    <th className="px-3 py-1 text-left">Column</th>
                                    <th className="px-3 py-1 text-center">Tableau Type</th>
                                    <th className="px-3 py-1 text-center">Power BI Type</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {tableSchema.columnTypeMismatches.map((m, i) => (
                                    <tr key={i} className="border-b last:border-0">
                                      <td className="px-3 py-2 font-mono">{m.column}</td>
                                      <td className="px-3 py-2 text-center text-blue-600">{m.twbxCanonical}</td>
                                      <td className="px-3 py-2 text-center text-violet-600">{m.pbiCanonical}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {tableVal && tableVal.columnAnalyses.length > 0 && (
                            <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-3 py-1.5 bg-zinc-50 border-b border-zinc-200 text-[10px] font-bold text-zinc-500 uppercase">Column Value Mismatches</div>
                              <table className="w-full text-[10px]">
                                <thead className="text-zinc-400 border-b border-zinc-100">
                                  <tr>
                                    <th className="px-4 py-2 text-left">Matched Column</th>
                                    <th className="px-4 py-2 text-center whitespace-nowrap">Tableau Unique</th>
                                    <th className="px-4 py-2 text-center whitespace-nowrap">Power BI Unique</th>
                                    <th className="px-4 py-2 text-center text-orange-600 whitespace-nowrap">Only in Tableau</th>
                                    <th className="px-4 py-2 text-center text-fuchsia-600 whitespace-nowrap">Only in Power BI</th>
                                    <th className="px-4 py-2 text-left w-24">Overlap</th>
                                    <th className="px-4 py-2 text-center">Result</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {tableVal.columnAnalyses.map((col) => {
                                    const colKey = `${tableName}:${col.columnName}`;
                                    const colOpen = openColumns.has(colKey);
                                    const colFail = col.result === "FAIL";
                                    return (
                                      <React.Fragment key={col.columnName}>
                                        <tr className={cn("border-b last:border-0", colFail && "bg-red-50/30")}>
                                          <td className="px-4 py-2 font-medium">
                                            <button onClick={() => colFail && toggleColumn(colKey)} className="flex items-center gap-2">
                                              {colFail && (
                                                <svg className={cn("w-2.5 h-2.5 text-zinc-400 transition-transform", colOpen && "rotate-90")}
                                                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                                </svg>
                                              )}
                                              {col.columnName}
                                            </button>
                                          </td>
                                          <td className="px-4 py-2 text-center tabular-nums">{col.twbxUniqueCount.toLocaleString()}</td>
                                          <td className="px-4 py-2 text-center tabular-nums">{col.pbixUniqueCount.toLocaleString()}</td>
                                          <td className="px-4 py-2 text-center tabular-nums font-semibold text-orange-600">{col.onlyInTwbxCount || "0"}</td>
                                          <td className="px-4 py-2 text-center tabular-nums font-semibold text-fuchsia-600">{col.onlyInPbixCount || "0"}</td>
                                          <td className="px-4 py-2"><OverlapBar pct={col.overlapPct} /></td>
                                          <td className="px-4 py-2 text-center">
                                            <span className={cn("font-bold text-[8px] uppercase", colFail ? "text-red-500" : "text-emerald-500")}>{col.result}</span>
                                          </td>
                                        </tr>
                                        {colOpen && colFail && (
                                          <tr>
                                            <td colSpan={7} className="px-6 py-4 bg-zinc-50 border-b">
                                              <div className="grid grid-cols-2 gap-6">
                                                <div>
                                                  <p className="text-[9px] font-bold text-blue-700 uppercase mb-2">Unique to Tableau ({col.onlyInTwbxCount})</p>
                                                  <div className="flex flex-wrap gap-1">
                                                    {col.onlyInTwbx.map(v => <Chip key={v} label={v} color="bg-blue-50 text-blue-700 border-blue-200" />)}
                                                    {col.twbxPreviewTruncated && <span className="text-[8px] text-zinc-400 italic">...more</span>}
                                                  </div>
                                                </div>
                                                <div>
                                                  <p className="text-[9px] font-bold text-fuchsia-700 uppercase mb-2">Unique to Power BI ({col.onlyInPbixCount})</p>
                                                  <div className="flex flex-wrap gap-1">
                                                    {col.onlyInPbix.map(v => <Chip key={v} label={v} color="bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200" />)}
                                                    {col.pbixPreviewTruncated && <span className="text-[8px] text-zinc-400 italic">...more</span>}
                                                  </div>
                                                </div>
                                              </div>
                                            </td>
                                          </tr>
                                        )}
                                      </React.Fragment>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {!tableVal && tableSchema?.failureReasons && tableSchema.failureReasons.length > 0 && (
                            <div className="p-3 bg-red-50 border border-red-100 rounded-xl">
                              <p className="text-[10px] font-bold text-red-700 uppercase mb-1">Detailed Issues</p>
                              <ul className="list-disc list-inside text-[11px] text-red-600">
                                {tableSchema.failureReasons.map((r, i) => <li key={i}>{r}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ComparisonExplorer({ pairs, initialLeftId, onRefresh }: ComparisonExplorerProps) {
  const [selectedId, setSelectedId]       = useState<string>(initialLeftId ?? pairs[0]?.id ?? "");
  const [excluded, setExcluded]           = useState<ExcludedParameters>({ ...DEFAULT_EXCLUDED_PARAMS });
  const [cards, setCards]                 = useState<CardVisibility>({ ...DEFAULT_CARD_VISIBILITY });
  const [isRunning, setIsRunning]         = useState(false);
  const [liveResult, setLiveResult]       = useState<Record<string, any> | null>(null);
  const [filtersOpen, setFiltersOpen]     = useState(false);
  const [cardsOpen, setCardsOpen]         = useState(false);
  const [search, setSearch]               = useState("");

  const [showPass,    setShowPass]    = useState(true);
  const [showFail,    setShowFail]    = useState(true);
  const [showIgnored, setShowIgnored] = useState(true);

  useEffect(() => { if (initialLeftId) setSelectedId(initialLeftId); }, [initialLeftId]);
  useEffect(() => {
    if (pairs.length > 0 && (!selectedId || !pairs.find(p => p.id === selectedId))) {
      setSelectedId(pairs[0].id);
    }
  }, [pairs, selectedId]);

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
      await onRefresh?.();
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

  const activeExclusionCount = Object.values(excluded).filter(Boolean).length;
  const toggleCard = (key: keyof CardVisibility) =>
    setCards(prev => ({ ...prev, [key]: !prev[key] }));

  const paramResults: Record<string, string> | null =
    liveResult?.parameterResults
    ?? (vis?.parameterResults ?? null)
    ?? deriveParamResults(vis, excluded);

  const breakdownStatus: string =
    liveResult?.status ??
    vis?.status ??
    (paramResults
      ? Object.values(paramResults).some(s => s === "fail") ? "fail" :
        Object.values(paramResults).some(s => s === "pass") ? "pass" : "skipped"
      : "");

  const effectiveL1Status: LayerStatus = (() => {
    if (paramResults) {
      const vals = Object.values(paramResults);
      if (vals.some(s => s === "fail")) return "fail";
      if (vals.some(s => s === "pass")) return "pass";
    }
    const stored = pair?.layer1Status ?? "skipped";
    return (stored as string).toLowerCase() as LayerStatus;
  })();

  const storedL2Status: LayerStatus = ((pair?.layer2Status ?? "skipped") as string).toLowerCase() as LayerStatus;

  // L3 status comes from pair.layer3Status, which the backend and backendResultToReportPair
  // both derive from the measure-equivalence result (l3Result.status) when a PBIT was uploaded,
  // or from the data-layer table comparisons otherwise.  Never recompute it here.
  const storedL3Status: LayerStatus = ((pair?.layer3Status ?? "skipped") as string).toLowerCase() as LayerStatus;

  const effectiveOverallStatus: ValidationStatus = (() => {
    // Trust the backend's overall status as the authoritative source (it accounts for
    // data-layer failures even when L3 is "skipped" due to no PBIT being uploaded).
    if ((pair?.overallStatus ?? "").toUpperCase() === "FAIL") return "FAIL";
    const statuses = [effectiveL1Status, storedL2Status, storedL3Status];
    if (statuses.some(s => (s ?? "").toUpperCase() === "FAIL")) return "FAIL";
    return "PASS";
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
                    { key: "L2", status: storedL2Status },
                    { key: "L3", status: storedL3Status },
                  ].map(l => {
                    const s = (l.status ?? "skipped").toLowerCase();
                    const pillStyle =
                      s === "pass"    ? "bg-emerald-50 border-emerald-200 text-emerald-700" :
                      s === "fail"    ? "bg-red-50 border-red-200 text-red-600" :
                      s === "review"  ? "bg-amber-50 border-amber-200 text-amber-600" :
                      s === "running" ? "bg-blue-50 border-blue-200 text-blue-600" :
                      s === "pending" ? "bg-zinc-50 border-zinc-200 text-zinc-500" :
                      "bg-zinc-50 border-zinc-200 text-zinc-400";
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
                <StatusBadge status={effectiveOverallStatus} />
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
                      checked={cards.columnDataContent}
                      onChange={() => toggleCard("columnDataContent")}
                      label="Column Data Content"
                    />
                    <Checkbox
                      checked={cards.regressionLog}
                      onChange={() => toggleCard("regressionLog")}
                      label="Regression Log"
                    />
                  </div>
                </div>
              )}

              {filtersOpen && (
                <div className="border-t border-zinc-100 px-5 py-4 space-y-5">
                  <div>
                    <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-1">Exclude Parameters</p>
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

                  {paramResults && (
                    <div>
                      <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-3">Result Filters</p>
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

              {liveResult?.error && (
                <div className="border-t border-zinc-100 px-5 py-4">
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
                    Validation error: {liveResult.error}
                  </div>
                </div>
              )}
            </div>

            {/* ── Visual Comparison Breakdown ───────────────────────────── */}
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

            {/* ── Visual Comparison (screenshots + AI analysis) ─────────── */}
            {cards.visualBreakdown && (vis || pair.tableauScreenshot || pair.powerBiScreenshot) && (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-900">Visual Comparison</h4>
                    <p className="text-[10px] text-zinc-400 mt-0.5">Side-by-side screenshot comparison with AI analysis</p>
                  </div>
                  {vis?.gpt4oRiskLevel && (
                    <div className="text-right">
                      <p className="text-[10px] text-zinc-400">Risk Level</p>
                      <p className={cn(
                        "text-sm font-bold mt-0.5 uppercase tracking-wide",
                        vis.gpt4oRiskLevel === "low"    ? "text-emerald-600" :
                        vis.gpt4oRiskLevel === "medium" ? "text-amber-500"   : "text-red-500"
                      )}>
                        {vis.gpt4oRiskLevel}
                      </p>
                    </div>
                  )}
                </div>
                <div className="p-5 space-y-5">
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

                  {(liveResult?.aiSummary ?? vis?.aiSummary) && (
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

            {cards.visualBreakdown && !pair.tableauScreenshot && !pair.powerBiScreenshot && (
              <div className="bg-white border border-zinc-200 rounded-2xl shadow-sm p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xl shrink-0">🖼️</div>
                <div>
                  <p className="text-xs font-semibold text-slate-600">Visual Layer Not Validated</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Upload Tableau and Power BI screenshots to enable visual comparison.</p>
                </div>
              </div>
            )}

            {/* ── Column Analysis (L2/L3) ──────────────────────────────── */}
            {cards.columnDataContent && (
              <UnifiedColumnAnalysis
                layer2Details={pair.layer2Details}
                layer3Details={pair.layer3Details}
              />
            )}

            {/* ── Measure Equivalence (L3) — only shown when PBIT was uploaded ── */}
            {pair.l3Result && (
              <L3MeasureResults l3={pair.l3Result} />
            )}

            {/* ── Regression Log ────────────────────────────────────────── */}
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
                        <p className="text-[11px] text-emerald-600 mt-0.5">All checks passed across L1 Visual and L2 Semantic layers.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {pair.differences.map((d: Difference, i: number) => {
                        const displayLayer = (d.type as string) === "Data Regression" ? "L2" : d.layer;
                        const lc = LAYER_META[displayLayer as keyof typeof LAYER_META] ?? LAYER_META.L2;
                        const label = getDiffLabel(d.type, d.detail);
                        return (
                          <div key={i} className={cn("rounded-xl border p-4 flex gap-3 items-start", lc.bg, lc.border)}>
                            <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", lc.dot)} />
                            <div className="flex-1 min-w-0 space-y-1.5">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-[11px] font-bold text-zinc-800">{label}</span>
                                <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide", lc.pill)}>
                                  {displayLayer} · {lc.name}
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
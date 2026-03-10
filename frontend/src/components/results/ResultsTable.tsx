"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair, ValidationStatus } from "@/types";

// ─── Export Icon ──────────────────────────────────────────────────────────────

function ExportIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <path d="M6 1v6M3.5 4L6 1l2.5 3M1.5 9v1a.5.5 0 00.5.5h8a.5.5 0 00.5-.5V9"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── Filter Pill ──────────────────────────────────────────────────────────────

interface FilterPillProps {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
  colorClass?: string;
}

function FilterPill({ label, active, count, onClick, colorClass }: FilterPillProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 text-[10px] font-semibold rounded-md border transition-all",
        active
          ? colorClass ?? "bg-zinc-800 text-white border-zinc-800"
          : "bg-zinc-50 text-zinc-500 border-zinc-200 hover:bg-white"
      )}
    >
      {label}
      {count !== undefined && (
        <span className={cn("ml-1 opacity-70")}>{count}</span>
      )}
    </button>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

interface RowProps {
  pair: ReportPair;
  selected: boolean;
  checked: boolean;
  onChecked: (id: string) => void;
  onClick: () => void;
  onMoreInfo?: () => void;
}

function ResultRow({ pair, selected, checked, onChecked, onClick, onMoreInfo }: RowProps) {
  const tableauCaptured = !!pair.tableauScreenshot;
  const pbiCaptured = !!pair.powerBiScreenshot;

  return (
    <tr
      onClick={onClick}
      className={cn(
        "cursor-pointer transition-colors duration-100 border-b border-zinc-50 last:border-0",
        selected
          ? "bg-blue-50/80 border-l-2 border-l-blue-500"
          : "hover:bg-zinc-50/60"
      )}
    >
      {/* Checkbox */}
      <td className="pl-4 pr-1 py-3.5 w-8">
        <input
          type="checkbox"
          checked={checked}
          onChange={() => onChecked(pair.id)}
          onClick={e => e.stopPropagation()}
          className="w-3.5 h-3.5 rounded border-zinc-300 text-blue-600 accent-blue-600 cursor-pointer"
        />
      </td>

      {/* Report Name */}
      <td className="px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full shrink-0",
              pair.overallStatus === "PASS" ? "bg-emerald-400" :
                pair.overallStatus === "FAIL" ? "bg-red-400" :
                  pair.overallStatus === "PENDING" ? "bg-amber-300" : "bg-zinc-300"
            )}
          />
          <span className="text-xs font-medium text-zinc-800">{pair.reportName}</span>
          {pair.differences.length > 0 && (
            <span className="text-[9px] bg-red-100 text-red-600 font-bold px-1.5 py-0.5 rounded-full">
              {pair.differences.length}
            </span>
          )}
        </div>
      </td>

      {/* Tableau status */}
      <td className="px-3 py-3.5">
        <span className={cn(
          "text-[10px] font-medium px-2 py-0.5 rounded",
          tableauCaptured ? "text-emerald-600 bg-emerald-50" : "text-zinc-400 bg-zinc-50"
        )}>
          {tableauCaptured ? "Captured" : "Pending"}
        </span>
      </td>

      {/* Power BI status */}
      <td className="px-3 py-3.5">
        <span className={cn(
          "text-[10px] font-medium px-2 py-0.5 rounded",
          pbiCaptured ? "text-emerald-600 bg-emerald-50" : "text-amber-600 bg-amber-50"
        )}>
          {pbiCaptured ? "Captured" : "Pending"}
        </span>
      </td>

      {/* Layers */}
      <td className="px-3 py-3.5">
        <div className="flex items-center gap-1.5">
          <LayerDot status={pair.layer1Status} label="L1" />
          <LayerDot status={pair.layer2Status} label="L2" />
          <LayerDot status={pair.layer3Status} label="L3" />
        </div>
      </td>

      {/* Result */}
      <td className="px-3 py-3.5">
        <StatusBadge status={pair.overallStatus} />
      </td>

      {/* Actions */}
      <td className="px-5 py-3.5 text-right">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onMoreInfo?.();
          }}
          className="px-3 py-1.5 text-[10px] font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm transition-all"
        >
          More Info
        </button>
      </td>
    </tr>
  );
}

// ─── Results Table ────────────────────────────────────────────────────────────

interface ResultsTableProps {
  pairs: ReportPair[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMoreInfo?: (pair: ReportPair) => void;
  onExport?: (pairs: ReportPair[]) => void;
}

const FILTER_LABELS: { label: string; value: ValidationStatus | "ALL" }[] = [
  { label: "All", value: "ALL" },
  { label: "Pass", value: "PASS" },
  { label: "Fail", value: "FAIL" },
  { label: "Pending", value: "PENDING" },
];

const FILTER_COLORS: Record<string, string> = {
  ALL: "bg-zinc-800 text-white border-zinc-800",
  PASS: "bg-emerald-600 text-white border-emerald-600",
  FAIL: "bg-red-600 text-white border-red-600",
  PENDING: "bg-amber-500 text-white border-amber-500",
};

export function ResultsTable({ pairs, selectedId, onSelect, onMoreInfo, onExport }: ResultsTableProps) {
  const [filter, setFilter] = useState<ValidationStatus | "ALL">("ALL");
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  const filtered = filter === "ALL"
    ? pairs
    : pairs.filter(p => p.overallStatus === filter);

  const counts: Record<string, number> = {
    ALL: pairs.length,
    PASS: pairs.filter(p => p.overallStatus === "PASS").length,
    FAIL: pairs.filter(p => p.overallStatus === "FAIL").length,
    PENDING: pairs.filter(p => p.overallStatus === "PENDING").length,
  };

  const allFilteredChecked = filtered.length > 0 && filtered.every(p => checkedIds.has(p.id));
  const someFilteredChecked = filtered.some(p => checkedIds.has(p.id));

  const toggleCheck = (id: string) => {
    setCheckedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allFilteredChecked) {
      setCheckedIds(prev => {
        const next = new Set(prev);
        filtered.forEach(p => next.delete(p.id));
        return next;
      });
    } else {
      setCheckedIds(prev => {
        const next = new Set(prev);
        filtered.forEach(p => next.add(p.id));
        return next;
      });
    }
  };

  const handleExport = () => {
    const toExport = someFilteredChecked
      ? pairs.filter(p => checkedIds.has(p.id))
      : pairs;
    onExport?.(toExport);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-zinc-900">Validation Results</h3>
          <p className="text-xs text-zinc-400 mt-0.5">Select runs to export, or click a row to inspect differences</p>
        </div>
        <div className="flex items-center gap-2">
          {onExport && (
            <button
              onClick={handleExport}
              className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <ExportIcon />
              {someFilteredChecked ? `Export Selected (${checkedIds.size})` : "Export Report"}
            </button>
          )}
          <div className="flex items-center gap-1.5">
            {FILTER_LABELS.map(f => (
              <FilterPill
                key={f.value}
                label={f.label}
                count={counts[f.value]}
                active={filter === f.value}
                onClick={() => setFilter(f.value)}
                colorClass={FILTER_COLORS[f.value]}
              />
            ))}
          </div>
        </div>
      </CardHeader>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-100">
              {/* Select-all checkbox */}
              <th className="pl-4 pr-1 py-3 w-8">
                <input
                  type="checkbox"
                  checked={allFilteredChecked}
                  ref={el => { if (el) el.indeterminate = someFilteredChecked && !allFilteredChecked; }}
                  onChange={toggleAll}
                  className="w-3.5 h-3.5 rounded border-zinc-300 accent-blue-600 cursor-pointer"
                />
              </th>
              {["Report Name", "Tableau", "Power BI", "Layers", "Result", ""].map((col, idx) => (
                <th
                  key={idx}
                  className={cn(
                    "text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider px-5 py-3 first:pl-5",
                    idx === 5 && "text-right"
                  )}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-xs text-zinc-400">
                  No results match the selected filter.
                </td>
              </tr>
            ) : (
              filtered.map(pair => (
                <ResultRow
                  key={pair.id}
                  pair={pair}
                  selected={selectedId === pair.id}
                  checked={checkedIds.has(pair.id)}
                  onChecked={toggleCheck}
                  onClick={() => onSelect(pair.id)}
                  onMoreInfo={() => onMoreInfo?.(pair)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="px-5 py-3 border-t border-zinc-50 flex items-center justify-between">
        <span className="text-[10px] text-zinc-400">{filtered.length} report{filtered.length !== 1 ? "s" : ""}</span>
        <span className="text-[10px] text-zinc-400 font-mono">
          L1=Visual · L2=Semantic · L3=Data regression
        </span>
      </div>
    </Card>
  );
}

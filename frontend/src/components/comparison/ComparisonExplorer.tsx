"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair } from "@/types";

const resolvePath = (path: string | undefined | null) => {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${baseUrl}${path.startsWith("/") ? "" : "/"}${path}`;
};

interface ComparisonExplorerProps {
  pairs: ReportPair[];
  initialLeftId?: string;
}

export function ComparisonExplorer({ pairs, initialLeftId }: ComparisonExplorerProps) {
  const [selectedId, setSelectedId] = useState<string>(initialLeftId ?? pairs[0]?.id ?? "");
  const [showDiff, setShowDiff] = useState(false);

  // When "More Info" navigates here, update the selection
  useEffect(() => {
    if (initialLeftId) setSelectedId(initialLeftId);
  }, [initialLeftId]);

  // Fallback if current selection disappears from list
  useEffect(() => {
    if (pairs.length > 0 && (!selectedId || !pairs.find(p => p.id === selectedId))) {
      setSelectedId(pairs[0].id);
    }
  }, [pairs, selectedId]);

  const pair = pairs.find(p => p.id === selectedId);

  if (pairs.length === 0) {
    return (
      <Card>
        <div className="p-12 text-center">
          <div className="text-4xl mb-3">🔍</div>
          <h3 className="text-sm font-semibold text-zinc-700 mb-1">No reports available</h3>
          <p className="text-xs text-zinc-400">Run a validation to see detailed comparison results here.</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-5">

      {/* ── Report selector ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-1">
            <div>
              <h3 className="text-sm font-semibold text-zinc-900">Report Comparison Detail</h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Select a report pair to inspect its full validation results
              </p>
            </div>
            {pair?.visualResult && (
              <button
                onClick={() => setShowDiff(v => !v)}
                className={cn(
                  "px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md border transition-all",
                  showDiff
                    ? "bg-red-50 text-red-600 border-red-200"
                    : "bg-white text-zinc-500 border-zinc-200 hover:bg-zinc-50"
                )}
              >
                {showDiff ? "Hide Diff Highlights" : "Show Diff Highlights"}
              </button>
            )}
          </div>
        </CardHeader>
        <div className="p-5">
          <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5 block">
            Report Pair
          </label>
          <select
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
            className="w-full text-xs text-zinc-800 bg-white border border-zinc-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {pairs.map(p => (
              <option key={p.id} value={p.id}>{p.reportName}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* ── Detail panel ────────────────────────────────────────────────── */}
      {!pair ? (
        <div className="bg-zinc-100 rounded-xl border-2 border-dashed border-zinc-200 h-48 flex items-center justify-center text-zinc-400 text-xs">
          Select a report to view details
        </div>
      ) : (
        <div className="space-y-4">

          {/* Header card */}
          <Card>
            <CardHeader>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-zinc-900 truncate">{pair.reportName}</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">{pair.id}</div>
              </div>
              <div className="flex items-center gap-2">
                {pair.visualResult?.status === "review" && (
                  <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[9px] font-bold uppercase">
                    Manual Review
                  </span>
                )}
                <StatusBadge status={pair.overallStatus} />
              </div>
            </CardHeader>

            {/* Layer status strip */}
            <div className="px-5 pb-4 grid grid-cols-3 gap-3">
              {[
                { label: "Visual (L1)", status: pair.layer1Status, icon: "👁️" },
                { label: "Semantic (L2)", status: pair.layer2Status, icon: "🧠" },
                { label: "Data (L3)", status: pair.layer3Status, icon: "🔢" },
              ].map(l => (
                <div
                  key={l.label}
                  className="bg-zinc-50 border border-zinc-100 rounded-lg p-3 flex flex-col items-center gap-1.5"
                >
                  <span className="text-base">{l.icon}</span>
                  <span className="text-[9px] font-bold text-zinc-400 uppercase tracking-tight">{l.label}</span>
                  <LayerDot status={l.status} label={l.status.toUpperCase()} />
                </div>
              ))}
            </div>
          </Card>

          {/* Visual layer — skipped when no screenshots */}
          {!pair.visualResult && (
            <Card>
              <div className="p-5 flex items-center gap-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-2xl">🖼️</span>
                <div>
                  <div className="text-xs font-semibold text-slate-600">Visual Layer Not Validated</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    No screenshots were uploaded for this report pair. Upload Tableau and Power BI screenshots to enable visual comparison.
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Visual analysis */}
          {pair.visualResult && (() => {
            const vis = pair.visualResult!;
            let keyDiffs: string[] = [];
            if (vis.aiKeyDifferences) {
              try {
                const parsed = JSON.parse(vis.aiKeyDifferences);
                keyDiffs = Array.isArray(parsed) ? parsed : [String(parsed)];
              } catch {
                keyDiffs = [vis.aiKeyDifferences];
              }
            }

            return (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between flex-1">
                    <h4 className="text-xs font-semibold text-zinc-900">Visual Comparison</h4>
                    {vis.pixelSimilarityPct !== undefined && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-zinc-400">Pixel similarity:</span>
                        <span className={cn(
                          "text-xs font-bold",
                          vis.pixelSimilarityPct > 95 ? "text-emerald-600" : "text-amber-600"
                        )}>
                          {vis.pixelSimilarityPct.toFixed(1)}%
                        </span>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <div className="p-5 space-y-5">

                  {/* AI summary */}
                  {vis.aiSummary && (
                    <div className="bg-blue-50/60 rounded-xl border border-blue-100 p-4 space-y-1">
                      <div className="text-[10px] font-bold text-blue-500 uppercase tracking-wider">AI Narrative</div>
                      <p className="text-[11px] text-zinc-700 leading-relaxed italic">
                        &ldquo;{vis.aiSummary}&rdquo;
                      </p>
                    </div>
                  )}

                  {/* Key differences chips */}
                  {keyDiffs.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                        Key Visual Differences
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {keyDiffs.map((d, i) => (
                          <span
                            key={i}
                            className="px-2.5 py-1 bg-white border border-zinc-200 text-zinc-600 text-[10px] rounded-md shadow-sm"
                          >
                            {d}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Annotated screenshots side-by-side */}
                  <div className="space-y-2">
                    <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                      {showDiff ? "Pixel Diff" : "Annotated Screenshots"}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        {
                          label: "Tableau Source",
                          path: showDiff
                            ? resolvePath(vis.diffImagePath)
                            : (resolvePath(vis.tableauAnnotatedPath) || resolvePath(pair.tableauScreenshot)),
                          icon: "📊",
                        },
                        {
                          label: "Power BI Migration",
                          path: showDiff
                            ? resolvePath(vis.diffImagePath)
                            : (resolvePath(vis.powerbiAnnotatedPath) || resolvePath(pair.powerBiScreenshot)),
                          icon: "⚡",
                        },
                      ].map(side => (
                        <div key={side.label}>
                          <div className="text-[9px] text-zinc-400 mb-1.5 font-medium">{side.label}</div>
                          <div className="bg-zinc-50 rounded-xl border border-zinc-200 h-48 flex items-center justify-center overflow-hidden relative group">
                            {side.path ? (
                              <img
                                src={side.path}
                                alt={side.label}
                                className="w-full h-full object-contain"
                              />
                            ) : (
                              <div className="text-3xl opacity-20">{side.icon}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {showDiff && (
                      <p className="text-[9px] text-red-500 italic text-center font-medium">
                        Red areas indicate pixel-level differences between the two reports
                      </p>
                    )}
                  </div>

                  {/* Full comparison image */}
                  {vis.comparisonImagePath && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                        Side-by-Side Comparison Report
                      </div>
                      <div className="rounded-xl border border-zinc-200 overflow-hidden">
                        <img
                          src={resolvePath(vis.comparisonImagePath)}
                          alt="Comparison report card"
                          className="w-full object-contain"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            );
          })()}

          {/* Regression log */}
          <Card>
            <CardHeader>
              <h4 className="text-xs font-semibold text-zinc-900">Regression Log</h4>
              <span className="text-[10px] text-zinc-400 font-medium">
                {pair.differences.length} issue{pair.differences.length !== 1 ? "s" : ""} detected
              </span>
            </CardHeader>
            <div className="p-5">
              {pair.differences.length === 0 ? (
                <div className="text-xs text-zinc-400 italic bg-zinc-50 rounded-lg p-4 text-center border border-dashed border-zinc-200">
                  All checks passed — no regressions detected
                </div>
              ) : (
                <div className="space-y-2">
                  {pair.differences.map((d, i) => (
                    <div
                      key={i}
                      className={cn(
                        "border rounded-lg px-3 py-2.5 flex gap-3 items-start",
                        d.layer === "L1" ? "bg-blue-50 border-blue-100" :
                          d.layer === "L2" ? "bg-purple-50 border-purple-100" :
                            "bg-red-50 border-red-100"
                      )}
                    >
                      <div className={cn(
                        "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                        d.layer === "L1" ? "bg-blue-400" :
                          d.layer === "L2" ? "bg-purple-400" :
                            "bg-red-400"
                      )} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-[9px] font-bold text-zinc-900 uppercase">{d.type}</span>
                          <span className="text-[8px] text-zinc-400 font-bold uppercase">{d.layer}</span>
                        </div>
                        <div className="text-[10px] text-zinc-600 leading-tight">{d.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

        </div>
      )}
    </div>
  );
}

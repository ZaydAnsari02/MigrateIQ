"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair } from "@/types";

interface ComparisonExplorerProps {
  pairs: ReportPair[];
  initialLeftId?: string;
}

export function ComparisonExplorer({ pairs, initialLeftId }: ComparisonExplorerProps) {
  const [selectedId, setSelectedId] = useState<string>(initialLeftId ?? pairs[0]?.id ?? "");

  useEffect(() => {
    if (initialLeftId) setSelectedId(initialLeftId);
  }, [initialLeftId]);

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
          <h3 className="text-sm font-semibold text-zinc-700 mb-1">No reports to compare</h3>
          <p className="text-xs text-zinc-400">Run a validation or upload reports to see them here.</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Selector */}
      <Card>
        <CardHeader>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">Comparison Explorer</h3>
            <p className="text-xs text-zinc-400 mt-0.5">Select a report to inspect its validation details</p>
          </div>
        </CardHeader>
        <div className="p-5">
          <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5 block">
            Report
          </label>
          <select
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
            className="w-full text-xs text-zinc-800 bg-white border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {pairs.map(p => (
              <option key={p.id} value={p.id}>{p.reportName}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* Detail panel */}
      {!pair ? (
        <div className="bg-zinc-100 rounded-xl border-2 border-dashed border-zinc-200 h-48 flex items-center justify-center text-zinc-400 text-xs">
          Select a report
        </div>
      ) : (
        <Card>
          <CardHeader>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-zinc-900 truncate">{pair.reportName}</div>
              <div className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">{pair.id}</div>
            </div>
            <StatusBadge status={pair.overallStatus} />
          </CardHeader>
          <div className="p-5 space-y-4">
            {/* Screenshots */}
            <div>
              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Screenshots</div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "Tableau", path: pair.tableauScreenshot, icon: "📊" },
                  { label: "Power BI", path: pair.powerBiScreenshot, icon: "⚡" },
                ].map(side => (
                  <div key={side.label}>
                    <div className="text-[9px] text-zinc-400 mb-1">{side.label}</div>
                    <div className="bg-zinc-100 rounded-lg h-28 flex items-center justify-center border border-zinc-200 overflow-hidden">
                      {side.path ? (
                        <img src={side.path} alt={side.label} className="w-full h-full object-cover" />
                      ) : (
                        <div className="text-2xl">{side.icon}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Layers */}
            <div>
              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Validation Layers</div>
              <div className="space-y-1.5">
                {[
                  { label: "L1 Visual",   status: pair.layer1Status },
                  { label: "L2 Semantic", status: pair.layer2Status },
                  { label: "L3 Data",     status: pair.layer3Status },
                ].map(l => (
                  <div key={l.label} className="flex items-center justify-between py-1 border-b border-zinc-50 last:border-0">
                    <span className="text-xs text-zinc-600">{l.label}</span>
                    <LayerDot status={l.status} label={l.status.toUpperCase()} />
                  </div>
                ))}
              </div>
            </div>

            {/* Differences */}
            <div>
              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                Differences ({pair.differences.length})
              </div>
              {pair.differences.length === 0 ? (
                <div className="text-xs text-zinc-400 italic">None detected</div>
              ) : (
                <div className="space-y-1.5">
                  {pair.differences.slice(0, 3).map((d, i) => (
                    <div key={i} className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                      <div className="text-[10px] font-bold text-red-700">{d.type}</div>
                      <div className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate">{d.detail}</div>
                    </div>
                  ))}
                  {pair.differences.length > 3 && (
                    <div className="text-[9px] text-zinc-400 text-center">+ {pair.differences.length - 3} more issues</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

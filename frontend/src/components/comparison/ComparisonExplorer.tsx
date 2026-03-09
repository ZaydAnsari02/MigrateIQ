"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusBadge, LayerDot } from "@/components/ui/Badge";
import type { ReportPair } from "@/types";

interface ComparisonExplorerProps {
  pairs: ReportPair[];
}

export function ComparisonExplorer({ pairs }: ComparisonExplorerProps) {
  const [leftId, setLeftId]   = useState<string>(pairs[0]?.id ?? "");
  const [rightId, setRightId] = useState<string>(pairs[1]?.id ?? "");

  const left  = pairs.find(p => p.id === leftId);
  const right = pairs.find(p => p.id === rightId);

  return (
    <div className="space-y-4">
      {/* Selector row */}
      <Card>
        <CardHeader>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">Comparison Explorer</h3>
            <p className="text-xs text-zinc-400 mt-0.5">Select two report pairs to compare side-by-side</p>
          </div>
        </CardHeader>
        <div className="p-5 grid grid-cols-2 gap-4">
          {[
            { label: "Left Report", value: leftId, onChange: setLeftId },
            { label: "Right Report", value: rightId, onChange: setRightId },
          ].map(sel => (
            <div key={sel.label}>
              <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5 block">
                {sel.label}
              </label>
              <select
                value={sel.value}
                onChange={e => sel.onChange(e.target.value)}
                className="w-full text-xs text-zinc-800 bg-white border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {pairs.map(p => (
                  <option key={p.id} value={p.id}>{p.reportName}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </Card>

      {/* Side-by-side */}
      {left && right && (
        <div className="grid grid-cols-2 gap-4">
          {[left, right].map((pair, idx) => (
            <Card key={pair.id}>
              <CardHeader>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-zinc-900 truncate">{pair.reportName}</div>
                  <div className="text-[10px] text-zinc-400 font-mono mt-0.5">{pair.id}</div>
                </div>
                <StatusBadge status={pair.overallStatus} />
              </CardHeader>
              <div className="p-5 space-y-4">
                {/* Screenshot */}
                <div>
                  <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">Screenshots</div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "Tableau", path: pair.tableauScreenshot, icon: "📊" },
                      { label: "Power BI", path: pair.powerBiScreenshot, icon: "⚡" },
                    ].map(side => (
                      <div key={side.label}>
                        <div className="text-[9px] text-zinc-400 mb-1">{side.label}</div>
                        <div className="bg-zinc-100 rounded-lg h-20 flex items-center justify-center border border-zinc-200 text-2xl">
                          {side.icon}
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
                      {pair.differences.map((d, i) => (
                        <div key={i} className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                          <div className="text-[10px] font-bold text-red-700">{d.type}</div>
                          <div className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate">{d.detail}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

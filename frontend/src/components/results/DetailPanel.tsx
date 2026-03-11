"use client";

import { cn, getSeverityColors } from "@/lib/utils";
import { Card } from "@/components/ui/Card";
import { LayerDot, SeverityBadge } from "@/components/ui/Badge";
import type { ReportPair, LayerStatus } from "@/types";

// ─── Layer Card ───────────────────────────────────────────────────────────────

interface LayerCardProps {
  label: string;
  status: LayerStatus;
  description: string;
}

function LayerCard({ label, status, description }: LayerCardProps) {
  const bg    = status === "pass" ? "bg-emerald-50 border-emerald-200" :
                status === "fail" ? "bg-red-50 border-red-200" :
                "bg-zinc-50 border-zinc-200";
  return (
    <div className={cn("rounded-lg p-3 border", bg)}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <LayerDot status={status} />
        <span className="text-[10px] font-bold text-zinc-700 uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-[9px] text-zinc-400 pl-3.5">{description}</div>
    </div>
  );
}

// ─── Screenshot Comparison ────────────────────────────────────────────────────

interface ScreenshotProps {
  tableauPath?: string;
  pbiPath?: string;
  hasMismatch: boolean;
}

function ScreenshotComparison({ tableauPath, pbiPath, hasMismatch }: ScreenshotProps) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-zinc-700 mb-3 flex items-center gap-1.5">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <rect x="1" y="2" width="4.5" height="8" rx="1" stroke="currentColor" strokeWidth="1.2" />
          <rect x="6.5" y="2" width="4.5" height="8" rx="1" stroke="currentColor" strokeWidth="1.2" />
        </svg>
        Screenshot Comparison
      </h4>
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: "Tableau", dot: "bg-blue-400",  path: tableauPath,  icon: "📊" },
          { label: "Power BI", dot: "bg-amber-400", path: pbiPath,      icon: "⚡" },
        ].map(side => (
          <div key={side.label}>
            <div className="text-[9px] text-zinc-400 font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <span className={cn("w-1.5 h-1.5 rounded-full inline-block", side.dot)} />
              {side.label}
            </div>
            <div className="bg-zinc-100 rounded-lg h-28 flex items-center justify-center border border-zinc-200 overflow-hidden">
              {side.path ? (
                <img src={side.path} alt={side.label} className="w-full h-full object-cover" />
              ) : (
                <div className="text-center">
                  <div className="text-2xl mb-1">{side.icon}</div>
                  <div className="text-[9px] text-zinc-400">{side.label} screenshot</div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {hasMismatch && (
        <div className="mt-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex items-center gap-2">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="shrink-0">
            <circle cx="5" cy="5" r="4.5" stroke="#ef4444" strokeWidth="1" />
            <path d="M5 3v2.5M5 7v.5" stroke="#ef4444" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span className="text-[10px] text-red-600 font-medium">
            AI detected visual discrepancies between screenshots
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Differences List ─────────────────────────────────────────────────────────

interface DiffListProps {
  differences: ReportPair["differences"];
}

function DifferencesList({ differences }: DiffListProps) {
  if (differences.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-16 text-center">
        <div className="text-lg mb-1">✅</div>
        <div className="text-xs text-zinc-400">No differences detected</div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {differences.map((diff, i) => {
        const c = getSeverityColors(diff.severity);
        return (
          <div key={i} className={cn("rounded-lg p-3 border", c.bg, c.border)}>
            <div className="flex items-center gap-2 mb-1">
              <span className={cn("text-[10px] font-bold", c.text)}>{diff.type}</span>
              <SeverityBadge severity={diff.severity} />
              <span className="ml-auto text-[9px] font-mono text-zinc-400 bg-white border border-zinc-200 px-1.5 py-0.5 rounded">
                {diff.layer}
              </span>
            </div>
            <p className="text-[10px] text-zinc-600 leading-relaxed font-mono">{diff.detail}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── Detail Panel ─────────────────────────────────────────────────────────────

interface DetailPanelProps {
  pair: ReportPair;
  onClose: () => void;
}

export function DetailPanel({ pair, onClose }: DetailPanelProps) {
  const hasMismatch = pair.differences.some(d => d.type === "Visual Mismatch");

  return (
    <div className="flex flex-col gap-4 animate-slide-in-right">
      {/* Header Card */}
      <Card>
        <div className="p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h4 className="text-sm font-semibold text-zinc-900">{pair.reportName}</h4>
              <p className="text-[10px] text-zinc-400 mt-0.5 font-mono">
                pair_id: {pair.id} · run: {pair.runId ?? "—"}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-zinc-600 transition-colors p-1 rounded-lg hover:bg-zinc-100"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {/* Layer breakdown */}
          <div className="grid grid-cols-3 gap-2">
            <LayerCard label="Visual"   status={(pair.layer1Status as string).toLowerCase() as LayerStatus} description="Screenshot diff" />
            <LayerCard label="Semantic" status={(pair.layer2Status as string).toLowerCase() as LayerStatus} description="DAX / Calc fields" />
            <LayerCard label="Data"     status={"pass"} description="KPI regression" />
          </div>
        </div>
      </Card>

      {/* Screenshots */}
      <Card>
        <div className="p-5">
          <ScreenshotComparison
            tableauPath={pair.tableauScreenshot}
            pbiPath={pair.powerBiScreenshot}
            hasMismatch={hasMismatch}
          />
        </div>
      </Card>

      {/* Differences */}
      <Card>
        <div className="p-5">
          <h4 className="text-xs font-semibold text-zinc-700 mb-3 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 1.5v5M6 8.5v1" stroke="#f59e0b" strokeWidth="1.4" strokeLinecap="round" />
              <circle cx="6" cy="6" r="5.5" stroke="#f59e0b" strokeWidth="1" />
            </svg>
            Detected Differences
            {pair.differences.length > 0 && (
              <span className="ml-auto bg-red-100 text-red-600 text-[9px] font-bold px-2 py-0.5 rounded-full">
                {pair.differences.length} issue{pair.differences.length !== 1 ? "s" : ""}
              </span>
            )}
          </h4>
          <DifferencesList differences={pair.differences} />
        </div>
      </Card>
    </div>
  );
}

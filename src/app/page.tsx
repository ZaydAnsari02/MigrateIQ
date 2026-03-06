"use client";

import { useState, useCallback } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { UploadSection } from "@/components/upload/UploadSection";
import { ResultsTable } from "@/components/results/ResultsTable";
import { DetailPanel } from "@/components/results/DetailPanel";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { ComparisonExplorer } from "@/components/comparison/ComparisonExplorer";
import { useSidebar, useUpload, useSelection } from "@/hooks";
import { computeStats } from "@/lib/utils";
import { MOCK_REPORT_PAIRS, MOCK_RUNS } from "@/constants";
import type { NavItem } from "@/types";
import { cn } from "@/lib/utils";

// ─── Page Title Map ───────────────────────────────────────────────────────────

const PAGE_TITLES: Record<NavItem, { title: string; sub: string }> = {
  dashboard: { title: "Validation Dashboard",    sub: "AI Telekom TD → Fabric · Overview" },
  upload:    { title: "Upload Reports",           sub: "Upload source files to trigger a new validation run" },
  runs:      { title: "Validation Runs",          sub: "History of all pipeline executions" },
  results:   { title: "Validation Results",       sub: "Per-report validation outcomes across all three layers" },
  explorer:  { title: "Comparison Explorer",      sub: "Side-by-side visual and metric comparison" },
  settings:  { title: "Settings",                 sub: "Project configuration and integration settings" },
};

// ─── Settings Placeholder ─────────────────────────────────────────────────────

function SettingsPage() {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-card p-8 text-center">
      <div className="text-4xl mb-3">⚙️</div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-1">Settings</h3>
      <p className="text-xs text-zinc-400">Project config, Tableau server credentials, and Power BI workspace settings will appear here.</p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [activeNav, setActiveNav] = useState<NavItem>("dashboard");
  const [startLoading, setStartLoading] = useState(false);

  const sidebar    = useSidebar(false);
  const upload     = useUpload();
  const selection  = useSelection<string>();

  const pairs      = MOCK_REPORT_PAIRS;
  const runs       = MOCK_RUNS;
  const stats      = computeStats(pairs);
  const selectedPair = pairs.find(p => p.id === selection.selected) ?? null;

  const page = PAGE_TITLES[activeNav];

  const handleStartValidation = useCallback(async () => {
    setStartLoading(true);
    await new Promise(r => setTimeout(r, 1800)); // simulate API call
    setStartLoading(false);
    upload.reset();
    setActiveNav("results");
  }, [upload]);

  return (
    <div className="flex h-screen overflow-hidden bg-[#F4F5F7]">
      <Sidebar
        activeNav={activeNav}
        onNav={setActiveNav}
        collapsed={sidebar.collapsed}
        onToggle={sidebar.toggle}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-screen-xl mx-auto px-6 py-6">

            {/* Page heading */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold text-zinc-900 tracking-tight">{page.title}</h2>
                <p className="text-xs text-zinc-400 mt-0.5">{page.sub}</p>
              </div>

              {activeNav === "dashboard" && (
                <div className="flex items-center gap-2">
                  <button className="px-3 py-2 text-xs font-medium text-zinc-600 border border-zinc-200 bg-white rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-1.5">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 1v6M3.5 4L6 1l2.5 3M1.5 9v1a.5.5 0 00.5.5h8a.5.5 0 00.5-.5V9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Export Report
                  </button>
                  <button
                    onClick={() => setActiveNav("upload")}
                    className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1.5 shadow-sm shadow-blue-200"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 2v8M2 6h8" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                    New Validation Run
                  </button>
                </div>
              )}
            </div>

            {/* Page content */}
            {activeNav === "dashboard" && (
              <DashboardOverview stats={stats} runs={runs} pairs={pairs} />
            )}

            {activeNav === "upload" && (
              <UploadSection
                files={upload.files}
                uploadCount={upload.uploadCount}
                isReady={upload.isReady}
                onFile={upload.setFile}
                onRemove={upload.removeFile}
                onStart={handleStartValidation}
                loading={startLoading}
              />
            )}

            {activeNav === "runs" && (
              <RunsTable runs={runs} />
            )}

            {activeNav === "results" && (
              <div className={cn("grid gap-5", selectedPair ? "grid-cols-5" : "grid-cols-1")}>
                <div className={selectedPair ? "col-span-3" : "col-span-1"}>
                  <ResultsTable
                    pairs={pairs}
                    selectedId={selection.selected}
                    onSelect={selection.toggle}
                  />
                </div>
                {selectedPair && (
                  <div className="col-span-2">
                    <DetailPanel pair={selectedPair} onClose={selection.deselect} />
                  </div>
                )}
              </div>
            )}

            {activeNav === "explorer" && (
              <ComparisonExplorer pairs={pairs} />
            )}

            {activeNav === "settings" && (
              <SettingsPage />
            )}

            {/* Footer */}
            <div className="flex items-center justify-between text-[10px] text-zinc-400 py-4 mt-2">
              <span>MigrateIQ v1.0.0 · Three-layer automated validation engine</span>
              <span className="font-mono">L1 Visual · L2 Semantic · L3 Data Regression</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

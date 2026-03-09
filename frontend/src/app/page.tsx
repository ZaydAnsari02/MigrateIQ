"use client";

import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { UploadSection } from "@/components/upload/UploadSection";
import { ResultsTable } from "@/components/results/ResultsTable";
import { DetailPanel } from "@/components/results/DetailPanel";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { ComparisonExplorer } from "@/components/comparison/ComparisonExplorer";
import { useSidebar, useUpload, useSelection } from "@/hooks";
import { computeStats, cn } from "@/lib/utils";
import { MOCK_RUNS } from "@/constants";
import { validationService, type BackendResult } from "@/services/validationService";
import type { NavItem, ReportPair, ValidationStatus, LayerStatus, Difference, DiffType } from "@/types";

// ─── Map backend result → frontend ReportPair ─────────────────────────────────
//
// The backend returns one flat result object per validation run.
// The frontend ResultsTable expects an array of ReportPair objects — one row
// per report. Until the backend supports multi-report runs we map the single
// result to one ReportPair row so every other component keeps working unchanged.

function backendResultToReportPair(result: BackendResult): ReportPair {
  const toStatus = (s: string): ValidationStatus =>
    (["PASS", "FAIL", "PENDING", "RUNNING"].includes(s) ? s : "PENDING") as ValidationStatus;

  const toLayer = (s: string): LayerStatus =>
    (["pass", "fail", "pending", "running"].includes(s.toLowerCase())
      ? s.toLowerCase()
      : "pending") as LayerStatus;

  // Collect differences from all three layers
  const differences: Difference[] = [];

  // Data layer (L3) - details is an array
  result.categories.data.details
    .filter(d => d.result === "FAIL")
    .forEach(d => {
      differences.push({
        type: "Data Regression",
        detail: d.failure_reasons?.join(", ") || `Table '${d.table_name}' validation failed`,
        severity: "high",
        layer: "L3",
      });
    });

  // Semantic model layer (L2) - details is an object with failure_reasons array
  if (result.categories.semantic_model.details.failure_reasons.length > 0) {
    result.categories.semantic_model.details.failure_reasons.forEach(reason => {
      differences.push({
        type: "DAX Mismatch",
        detail: reason,
        severity: "high",
        layer: "L2",
      });
    });
  }

  // Relationships layer (L1) - details is an object with failure_reasons array
  if (result.categories.relationships.details.failure_reasons.length > 0) {
    result.categories.relationships.details.failure_reasons.forEach(reason => {
      differences.push({
        type: "Missing Filter",
        detail: reason,
        severity: "high",
        layer: "L1",
      });
    });
  }

  return {
    id:               result.comparison_id,
    projectId:        "proj-001",
    runId:            result.comparison_id,
    reportName:       "Validation Run",
    overallStatus:    toStatus(result.overall_result),
    layer1Status:     toLayer(result.categories.relationships.result),
    layer2Status:     toLayer(result.categories.semantic_model.result),
    layer3Status:     toLayer(result.categories.data.result),
    differences,
    createdAt:        result.timestamp,
    updatedAt:        result.timestamp,
  };
}

// ─── Page Title Map ───────────────────────────────────────────────────────────

const PAGE_TITLES: Record<NavItem, { title: string; sub: string }> = {
  dashboard: { title: "Validation Dashboard",   sub: "AI Telekom TD → Fabric · Overview" },
  upload:    { title: "Upload Reports",          sub: "Upload source files to trigger a new validation run" },
  runs:      { title: "Validation Runs",         sub: "History of all pipeline executions" },
  results:   { title: "Validation Results",      sub: "Per-report validation outcomes across all three layers" },
  explorer:  { title: "Comparison Explorer",     sub: "Side-by-side visual and metric comparison" },
  settings:  { title: "Settings",                sub: "Project configuration and integration settings" },
};

// ─── Settings placeholder ─────────────────────────────────────────────────────

function SettingsPage() {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-card p-8 text-center">
      <div className="text-4xl mb-3">⚙️</div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-1">Settings</h3>
      <p className="text-xs text-zinc-400">
        Project config, Tableau server credentials, and Power BI workspace settings will appear here.
      </p>
    </div>
  );
}

// ─── Backend status banner ────────────────────────────────────────────────────

function BackendBanner({ online }: { online: boolean | null }) {
  if (online === null) return null;
  if (online) return null; // don't clutter the UI when all is fine
  return (
    <div className="mx-6 mt-3 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-4 py-2.5 text-xs flex items-center gap-2">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0">
        <circle cx="6" cy="6" r="5.5" stroke="currentColor" strokeWidth="1" />
        <path d="M6 3.5v3M6 8v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      <span>
        Backend not reachable at <code className="font-mono">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>.
        Start FastAPI with <code className="font-mono">uvicorn api:app --reload</code> then refresh.
      </span>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [activeNav,     setActiveNav]     = useState<NavItem>("dashboard");
  const [startLoading,  setStartLoading]  = useState(false);
  const [uploadPct,     setUploadPct]     = useState(0);
  const [apiError,      setApiError]      = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // All real results that have come back from the backend this session
  const [livePairs, setLivePairs] = useState<ReportPair[]>([] as ReportPair[]);

  const sidebar   = useSidebar(false);
  const upload    = useUpload();
  const selection = useSelection<string>();

  const stats        = computeStats(livePairs);
  const selectedPair = livePairs.find(p => p.id === selection.selected) ?? null;
  const page         = PAGE_TITLES[activeNav];

  // ── Health check on mount ────────────────────────────────────────────────

  useEffect(() => {
    validationService.healthCheck().then(setBackendOnline);
  }, []);

  // ── Start Validation ─────────────────────────────────────────────────────
  //
  // 1. POST /validate with the uploaded files
  // 2. Map the returned JSON to a ReportPair
  // 3. Append to livePairs and navigate to Results

  const handleStartValidation = useCallback(async () => {
    setApiError(null);
    setStartLoading(true);
    setUploadPct(0);

    try {
      const result = await validationService.startValidation(
        upload.files,
        setUploadPct,
      );
      const pair = backendResultToReportPair(result);
      setLivePairs(prev => [pair, ...prev]);
      upload.reset();
      setActiveNav("results");
      selection.select(pair.id); // auto-open the detail panel
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : String(err));
    } finally {
      setStartLoading(false);
      setUploadPct(0);
    }
  }, [upload, selection]);

  // ── Load a past result by run ID (called from RunsTable "View" action) ───

  const handleLoadRun = useCallback(async (runId: string) => {
    try {
      const result = await validationService.getResult(runId);
      const pair   = backendResultToReportPair(result);
      setLivePairs(prev => {
        const exists = prev.some(p => p.id === pair.id);
        return exists ? prev : [pair, ...prev];
      });
      setActiveNav("results");
      selection.select(pair.id);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : String(err));
    }
  }, [selection]);

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
        <BackendBanner online={backendOnline} />

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

            {/* API error banner */}
            {apiError && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-xs flex items-start gap-2">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="mt-0.5 shrink-0">
                  <circle cx="6" cy="6" r="5.5" stroke="currentColor" strokeWidth="1" />
                  <path d="M6 3.5v3M6 8v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
                <div>
                  <span className="font-semibold">Error: </span>{apiError}
                  <button onClick={() => setApiError(null)} className="ml-3 underline opacity-70 hover:opacity-100">Dismiss</button>
                </div>
              </div>
            )}

            {/* ── Dashboard ──────────────────────────────────────────────── */}
            {activeNav === "dashboard" && (
              <DashboardOverview stats={stats} runs={MOCK_RUNS} pairs={livePairs} />
            )}

            {/* ── Upload ─────────────────────────────────────────────────── */}
            {activeNav === "upload" && (
              <>
                <UploadSection
                  files={upload.files}
                  uploadCount={upload.uploadCount}
                  isReady={upload.isReady}
                  onFile={upload.setFile}
                  onRemove={upload.removeFile}
                  onStart={handleStartValidation}
                  loading={startLoading}
                />
                {/* Upload progress bar */}
                {startLoading && uploadPct > 0 && uploadPct < 100 && (
                  <div className="mt-4 bg-white border border-zinc-200 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-zinc-600 font-medium">Uploading files…</span>
                      <span className="text-xs font-mono text-blue-600">{uploadPct}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-blue-600 h-full rounded-full transition-all duration-300"
                        style={{ width: `${uploadPct}%` }}
                      />
                    </div>
                  </div>
                )}
                {startLoading && uploadPct === 100 && (
                  <div className="mt-4 bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
                    <svg className="animate-spin w-4 h-4 text-blue-600 shrink-0" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity=".25" />
                      <path d="M12 2a10 10 0 0110 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                    <span className="text-xs text-zinc-600">
                      Files uploaded — running validation engine (this may take 5–30 seconds)…
                    </span>
                  </div>
                )}
              </>
            )}

            {/* ── Runs ───────────────────────────────────────────────────── */}
            {activeNav === "runs" && (
              <RunsTable runs={MOCK_RUNS} onSelect={run => handleLoadRun(run.id)} />
            )}

            {/* ── Results ────────────────────────────────────────────────── */}
            {activeNav === "results" && (
              livePairs.length === 0 ? (
                <div className="bg-white rounded-xl border border-zinc-200 shadow-card p-12 text-center">
                  <div className="text-4xl mb-3">📭</div>
                  <h3 className="text-sm font-semibold text-zinc-700 mb-1">No results yet</h3>
                  <p className="text-xs text-zinc-400 mb-4">Upload a Tableau and Power BI file to run your first validation.</p>
                  <button
                    onClick={() => setActiveNav("upload")}
                    className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Go to Upload
                  </button>
                </div>
              ) : (
                <div className={cn("grid gap-5", selectedPair ? "grid-cols-5" : "grid-cols-1")}>
                  <div className={selectedPair ? "col-span-3" : "col-span-1"}>
                    <ResultsTable
                      pairs={livePairs}
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
              )
            )}

            {/* ── Explorer ───────────────────────────────────────────────── */}
            {activeNav === "explorer" && (
              <ComparisonExplorer pairs={livePairs} />
            )}

            {/* ── Settings ───────────────────────────────────────────────── */}
            {activeNav === "settings" && <SettingsPage />}

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

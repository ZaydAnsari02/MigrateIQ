// ─── Enums ────────────────────────────────────────────────────────────────────

export type ValidationStatus = "PASS" | "FAIL" | "PENDING" | "RUNNING" | "ERROR" | "REVIEW";
export type LayerStatus = "pass" | "fail" | "pending" | "running" | "review" | "skipped";
export type DiffSeverity = "high" | "medium" | "low";
export type DiffType = "Metric Mismatch" | "Missing Filter" | "Visual Mismatch" | "DAX Mismatch" | "Data Regression";

// ─── Core Entities ────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  clientName: string;
  description?: string;
  tableauServerUrl?: string;
  powerBiWorkspaceId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ValidationRun {
  id: string;
  projectId: string;
  triggeredBy: string;
  status: ValidationStatus;
  totalReports: number;
  passed: number;
  failed: number;
  errored: number;
  startedAt: string;
  completedAt?: string;
}

export interface ReportPair {
  id: string;
  projectId: string;
  runId?: string;
  reportName: string;
  // Tableau
  tableauWorkbook?: string;
  tableauViewName?: string;
  tableauViewId?: string;
  tableauScreenshot?: string;
  // Power BI
  powerBiReportName?: string;
  powerBiPageName?: string;
  powerBiReportId?: string;
  powerBiScreenshot?: string;
  // Results
  overallStatus: ValidationStatus;
  overallRisk?: "low" | "medium" | "high";
  layer1Status: LayerStatus;
  layer2Status: LayerStatus;
  layer3Status: LayerStatus;
  differences: Difference[];
  visualResult?: VisualResult;
  createdAt: string;
  updatedAt: string;
}

// ─── Layer Results ─────────────────────────────────────────────────────────────

export interface VisualResult {
  id: string;
  reportPairId: string;
  pixelSimilarityPct?: number;
  pixelDiffCount?: number;
  totalPixels?: number;
  hashDistance?: number;
  diffImagePath?: string;
  comparisonImagePath?: string;
  tableauAnnotatedPath?: string;
  powerbiAnnotatedPath?: string;
  comparedWidth?: number;
  comparedHeight?: number;
  gpt4oCalled: boolean;
  chartTypeMatch?: boolean;
  colorSchemeMatch?: boolean;
  layoutMatch?: boolean;
  axisLabelsMatch?: boolean;
  legendMatch?: boolean;
  titleMatch?: boolean;
  dataLabelsMatch?: boolean;
  aiSummary?: string;
  aiKeyDifferences?: string;
  aiRawResponse?: string;
  status: LayerStatus;
  passThresholdPct: number;
  createdAt: string;
}

export interface SemanticResult {
  id: string;
  reportPairId: string;
  totalFields: number;
  matchedFields: number;
  flaggedFields: number;
  status: LayerStatus;
  createdAt: string;
  calcFields: CalcField[];
}

export interface CalcField {
  id: string;
  semanticResultId: string;
  fieldName: string;
  tableauFormula?: string;
  daxFromPbix?: string;
  isEquivalent?: boolean;
  differences?: string;
  aiExplanation?: string;
  status: LayerStatus;
  createdAt: string;
}

export interface DataResult {
  id: string;
  reportPairId: string;
  tableauRowCount?: number;
  powerBiRowCount?: number;
  rowCountMatch?: boolean;
  totalKpisChecked: number;
  kpisMatched: number;
  kpisMismatched: number;
  status: LayerStatus;
  createdAt: string;
  kpiComparisons: KpiComparison[];
}

export interface KpiComparison {
  id: string;
  dataResultId: string;
  metricName: string;
  aggregationType?: string;
  tableauValue?: number;
  powerBiValue?: number;
  absoluteDiff?: number;
  percentageDiff?: number;
  isMatch?: boolean;
  tolerancePct?: number;
  createdAt: string;
}

// ─── Differences ──────────────────────────────────────────────────────────────

export interface Difference {
  type: DiffType;
  detail: string;
  severity: DiffSeverity;
  layer: "L1" | "L2" | "L3";
}

// ─── Upload ───────────────────────────────────────────────────────────────────

export interface UploadedFiles {
  twb?: File;
  pbix?: File;
  tableauScreenshots?: File;
  pbiScreenshots?: File;
}

export interface UploadZoneConfig {
  id: keyof UploadedFiles;
  label: string;
  ext: string;
  icon: string;
  accept: string;
  description: string;
}

// ─── UI State ─────────────────────────────────────────────────────────────────

export type NavItem =
  | "dashboard"
  | "upload"
  | "runs"
  | "results"
  | "explorer";

export interface DashboardStats {
  totalReports: number;
  passed: number;
  failed: number;
  pending: number;
  passRate: number;
}

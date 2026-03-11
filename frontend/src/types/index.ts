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
  gpt4oCalled: boolean;
  // Per-parameter match booleans from GPT-4o
  chartTypeMatch?: boolean;
  colorSchemeMatch?: boolean;
  layoutMatch?: boolean;
  axisLabelsMatch?: boolean;
  axisScaleMatch?: boolean;
  legendMatch?: boolean;
  titleMatch?: boolean;
  dataLabelsMatch?: boolean;
  textContentMatch?: boolean;
  aiSummary?: string;
  aiKeyDifferences?: string | string[];
  aiRawResponse?: string;
  gpt4oRiskLevel?: "low" | "medium" | "high";
  status: LayerStatus;
  createdAt: string;
  parametersUsed?: VisualComparisonParameters;
  parameterResults?: VisualParameterResults;
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

// ─── Visual Comparison Parameters ─────────────────────────────────────────────

/** API-facing: True = validate this parameter (backend receives enabled map) */
export interface VisualComparisonParameters {
  chart_type:   boolean;
  color:        boolean;
  legend:       boolean;
  axis_labels:  boolean;
  axis_scale:   boolean;
  title:        boolean;
  data_labels:  boolean;
  layout:       boolean;
  text_content: boolean;
  text_case:    boolean;
}

/** All parameters enabled (strict mode) */
export const DEFAULT_VISUAL_PARAMS: VisualComparisonParameters = {
  chart_type:   true,
  color:        true,
  legend:       true,
  axis_labels:  true,
  axis_scale:   true,
  title:        true,
  data_labels:  true,
  layout:       true,
  text_content: true,
  text_case:    true,
};

/** UI-facing exclusion map: True = this parameter is EXCLUDED / ignored */
export type ExcludedParameters = VisualComparisonParameters;

/** Default: nothing excluded (= full strict validation) */
export const DEFAULT_EXCLUDED_PARAMS: ExcludedParameters = {
  chart_type:   false,
  color:        false,
  legend:       false,
  axis_labels:  false,
  axis_scale:   false,
  title:        false,
  data_labels:  false,
  layout:       false,
  text_content: false,
  text_case:    false,
};

/** Convert exclusion map → enabled map for the backend */
export function excludedToEnabled(ex: ExcludedParameters): VisualComparisonParameters {
  return {
    chart_type:   !ex.chart_type,
    color:        !ex.color,
    legend:       !ex.legend,
    axis_labels:  !ex.axis_labels,
    axis_scale:   !ex.axis_scale,
    title:        !ex.title,
    data_labels:  !ex.data_labels,
    layout:       !ex.layout,
    text_content: !ex.text_content,
    text_case:    !ex.text_case,
  };
}

export type ParameterStatus = "pass" | "fail" | "ignored" | "skipped";

export interface VisualParameterResults {
  chart_type:   ParameterStatus;
  color:        ParameterStatus;
  legend:       ParameterStatus;
  axis_labels:  ParameterStatus;
  axis_scale:   ParameterStatus;
  title:        ParameterStatus;
  data_labels:  ParameterStatus;
  layout:       ParameterStatus;
  text_content: ParameterStatus;
}

// ─── Card Visibility ──────────────────────────────────────────────────────────

export interface CardVisibility {
  visualBreakdown: boolean;   // Parameter results table after re-run
  regressionLog:   boolean;   // All-layers regression log
}

export const DEFAULT_CARD_VISIBILITY: CardVisibility = {
  visualBreakdown: true,
  regressionLog:   true,
};

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

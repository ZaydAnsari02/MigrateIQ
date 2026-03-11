// import type {
//   NavItem,
//   UploadZoneConfig,
//   ReportPair,
//   ValidationRun,
//   Project,
// } from "@/types";

// // ─── Navigation ───────────────────────────────────────────────────────────────

// export const NAV_ITEMS: { id: NavItem; label: string; group?: string }[] = [
//   { id: "dashboard",  label: "Dashboard" },
//   { id: "upload",     label: "Upload Reports" },
//   { id: "runs",       label: "Validation Runs" },
//   { id: "results",    label: "Results" },
//   { id: "explorer",   label: "Comparison Explorer" },
//   { id: "settings",   label: "Settings" },
// ];

// // ─── Upload Zones ─────────────────────────────────────────────────────────────

// export const UPLOAD_ZONES: UploadZoneConfig[] = [
//   {
//     id: "twb",
//     label: "Tableau Workbook",
//     ext: ".twb / .twbx",
//     icon: "tableau",
//     accept: ".twb,.twbx",
//     description: "Source Tableau workbook file",
//   },
//   {
//     id: "pbix",
//     label: "Power BI File",
//     ext: ".pbix",
//     icon: "powerbi",
//     accept: ".pbix",
//     description: "Target Power BI report file",
//   },
//   {
//     id: "tableauScreenshots",
//     label: "Tableau Screenshots",
//     ext: ".zip / folder",
//     icon: "screenshots",
//     accept: ".zip,image/*",
//     description: "Captured Tableau view screenshots",
//   },
//   {
//     id: "pbiScreenshots",
//     label: "Power BI Screenshots",
//     ext: ".zip / folder",
//     icon: "screenshots",
//     accept: ".zip,image/*",
//     description: "Captured Power BI page screenshots",
//   },
// ];

// // ─── Mock Data ────────────────────────────────────────────────────────────────

// export const MOCK_PROJECT: Project = {
//   id: "proj-001",
//   name: "AI Telekom TD → Fabric",
//   clientName: "AI Telekom",
//   description: "Teradata-to-Microsoft Fabric comprehensive migration",
//   tableauServerUrl: "https://tableau.aitelekom.com",
//   powerBiWorkspaceId: "ws-9f3a2b1c",
//   createdAt: "2026-02-01T09:00:00Z",
//   updatedAt: "2026-03-06T12:49:00Z",
// };

// export const MOCK_RUNS: ValidationRun[] = [
//   {
//     id: "run-004",
//     projectId: "proj-001",
//     triggeredBy: "John Mitchell",
//     status: "PASS",
//     totalReports: 6,
//     passed: 4,
//     failed: 2,
//     errored: 0,
//     startedAt: "2026-03-06T12:30:00Z",
//     completedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "run-003",
//     projectId: "proj-001",
//     triggeredBy: "GitHub Actions",
//     status: "FAIL",
//     totalReports: 6,
//     passed: 3,
//     failed: 3,
//     errored: 0,
//     startedAt: "2026-03-05T08:00:00Z",
//     completedAt: "2026-03-05T08:22:00Z",
//   },
//   {
//     id: "run-002",
//     projectId: "proj-001",
//     triggeredBy: "Prutha Annadate",
//     status: "PASS",
//     totalReports: 5,
//     passed: 5,
//     failed: 0,
//     errored: 0,
//     startedAt: "2026-03-03T14:10:00Z",
//     completedAt: "2026-03-03T14:31:00Z",
//   },
// ];

// export const MOCK_REPORT_PAIRS: ReportPair[] = [
//   {
//     id: "rp-001",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Sales Overview Dashboard",
//     tableauWorkbook: "Sales_Overview.twbx",
//     tableauViewName: "Sales Overview",
//     tableauScreenshot: "/screenshots/tableau/sales_overview.png",
//     powerBiReportName: "Sales Overview",
//     powerBiPageName: "Page 1",
//     powerBiScreenshot: "/screenshots/pbi/sales_overview.png",
//     overallStatus: "PASS",
//     layer1Status: "pass",
//     layer2Status: "pass",
//     layer3Status: "pass",
//     differences: [],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "rp-002",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Regional Revenue Breakdown",
//     tableauWorkbook: "Revenue.twbx",
//     tableauViewName: "Regional Revenue",
//     tableauScreenshot: "/screenshots/tableau/regional_revenue.png",
//     powerBiReportName: "Regional Revenue",
//     powerBiPageName: "Revenue Page",
//     powerBiScreenshot: "/screenshots/pbi/regional_revenue.png",
//     overallStatus: "FAIL",
//     layer1Status: "pass",
//     layer2Status: "fail",
//     layer3Status: "fail",
//     differences: [
//       {
//         type: "Metric Mismatch",
//         detail: "Total Revenue: Tableau=€4.2M vs PBI=€4.1M (Δ 2.3%)",
//         severity: "high",
//         layer: "L3",
//       },
//       {
//         type: "Missing Filter",
//         detail: "Region filter 'EMEA' not found in Power BI report",
//         severity: "medium",
//         layer: "L1",
//       },
//     ],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "rp-003",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Customer Churn Analysis",
//     tableauWorkbook: "Churn.twbx",
//     tableauViewName: "Churn Analysis",
//     overallStatus: "PENDING",
//     layer1Status: "pending",
//     layer2Status: "pending",
//     layer3Status: "pending",
//     differences: [],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "rp-004",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Product Performance YTD",
//     tableauWorkbook: "Products.twbx",
//     tableauViewName: "Product YTD",
//     tableauScreenshot: "/screenshots/tableau/product_ytd.png",
//     powerBiReportName: "Product Performance",
//     powerBiPageName: "YTD View",
//     powerBiScreenshot: "/screenshots/pbi/product_ytd.png",
//     overallStatus: "PASS",
//     layer1Status: "pass",
//     layer2Status: "pass",
//     layer3Status: "pass",
//     differences: [],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "rp-005",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Marketing Attribution",
//     tableauWorkbook: "Marketing.twbx",
//     tableauViewName: "Attribution Model",
//     tableauScreenshot: "/screenshots/tableau/marketing.png",
//     powerBiReportName: "Marketing Attribution",
//     powerBiPageName: "Attribution",
//     powerBiScreenshot: "/screenshots/pbi/marketing.png",
//     overallStatus: "FAIL",
//     layer1Status: "fail",
//     layer2Status: "pass",
//     layer3Status: "fail",
//     differences: [
//       {
//         type: "Visual Mismatch",
//         detail: "Pie chart in Tableau rendered as bar chart in Power BI",
//         severity: "high",
//         layer: "L1",
//       },
//       {
//         type: "DAX Mismatch",
//         detail: "CPC: Tableau uses SUM/COUNT, PBI uses AVERAGEX — semantically divergent",
//         severity: "high",
//         layer: "L2",
//       },
//       {
//         type: "Missing Filter",
//         detail: "Date range slicer missing from Power BI 'Attribution' page",
//         severity: "medium",
//         layer: "L1",
//       },
//     ],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
//   {
//     id: "rp-006",
//     projectId: "proj-001",
//     runId: "run-004",
//     reportName: "Inventory Turnover Report",
//     tableauWorkbook: "Inventory.twbx",
//     tableauViewName: "Inventory Turnover",
//     tableauScreenshot: "/screenshots/tableau/inventory.png",
//     powerBiReportName: "Inventory Turnover",
//     powerBiPageName: "Turnover",
//     powerBiScreenshot: "/screenshots/pbi/inventory.png",
//     overallStatus: "PASS",
//     layer1Status: "pass",
//     layer2Status: "pass",
//     layer3Status: "pass",
//     differences: [],
//     createdAt: "2026-03-06T12:49:00Z",
//     updatedAt: "2026-03-06T12:49:00Z",
//   },
// ];

import type {
  NavItem,
  UploadZoneConfig,
} from "@/types";

// ─── API CONFIG ─────────────────────────────────────────────────────────────

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";


// ─── Navigation ─────────────────────────────────────────────────────────────

export const NAV_ITEMS: { id: NavItem; label: string; group?: string }[] = [
  { id: "dashboard",  label: "Dashboard" },
  { id: "upload",     label: "Upload Reports" },
  { id: "runs",       label: "Validation Runs" },
  { id: "results",    label: "Results" },
  { id: "explorer",   label: "Comparison Explorer" },
];


// ─── Upload Zones ───────────────────────────────────────────────────────────

export const UPLOAD_ZONES: UploadZoneConfig[] = [
  {
    id: "twb",
    label: "Tableau Workbook",
    ext: ".twb / .twbx",
    icon: "tableau",
    accept: ".twb,.twbx",
    description: "Source Tableau workbook file",
  },
  {
    id: "pbix",
    label: "Power BI File",
    ext: ".pbix",
    icon: "powerbi",
    accept: ".pbix",
    description: "Target Power BI report file",
  },
  {
    id: "pbit",
    label: "Power BI Template",
    ext: ".pbit",
    icon: "powerbi",
    accept: ".pbit",
    description: "Optional — enables L3 measure validation",
  },
  {
    id: "tableauScreenshots",
    label: "Tableau Screenshots",
    ext: ".zip / folder",
    icon: "tableau_screenshots",
    accept: ".zip,image/*",
    description: "Captured Tableau view screenshots",
  },
  {
    id: "pbiScreenshots",
    label: "Power BI Screenshots",
    ext: ".zip / folder",
    icon: "powerbi_screenshots",
    accept: ".zip,image/*",
    description: "Captured Power BI page screenshots",
  },
];


// ─── Session Helpers ────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function getCurrentUser(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("username");
}

export function logout() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  window.location.href = "/login";
}
/**
 * services/validationService.ts
 *
 * Abstracts all HTTP calls to the MigrateIQ FastAPI backend.
 * In development, returns mock data. Swap BASE_URL for production.
 */

import axios from "axios";
import type {
  Project,
  ValidationRun,
  ReportPair,
  VisualResult,
  SemanticResult,
  DataResult,
  UploadedFiles,
} from "@/types";
import {
  MOCK_PROJECT,
  MOCK_RUNS,
  MOCK_REPORT_PAIRS,
} from "@/constants";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ─── Mock delay helper ────────────────────────────────────────────────────────
const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

// ─── Projects ─────────────────────────────────────────────────────────────────

export const projectService = {
  async getProject(projectId: string): Promise<Project> {
    await delay(200);
    return MOCK_PROJECT;
    // Real: return (await api.get<Project>(`/projects/${projectId}`)).data;
  },

  async listProjects(): Promise<Project[]> {
    await delay(200);
    return [MOCK_PROJECT];
    // Real: return (await api.get<Project[]>("/projects")).data;
  },

  async createProject(payload: Partial<Project>): Promise<Project> {
    await delay(400);
    return { ...MOCK_PROJECT, ...payload, id: `proj-${Date.now()}` };
    // Real: return (await api.post<Project>("/projects", payload)).data;
  },
};

// ─── Validation Runs ──────────────────────────────────────────────────────────

export const runService = {
  async listRuns(projectId: string): Promise<ValidationRun[]> {
    await delay(300);
    return MOCK_RUNS.filter(r => r.projectId === projectId);
    // Real: return (await api.get<ValidationRun[]>(`/projects/${projectId}/runs`)).data;
  },

  async getRun(runId: string): Promise<ValidationRun> {
    await delay(200);
    const run = MOCK_RUNS.find(r => r.id === runId);
    if (!run) throw new Error(`Run ${runId} not found`);
    return run;
    // Real: return (await api.get<ValidationRun>(`/runs/${runId}`)).data;
  },

  async triggerRun(projectId: string, files: UploadedFiles): Promise<ValidationRun> {
    await delay(600);
    const newRun: ValidationRun = {
      id: `run-${Date.now()}`,
      projectId,
      triggeredBy: "Current User",
      status: "RUNNING",
      totalReports: 0,
      passed: 0,
      failed: 0,
      errored: 0,
      startedAt: new Date().toISOString(),
    };
    return newRun;
    // Real:
    // const form = new FormData();
    // if (files.twb)               form.append("twb", files.twb);
    // if (files.pbix)              form.append("pbix", files.pbix);
    // if (files.tableauScreenshots) form.append("tableau_screenshots", files.tableauScreenshots);
    // if (files.pbiScreenshots)    form.append("pbi_screenshots", files.pbiScreenshots);
    // return (await api.post<ValidationRun>(`/projects/${projectId}/runs`, form, {
    //   headers: { "Content-Type": "multipart/form-data" },
    // })).data;
  },
};

// ─── Report Pairs ─────────────────────────────────────────────────────────────

export const reportService = {
  async listPairs(runId: string): Promise<ReportPair[]> {
    await delay(250);
    return MOCK_REPORT_PAIRS.filter(p => p.runId === runId);
    // Real: return (await api.get<ReportPair[]>(`/runs/${runId}/pairs`)).data;
  },

  async getPair(pairId: string): Promise<ReportPair> {
    await delay(200);
    const pair = MOCK_REPORT_PAIRS.find(p => p.id === pairId);
    if (!pair) throw new Error(`Pair ${pairId} not found`);
    return pair;
    // Real: return (await api.get<ReportPair>(`/pairs/${pairId}`)).data;
  },

  async getAllPairs(projectId: string): Promise<ReportPair[]> {
    await delay(250);
    return MOCK_REPORT_PAIRS.filter(p => p.projectId === projectId);
  },
};

// ─── Layer Results ─────────────────────────────────────────────────────────────

export const layerService = {
  async getVisualResult(pairId: string): Promise<VisualResult | null> {
    await delay(200);
    // Real: return (await api.get<VisualResult>(`/pairs/${pairId}/visual`)).data;
    return null;
  },

  async getSemanticResult(pairId: string): Promise<SemanticResult | null> {
    await delay(200);
    // Real: return (await api.get<SemanticResult>(`/pairs/${pairId}/semantic`)).data;
    return null;
  },

  async getDataResult(pairId: string): Promise<DataResult | null> {
    await delay(200);
    // Real: return (await api.get<DataResult>(`/pairs/${pairId}/data`)).data;
    return null;
  },
};

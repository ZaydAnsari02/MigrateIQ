/**
 * src/services/validationService.ts
 *
 * All HTTP calls to the MigrateIQ FastAPI backend.
 *
 * Base URL is read from NEXT_PUBLIC_API_URL (set in .env.local).
 * Falls back to http://localhost:8000 for local development.
 */

import axios, { AxiosError } from "axios";
import type { UploadedFiles, VisualComparisonParameters } from "@/types";

// ─── Axios instance ───────────────────────────────────────────────────────────

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,          // 2 min — parsing large files can be slow
});

// Attach the session token on every request so the backend can record
// which user triggered each validation run.
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token    = localStorage.getItem("migrateiq_token");
    const username = localStorage.getItem("migrateiq_user");
    if (token)    config.headers["x-token"]    = token;
    if (username) config.headers["x-username"] = username;
  }
  return config;
});

// On 401, clear the stored session and redirect to login.
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("migrateiq_token");
      localStorage.removeItem("migrateiq_user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ─── Types returned by the FastAPI backend ────────────────────────────────────
// These mirror the JSON structure produced by output/result_builder.py

export interface BackendResult {
  comparison_id: string;
  timestamp: string;
  inputs: {
    twbx_file: string;
    pbix_file: string;
  };
  overall_result: "PASS" | "FAIL";
  categories: {
    data: {
      result: "PASS" | "FAIL";
      tolerance_threshold_pct: number;
      tables_compared: number;
      details: BackendCheckDetail[];
    };
    semantic_model: {
      result: "PASS" | "FAIL";
      measures_compared: number;
      details: {
        measures_matched: any[];
        measures_missing_in_pbix: any[];
        measures_missing_in_twbx: any[];
        expression_mismatches: any[];
        data_type_mismatches: any[];
        failure_reasons: string[];
      };
      column_value_analysis?: {
        result: "PASS" | "FAIL";
        tables_analyzed: number;
        tables_with_mismatches: number;
        details: Array<{
          table_name: string;
          pbix_name?: string;
          result: "PASS" | "FAIL" | "SKIPPED";
          columns_analyzed: number;
          mismatched_columns: number;
          failure_reasons: string[];
          column_analyses: Array<{
            column_name: string;
            result: "PASS" | "FAIL";
            overlap_pct: number;
            mismatch_pct: number;
            twbx_unique_count: number;
            pbix_unique_count: number;
            only_in_twbx: string[];
            only_in_pbix: string[];
            only_in_twbx_count: number;
            only_in_pbix_count: number;
            twbx_preview_truncated: boolean;
            pbix_preview_truncated: boolean;
            numeric_stats?: {
              twbx: { mean: number | null; std: number | null; min: number | null; max: number | null };
              pbix: { mean: number | null; std: number | null; min: number | null; max: number | null };
              mean_diff: number | null;
              mean_diff_pct: number | null;
            };
          }>;
        }>;
      };
    };
    relationships: {
      result: "PASS" | "FAIL";
      relationships_compared: number;
      details: {
        relationships_matched: any[];
        relationships_missing_in_pbix: any[];
        relationships_missing_in_twbx: any[];
        cardinality_mismatches: any[];
        failure_reasons: string[];
      };
    };
    visual?: {
      result: "PASS" | "FAIL" | "REVIEW" | "PENDING";
      metrics?: {
        similarity: number | null;
        gpt4o_called: boolean;
        risk_level: string | null;
      };
      images?: {
        tableau_annotated: string | null;
        powerbi_annotated: string | null;
        comparison: string | null;
        diff: string | null;
      };
      ai_analysis?: {
        summary: string | null;
        key_differences: string[];
        recommendation: string | null;
      };
    };
  };
  summary: {
    total_failures: number;
    failure_categories: any[];
    notes: string;
  };
}

export interface BackendCheckDetail {
  table_name: string;
  result: "PASS" | "FAIL" | "WARNING";
  match_method?: string;
  row_count_twbx?: number | null;
  row_count_pbix?: number | null;
  row_count_diff_pct?: number | null;
  column_count_twbx?: number | null;
  column_count_pbix?: number | null;
  columns_matched?: string[];
  columns_missing_in_pbix?: string[];
  columns_missing_in_twbx?: string[];
  column_type_mismatches?: Array<{
    column: string;
    twbx_type: string;
    pbix_type: string;
    twbx_canonical: string;
    pbix_canonical: string;
  }>;
  failure_reasons: string[];
}

export interface ResultListResponse {
  run_ids: string[];
  count: number;
}

// ─── Error helper ─────────────────────────────────────────────────────────────

function extractError(err: unknown): string {
  if (err instanceof AxiosError) {
    return err.response?.data?.detail ?? err.message;
  }
  return String(err);
}

// ─── Validation Service ───────────────────────────────────────────────────────

export const validationService = {
  /**
   * POST /validate
   *
   * Sends the .twbx and .pbix files to the backend.
   * The backend runs compare_reports.py and returns the full JSON result
   * synchronously (the response arrives once the script finishes).
   *
   * @param files   The UploadedFiles object from the useUpload hook
   * @param onProgress  Optional callback — receives 0–100 upload progress
   */
  async startValidation(
    files: UploadedFiles,
    onProgress?: (pct: number) => void,
    visualParameters?: VisualComparisonParameters | null,
  ): Promise<BackendResult> {
    if (!files.twb || !files.pbix) {
      throw new Error("Both a Tableau workbook (.twbx) and a Power BI file (.pbix) are required.");
    }

    const form = new FormData();
    form.append("twbx", files.twb);
    form.append("pbix", files.pbix);

    // Attach screenshots if provided.
    // The backend handles both single images and .zip files.
    if (files.tableauScreenshots) form.append("tableau_screenshot", files.tableauScreenshots);
    if (files.pbiScreenshots) form.append("pbi_screenshot", files.pbiScreenshots);

    // Attach visual comparison parameters if any exclusions are set
    if (visualParameters) form.append("visual_parameters", JSON.stringify(visualParameters));

    try {
      const { data } = await api.post<BackendResult>("/validate", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (evt) => {
          if (onProgress && evt.total) {
            onProgress(Math.round((evt.loaded / evt.total) * 100));
          }
        },
      });
      return data;
    } catch (err) {
      throw new Error(`Validation failed: ${extractError(err)}`);
    }
  },

  /**
   * GET /results/{run_id}
   *
   * Fetches a previously-generated result by run ID.
   * Useful for history or after a page reload.
   */
  async getResult(runId: string): Promise<BackendResult> {
    try {
      const { data } = await api.get<BackendResult>(`/results/${runId}`);
      return data;
    } catch (err) {
      throw new Error(`Could not load result ${runId}: ${extractError(err)}`);
    }
  },

  /**
   * GET /results
   *
   * Returns a list of all stored run IDs.
   */
  async listResults(): Promise<ResultListResponse> {
    try {
      const { data } = await api.get<ResultListResponse>("/results");
      return data;
    } catch (err) {
      throw new Error(`Could not list results: ${extractError(err)}`);
    }
  },

  /**
   * GET /runs
   */
  async listRuns(): Promise<any[]> {
    try {
      const { data } = await api.get<any[]>("/runs");
      return data;
    } catch (err) {
      throw new Error(`Could not list runs: ${extractError(err)}`);
    }
  },

  async listReportPairs(): Promise<any[]> {
    try {
      const { data } = await api.get<any[]>("/report-pairs");
      return data;
    } catch (err) {
      throw new Error(`Could not list report pairs: ${extractError(err)}`);
    }
  },

  /**
   * GET /health
   *
   * Ping the backend to confirm it is reachable.
   */
  async healthCheck(): Promise<boolean> {
    try {
      await api.get("/health");
      return true;
    } catch {
      return false;
    }
  },
};
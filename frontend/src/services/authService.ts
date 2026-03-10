/**
 * src/services/authService.ts
 *
 * Authentication calls to the MigrateIQ FastAPI backend.
 */

import axios, { AxiosError } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL, timeout: 10_000 });

export interface LoginResponse {
  token: string;
  username: string;
}

function extractError(err: unknown): string {
  if (err instanceof AxiosError) return err.response?.data?.detail ?? err.message;
  return String(err);
}

export const authService = {
  /** POST /login  — sends JSON body { username, password } */
  async login(username: string, password: string): Promise<LoginResponse> {
    try {
      const { data } = await api.post<LoginResponse>("/login", { username, password });
      return data;
    } catch (err) {
      throw new Error(extractError(err));
    }
  },
};

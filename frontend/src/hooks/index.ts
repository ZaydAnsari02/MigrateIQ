import { useState, useCallback, useEffect } from "react";
import type { UploadedFiles } from "@/types";
import { formatBytes } from "@/lib/utils";

// ─── useUpload ────────────────────────────────────────────────────────────────

export function useUpload() {
  const [files, setFiles] = useState<UploadedFiles>({});

  const setFile = useCallback((id: keyof UploadedFiles, file: File) => {
    setFiles(prev => ({ ...prev, [id]: file }));
  }, []);

  const removeFile = useCallback((id: keyof UploadedFiles) => {
    setFiles(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  const reset = useCallback(() => setFiles({}), []);

  const uploadCount = Object.keys(files).length;
  const isReady = uploadCount >= 2; // at minimum twb + pbix

  const fileSummary = Object.entries(files).map(([id, file]) => ({
    id,
    name: file.name,
    size: formatBytes(file.size),
  }));

  return { files, setFile, removeFile, reset, uploadCount, isReady, fileSummary };
}

// ─── useSidebar ───────────────────────────────────────────────────────────────

export function useSidebar(defaultCollapsed = false) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const toggle = useCallback(() => setCollapsed(v => !v), []);
  return { collapsed, toggle };
}

// ─── useSelection ─────────────────────────────────────────────────────────────

export function useSelection<T = string>() {
  const [selected, setSelected] = useState<T | null>(null);
  const select   = useCallback((id: T) => setSelected(id), []);
  const deselect = useCallback(() => setSelected(null), []);
  const toggle   = useCallback((id: T) => setSelected(prev => prev === id ? null : id), []);
  return { selected, select, deselect, toggle };
}

// ─── useAuth ──────────────────────────────────────────────────────────────────

const TOKEN_KEY = "migrateiq_token";
const USER_KEY  = "migrateiq_user";

export function useAuth() {
  const [token, setToken]           = useState<string | null>(null);
  const [username, setUsername]     = useState<string | null>(null);
  // `initialized` becomes true once we've read localStorage — guards must
  // wait for this before redirecting, otherwise they act on the null default.
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem(TOKEN_KEY));
    setUsername(localStorage.getItem(USER_KEY));
    setInitialized(true);
  }, []);

  const login = useCallback((t: string, u: string) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, u);
    setToken(t);
    setUsername(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUsername(null);
  }, []);

  return { token, username, login, logout, isAuthenticated: !!token, initialized };
}

// ─── useAsync ─────────────────────────────────────────────────────────────────

export function useAsync<T>(fn: () => Promise<T>) {
  const [data, setData]       = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, [fn]);

  return { data, loading, error, execute };
}

import { useState, useCallback } from "react";
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

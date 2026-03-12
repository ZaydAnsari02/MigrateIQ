"use client";

import { useRef, useState } from "react";
import { cn, formatBytes } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { UPLOAD_ZONES } from "@/constants";
import type { UploadedFiles, ExcludedParameters } from "@/types";
import { DEFAULT_EXCLUDED_PARAMS } from "@/types";

const EXCLUSION_OPTIONS: { key: keyof ExcludedParameters; label: string }[] = [
  { key: "color",        label: "Ignore Color Differences" },
  { key: "legend",       label: "Ignore Legend Differences" },
  { key: "axis_labels",  label: "Ignore Axis Labels" },
  { key: "axis_scale",   label: "Ignore Axis Scale" },
  { key: "title",        label: "Ignore Chart Title" },
  { key: "data_labels",  label: "Ignore Data Labels" },
  { key: "layout",       label: "Ignore Layout Differences" },
  { key: "text_content", label: "Ignore Text Content" },
  { key: "text_case",    label: "Ignore Text Case Differences" },
];

// ─── Zone Icons ───────────────────────────────────────────────────────────────

function TableauLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect x="14" y="2" width="4" height="28" rx="1.5" fill="#4E79A7"/>
      <rect x="2" y="14" width="28" height="4" rx="1.5" fill="#4E79A7"/>
      <rect x="10" y="6" width="3" height="20" rx="1" fill="#E15759"/>
      <rect x="6" y="10" width="20" height="3" rx="1" fill="#E15759"/>
      <rect x="13" y="13" width="6" height="6" rx="1" fill="#59A14F"/>
    </svg>
  );
}

function PowerBILogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect x="2"  y="18" width="6"  height="12" rx="1.5" fill="#F2C811" opacity="0.55"/>
      <rect x="10" y="10" width="6"  height="20" rx="1.5" fill="#F2C811" opacity="0.75"/>
      <rect x="18" y="4"  width="6"  height="26" rx="1.5" fill="#F2C811"/>
      <rect x="26" y="14" width="4"  height="16" rx="1.5" fill="#F2C811" opacity="0.4"/>
    </svg>
  );
}

function ZoneIcon({ type, uploaded }: { type: string; uploaded: boolean }) {
  if (uploaded) {
    return (
      <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M4 9l3.5 3.5L14 6" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }
  if (type === "tableau" || type === "tableau_screenshots") {
    return (
      <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center">
        <TableauLogo size={22} />
      </div>
    );
  }
  if (type === "powerbi" || type === "powerbi_screenshots" || type === "pbit") {
    return (
      <div className="w-9 h-9 rounded-xl bg-yellow-50 border border-yellow-100 flex items-center justify-center">
        <PowerBILogo size={22} />
      </div>
    );
  }
  return (
    <div className="w-9 h-9 rounded-xl bg-zinc-100 flex items-center justify-center text-xl">
      📁
    </div>
  );
}

// ─── Single Drop Zone ─────────────────────────────────────────────────────────

interface DropZoneProps {
  zoneId: keyof UploadedFiles;
  label: string;
  ext: string;
  icon: string;
  accept: string;
  description: string;
  optional?: boolean;
  file?: File;
  onFile: (id: keyof UploadedFiles, file: File) => void;
  onRemove: (id: keyof UploadedFiles) => void;
}

function DropZone({ zoneId, label, ext, icon, accept, description, optional, file, onFile, onRemove }: DropZoneProps) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(zoneId, f);
  };

  return (
    <div
      className={cn(
        "relative border-2 border-dashed rounded-xl p-4 flex flex-col items-center gap-2 cursor-pointer transition-all duration-200",
        drag      ? "border-blue-400 bg-blue-50/60 scale-[1.01]" :
        file      ? "border-emerald-300 bg-emerald-50/40 cursor-default" :
        optional  ? "border-zinc-200 border-dashed bg-zinc-50/50 hover:border-zinc-300 hover:bg-white" :
                    "border-zinc-200 bg-zinc-50 hover:border-zinc-300 hover:bg-white"
      )}
      onClick={() => !file && ref.current?.click()}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
    >
      <input
        ref={ref}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(zoneId, f); }}
      />

      {/* Optional badge */}
      {optional && !file && (
        <span className="absolute top-2 right-2 text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-zinc-100 text-zinc-400 uppercase tracking-wide">
          Optional
        </span>
      )}

      <ZoneIcon type={icon} uploaded={!!file} />

      <div className="text-center">
        <div className="text-xs font-semibold text-zinc-700">{label}</div>
        <div className="text-[10px] text-zinc-400 mt-0.5">{description}</div>
      </div>

      {file ? (
        <div className="w-full">
          <div className="bg-white border border-emerald-200 rounded-lg px-3 py-2 flex items-center gap-2">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-emerald-600 shrink-0">
              <path d="M10 3L4.5 8.5 2 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-[10px] text-zinc-700 font-medium truncate flex-1">{file.name}</span>
            <span className="text-[9px] text-zinc-400 shrink-0">{formatBytes(file.size)}</span>
            <button
              onClick={ev => { ev.stopPropagation(); onRemove(zoneId); }}
              className="text-zinc-400 hover:text-red-500 transition-colors"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 2l6 6M8 2L2 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
      ) : (
        <div className="text-[10px] text-zinc-400 font-mono bg-zinc-100 px-2 py-0.5 rounded">{ext}</div>
      )}
    </div>
  );
}

// ─── Upload Section ───────────────────────────────────────────────────────────

interface UploadSectionProps {
  files: UploadedFiles;
  uploadCount: number;
  isReady: boolean;
  onFile: (id: keyof UploadedFiles, file: File) => void;
  onRemove: (id: keyof UploadedFiles) => void;
  onStart: () => void;
  loading?: boolean;
  excludedParams: ExcludedParameters;
  onExcludedParamsChange: (params: ExcludedParameters) => void;
}

export function UploadSection({
  files,
  uploadCount,
  isReady,
  onFile,
  onRemove,
  onStart,
  loading = false,
  excludedParams,
  onExcludedParamsChange,
}: UploadSectionProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeExclusionCount = Object.values(excludedParams).filter(Boolean).length;

  // ── Count only required zones for the "X / Y uploaded" counter ──────────────
  const requiredZones = UPLOAD_ZONES.filter(z => !z.optional);

  return (
    <Card>
      <CardHeader>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-zinc-900">Upload Reports</h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Upload source files to begin a new automated validation run
          </p>
        </div>
        <span className="text-xs text-zinc-400 font-mono bg-zinc-50 border border-zinc-200 px-2 py-1 rounded">
          {uploadCount} / 2 required uploads
        </span>
      </CardHeader>

      <div className="p-5 grid grid-cols-2 md:grid-cols-4 gap-3">
        {UPLOAD_ZONES.map(zone => (
          <DropZone
            key={zone.id}
            zoneId={zone.id}
            label={zone.label}
            ext={zone.ext}
            icon={zone.icon}
            accept={zone.accept}
            description={zone.description}
            optional={zone.optional}
            file={files[zone.id]}
            onFile={onFile}
            onRemove={onRemove}
          />
        ))}
      </div>

      {/* ── Advanced Filters ──────────────────────────────────────────────── */}
      <div className="border-t border-zinc-100 mx-5 mb-4">
        <button
          onClick={() => setFiltersOpen(o => !o)}
          className="flex items-center gap-2 py-3 text-xs font-semibold text-zinc-600 hover:text-zinc-900 transition-colors w-full text-left"
        >
          <svg
            className={cn("w-3 h-3 transition-transform text-zinc-400", filtersOpen && "rotate-180")}
            viewBox="0 0 12 12" fill="none"
          >
            <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Advanced Filters
          {activeExclusionCount > 0 && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[9px] font-bold">
              {activeExclusionCount} excluded
            </span>
          )}
        </button>

        {filtersOpen && (
          <div className="pb-4">
            <p className="text-[10px] text-zinc-400 mb-3 font-medium uppercase tracking-wider">
              Exclude from Visual Validation
            </p>
            <p className="text-[10px] text-zinc-400 mb-3">
              Checked parameters will be ignored during visual comparison. Default is strict validation (nothing excluded).
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2.5">
              {EXCLUSION_OPTIONS.map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2.5 cursor-pointer group">
                  <div
                    className={cn(
                      "w-4 h-4 rounded border-2 flex items-center justify-center transition-colors shrink-0",
                      excludedParams[key]
                        ? "bg-amber-500 border-amber-500"
                        : "bg-white border-zinc-300 group-hover:border-zinc-400"
                    )}
                    onClick={() => onExcludedParamsChange({ ...excludedParams, [key]: !excludedParams[key] })}
                  >
                    {excludedParams[key] && (
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 12 12">
                        <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                  </div>
                  <span className={cn(
                    "text-[11px] font-medium",
                    excludedParams[key] ? "text-amber-700" : "text-zinc-600"
                  )}>
                    {label}
                  </span>
                </label>
              ))}
            </div>
            {activeExclusionCount > 0 && (
              <button
                // ── FIX: use DEFAULT_EXCLUDED_PARAMS instead of Object.fromEntries ──
                onClick={() => onExcludedParamsChange({ ...DEFAULT_EXCLUDED_PARAMS })}
                className="mt-3 text-[10px] text-zinc-400 hover:text-zinc-600 underline"
              >
                Clear all exclusions
              </button>
            )}
          </div>
        )}
      </div>

      <div className="px-5 pb-5 flex items-center justify-between">
        <p className="text-xs text-zinc-400">
          {isReady
            ? activeExclusionCount > 0
              ? `✓ Ready — ${activeExclusionCount} parameter${activeExclusionCount !== 1 ? "s" : ""} excluded`
              : "✓ Ready to run — all required files uploaded"
            : "Upload Tableau workbook + Power BI file to enable validation"}
        </p>
        <Button
          variant="primary"
          size="lg"
          disabled={!isReady}
          loading={loading}
          onClick={onStart}
          icon={
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 6l2.5 2.5L9 4" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          }
        >
          Start Validation
        </Button>
      </div>
    </Card>
  );
}
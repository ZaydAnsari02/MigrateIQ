"use client";

import { useRef, useState } from "react";
import { cn, formatBytes } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { UPLOAD_ZONES } from "@/constants";
import type { UploadedFiles } from "@/types";

// ─── Zone Icons ───────────────────────────────────────────────────────────────

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
  const map: Record<string, string> = {
    tableau:     "📊",
    powerbi:     "⚡",
    screenshots: "🖼",
  };
  return (
    <div className="w-9 h-9 rounded-xl bg-zinc-100 flex items-center justify-center text-xl">
      {map[type] ?? "📁"}
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
  file?: File;
  onFile: (id: keyof UploadedFiles, file: File) => void;
  onRemove: (id: keyof UploadedFiles) => void;
}

function DropZone({ zoneId, label, ext, icon, accept, description, file, onFile, onRemove }: DropZoneProps) {
  const ref   = useRef<HTMLInputElement>(null);
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
}

export function UploadSection({
  files,
  uploadCount,
  isReady,
  onFile,
  onRemove,
  onStart,
  loading = false,
}: UploadSectionProps) {
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
          {uploadCount} / {UPLOAD_ZONES.length} uploaded
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
            file={files[zone.id]}
            onFile={onFile}
            onRemove={onRemove}
          />
        ))}
      </div>

      <div className="px-5 pb-5 flex items-center justify-between">
        <p className="text-xs text-zinc-400">
          {isReady
            ? "✓ Ready to run — all required files uploaded"
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

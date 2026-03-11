/**
 * useExportReport
 *
 * Generates a polished PDF validation report client-side using jsPDF.
 * The PDF combines:
 *   - Section 1: Results summary (stats + layer-status table for all runs)
 *   - Section 2: Detailed comparison per report (mirrors Comparison Explorer)
 *     • AI narrative summary + similarity %
 *     • Key visual differences list
 *     • Comparison image / annotated screenshots (fetched from backend)
 *     • Regression log (differences)
 */

import { useCallback } from "react";
import type { ReportPair } from "@/types";

interface Stats {
  total: number;
  passed: number;
  failed: number;
  pending: number;
  passRate: number;
}

// ─── Colours ─────────────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, [number, number, number]> = {
  pass:    [34,  197, 94],
  fail:    [239, 68,  68],
  pending: [161, 161, 170],
  running: [59,  130, 246],
  review:  [245, 158, 11],
  error:   [249, 115, 22],
};

const BRAND_BLUE: [number, number, number] = [37,  99,  235];
const DARK:       [number, number, number] = [24,  24,  27];
const MID:        [number, number, number] = [113, 113, 122];
const LIGHT:      [number, number, number] = [244, 244, 245];
const WHITE:      [number, number, number] = [255, 255, 255];
const RED_BG:     [number, number, number] = [254, 242, 242];
const RED_BORDER: [number, number, number] = [252, 165, 165];
const RED_TEXT:   [number, number, number] = [185, 28,  28];
const BLUE_LIGHT: [number, number, number] = [232, 240, 254];
const GREEN_BG:   [number, number, number] = [240, 253, 244];
const AMBER_BG:   [number, number, number] = [255, 251, 235];

// ─── Image helper ────────────────────────────────────────────────────────────

function resolveUrl(path: string | undefined | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function fetchBase64(url: string): Promise<{ dataUrl: string; format: "PNG" | "JPEG" } | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    const format: "PNG" | "JPEG" = blob.type.includes("png") ? "PNG" : "JPEG";
    return new Promise(resolve => {
      const reader = new FileReader();
      reader.onloadend = () => resolve({ dataUrl: reader.result as string, format });
      reader.onerror   = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useExportReport() {
  return useCallback(async (pairs: ReportPair[]) => {
    const stats: Stats = {
      total:    pairs.length,
      passed:   pairs.filter(p => p.overallStatus === "PASS").length,
      failed:   pairs.filter(p => p.overallStatus === "FAIL").length,
      pending:  pairs.filter(p => p.overallStatus === "PENDING").length,
      passRate: pairs.length > 0
        ? (pairs.filter(p => p.overallStatus === "PASS").length / pairs.length) * 100
        : 0,
    };

    const { jsPDF } = await import("jspdf");

    const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
    const W   = doc.internal.pageSize.getWidth();   // 595 pt
    const H   = doc.internal.pageSize.getHeight();  // 842 pt
    const PAD = 40;
    let   y   = 0;

    // ── Helpers ───────────────────────────────────────────────────────────────

    const newPage = () => { doc.addPage(); y = PAD; };

    const checkPage = (needed: number) => {
      if (y + needed > H - PAD - 30) newPage();
    };

    const setFont = (size: number, color: [number,number,number], style: "normal"|"bold" = "normal") => {
      doc.setFontSize(size);
      doc.setTextColor(...color);
      doc.setFont("helvetica", style);
    };

    const rule = (lx = PAD, rx = W - PAD, color: [number,number,number] = [228,228,231], thickness = 0.4) => {
      doc.setDrawColor(...color);
      doc.setLineWidth(thickness);
      doc.line(lx, y, rx, y);
    };

    const badge = (status: string, bx: number, by: number, bw = 46) => {
      const key   = status.toLowerCase();
      const col   = STATUS_COLORS[key] ?? ([161,161,170] as [number,number,number]);
      const label = status.toUpperCase();
      const bh    = 15;
      const bg: [number,number,number] = [
        Math.min(255, col[0] + 175),
        Math.min(255, col[1] + 175),
        Math.min(255, col[2] + 175),
      ];
      doc.setFillColor(...bg);
      doc.roundedRect(bx, by - bh + 3, bw, bh, 4, 4, "F");
      doc.setFontSize(7);
      doc.setTextColor(...col);
      doc.setFont("helvetica", "bold");
      doc.text(label, bx + bw / 2, by - 1, { align: "center" });
    };

    // ── Page 1: HEADER BAND ───────────────────────────────────────────────────
    doc.setFillColor(...BRAND_BLUE);
    doc.rect(0, 0, W, 68, "F");

    y = 28;
    setFont(20, WHITE, "bold");
    doc.text("MigrateIQ", PAD, y);

    y = 48;
    setFont(10, [147, 197, 253]);
    doc.text("Validation Report", PAD, y);

    const now = new Date().toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
      timeZone: "Asia/Kolkata",
    });
    y = 28;
    setFont(8, [147, 197, 253]);
    doc.text(`Generated: ${now}`, W - PAD, y, { align: "right" });

    y = 42;
    doc.text("Tableau -> PowerBI Validation  |  L1 Visual  |  L2 Semantic  |  L3 Data Regression",
      W - PAD, y, { align: "right" });

    y = 84;

    // ════════════════════════════════════════════════════════════════════════
    // SECTION 1 — RESULTS SUMMARY
    // ════════════════════════════════════════════════════════════════════════

    setFont(13, DARK, "bold");
    doc.text("Results Summary", PAD, y);
    y += 16;

    // ── Stat cards ────────────────────────────────────────────────────────────
    const statCards: Array<{ label: string; value: string; color: [number,number,number] }> = [
      { label: "Total Runs", value: String(stats.total),              color: BRAND_BLUE },
      { label: "Passed",     value: String(stats.passed),             color: [34, 197, 94] },
      { label: "Failed",     value: String(stats.failed),             color: [239, 68, 68] },
      { label: "Pass Rate",  value: `${stats.passRate.toFixed(1)}%`,  color: BRAND_BLUE },
    ];

    const cardW = (W - PAD * 2 - 12 * 3) / 4;
    const cardH = 54;
    const cardY = y;

    statCards.forEach((card, i) => {
      const cx = PAD + i * (cardW + 12);
      doc.setFillColor(...LIGHT);
      doc.roundedRect(cx, cardY, cardW, cardH, 6, 6, "F");
      doc.setFillColor(...card.color);
      doc.roundedRect(cx, cardY, cardW, 3, 1, 1, "F");

      doc.setFontSize(22);
      doc.setTextColor(...card.color);
      doc.setFont("helvetica", "bold");
      doc.text(card.value, cx + cardW / 2, cardY + 30, { align: "center" });

      setFont(8, MID);
      doc.text(card.label, cx + cardW / 2, cardY + 44, { align: "center" });
    });

    y = cardY + cardH + 24;
    rule();
    y += 18;

    // ── Layer status table ────────────────────────────────────────────────────
    if (pairs.length === 0) {
      setFont(10, MID);
      doc.text("No validation results available.", PAD, y);
      y += 20;
    } else {
      setFont(11, DARK, "bold");
      doc.text("Layer Status per Run", PAD, y);
      y += 14;

      // Total available width = W - 2*PAD = 515pt
      // name(160) + ts(113) + ovr(62) + l1(60) + l2(60) + l3(60) = 515
      const COL = {
        name: { x: PAD,       w: 160, label: "Report Name", center: false },
        ts:   { x: PAD + 160, w: 113, label: "Timestamp",   center: false },
        ovr:  { x: PAD + 273, w: 62,  label: "Overall",     center: true  },
        l1:   { x: PAD + 335, w: 60,  label: "L1",          center: true  },
        l2:   { x: PAD + 395, w: 60,  label: "L2",          center: true  },
        l3:   { x: PAD + 455, w: 60,  label: "L3",          center: true  },
      };

      // Header row
      doc.setFillColor(...BLUE_LIGHT);
      doc.rect(PAD, y, W - PAD * 2, 20, "F");
      const hY = y + 13;
      Object.values(COL).forEach(col => {
        setFont(7.5, MID, "bold");
        if (col.center) {
          doc.text(col.label.toUpperCase(), col.x + col.w / 2, hY, { align: "center" });
        } else {
          doc.text(col.label.toUpperCase(), col.x + 4, hY);
        }
      });
      y += 20;

      const ROW_H = 26;
      pairs.forEach((pair, idx) => {
        checkPage(ROW_H + 2);
        doc.setFillColor(...(idx % 2 === 0 ? WHITE : LIGHT));
        doc.rect(PAD, y, W - PAD * 2, ROW_H, "F");
        const rY = y + 16;

        setFont(8, DARK);
        const nameLines = doc.splitTextToSize(pair.reportName, COL.name.w - 8) as string[];
        const shortName = nameLines.length > 1 ? nameLines[0].trimEnd() + "…" : pair.reportName;
        doc.text(shortName, COL.name.x + 4, rY);

        const ts = new Date(pair.createdAt).toLocaleString("en-GB", {
          day: "2-digit", month: "short", year: "numeric",
          hour: "2-digit", minute: "2-digit",
          timeZone: "Asia/Kolkata",
        });
        setFont(7.5, MID);
        doc.text(ts, COL.ts.x + 4, rY);

        // Center badges within their column widths
        const OVR_BW = 46;
        badge(pair.overallStatus, COL.ovr.x + (COL.ovr.w - OVR_BW) / 2, rY, OVR_BW);
        const LAYER_BW = 42;
        const layerBadge = (status: string, col: { x: number; w: number }, y2: number) => {
          const bx = col.x + (col.w - LAYER_BW) / 2;
          if (status === "skipped") {
            setFont(9, MID, "bold");
            doc.text("—", col.x + col.w / 2, y2, { align: "center" });
          } else {
            badge(status, bx, y2, LAYER_BW);
          }
        };
        layerBadge(pair.layer1Status, COL.l1, rY);
        layerBadge(pair.layer2Status, COL.l2, rY);
        layerBadge(pair.layer3Status, COL.l3, rY);

        y += ROW_H;
      });

      y += 10;
      rule();
      y += 16;
    }

    // ════════════════════════════════════════════════════════════════════════
    // SECTION 2 — DETAILED COMPARISON
    // ════════════════════════════════════════════════════════════════════════

    if (pairs.length > 0) {
      newPage();

      // Section page header band
      doc.setFillColor(...BLUE_LIGHT);
      doc.rect(0, 0, W, 44, "F");
      y = 28;
      setFont(14, BRAND_BLUE, "bold");
      doc.text("Detailed Comparison", PAD, y);
      y = 56;

      for (const pair of pairs) {
        const vis = pair.visualResult;

        // ── Pair header card ────────────────────────────────────────────────
        const BADGE_W  = 50;
        const NAME_MAX = W - PAD * 2 - BADGE_W - 24;

        const nameLines: string[] = doc.splitTextToSize(pair.reportName, NAME_MAX) as string[];
        const headerH = Math.max(36, 12 + nameLines.length * 13 + 14);

        checkPage(headerH + 100);

        doc.setFillColor(250, 250, 250);
        doc.roundedRect(PAD, y, W - PAD * 2, headerH, 5, 5, "F");
        doc.setDrawColor(228, 228, 231);
        doc.setLineWidth(0.5);
        doc.roundedRect(PAD, y, W - PAD * 2, headerH, 5, 5, "S");

        const accentCol = STATUS_COLORS[pair.overallStatus.toLowerCase()] ?? MID;
        doc.setFillColor(...accentCol);
        doc.roundedRect(PAD, y, 4, headerH, 2, 2, "F");

        const nameStartY = y + 14;
        nameLines.forEach((line, li) => {
          setFont(10, DARK, "bold");
          doc.text(line, PAD + 12, nameStartY + li * 13);
        });

        const subtitleY = nameStartY + nameLines.length * 13 + 1;
        const fmtDate = new Date(pair.createdAt).toLocaleString("en-GB", {
          day: "2-digit", month: "short", year: "numeric",
          hour: "2-digit", minute: "2-digit",
        });
        setFont(8, MID);
        doc.text(fmtDate, PAD + 12, subtitleY);

        badge(pair.overallStatus, W - PAD - BADGE_W - 4, y + headerH / 2 - 2, BADGE_W);
        y += headerH + 10;

        // ── Validation Layers ──────────────────────────────────────────────
        setFont(7.5, MID, "bold");
        doc.text("VALIDATION LAYERS", PAD, y);
        y += 8;

        const layers = [
          { label: "L1  Visual",   status: pair.layer1Status },
          { label: "L2  Semantic", status: pair.layer2Status },
          { label: "L3  Data",     status: pair.layer3Status },
        ];

        layers.forEach(l => {
          checkPage(20);
          doc.setFillColor(...WHITE);
          doc.rect(PAD, y, W - PAD * 2, 20, "F");
          doc.setDrawColor(240, 240, 242);
          doc.setLineWidth(0.3);
          doc.line(PAD, y + 20, W - PAD, y + 20);
          setFont(8.5, DARK);
          doc.text(l.label, PAD + 8, y + 13);
          if (l.status === "skipped") {
            setFont(9, MID, "bold");
            doc.text("—", W - PAD - 28, y + 13, { align: "center" });
          } else {
            badge(l.status, W - PAD - 52, y + 13, 48);
          }
          y += 20;
        });

        y += 12;

        // ── Visual Analysis ────────────────────────────────────────────────
        if (vis) {
          checkPage(24);
          setFont(7.5, MID, "bold");
          doc.text("VISUAL ANALYSIS", PAD, y);
          y += 10;

          // Similarity bar
          if (vis.pixelSimilarityPct !== undefined && vis.pixelSimilarityPct !== null) {
            checkPage(28);
            const simPct   = Math.max(0, Math.min(100, vis.pixelSimilarityPct));
            const barW     = W - PAD * 2;
            const filledW  = barW * (simPct / 100);
            const barColor: [number,number,number] = simPct >= 95 ? [34, 197, 94] : simPct >= 75 ? [245, 158, 11] : [239, 68, 68];

            // Label row
            setFont(8, DARK);
            doc.text("Pixel Similarity", PAD, y);
            setFont(8, barColor, "bold");
            doc.text(`${simPct.toFixed(1)}%`, W - PAD, y, { align: "right" });
            y += 6;

            // Track
            doc.setFillColor(...LIGHT);
            doc.roundedRect(PAD, y, barW, 7, 3, 3, "F");
            // Fill
            doc.setFillColor(...barColor);
            doc.roundedRect(PAD, y, filledW, 7, 3, 3, "F");
            y += 16;
          }

          // AI summary
          if (vis.aiSummary) {
            const summaryLines: string[] = doc.splitTextToSize(`"${vis.aiSummary}"`, W - PAD * 2 - 24) as string[];
            const summaryH = summaryLines.length * 11 + 26;
            checkPage(summaryH + 8);

            const summaryBg: [number,number,number] = [238, 244, 255];
            doc.setFillColor(...summaryBg);
            doc.roundedRect(PAD, y, W - PAD * 2, summaryH, 5, 5, "F");
            doc.setDrawColor(...BLUE_LIGHT);
            doc.setLineWidth(0.4);
            doc.roundedRect(PAD, y, W - PAD * 2, summaryH, 5, 5, "S");

            // Left accent
            doc.setFillColor(...BRAND_BLUE);
            doc.rect(PAD, y + 4, 3, summaryH - 8, "F");

            setFont(7.5, BRAND_BLUE, "bold");
            doc.text("AI NARRATIVE SUMMARY", PAD + 10, y + 12);

            setFont(8, [60, 80, 130]);
            summaryLines.forEach((line, li) => {
              doc.text(line, PAD + 10, y + 22 + li * 11);
            });

            y += summaryH + 8;
          }

          // Key visual differences
          let keyDiffs: string[] = [];
          if (vis.aiKeyDifferences) {
            try {
              const parsed = JSON.parse(vis.aiKeyDifferences);
              keyDiffs = Array.isArray(parsed) ? parsed.map(String) : [String(parsed)];
            } catch {
              keyDiffs = [vis.aiKeyDifferences];
            }
          }

          if (keyDiffs.length > 0) {
            checkPage(24 + keyDiffs.length * 16);
            setFont(7.5, MID, "bold");
            doc.text("KEY VISUAL DIFFERENCES", PAD, y);
            y += 10;

            keyDiffs.forEach(diff => {
              const diffLines: string[] = doc.splitTextToSize(diff, W - PAD * 2 - 20) as string[];
              const itemH = diffLines.length * 10 + 12;
              checkPage(itemH + 2);

              doc.setFillColor(...AMBER_BG);
              doc.roundedRect(PAD, y, W - PAD * 2, itemH, 3, 3, "F");
              doc.setFillColor(245, 158, 11);
              doc.circle(PAD + 10, y + itemH / 2, 2, "F");
              setFont(8, [120, 80, 20]);
              diffLines.forEach((line, li) => {
                doc.text(line, PAD + 18, y + 9 + li * 10);
              });
              y += itemH + 3;
            });
            y += 4;
          }

          // Comparison image (full report card)
          const compUrl  = resolveUrl(vis.comparisonImagePath);
          const tabUrl   = resolveUrl(vis.tableauAnnotatedPath) || resolveUrl(pair.tableauScreenshot);
          const pbiUrl   = resolveUrl(vis.powerbiAnnotatedPath) || resolveUrl(pair.powerBiScreenshot);

          if (compUrl) {
            const img = await fetchBase64(compUrl);
            if (img) {
              // Full-width comparison report card
              const imgW = W - PAD * 2;
              const imgH = imgW * (960 / 1280); // comparison image is 1280×960

              checkPage(imgH + 30);
              setFont(7.5, MID, "bold");
              doc.text("COMPARISON REPORT CARD", PAD, y);
              y += 8;

              doc.addImage(img.dataUrl, img.format, PAD, y, imgW, imgH);
              y += imgH + 12;
            }
          } else if (tabUrl || pbiUrl) {
            // Side-by-side annotated screenshots
            const halfW = (W - PAD * 2 - 8) / 2;
            const halfH = halfW * (960 / 1280);

            checkPage(halfH + 36);
            setFont(7.5, MID, "bold");
            doc.text("ANNOTATED SCREENSHOTS", PAD, y);
            y += 8;

            if (tabUrl) {
              const img = await fetchBase64(tabUrl);
              if (img) {
                setFont(7, MID);
                doc.text("Tableau Source", PAD, y);
                doc.addImage(img.dataUrl, img.format, PAD, y + 6, halfW, halfH);
              }
            }
            if (pbiUrl) {
              const img = await fetchBase64(pbiUrl);
              if (img) {
                setFont(7, MID);
                doc.text("Power BI Migration", PAD + halfW + 8, y);
                doc.addImage(img.dataUrl, img.format, PAD + halfW + 8, y + 6, halfW, halfH);
              }
            }
            y += halfH + 20;
          }

          y += 4;
        }

        // ── Differences ────────────────────────────────────────────────────
        setFont(7.5, MID, "bold");
        doc.text(`REGRESSION LOG  (${pair.differences.length})`, PAD, y);
        y += 8;

        if (pair.differences.length === 0) {
          checkPage(24);
          doc.setFillColor(...GREEN_BG);
          doc.roundedRect(PAD, y, W - PAD * 2, 22, 4, 4, "F");
          setFont(8.5, [21, 128, 61]);
          doc.text("All checks passed — no regressions detected", PAD + 10, y + 14);
          y += 22;
        } else {
          pair.differences.forEach(d => {
            const DETAIL_MAX  = W - PAD * 2 - 44;
            const detailLines: string[] = doc.splitTextToSize(d.detail, DETAIL_MAX) as string[];
            const diffH = 14 + 14 + detailLines.length * 10 + 8;

            checkPage(diffH + 4);

            doc.setFillColor(...RED_BG);
            doc.roundedRect(PAD, y, W - PAD * 2, diffH, 4, 4, "F");
            doc.setDrawColor(...RED_BORDER);
            doc.setLineWidth(0.3);
            doc.roundedRect(PAD, y, W - PAD * 2, diffH, 4, 4, "S");

            const tagCol = STATUS_COLORS["fail"];
            doc.setFillColor(...tagCol);
            doc.roundedRect(PAD + 6, y + 10, 22, 12, 3, 3, "F");
            setFont(6.5, WHITE, "bold");
            doc.text(d.layer ?? "", PAD + 17, y + 18, { align: "center" });

            setFont(8.5, RED_TEXT, "bold");
            doc.text(d.type, PAD + 34, y + 18);

            setFont(8, [100, 100, 110]);
            detailLines.forEach((line, li) => {
              doc.text(line, PAD + 34, y + 30 + li * 10);
            });

            y += diffH + 4;
          });
        }

        y += 16;
        rule(PAD, W - PAD, [220, 220, 224], 0.5);
        y += 20;
      }
    }

    // ── Footer on every page ──────────────────────────────────────────────────
    const totalPages = doc.internal.pages.length - 1;
    for (let p = 1; p <= totalPages; p++) {
      doc.setPage(p);
      doc.setFillColor(...LIGHT);
      doc.rect(0, H - 28, W, 28, "F");
      doc.setDrawColor(220, 220, 224);
      doc.setLineWidth(0.4);
      doc.line(0, H - 28, W, H - 28);
      setFont(7.5, MID);
      doc.text("MigrateIQ v1.0.0  |  Three-layer automated validation engine", PAD, H - 10);
      doc.text(`Page ${p} of ${totalPages}`, W - PAD, H - 10, { align: "right" });
    }

    // ── Save ──────────────────────────────────────────────────────────────────
    const filename = `migrateiq-report-${new Date().toISOString().slice(0, 10)}.pdf`;
    doc.save(filename);
  }, []);
}

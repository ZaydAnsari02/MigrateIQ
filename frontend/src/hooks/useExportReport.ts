/**
 * useExportReport
 *
 * Generates a polished PDF validation report client-side using jsPDF.
 * The PDF combines:
 *   - Section 1: Results summary (stats + layer-status table for all runs)
 *   - Section 2: Detailed comparison per report (mirrors Comparison Explorer)
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

      const COL = {
        name: { x: PAD,       w: 170, label: "Report Name" },
        ts:   { x: PAD + 178, w: 106, label: "Timestamp"   },
        ovr:  { x: PAD + 292, w: 66,  label: "Overall"     },
        l1:   { x: PAD + 366, w: 52,  label: "L1"          },
        l2:   { x: PAD + 426, w: 52,  label: "L2"          },
        l3:   { x: PAD + 486, w: 52,  label: "L3"          },
      };

      // Header row
      doc.setFillColor(...BLUE_LIGHT);
      doc.rect(PAD, y, W - PAD * 2, 20, "F");
      const hY = y + 13;
      Object.values(COL).forEach(col => {
        setFont(7.5, MID, "bold");
        doc.text(col.label.toUpperCase(), col.x + 4, hY);
      });
      y += 20;

      const ROW_H = 26;
      pairs.forEach((pair, idx) => {
        checkPage(ROW_H + 2);
        doc.setFillColor(...(idx % 2 === 0 ? WHITE : LIGHT));
        doc.rect(PAD, y, W - PAD * 2, ROW_H, "F");
        const rY = y + 16;

        // Name — truncated to fit column width
        const shortName = pair.reportName.length > 26 ? pair.reportName.slice(0, 24) + "..." : pair.reportName;
        setFont(8, DARK);
        doc.text(shortName, COL.name.x + 4, rY);

        // Timestamp
        const ts = new Date(pair.createdAt).toLocaleString("en-GB", {
          day: "2-digit", month: "short", year: "numeric",
          hour: "2-digit", minute: "2-digit",
        });
        setFont(7.5, MID);
        doc.text(ts, COL.ts.x + 4, rY);

        badge(pair.overallStatus, COL.ovr.x + 4, rY);
        badge(pair.layer1Status,  COL.l1.x + 2,  rY, 42);
        badge(pair.layer2Status,  COL.l2.x + 2,  rY, 42);
        badge(pair.layer3Status,  COL.l3.x + 2,  rY, 42);

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
        // ── Pair header card ────────────────────────────────────────────────
        const BADGE_W  = 50;
        const NAME_MAX = W - PAD * 2 - BADGE_W - 24;

        // Wrap report name
        const nameLines: string[] = doc.splitTextToSize(pair.reportName, NAME_MAX) as string[];
        const headerH = Math.max(36, 12 + nameLines.length * 13 + 14);

        checkPage(headerH + 100); // ensure enough room for header + layers

        // Card background
        doc.setFillColor(250, 250, 250);
        doc.roundedRect(PAD, y, W - PAD * 2, headerH, 5, 5, "F");
        doc.setDrawColor(228, 228, 231);
        doc.setLineWidth(0.5);
        doc.roundedRect(PAD, y, W - PAD * 2, headerH, 5, 5, "S");

        // Coloured left accent
        const accentCol = STATUS_COLORS[pair.overallStatus.toLowerCase()] ?? MID;
        doc.setFillColor(...accentCol);
        doc.roundedRect(PAD, y, 4, headerH, 2, 2, "F");

        // Report name (multi-line)
        const nameStartY = y + 14;
        nameLines.forEach((line, li) => {
          setFont(10, DARK, "bold");
          doc.text(line, PAD + 12, nameStartY + li * 13);
        });

        // Timestamp subtitle
        const subtitleY = nameStartY + nameLines.length * 13 + 1;
        const fmtDate = new Date(pair.createdAt).toLocaleString("en-GB", {
          day: "2-digit", month: "short", year: "numeric",
          hour: "2-digit", minute: "2-digit",
        });
        setFont(8, MID);
        doc.text(fmtDate, PAD + 12, subtitleY);

        // Overall badge — vertically centred
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
          badge(l.status, W - PAD - 52, y + 13, 48);

          y += 20;
        });

        y += 10;

        // ── Differences ────────────────────────────────────────────────────
        setFont(7.5, MID, "bold");
        doc.text(`DIFFERENCES  (${pair.differences.length})`, PAD, y);
        y += 8;

        if (pair.differences.length === 0) {
          checkPage(24);
          doc.setFillColor(248, 250, 252);
          doc.roundedRect(PAD, y, W - PAD * 2, 22, 4, 4, "F");
          setFont(8.5, MID);
          doc.text("None detected", PAD + 10, y + 14);
          y += 22;
        } else {
          pair.differences.forEach(d => {
            const DETAIL_MAX  = W - PAD * 2 - 44;
            const detailLines: string[] = doc.splitTextToSize(d.detail, DETAIL_MAX) as string[];
            const diffH = 14 + 14 + detailLines.length * 10 + 8; // top pad + type row + detail lines + bottom pad

            checkPage(diffH + 4);

            // Card
            doc.setFillColor(...RED_BG);
            doc.roundedRect(PAD, y, W - PAD * 2, diffH, 4, 4, "F");
            doc.setDrawColor(...RED_BORDER);
            doc.setLineWidth(0.3);
            doc.roundedRect(PAD, y, W - PAD * 2, diffH, 4, 4, "S");

            // Layer tag pill
            const tagCol = STATUS_COLORS["fail"];
            doc.setFillColor(...tagCol);
            doc.roundedRect(PAD + 6, y + 10, 22, 12, 3, 3, "F");
            setFont(6.5, WHITE, "bold");
            doc.text(d.layer ?? "", PAD + 17, y + 18, { align: "center" });

            // Type
            setFont(8.5, RED_TEXT, "bold");
            doc.text(d.type, PAD + 34, y + 18);

            // Detail — all wrapped lines
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

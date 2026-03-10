from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import config

logger = logging.getLogger(__name__)


# ── Normalisation target ───────────────────────────────────────────────────────
# Re-exported from config so that existing imports in pipeline.py and tests
# (e.g. `from visual.pixel_diff import PASS_THRESHOLD`) continue to work.
NORM_W: int             = config.PIXEL_NORM_W
NORM_H: int             = config.PIXEL_NORM_H
CHANNEL_THRESHOLD: int  = config.PIXEL_CHANNEL_THRESHOLD
GPT4O_CALL_THRESHOLD: float = config.PIXEL_GPT4O_CALL_THRESHOLD
PASS_THRESHOLD: float   = config.PIXEL_PASS_THRESHOLD
REVIEW_THRESHOLD: float = config.PIXEL_REVIEW_THRESHOLD

# Perceptual hash grid size. 8×8 = 64-bit hash.
_HASH_SIZE: int = 8

# Resampling filter — use Resampling enum (Pillow ≥ 10); fall back for older versions.
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:                         # Pillow < 10
    _RESAMPLE = Image.LANCZOS                  # type: ignore[attr-defined]


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PixelDiffResult:
    """
    Immutable result returned by compute_pixel_diff.
    All consumers should treat this as read-only.
    """
    similarity_pct:   float   # 0.0–100.0 — higher is more similar
    diff_pixel_count: int     # raw number of pixels that differ
    total_pixels:     int     # NORM_W * NORM_H
    hash_distance:    int     # 0 = structurally identical, 64 = completely different
    diff_image_path:          str   # path to the blended red-highlight diff image
    compared_width:           int
    compared_height:          int
    tableau_annotated_path:   str = ""  # Tableau screenshot with heatmap overlay
    powerbi_annotated_path:   str = ""  # Power BI screenshot with heatmap overlay
    comparison_image_path:    str = ""  # Side-by-side labeled composite

    @property
    def status(self) -> str:
        """Classify result as pass / review / fail based on similarity percentage."""
        if self.similarity_pct >= PASS_THRESHOLD:
            return "pass"
        if self.similarity_pct >= REVIEW_THRESHOLD:
            return "review"
        return "fail"

    @property
    def should_call_gpt4o(self) -> bool:
        """True when the diff is large enough to warrant a GPT-4o visual explanation."""
        return self.similarity_pct < GPT4O_CALL_THRESHOLD

    def __str__(self) -> str:
        return (
            f"PixelDiffResult(similarity={self.similarity_pct:.2f}%, "
            f"diff_pixels={self.diff_pixel_count:,}, "
            f"hash_distance={self.hash_distance}, "
            f"status={self.status})"
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_normalised(path: str) -> np.ndarray:
    """
    Open any image, convert to RGB, resize to (NORM_W × NORM_H).

    Returns:
        np.ndarray of shape (NORM_H, NORM_W, 3), dtype uint8

    Raises:
        FileNotFoundError: if path does not exist
        OSError: if the file exists but cannot be decoded as an image
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Screenshot not found: {path}")

    img = Image.open(p).convert("RGB")

    if img.size != (NORM_W, NORM_H):
        logger.debug("Resizing %s from %s to (%d, %d)", path, img.size, NORM_W, NORM_H)
        img = img.resize((NORM_W, NORM_H), _RESAMPLE)

    return np.array(img, dtype=np.uint8)


def _perceptual_hash(path: str) -> np.ndarray:
    """
    Compute a simple average-hash (aHash) — a fast structural fingerprint.

    Steps:
      1. Convert to grayscale
      2. Resize to _HASH_SIZE × _HASH_SIZE (discards fine detail, keeps structure)
      3. Threshold each pixel against the mean → boolean grid

    The Hamming distance between two hashes tells you how structurally similar
    two images are, independent of colour or minor pixel differences.
    Distance 0 = identical structure.  Distance > 10 = meaningfully different.

    Returns:
        np.ndarray of shape (_HASH_SIZE, _HASH_SIZE), dtype bool
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Screenshot not found: {path}")

    img = Image.open(p).convert("L")                          # grayscale
    img = img.resize((_HASH_SIZE, _HASH_SIZE), _RESAMPLE)
    px  = np.array(img, dtype=np.float32)
    return px > px.mean()


def _hamming_distance(h1: np.ndarray, h2: np.ndarray) -> int:
    """
    Count bit positions where two boolean hash arrays differ.

    Args:
        h1, h2: boolean arrays of identical shape

    Returns:
        int in range [0, h1.size]
    """
    if h1.shape != h2.shape:
        raise ValueError(
            f"Hash shape mismatch: {h1.shape} vs {h2.shape}. "
            "Both images must use the same _HASH_SIZE."
        )
    return int(np.sum(h1 != h2))


def _build_diff_image(
    a: np.ndarray,
    b: np.ndarray,
    output_path: str,
    highlight: Tuple[int, int, int] = (255, 50, 50),
) -> None:
    """
    Create and save a visual diff image that highlights changed pixels in red.

    Layout:
      - Matching pixels  →  dimmed 50 % blend of both images (preserves context)
      - Differing pixels →  solid red highlight

    This makes it immediately obvious WHERE differences are when a migration
    engineer opens the diff image in the certification dashboard.

    Args:
        a:            normalised numpy array for Tableau screenshot
        b:            normalised numpy array for Power BI screenshot
        output_path:  where to write the resulting PNG
        highlight:    RGB tuple for the diff highlight colour (default red)
    """
    if a.shape != b.shape:
        raise ValueError(
            f"Array shape mismatch in diff: {a.shape} vs {b.shape}. "
            "Both arrays must be normalised to the same dimensions."
        )

    # Boolean mask: True wherever the images differ meaningfully
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    mask = np.any(diff > CHANNEL_THRESHOLD, axis=2)          # shape (H, W)

    # Background: dim blend so context remains readable
    blend  = (a.astype(np.float32) * 0.5 + b.astype(np.float32) * 0.5)
    output = (blend * 0.55).astype(np.uint8)

    # Paint differing pixels in the highlight colour
    output[mask] = highlight

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output).save(output_path)
    logger.debug("Diff image saved → %s  (%d highlighted pixels)", output_path, int(mask.sum()))


def _diff_output_path(diff_output_dir: str, report_name: str) -> str:
    """Build the canonical path for a diff image given a directory and report name."""
    safe_name = report_name.replace(" ", "_")
    return str(Path(diff_output_dir) / f"{safe_name}_diff.png")


def _annotated_output_path(diff_output_dir: str, report_name: str, source: str) -> str:
    """Build the path for a source-annotated image (source = 'tableau' or 'powerbi')."""
    safe_name = report_name.replace(" ", "_")
    return str(Path(diff_output_dir) / f"{safe_name}_{source}_annotated.png")


def _comparison_output_path(diff_output_dir: str, report_name: str) -> str:
    """Build the path for the side-by-side comparison composite."""
    safe_name = report_name.replace(" ", "_")
    return str(Path(diff_output_dir) / f"{safe_name}_comparison.png")


def _find_diff_regions(
    mask:            np.ndarray,
    padding:         int   = 12,
    min_area:        int   = 800,
    gap:             int   = 8,
    dilate_size:     int   = 5,
    split_threshold: float = 0.08,
    large_frac:      float = 0.12,
) -> List[Tuple[int, int, int, int]]:
    """
    Locate distinct changed regions in a boolean diff mask.

    Two-pass algorithm:
      Pass 1 — small dilation (5 px) + tight gap detection finds initial blobs.
      Pass 2 — any blob covering > large_frac of the image area is split at
               rows/cols where per-row diff density drops below split_threshold.
               This separates individual bar rows, legend boxes, and title areas
               that otherwise merge into one giant rectangle.

    Args:
        mask:            boolean diff array (H, W)
        padding:         extra pixels added around each final box
        min_area:        minimum bounding-box area to keep (filters noise)
        gap:             minimum consecutive zero-rows/cols to start a new blob
        dilate_size:     MaxFilter kernel size (must be odd; 5 = ±2 px merge)
        split_threshold: per-row diff fraction below which a row is a "gap"
        large_frac:      fraction of total image area above which we attempt split

    Returns:
        List of (y1, x1, y2, x2) bounding boxes, smallest first.
    """
    h, w   = mask.shape
    total  = h * w

    # ── Pass 1: dilate + row/col projection ──────────────────────────────────
    safe_size = dilate_size if dilate_size % 2 == 1 else dilate_size + 1
    pil_mask  = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    dilated   = np.array(pil_mask.filter(ImageFilter.MaxFilter(size=safe_size))) > 128

    def _segments(active_1d: np.ndarray, gap_thr: int) -> List[Tuple[int, int]]:
        segs: List[Tuple[int, int]] = []
        start = gap_run = -1
        for i, v in enumerate(active_1d):
            if v:
                if start == -1:
                    start = i
                gap_run = 0
            else:
                if start != -1:
                    gap_run += 1
                    if gap_run > gap_thr:
                        segs.append((start, i - gap_run))
                        start = gap_run = -1
        if start != -1:
            segs.append((start, len(active_1d) - 1))
        return segs

    initial: List[Tuple[int, int, int, int]] = []
    for (r1, r2) in _segments(np.any(dilated, axis=1), gap):
        for (c1, c2) in _segments(np.any(dilated[r1:r2 + 1, :], axis=0), gap):
            if (r2 - r1) * (c2 - c1) >= min_area:
                initial.append((r1, c1, r2, c2))

    # ── Pass 2: split oversized blobs at natural low-density rows/cols ────────
    def _split_box(y1: int, x1: int, y2: int, x2: int) -> List[Tuple[int, int, int, int]]:
        """
        Split a bounding box at rows where diff density < split_threshold.
        Returns the sub-boxes (with tight column bounds) that survive min_area.
        """
        sub   = mask[y1:y2, x1:x2]
        rdens = sub.mean(axis=1)     # per-row diff fraction (0–1)

        results: List[Tuple[int, int, int, int]] = []
        seg_start = -1
        for r, d in enumerate(rdens):
            if d >= split_threshold:
                if seg_start == -1:
                    seg_start = r
            else:
                if seg_start != -1:
                    sy1, sy2 = y1 + seg_start, y1 + r
                    chunk    = mask[sy1:sy2, x1:x2]
                    col_any  = chunk.any(axis=0)
                    if col_any.any():
                        cx1 = x1 + int(np.argmax(col_any))
                        cx2 = x1 + int(len(col_any) - np.argmax(col_any[::-1]))
                        if (sy2 - sy1) * (cx2 - cx1) >= min_area:
                            results.append((sy1, cx1, sy2, cx2))
                    seg_start = -1
        # flush last segment
        if seg_start != -1:
            sy1, sy2 = y1 + seg_start, y2
            chunk   = mask[sy1:sy2, x1:x2]
            col_any = chunk.any(axis=0)
            if col_any.any():
                cx1 = x1 + int(np.argmax(col_any))
                cx2 = x1 + int(len(col_any) - np.argmax(col_any[::-1]))
                if (sy2 - sy1) * (cx2 - cx1) >= min_area:
                    results.append((sy1, cx1, sy2, cx2))
        return results

    boxes: List[Tuple[int, int, int, int]] = []
    for (r1, c1, r2, c2) in initial:
        area = (r2 - r1) * (c2 - c1)
        if area > large_frac * total:
            sub_boxes = _split_box(r1, c1, r2, c2)
            # If splitting didn't help (still one big box), keep the original
            if len(sub_boxes) <= 1:
                boxes.append((r1, c1, r2, c2))
            else:
                boxes.extend(sub_boxes)
        else:
            boxes.append((r1, c1, r2, c2))

    # ── Add padding and clamp ────────────────────────────────────────────────
    padded = [
        (
            max(0,     y1 - padding),
            max(0,     x1 - padding),
            min(h - 1, y2 + padding),
            min(w - 1, x2 + padding),
        )
        for (y1, x1, y2, x2) in boxes
    ]

    logger.debug("Found %d diff region(s) in mask", len(padded))
    return padded


def _draw_ellipse_outline(
    draw:      "ImageDraw.ImageDraw",
    y1: int, x1: int, y2: int, x2: int,
    color:     Tuple[int, int, int],
    thickness: int = 4,
) -> None:
    """Draw a thick ellipse outline (no fill) by stacking concentric ellipses."""
    for t in range(thickness):
        draw.ellipse(
            [x1 - t, y1 - t, x2 + t, y2 + t],
            outline=color,
        )


def _annotate_arr(arr: np.ndarray, diff_mask: np.ndarray) -> "Image.Image":
    """
    Draw numbered red ellipses around each distinct diff region on `arr`.

    Returns a PIL Image — does NOT save to disk.  Call .save(path) yourself,
    or pass the result to _build_comparison_image to embed it in the report card.
    """
    boxes = _find_diff_regions(diff_mask)
    img   = Image.fromarray(arr.copy(), mode="RGB")
    draw  = ImageDraw.Draw(img)
    RED   = (220, 38, 38)

    for idx, (y1, x1, y2, x2) in enumerate(boxes, start=1):
        _draw_ellipse_outline(draw, y1, x1, y2, x2, color=RED, thickness=4)

        # Numbered badge: filled red circle with white digit
        r  = 14
        cx = x1 + r + 2
        cy = y1 + r + 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
        tx = cx - (len(str(idx)) * 4)
        draw.text((tx, cy - 7), str(idx), fill=(255, 255, 255))

    logger.debug("_annotate_arr: drew %d ellipse(s)", len(boxes))
    return img


def _build_annotated_image(
    arr:         np.ndarray,
    diff_mask:   np.ndarray,
    output_path: str,
) -> None:
    """
    Save an ellipse-annotated copy of `arr` to `output_path`.

    Distinct diff regions are found via _find_diff_regions (small dilation +
    row-density split so individual bars / legend boxes are separate ellipses
    rather than one huge rectangle).
    """
    img = _annotate_arr(arr, diff_mask)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    logger.debug("Ellipse-annotated image saved → %s", output_path)


def _build_report_card(
    ann_t:          "Image.Image",
    ann_p:          "Image.Image",
    output_path:    str,
    similarity_pct: float = 0.0,
    footer_text:    str   = "",
    scale:          float = 0.55,
) -> None:
    """
    Render a side-by-side report card from two already-annotated PIL Images.

    Both images are resized to `scale` of their original size and placed
    side-by-side inside a canvas with:
      • Dark header  — coloured PASS / REVIEW / FAIL badge + similarity %
      • Both thumbnails with thin border
      • Source labels below each image
      • Light footer row with diff stats (or custom footer_text)

    This is the shared layout used by both the pixel-diff comparison and the
    GPT-4o spatial comparison, so both report cards look identical in style.
    """
    orig_w, orig_h = ann_t.size

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]

    thumb_w = int(orig_w * scale)
    thumb_h = int(orig_h * scale)

    thumb_t = ann_t.resize((thumb_w, thumb_h), resample)
    thumb_p = ann_p.resize((thumb_w, thumb_h), resample)

    # Status badge
    if similarity_pct >= PASS_THRESHOLD:
        status_label, status_color = "PASS",   (39, 174, 96)
    elif similarity_pct >= REVIEW_THRESHOLD:
        status_label, status_color = "REVIEW", (230, 126, 34)
    else:
        status_label, status_color = "FAIL",   (192, 57, 43)

    pad      = 24
    header_h = 64
    label_h  = 28
    footer_h = 36
    canvas_w = thumb_w * 2 + pad * 3
    canvas_h = header_h + thumb_h + label_h + footer_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), (245, 245, 245))
    draw   = ImageDraw.Draw(canvas)

    # Header
    draw.rectangle([0, 0, canvas_w, header_h], fill=(30, 30, 30))
    bx1, by1 = 20, 16
    bx2, by2 = bx1 + len(status_label) * 10 + 20, by1 + 30
    draw.rectangle([bx1, by1, bx2, by2], fill=status_color)
    draw.text((bx1 + 10, by1 + 7), status_label, fill=(255, 255, 255))
    draw.text((bx2 + 20, by1 + 7), f"Similarity: {similarity_pct:.1f}%", fill=(220, 220, 220))
    title = "MigrateIQ  |  Visual Report Comparison"
    draw.text((canvas_w - len(title) * 7 - 20, by1 + 7), title, fill=(160, 160, 160))

    # Images
    img_y = header_h
    canvas.paste(thumb_t, (pad, img_y))
    canvas.paste(thumb_p, (pad * 2 + thumb_w, img_y))
    draw.rectangle([pad - 1, img_y - 1, pad + thumb_w, img_y + thumb_h], outline=(180, 180, 180))
    draw.rectangle([pad * 2 + thumb_w - 1, img_y - 1, pad * 2 + thumb_w * 2, img_y + thumb_h], outline=(180, 180, 180))

    # Labels
    label_y = header_h + thumb_h + 6
    draw.text((pad, label_y), "Tableau  (original)", fill=(60, 60, 60))
    draw.text((pad * 2 + thumb_w, label_y), "Power BI  (migrated)", fill=(60, 60, 60))

    # Footer
    footer_y = header_h + thumb_h + label_h
    draw.rectangle([0, footer_y, canvas_w, canvas_h], fill=(220, 220, 220))
    draw.text((pad, footer_y + 10), footer_text, fill=(80, 80, 80))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    logger.debug("Report card saved → %s", output_path)


def _build_comparison_image(
    arr_t:          np.ndarray,
    arr_p:          np.ndarray,
    diff_mask:      np.ndarray,
    output_path:    str,
    similarity_pct: float = 0.0,
) -> None:
    """Pixel-diff comparison: annotate with ellipses then render the report card."""
    h, w    = arr_t.shape[:2]
    ann_t   = _annotate_arr(arr_t, diff_mask)
    ann_p   = _annotate_arr(arr_p, diff_mask)
    diff_px = int(diff_mask.sum())
    footer  = (
        f"Diff pixels: {diff_px:,} / {diff_mask.size:,}    "
        f"Changed: {100 - similarity_pct:.1f}%    "
        f"Resolution compared: {w}x{h}"
    )
    _build_report_card(ann_t, ann_p, output_path, similarity_pct, footer_text=footer)


# ── GPT-4o hybrid annotation ───────────────────────────────────────────────────

# Maps keywords found in a GPT-4o key_difference sentence to a function that
# returns the (y1, x1, y2, x2) zone for that element, given image (h, w).
# Zones are generous so the ellipse always encloses the real element.
def build_gpt4o_annotated_images(
    arr_t:            np.ndarray,
    arr_p:            np.ndarray,
    spatial_analysis: "SpatialAnalysis",
    tab_out_path:     str,
    pbi_out_path:     str,
    comp_out_path:    str   = "",
    similarity_pct:   float = 0.0,
) -> None:
    """
    Draw numbered red ellipses on both screenshots using GPT-4o's spatial analysis.

    Unlike the old keyword-heuristic approach, this function uses the EXACT
    bounding box coordinates that GPT-4o returned for each difference — no
    guessing, no zone maps.  GPT-4o was instructed to ignore UI chrome and
    focus only on the chart content, so the ellipses are tightly placed on
    the specific elements that changed.

    For differences where an element is ABSENT in one image (e.g. legend only
    in Power BI), that image shows NO ellipse for that difference number —
    this communicates "nothing to circle here, it's missing".

    Args:
        arr_t, arr_p:      normalised uint8 RGB arrays (H × W × 3)
        spatial_analysis:  SpatialAnalysis from analyze_with_spatial_diff()
        tab_out_path:      where to save the annotated Tableau PNG
        pbi_out_path:      where to save the annotated Power BI PNG
    """
    from visual.gpt4o_analyzer import SpatialAnalysis  # local to avoid circular

    h, w = arr_t.shape[:2]
    RED  = (220, 38, 38)
    ELLIPSE_PAD = 8   # extra pixels around each GPT-4o box

    def _draw_on(arr: np.ndarray, get_box, content_vp) -> "Image.Image":
        """
        Draw a thin blue content-viewport border + red ellipses onto arr.
        content_vp is a DiffBox (or None) from SpatialAnalysis; all ellipses
        are already clipped to it by _parse_spatial_response so no chrome leaks.
        """
        img  = Image.fromarray(arr.copy(), mode="RGB")
        draw = ImageDraw.Draw(img)

        # Thin blue border marks where GPT-4o identified the chart canvas
        if content_vp is not None and content_vp.is_valid():
            vx1, vy1, vx2, vy2 = content_vp.to_pixels(w, h)
            for t in range(2):
                draw.rectangle(
                    [vx1 - t, vy1 - t, vx2 + t, vy2 + t],
                    outline=(100, 149, 237),   # cornflower blue
                )

        for idx, diff in enumerate(spatial_analysis.differences, start=1):
            box = get_box(diff)
            if box is None or not box.is_valid():
                continue

            px1, py1, px2, py2 = box.to_pixels(w, h)
            px1 = max(0,     px1 - ELLIPSE_PAD)
            py1 = max(0,     py1 - ELLIPSE_PAD)
            px2 = min(w - 1, px2 + ELLIPSE_PAD)
            py2 = min(h - 1, py2 + ELLIPSE_PAD)

            _draw_ellipse_outline(draw, py1, px1, py2, px2, color=RED, thickness=4)

            r  = 14
            cx = px1 + r + 2
            cy = py1 + r + 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
            tx = cx - (len(str(idx)) * 4)
            draw.text((tx, cy - 7), str(idx), fill=(255, 255, 255))

        return img

    ann_t = _draw_on(arr_t, lambda d: d.tableau_box, spatial_analysis.tableau_content)
    ann_p = _draw_on(arr_p, lambda d: d.powerbi_box, spatial_analysis.powerbi_content)

    for img, out_path in [(ann_t, tab_out_path), (ann_p, pbi_out_path)]:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        logger.debug("Spatial-annotated image saved → %s", out_path)

    # Optionally produce a side-by-side comparison report card
    if comp_out_path:
        n = len(spatial_analysis.differences)
        footer = (
            f"GPT-4o spatial analysis  |  "
            f"{n} difference(s) found  |  "
            f"Risk: {spatial_analysis.risk_level.upper()}  |  "
            f"Similarity: {similarity_pct:.1f}%"
        )
        _build_report_card(ann_t, ann_p, comp_out_path, similarity_pct, footer_text=footer)
        logger.debug("Spatial comparison report card saved → %s", comp_out_path)

    logger.info(
        "build_gpt4o_annotated_images: drew ellipses for %d difference(s)",
        len(spatial_analysis.differences),
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_pixel_diff(
    tableau_path:    str,
    powerbi_path:    str,
    diff_output_dir: str = "screenshots/diffs",
    report_name:     str = "report",
) -> PixelDiffResult:
    """
    Compare two BI report screenshots. Main entry point for Layer 1.

    The function:
      1. Validates both file paths exist.
      2. Loads and normalises both images to (NORM_W × NORM_H).
      3. Computes a per-pixel diff using a channel threshold.
      4. Computes a perceptual (structural) hash distance.
      5. Saves a red-highlight diff image.
      6. Returns an immutable PixelDiffResult.

    Args:
        tableau_path:    path to the Tableau screenshot PNG
        powerbi_path:    path to the Power BI screenshot PNG
        diff_output_dir: directory where the diff image will be saved
        report_name:     used as the filename prefix for the diff image
                         (spaces replaced with underscores automatically)

    Returns:
        PixelDiffResult — all metrics + path to the saved diff image

    Raises:
        FileNotFoundError: if either screenshot path does not exist
        OSError: if either file cannot be decoded as an image
    """
    logger.info("Computing pixel diff for %r", report_name)

    # ── Step 1 — Load and normalise ──────────────────────────────────────────
    arr_t = _load_normalised(tableau_path)
    arr_p = _load_normalised(powerbi_path)

    total = NORM_W * NORM_H   # 1,228,800 for default resolution

    # ── Step 2 — Pixel diff ──────────────────────────────────────────────────
    # Cast to int16 before subtraction to avoid uint8 wrap-around underflow.
    diff       = np.abs(arr_t.astype(np.int16) - arr_p.astype(np.int16))
    diff_mask  = np.any(diff > CHANNEL_THRESHOLD, axis=2)
    diff_count = int(diff_mask.sum())
    similarity = round((1.0 - diff_count / total) * 100.0, 2)

    logger.debug(
        "Pixel diff: %d/%d pixels differ → %.2f%% similarity",
        diff_count, total, similarity,
    )

    # ── Step 3 — Structural perceptual hash ──────────────────────────────────
    h_t       = _perceptual_hash(tableau_path)
    h_p       = _perceptual_hash(powerbi_path)
    hash_dist = _hamming_distance(h_t, h_p)

    logger.debug("Hash distance: %d / %d", hash_dist, _HASH_SIZE ** 2)

    # ── Step 4 — Save visual diff image ─────────────────────────────────────
    diff_path = _diff_output_path(diff_output_dir, report_name)
    Path(diff_output_dir).mkdir(parents=True, exist_ok=True)
    _build_diff_image(arr_t, arr_p, diff_path)

    # ── Step 5 — Save heatmap-annotated images (one per source) + composite ──
    tab_ann_path  = _annotated_output_path(diff_output_dir, report_name, "tableau")
    pbi_ann_path  = _annotated_output_path(diff_output_dir, report_name, "powerbi")
    comp_path     = _comparison_output_path(diff_output_dir, report_name)

    _build_annotated_image(arr_t, diff_mask, tab_ann_path)
    _build_annotated_image(arr_p, diff_mask, pbi_ann_path)
    _build_comparison_image(arr_t, arr_p, diff_mask, comp_path, similarity_pct=similarity)
    logger.info("[%s] Annotated images and comparison report card saved", report_name)

    result = PixelDiffResult(
        similarity_pct         = similarity,
        diff_pixel_count       = diff_count,
        total_pixels           = total,
        hash_distance          = hash_dist,
        diff_image_path        = diff_path,
        compared_width         = NORM_W,
        compared_height        = NORM_H,
        tableau_annotated_path = tab_ann_path,
        powerbi_annotated_path = pbi_ann_path,
        comparison_image_path  = comp_path,
    )

    logger.info(
        "Pixel diff result for %r: %s | gpt4o_needed=%s",
        report_name, result, result.should_call_gpt4o,
    )

    return result
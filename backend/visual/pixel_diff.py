from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image

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
    diff_image_path:  str     # path to the saved diff image (red highlights)
    compared_width:   int
    compared_height:  int

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

    result = PixelDiffResult(
        similarity_pct   = similarity,
        diff_pixel_count = diff_count,
        total_pixels     = total,
        hash_distance    = hash_dist,
        diff_image_path  = diff_path,
        compared_width   = NORM_W,
        compared_height  = NORM_H,
    )

    logger.info(
        "Pixel diff result for %r: %s | gpt4o_needed=%s",
        report_name, result, result.should_call_gpt4o,
    )

    return result
"""
Centralized configuration for MigrateIQ.

All tuneable values are read from environment variables so you can
override them via a `.env` file (loaded automatically if python-dotenv
is installed) or by exporting them in your shell before running.

Usage:
    import config
    print(config.OUTPUT_DIR)            # PosixPath / WindowsPath
    print(config.TOLERANCE_PCT)         # float
    print(config.OPENAI_API_KEY)        # str
    print(config.PIXEL_PASS_THRESHOLD)  # float
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Server / Environment settings
# ---------------------------------------------------------------------------
BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
DB_URL:   str = os.getenv("DB_URL", "sqlite:///migrateiq.db")

# ---------------------------------------------------------------------------
# Optionally load a .env file (silently ignored if python-dotenv is absent)
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_ENV_PATH, override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on shell environment variables


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

# OpenAI API key — used by the GPT-4o visual analyser (Layer 1).
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Anthropic API key — used by the Claude semantic auditor (Layer 2).
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# Azure OpenAI (optional — used instead of OpenAI when endpoint is set)
# ---------------------------------------------------------------------------
# Azure endpoint, e.g. https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")

# Azure API key (from Azure AI Foundry → Keys and Endpoint)
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")

# Name of the GPT-4o deployment you created in Azure AI Foundry
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# Azure OpenAI API version
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# SQLite URL; can be overridden for testing or production (e.g. PostgreSQL URL).
DB_URL: str = os.getenv("DB_URL", "sqlite:///migrateiq.db")


# ---------------------------------------------------------------------------
# AI Model identifiers
# ---------------------------------------------------------------------------

# Claude model used for semantic audits (Layer 2).
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# GPT-4o model used for visual analysis (Layer 1).
GPT4O_MODEL: str = os.getenv("GPT4O_MODEL", "gpt-4o")


# ---------------------------------------------------------------------------
# Claude generation settings
# ---------------------------------------------------------------------------

# Maximum output tokens for Claude audit responses.
CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "1500"))


# ---------------------------------------------------------------------------
# GPT-4o generation settings
# ---------------------------------------------------------------------------

# Maximum output tokens for GPT-4o vision responses.
GPT4O_MAX_TOKENS: int = int(os.getenv("GPT4O_MAX_TOKENS", "1000"))

# Sampling temperature for GPT-4o.
# Low value (0.1) → factual, consistent, less hallucination.
GPT4O_TEMPERATURE: float = float(os.getenv("GPT4O_TEMPERATURE", "0.1"))


# ---------------------------------------------------------------------------
# Pixel-diff thresholds (Layer 1 visual comparison)
# ---------------------------------------------------------------------------

# Normalisation target resolution for screenshot comparison.
PIXEL_NORM_W: int = int(os.getenv("PIXEL_NORM_W", "1280"))
PIXEL_NORM_H: int = int(os.getenv("PIXEL_NORM_H", "960"))

# A pixel is "different" if any RGB channel differs by more than this value.
# 10 filters out sub-pixel anti-aliasing noise from font rendering.
PIXEL_CHANNEL_THRESHOLD: int = int(os.getenv("PIXEL_CHANNEL_THRESHOLD", "10"))

# GPT-4o Vision is called only when pixel similarity falls BELOW this threshold.
# 98 % means ~25 000 pixels may differ before we bother calling the API.
PIXEL_GPT4O_CALL_THRESHOLD: float = float(os.getenv("PIXEL_GPT4O_CALL_THRESHOLD", "98.0"))

# Similarity band boundaries for the PASS / REVIEW / FAIL decision.
PIXEL_PASS_THRESHOLD: float   = float(os.getenv("PIXEL_PASS_THRESHOLD",   "95.0"))
PIXEL_REVIEW_THRESHOLD: float = float(os.getenv("PIXEL_REVIEW_THRESHOLD", "80.0"))


# ---------------------------------------------------------------------------
# Semantic field-matching (Layer 2)
# ---------------------------------------------------------------------------

# Minimum SequenceMatcher ratio to treat a Tableau field name and a DAX measure
# name as a match.  0.6 catches common renamings (e.g. "Profit Ratio" →
# "ProfitRatio") while avoiding false positives.
FIELD_NAME_MATCH_THRESHOLD: float = float(os.getenv("FIELD_NAME_MATCH_THRESHOLD", "0.6"))


# ---------------------------------------------------------------------------
# Output configuration
# ---------------------------------------------------------------------------

# Directory where all JSON result files are stored
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output_json"))

# Default filename used when no explicit output path is supplied
DEFAULT_OUTPUT_FILENAME: str = os.getenv(
    "DEFAULT_OUTPUT_FILENAME", "comparison_result.json"
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Verbose mode — equivalent to passing --verbose on the CLI
VERBOSE: bool = os.getenv("VERBOSE", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Comparator settings
# ---------------------------------------------------------------------------

# Acceptable percentage difference for numeric row-count comparisons
TOLERANCE_PCT: float = float(os.getenv("TOLERANCE_PCT", "0.5"))

# Case-sensitive column / table name comparison (default: case-insensitive)
CASE_SENSITIVE_COMPARISON: bool = (
    os.getenv("CASE_SENSITIVE_COMPARISON", "false").lower() == "true"
)

# Relationship matching strictness: 0 = lenient, 1 = strict
RELATIONSHIP_STRICTNESS: int = int(os.getenv("RELATIONSHIP_STRICTNESS", "0"))

# Data-type matching strictness: 0 = lenient (int/decimal same), 1 = strict
TYPE_MATCHING_STRICTNESS: int = int(os.getenv("TYPE_MATCHING_STRICTNESS", "1"))


# ---------------------------------------------------------------------------
# Parser settings
# ---------------------------------------------------------------------------

# Enable Hyper database extraction (Tableau)
ENABLE_HYPER: bool = os.getenv("ENABLE_HYPER", "true").lower() == "true"

# Fall back to CSV when Hyper is unavailable
ENABLE_CSV_FALLBACK: bool = (
    os.getenv("ENABLE_CSV_FALLBACK", "true").lower() == "true"
)

# Enable detailed SQL / DAX expression parsing
DEEP_EXPRESSION_PARSING: bool = (
    os.getenv("DEEP_EXPRESSION_PARSING", "false").lower() == "true"
)


# ---------------------------------------------------------------------------
# Performance settings
# ---------------------------------------------------------------------------

# Maximum file size to process (MB)
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "5000"))

# Timeout for file operations (seconds)
TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "300"))

# Keep temporary extraction folders after processing
KEEP_TEMP_FILES: bool = (
    os.getenv("KEEP_TEMP_FILES", "false").lower() == "true"
)

# Optional path to a custom temporary directory (empty = system default)
TEMP_DIR: str = os.getenv("TEMP_DIR", "")


# ---------------------------------------------------------------------------
# Notification / archive settings (optional integrations)
# ---------------------------------------------------------------------------

NOTIFY_ON_FAIL: bool = os.getenv("NOTIFY_ON_FAIL", "false").lower() == "true"
NOTIFICATION_EMAIL: str = os.getenv("NOTIFICATION_EMAIL", "")
NOTIFICATION_WEBHOOK: str = os.getenv("NOTIFICATION_WEBHOOK", "")

ARCHIVE_RESULTS: bool = os.getenv("ARCHIVE_RESULTS", "true").lower() == "true"
ARCHIVE_FORMAT: str = os.getenv("ARCHIVE_FORMAT", "gzip")  # gzip | zip | tar


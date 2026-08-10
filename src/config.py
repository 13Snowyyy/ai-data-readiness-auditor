"""Configuration and environment handling for the AI Data Readiness Auditor.

This module centralizes app settings, folder paths, and LLM provider
detection. It never prints or exposes API keys. The app defaults to
Template Engine Mode and only reports whether an LLM key *exists* -- it
never returns the key value itself.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_NAME = "AI Data Readiness Auditor"
APP_TAGLINE = "Clean the data before trusting the dashboard."
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Folder paths (created on demand by ensure_folders)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SAMPLE_DIR = PROJECT_ROOT / "sample_files"
DB_PATH = DATA_DIR / "data_readiness.db"
SAMPLE_CSV = SAMPLE_DIR / "sample_messy_dataset.csv"
ENV_FILE = PROJECT_ROOT / ".env"


# ---------------------------------------------------------------------------
# Optional .env support (no external dependency)
# ---------------------------------------------------------------------------
def load_dotenv(path: Path = ENV_FILE) -> None:
    """Load simple KEY=VALUE lines from a local .env file into os.environ.

    Existing environment variables always win, so real system/session
    variables are never overwritten. Missing file = no-op. Never raises.
    """
    try:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Quoted values are taken literally; unquoted values have any
            # trailing "# inline comment" removed (so a pasted example line
            # like `LLM_MODEL=my-model   # note` yields just `my-model`).
            if value[:1] in ("'", '"'):
                quote = value[0]
                end = value.find(quote, 1)
                value = value[1:end] if end != -1 else value[1:]
            else:
                hash_idx = value.find("#")
                if hash_idx != -1:
                    value = value[:hash_idx]
                value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value
    except OSError:
        # A malformed or unreadable .env should never break the app.
        return


# Load once at import so keys in .env are available to the whole app.
load_dotenv()

# ---------------------------------------------------------------------------
# Generation mode labels
# ---------------------------------------------------------------------------
MODE_TEMPLATE = "Template Engine Mode"
MODE_LLM = "LLM Enhanced Mode"

# ---------------------------------------------------------------------------
# Audit thresholds (tunable defaults)
# ---------------------------------------------------------------------------
MISSING_COLUMN_THRESHOLD = 0.30      # column flagged if >30% missing
ROW_MISSING_THRESHOLD = 0.50         # row flagged if >50% of its fields missing
HIGH_CARDINALITY_RATIO = 0.50        # unique/rows above this = high cardinality
OUTLIER_IQR_MULTIPLIER = 1.5         # IQR multiplier for outlier detection
MIN_RECORDS_FOR_ANALYSIS = 30        # minimum rows for meaningful analysis

# Values that look blank/placeholder even though they are not truly null.
BLANK_LIKE_VALUES = {
    "n/a", "na", "none", "null", "nil", "unknown", "unk", "-", "--",
    "tbd", "tba", "?", "??", "n.a.", "not available", "not applicable", "",
}

# Provider environment variable names. We only check for *presence*.
PROVIDER_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

# Default model per provider (override with the LLM_MODEL environment variable).
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "azure_openai": "",  # Azure uses a deployment name instead (see get_model).
    "claude": "claude-3-5-sonnet-latest",
}

# Base URLs for OpenAI-compatible chat-completions APIs. Claude and Azure are
# handled separately because they use different endpoints/auth.
OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


def ensure_folders() -> None:
    """Create required working folders if they do not already exist."""
    for folder in (DATA_DIR, OUTPUTS_DIR, SAMPLE_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def get_selected_provider() -> str:
    """Return the configured LLM provider name (lowercased) or a default."""
    return os.environ.get("LLM_PROVIDER", "").strip().lower()


def has_api_key() -> bool:
    """Return True if any usable LLM API key is present in the environment.

    Only a boolean is returned -- the key value is never exposed.
    """
    # Generic key applies to whatever provider is selected.
    if os.environ.get("LLM_API_KEY", "").strip():
        return True

    provider = get_selected_provider()
    if provider and provider in PROVIDER_ENV_KEYS:
        if os.environ.get(PROVIDER_ENV_KEYS[provider], "").strip():
            return True

    # Fall back to checking any known provider key.
    return any(
        os.environ.get(env_name, "").strip()
        for env_name in PROVIDER_ENV_KEYS.values()
    )


def llm_mode_available() -> bool:
    """LLM Enhanced Mode is available only when an API key is configured."""
    return has_api_key()


def get_active_provider() -> str:
    """Resolve which provider to use from the environment.

    Priority: an explicit ``LLM_PROVIDER`` (if recognized) wins. Otherwise, if a
    generic ``LLM_API_KEY`` is set the provider defaults to OpenAI, and finally
    we infer the provider from whichever provider-specific key is present.
    Returns "" when nothing is configured.
    """
    provider = get_selected_provider()
    if provider in PROVIDER_ENV_KEYS:
        return provider
    if os.environ.get("LLM_API_KEY", "").strip():
        return provider or "openai"
    for name, env_name in PROVIDER_ENV_KEYS.items():
        if os.environ.get(env_name, "").strip():
            return name
    return provider


def get_api_key_env_name(provider: str) -> str:
    """Return the *name* of the env var holding the key (never its value)."""
    if os.environ.get("LLM_API_KEY", "").strip():
        return "LLM_API_KEY"
    return PROVIDER_ENV_KEYS.get(provider, "")


def get_model(provider: str) -> str:
    """Return the model/deployment to use for a provider.

    ``LLM_MODEL`` overrides everything. For Azure OpenAI the value is the
    deployment name (``LLM_MODEL`` or ``AZURE_OPENAI_DEPLOYMENT``).
    """
    override = os.environ.get("LLM_MODEL", "").strip()
    if override:
        return override
    if provider == "azure_openai":
        return os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
    return DEFAULT_MODELS.get(provider, "")


def get_base_url(provider: str) -> str:
    """Return the OpenAI-compatible base URL, honoring an ``LLM_BASE_URL`` override."""
    override = os.environ.get("LLM_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider, "")

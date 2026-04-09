"""
config.py — Loads and validates all environment variables from .env
Production-ready, schema-aware configuration.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
# Expected path: project_root/config/.env
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
load_dotenv(dotenv_path=_env_path)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _require(key: str) -> str:
    """Fetch a required env variable or raise a descriptive error."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value.strip()


def _optional(key: str, default: str = "") -> str:
    """Fetch an optional env variable with default fallback."""
    return os.getenv(key, default).strip()


def _optional_int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _optional_float(key: str, default: float) -> float:
    return float(os.getenv(key, default))


def _optional_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() == "true"


# ── Settings Dataclass ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_embedding_deployment: str
    azure_openai_chat_deployment: str

    # ── Azure AI Search ───────────────────────────────────────────────────────
    azure_search_endpoint: str
    azure_search_index: str
    azure_search_api_key: str
    azure_search_top_k: int

    # 🔥 Schema-aware fields (VERY IMPORTANT for RAG)
    azure_search_content_field: str
    azure_search_vector_field: str
    azure_search_title_field: str

    # ── Server ────────────────────────────────────────────────────────────────
    api_bind_host: str
    api_advertised_host: str
    api_port: int
    api_reload: bool

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_temperature: float
    llm_max_tokens: int

    # ── App ───────────────────────────────────────────────────────────────────
    debug: bool
    log_level: str


# ── Load & Validate Settings ─────────────────────────────────────────────────
def load_settings() -> Settings:
    """Build and return a validated Settings instance."""

    settings = Settings(
        # ── Azure OpenAI ──────────────────────────────────────────────────────
        azure_openai_api_key=_require("AZURE_OPENAI_API_KEY"),
        azure_openai_endpoint=_require("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_version=_optional("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_openai_embedding_deployment=_optional(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"
        ),
        azure_openai_chat_deployment=_optional(
            "AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4"
        ),

        # ── Azure AI Search ───────────────────────────────────────────────────
        azure_search_endpoint=_require("AZURE_SEARCH_ENDPOINT"),
        azure_search_index=_require("AZURE_SEARCH_INDEX"),
        azure_search_api_key=_require("AZURE_SEARCH_API_KEY"),
        azure_search_top_k=_optional_int("AZURE_SEARCH_TOP_K", 5),

        # 🔥 Schema-aware fields (match your index!)
        azure_search_content_field=_optional("AZURE_SEARCH_CONTENT_FIELD", "chunk"),
        azure_search_vector_field=_optional("AZURE_SEARCH_VECTOR_FIELD", "text_vector"),
        azure_search_title_field=_optional("AZURE_SEARCH_TITLE_FIELD", "title"),

        # ── Server ────────────────────────────────────────────────────────────
        api_bind_host=_optional("API_BIND_HOST", "0.0.0.0"),
        api_advertised_host=_optional("API_ADVERTISED_HOST", "localhost"),
        api_port=_optional_int("API_PORT", 50505),
        api_reload=_optional_bool("API_RELOAD", False),

        # ── LLM ──────────────────────────────────────────────────────────────
        llm_temperature=_optional_float("LLM_TEMPERATURE", 0.0),
        llm_max_tokens=_optional_int("LLM_MAX_TOKENS", 2000),

        # ── App ──────────────────────────────────────────────────────────────
        debug=_optional_bool("DEBUG", False),
        log_level=_optional("LOG_LEVEL", "INFO"),
    )

    # ── Validations (Production Safety) ───────────────────────────────────────

    # ✅ Endpoint validation
    if not settings.azure_openai_endpoint.startswith("https://"):
        raise ValueError("AZURE_OPENAI_ENDPOINT must start with 'https://'")

    if not settings.azure_search_endpoint.startswith("https://"):
        raise ValueError("AZURE_SEARCH_ENDPOINT must start with 'https://'")

    # ✅ Numeric validations
    if settings.azure_search_top_k <= 0:
        raise ValueError("AZURE_SEARCH_TOP_K must be greater than 0")

    if settings.llm_max_tokens <= 0:
        raise ValueError("LLM_MAX_TOKENS must be greater than 0")

    if not (0.0 <= settings.llm_temperature <= 2.0):
        raise ValueError("LLM_TEMPERATURE must be between 0.0 and 2.0")

    # ✅ Log level validation
    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if settings.log_level.upper() not in valid_log_levels:
        raise ValueError(f"LOG_LEVEL must be one of {valid_log_levels}")

    return settings


# ── Singleton instance ───────────────────────────────────────────────────────
settings: Settings = load_settings()
"""
Runtime Configuration & LLM Provider Resolution.

Supports:
- Google Cloud Vertex AI via Application Default Credentials (ADC)
- Google Gemini Developer API via GEMINI_API_KEY
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Ensure .env is ingested into os.environ
load_dotenv()


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model_identifier: str
    project_id: str | None = None
    location: str | None = None
    api_key: str | None = None


def get_provider_config(override_model: str | None = None) -> ProviderConfig:
    """
    Resolves active provider settings and LiteLLM model string from environment.
    
    If override_model is provided, preserves it while configuring required
    provider environment variables (e.g. project/location for Vertex AI).
    """
    provider = os.getenv("LLM_PROVIDER", "").lower().strip()
    use_vertex = (
        provider == "vertex"
        or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
        or bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    )

    if use_vertex:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT", "")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION", "global")
        raw_model = override_model or os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

        # Set LiteLLM Vertex AI environment variables so ADC routes correctly
        if project_id:
            os.environ["VERTEXAI_PROJECT"] = project_id
        if location:
            os.environ["VERTEXAI_LOCATION"] = location

        # Format model string for LiteLLM if not already prefixed
        if not raw_model.startswith("vertex_ai/"):
            model_identifier = f"vertex_ai/{raw_model}"
        else:
            model_identifier = raw_model

        return ProviderConfig(
            provider="vertex",
            model_identifier=model_identifier,
            project_id=project_id,
            location=location,
            api_key=None,
        )
    else:
        raw_model = override_model or os.getenv("MODEL_NAME", "gemini-2.5-flash")
        if not raw_model.startswith("gemini/") and "/" not in raw_model:
            model_identifier = f"gemini/{raw_model}"
        else:
            model_identifier = raw_model

        api_key = os.getenv("GEMINI_API_KEY")

        return ProviderConfig(
            provider="gemini",
            model_identifier=model_identifier,
            project_id=None,
            location=None,
            api_key=api_key,
        )

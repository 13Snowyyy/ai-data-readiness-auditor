"""LLM Enhanced Mode provider.

Generates the data-readiness narrative with a hosted LLM selected entirely by
environment variables. Supports OpenAI-compatible APIs (OpenAI, Groq,
OpenRouter, Gemini's compatibility endpoint), Azure OpenAI, and Anthropic
Claude.

Design guarantees:
- No API key is required to import, instantiate, or run the app.
- Keys are read from ``os.environ`` only and are never logged or hardcoded.
- If no key is configured, or any error occurs, it falls back transparently to
  Template Engine Mode and reports why.
- Only the standard library is used for the HTTP call (``urllib``), so no extra
  dependencies are required.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .. import config
from .base_provider import BaseProvider
from .template_provider import TemplateProvider

# Narrative keys the LLM is asked to produce. Structured, field-derived keys
# (data dictionary, chart gallery, dashboard pages) stay deterministic locally.
_NARRATIVE_KEYS = (
    "executive_summary",
    "biggest_risks",
    "cleanup_recommendations",
    "suggested_charts",
    "suggested_business_questions",
    "suggested_next_steps",
    "final_summary",
)

_LIST_KEYS = {
    "biggest_risks",
    "cleanup_recommendations",
    "suggested_charts",
    "suggested_business_questions",
    "suggested_next_steps",
}

_HTTP_TIMEOUT = 60  # seconds


class LLMProvider(BaseProvider):
    """Provider that calls a hosted LLM, with automatic template fallback."""

    mode_name = config.MODE_LLM

    def __init__(self, provider_name: str = "") -> None:
        override = (provider_name or "").strip().lower()
        self.provider_name = override or config.get_active_provider()
        # Never store or log the key value -- only whether one exists.
        self._has_key = config.has_api_key()
        self._fallback = TemplateProvider()
        self._last_error: str = ""

    # ------------------------------------------------------------------
    # Prompt construction (future-ready)
    # ------------------------------------------------------------------
    def build_prompt(
        self,
        input_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        quality: Dict[str, Any],
        dashboard: Dict[str, Any],
    ) -> str:
        """Build a structured prompt for a future LLM call.

        The prompt asks the model to produce a professional, business-friendly
        data readiness narrative grounded strictly in the provided audit facts.
        """
        # Compact, fact-only context so the model cannot invent numbers.
        context = {
            "dataset_metadata": {
                k: input_data.get(k, "")
                for k in (
                    "dataset_name", "dataset_owner", "business_question",
                    "intended_audience", "intended_use",
                )
            },
            "shape": audit_results["shape"],
            "data_quality_score": quality["score"],
            "data_quality_status": quality["status"],
            "dashboard_readiness_score": dashboard["score"],
            "dashboard_readiness_status": dashboard["status"],
            "column_types": audit_results["types"]["type_counts"],
            "missing_summary": {
                "overall_missing_pct": audit_results["missing"]["overall_missing_pct"],
                "effective_missing_pct": audit_results["missing"]["effective_missing_pct"],
                "flagged_columns": audit_results["missing"]["flagged_columns"],
            },
            "duplicate_summary": audit_results["duplicates"],
            "category_issue_columns": audit_results["categories"]["columns_with_issues"],
            "date_reports": audit_results["dates"]["reports"],
            "numeric_reports": audit_results["numeric"]["reports"],
            "issue_log": audit_results["issue_log"],
        }

        instructions = (
            "You are a senior data quality and business intelligence consultant. "
            "Using ONLY the audit facts provided, write a professional data "
            "readiness narrative. Your response MUST:\n"
            "1. Summarize the overall dataset quality.\n"
            "2. Explain the biggest data risks.\n"
            "3. Explain dashboard readiness.\n"
            "4. State clearly whether the dataset is safe for decision-making.\n"
            "5. Suggest concrete cleanup actions.\n"
            "6. Suggest relevant business questions.\n"
            "7. Suggest dashboard ideas.\n"
            "8. Avoid making unsupported claims or inventing numbers.\n"
            "9. Clearly distinguish DETECTED ISSUES from RECOMMENDATIONS.\n"
            "10. Use concise, business-friendly language.\n\n"
            "OUTPUT FORMAT: Respond with ONLY a single valid JSON object and "
            "nothing else -- no explanations, no markdown, no code fences. "
            "executive_summary and final_summary are strings; biggest_risks, "
            "cleanup_recommendations, suggested_charts, "
            "suggested_business_questions, and suggested_next_steps are arrays "
            "of short strings. Use exactly these keys: "
            "executive_summary, biggest_risks, cleanup_recommendations, "
            "suggested_charts, suggested_business_questions, suggested_next_steps, "
            "final_summary."
        )

        return (
            f"{instructions}\n\n"
            f"AUDIT FACTS (JSON):\n{json.dumps(context, indent=2, default=str)}\n"
        )

    # ------------------------------------------------------------------
    # HTTP helpers (standard library only)
    # ------------------------------------------------------------------
    @staticmethod
    def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST JSON and return the parsed JSON response. Raises on failure."""
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        for name, value in headers.items():
            request.add_header(name, value)
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON object from model text, tolerating prose or code fences."""
        text = (text or "").strip()
        if not text:
            return None
        # Prefer the contents of a ```json ... ``` (or plain ```) code fence.
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        else:
            text = text.replace("```", "").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        # Fast path: the whole string is already valid JSON.
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Extract the first balanced {...} object, ignoring braces in strings.
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        # Last resort: first "{" through last "}".
        end = text.rfind("}")
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None

    def _openai_compatible_call(
        self, base_url: str, api_key: str, model: str, prompt: str,
    ) -> str:
        """Call an OpenAI-compatible /chat/completions endpoint; return the content."""
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            data = self._post_json(url, headers, payload)
        except urllib.error.HTTPError as exc:
            # Some models reject response_format -> retry once without it.
            if exc.code == 400:
                payload.pop("response_format", None)
                data = self._post_json(url, headers, payload)
            else:
                raise
        return data["choices"][0]["message"]["content"]

    def _azure_call(self, api_key: str, deployment: str, prompt: str) -> str:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set.")
        if not deployment:
            raise RuntimeError(
                "Azure deployment name is not set (LLM_MODEL / AZURE_OPENAI_DEPLOYMENT)."
            )
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01").strip()
        url = (
            f"{endpoint}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={api_version}"
        )
        headers = {"api-key": api_key}
        payload: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            data = self._post_json(url, headers, payload)
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                payload.pop("response_format", None)
                data = self._post_json(url, headers, payload)
            else:
                raise
        return data["choices"][0]["message"]["content"]

    def _anthropic_call(self, api_key: str, model: str, prompt: str) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        payload = {
            "model": model,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = self._post_json(url, headers, payload)
        blocks = data.get("content", [])
        return blocks[0]["text"] if blocks else ""

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------
    def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call the configured provider and return a parsed narrative dict.

        Returns None on any failure and records a human-readable reason in
        ``self._last_error`` so the caller can surface it and fall back.
        """
        provider = self.provider_name
        env_name = config.get_api_key_env_name(provider)
        api_key = os.environ.get(env_name, "").strip() if env_name else ""
        if not api_key:
            self._last_error = "No API key found in the environment for the selected provider."
            return None

        model = config.get_model(provider)
        if not model:
            self._last_error = f"No model configured for provider '{provider}' (set LLM_MODEL)."
            return None

        try:
            if provider == "claude":
                content = self._anthropic_call(api_key, model, prompt)
            elif provider == "azure_openai":
                content = self._azure_call(api_key, model, prompt)
            else:
                base_url = config.get_base_url(provider)
                if not base_url:
                    self._last_error = f"No base URL configured for provider '{provider}'."
                    return None
                content = self._openai_compatible_call(base_url, api_key, model, prompt)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:300]
            except Exception:
                pass
            self._last_error = f"{provider} API returned HTTP {exc.code}. {detail}".strip()
            return None
        except urllib.error.URLError as exc:
            self._last_error = f"Could not reach the {provider} API: {exc.reason}."
            return None
        except (KeyError, IndexError, TypeError) as exc:
            self._last_error = f"Unexpected response shape from {provider}: {exc}."
            return None
        except Exception as exc:  # last-resort guard so the app never crashes
            self._last_error = f"LLM call failed ({provider}): {exc}."
            return None

        parsed = self._extract_json_object(content)
        if parsed is None:
            self._last_error = f"The {provider} response was not valid JSON."
            return None
        return parsed

    # ------------------------------------------------------------------
    # Normalization + fallback
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(result: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce LLM output into the shapes the UI expects."""
        clean: Dict[str, Any] = {}
        for key in _NARRATIVE_KEYS:
            if key not in result or result[key] in (None, ""):
                continue
            value = result[key]
            if key in _LIST_KEYS:
                if isinstance(value, str):
                    value = [value]
                elif isinstance(value, list):
                    value = [str(v).strip() for v in value if str(v).strip()]
                else:
                    value = [str(value)]
            else:
                value = str(value).strip()
            clean[key] = value
        return clean

    def _template_package(
        self, input_data, audit_results, quality, dashboard, error: str = "",
    ) -> Dict[str, Any]:
        package = self._fallback.generate_data_readiness_narrative(
            input_data, audit_results, quality, dashboard
        )
        package["generation_mode"] = config.MODE_TEMPLATE
        package["llm_fallback"] = True
        if error:
            package["llm_error"] = error
        return package

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def generate_data_readiness_narrative(
        self,
        input_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        quality: Dict[str, Any],
        dashboard: Dict[str, Any],
    ) -> Dict[str, Any]:
        # No key configured -> Template Engine Mode (expected, not an error).
        if not self._has_key:
            return self._template_package(input_data, audit_results, quality, dashboard)

        prompt = self.build_prompt(input_data, audit_results, quality, dashboard)
        result = self._call_llm(prompt)
        if not result:
            return self._template_package(
                input_data, audit_results, quality, dashboard, self._last_error
            )

        # Start from the deterministic template package so structured, field-
        # derived sections (data dictionary, chart gallery, dashboard pages) are
        # always present and grounded, then overlay the LLM narrative on top.
        package = self._fallback.generate_data_readiness_narrative(
            input_data, audit_results, quality, dashboard
        )
        package.update(self._normalize(result))
        package["generation_mode"] = self.mode_name
        package["llm_fallback"] = False
        package["llm_provider"] = self.provider_name
        package["llm_model"] = config.get_model(self.provider_name)
        return package

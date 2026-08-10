"""Provider interface definition."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseProvider(ABC):
    """Common interface every generation provider must implement."""

    #: Human-readable mode name shown in the UI.
    mode_name: str = "Base Provider"

    @abstractmethod
    def generate_data_readiness_narrative(
        self,
        input_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        quality: Dict[str, Any],
        dashboard: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return a narrative package dictionary.

        Args:
            input_data: User-provided metadata (dataset name, owner, etc.).
            audit_results: Output of ``audit_engine.run_audit``.
            quality: Output of ``scoring.score_data_quality``.
            dashboard: Output of ``scoring.score_dashboard_readiness``.

        Returns:
            A dictionary with the narrative sections (see template_engine).
        """
        raise NotImplementedError

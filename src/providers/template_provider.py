"""Template Engine Mode provider -- the default, offline generator."""

from __future__ import annotations

from typing import Any, Dict

from .. import config, template_engine
from .base_provider import BaseProvider


class TemplateProvider(BaseProvider):
    """Generate the narrative package using local templates only.

    This provider requires no API key and no internet access.
    """

    mode_name = config.MODE_TEMPLATE

    def generate_data_readiness_narrative(
        self,
        input_data: Dict[str, Any],
        audit_results: Dict[str, Any],
        quality: Dict[str, Any],
        dashboard: Dict[str, Any],
    ) -> Dict[str, Any]:
        package = template_engine.generate_package(
            audit_results, quality, dashboard, input_data
        )
        package["generation_mode"] = self.mode_name
        return package

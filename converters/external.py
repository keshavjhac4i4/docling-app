"""Adapters for legacy standalone scripts implementing Markdown → JSON conversion."""

from __future__ import annotations

import importlib.util
import inspect
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Dict, Optional, Sequence

from .base import (
    BaseReportConverter,
    ConversionSettings,
    DetectionContext,
    DetectionResult,
    ReportConversionError,
)


@dataclass(frozen=True)
class ScriptSpec:
    """Declarative specification describing a report converter script."""

    report_id: str
    display_name: str
    description: str
    script_path: Path
    entrypoint: str
    keywords: Sequence[str] = field(default_factory=tuple)


class ExternalScriptConverter(BaseReportConverter):
    """Adapter that executes an external Python script's extraction function."""

    def __init__(self, spec: ScriptSpec) -> None:
        self._spec = spec
        self.report_id = spec.report_id
        self.display_name = spec.display_name
        self.description = spec.description
        self.keywords = tuple(spec.keywords)
        self._module: Optional[ModuleType] = None
        self._module_lock = threading.Lock()
        super().__init__()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, context: DetectionContext) -> Optional[DetectionResult]:
        if not self.keywords:
            return None

        text = context.markdown.lower()
        filename = (context.original_filename or "").lower()

        matched: Dict[str, int] = {}
        for keyword in self.keywords:
            kw = keyword.lower()
            occurrences = text.count(kw)
            if occurrences > 0:
                matched[keyword] = occurrences
            elif kw and kw in filename:
                matched[keyword] = matched.get(keyword, 0) + 1

        if not matched:
            return None

        score = float(sum(matched.values()))
        return DetectionResult(score=score, matched_keywords=list(matched.keys()))

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------
    def convert(
        self,
        markdown: str,
        markdown_path: Path,
        settings: ConversionSettings,
    ) -> Dict[str, object]:
        module = self._load_module()

        if not hasattr(module, self._spec.entrypoint):
            raise ReportConversionError(
                f"Converter entrypoint '{self._spec.entrypoint}' missing in {self._spec.script_path}"
            )

        entrypoint = getattr(module, self._spec.entrypoint)

        if not callable(entrypoint):
            raise ReportConversionError(
                f"Converter entrypoint '{self._spec.entrypoint}' is not callable."
            )

        kwargs = self._build_kwargs(entrypoint, markdown_path, settings)

        try:
            result = entrypoint(**kwargs)
        except Exception as exc:  # pragma: no cover - delegated scripts may raise anything
            raise ReportConversionError(
                f"Converter '{self.report_id}' failed: {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise ReportConversionError(
                f"Converter '{self.report_id}' must return a dict, got {type(result)!r}."
            )

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_module(self) -> ModuleType:
        with self._module_lock:
            if self._module is not None:
                return self._module

            script_path = self._spec.script_path
            if not script_path.exists():
                raise ReportConversionError(
                    f"Converter script not found: {script_path}"
                )

            module_name = f"docling_converter_{self.report_id}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            if spec is None or spec.loader is None:
                raise ReportConversionError(
                    f"Unable to load converter script: {script_path}"
                )

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._module = module
            return module

    @staticmethod
    def _build_kwargs(entrypoint, markdown_path: Path, settings: ConversionSettings) -> Dict[str, object]:
        signature = inspect.signature(entrypoint)
        kwargs: Dict[str, object] = {}

        for name, param in signature.parameters.items():
            if name == "md_file_path":
                kwargs[name] = str(markdown_path)
            elif name == "model":
                kwargs[name] = settings.ollama_model
            elif name in {"ollama_url", "ollama_base_url"}:
                kwargs[name] = settings.ollama_url
            elif param.default is param.empty:
                raise ReportConversionError(
                    f"Converter entrypoint requires unsupported parameter '{name}'."
                )

        return kwargs


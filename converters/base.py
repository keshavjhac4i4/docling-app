"""Base types for report-specific Markdown → JSON conversion plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class DetectionContext:
    """Context passed into converter detection heuristics."""

    markdown: str
    original_filename: Optional[str] = None


@dataclass(frozen=True)
class DetectionResult:
    """Result returned by a converter's detection routine."""

    score: float
    matched_keywords: Sequence[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "score": self.score,
            "matched_keywords": list(self.matched_keywords),
        }


@dataclass(frozen=True)
class ConversionSettings:
    """Runtime configuration for JSON conversion."""

    ollama_url: str
    ollama_model: str


@dataclass(frozen=True)
class ConversionResult:
    """Structured result produced by a converter implementation."""

    report_id: str
    display_name: str
    data: Dict[str, object]
    score: float
    matched_keywords: Sequence[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "report_id": self.report_id,
            "display_name": self.display_name,
            "data": self.data,
            "score": self.score,
            "matched_keywords": list(self.matched_keywords),
        }


class ReportConversionError(Exception):
    """Base exception for converter failures."""


class BaseReportConverter(ABC):
    """Abstract base class for Markdown → JSON report converters."""

    report_id: str
    display_name: str
    description: str
    keywords: Sequence[str]

    def __init__(self) -> None:
        if not getattr(self, "report_id", None):
            raise ValueError("Converter must define 'report_id'.")
        if not getattr(self, "display_name", None):
            raise ValueError("Converter must define 'display_name'.")

    @abstractmethod
    def detect(self, context: DetectionContext) -> Optional[DetectionResult]:
        """Return a score indicating how likely this converter matches the given markdown."""

    @abstractmethod
    def convert(
        self,
        markdown: str,
        markdown_path: Path,
        settings: ConversionSettings,
    ) -> Dict[str, object]:
        """Perform conversion and return JSON-serialisable data."""


@dataclass(frozen=True)
class ReportDescriptor:
    """Metadata describing a registered report converter."""

    report_id: str
    display_name: str
    description: str
    keywords: Sequence[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "id": self.report_id,
            "name": self.display_name,
            "description": self.description,
            "keywords": list(self.keywords),
        }


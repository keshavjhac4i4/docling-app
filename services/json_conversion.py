"""Service layer orchestrating Markdown → JSON conversion."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from converters import (
    ReportDescriptor,
    get_converter_by_id,
    get_converter_registry,
    list_report_descriptors,
)
from converters.base import (
    ConversionResult,
    ConversionSettings,
    DetectionContext,
    DetectionResult,
    ReportConversionError,
)


class UnknownReportError(Exception):
    """Raised when a supplied report_id does not exist."""


@dataclass
class ReportCandidate:
    report_id: str
    display_name: str
    score: float
    matched_keywords: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "id": self.report_id,
            "name": self.display_name,
            "score": self.score,
            "matched_keywords": list(self.matched_keywords),
        }


class ReportDetectionError(Exception):
    """Raised when converters cannot be uniquely determined."""

    def __init__(self, message: str, candidates: Optional[List[ReportCandidate]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.candidates = candidates or []


@dataclass
class JsonConversionOutcome:
    report_id: str
    display_name: str
    data: Dict[str, object]
    score: float
    matched_keywords: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "report_id": self.report_id,
            "display_name": self.display_name,
            "score": self.score,
            "matched_keywords": list(self.matched_keywords),
            "data": self.data,
        }


def _default_settings() -> ConversionSettings:
    return ConversionSettings(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
    )


def list_available_reports() -> List[Dict[str, object]]:
    """Return metadata about all registered report converters."""

    return [descriptor.as_dict() for descriptor in list_report_descriptors()]


def convert_markdown_to_json(
    markdown: str,
    *,
    report_id: Optional[str] = None,
    original_filename: Optional[str] = None,
    settings: Optional[ConversionSettings] = None,
) -> JsonConversionOutcome:
    """Convert markdown to JSON using a matching report converter."""

    if settings is None:
        settings = _default_settings()

    if report_id:
        converter = _get_converter_or_raise(report_id)
        detection_result = converter.detect(
            DetectionContext(markdown=markdown, original_filename=original_filename)
        )
        detection_score = detection_result.score if detection_result else 0.0
        matched_keywords = list(detection_result.matched_keywords) if detection_result else []
    else:
        converter, detection_score, matched_keywords = _auto_detect_converter(
            markdown, original_filename
        )

    conversion_result = _run_converter(converter, markdown, settings)

    return JsonConversionOutcome(
        report_id=converter.report_id,
        display_name=converter.display_name,
        data=conversion_result,
        score=detection_score,
        matched_keywords=matched_keywords,
    )


def _get_converter_or_raise(report_id: str):
    try:
        return get_converter_by_id(report_id)
    except KeyError as exc:  # pragma: no cover - sanity path
        raise UnknownReportError(f"Report '{report_id}' is not registered.") from exc


def _auto_detect_converter(markdown: str, original_filename: Optional[str]):
    registry = get_converter_registry()
    context = DetectionContext(markdown=markdown, original_filename=original_filename)

    results: List[ReportCandidate] = []
    for converter in registry.values():
        detection = converter.detect(context)
        if detection and detection.score > 0:
            results.append(
                ReportCandidate(
                    report_id=converter.report_id,
                    display_name=converter.display_name,
                    score=detection.score,
                    matched_keywords=list(detection.matched_keywords),
                )
            )

    if not results:
        raise ReportDetectionError(
            "Unable to determine report type automatically.",
            candidates=[
                ReportCandidate(
                    report_id=converter.report_id,
                    display_name=converter.display_name,
                    score=0.0,
                    matched_keywords=[],
                )
                for converter in registry.values()
            ],
        )

    results.sort(key=lambda candidate: candidate.score, reverse=True)
    best = results[0]

    # Tie or low-confidence detection should return options to the caller.
    if len(results) > 1 and results[1].score == best.score:
        raise ReportDetectionError(
            "Multiple report types matched with the same confidence. Please select one.",
            candidates=results[:5],
        )

    if best.score < 1.0:
        raise ReportDetectionError(
            "Detection confidence is low. Please specify report_id manually.",
            candidates=results[:5],
        )

    converter = registry[best.report_id]
    return converter, best.score, best.matched_keywords


def _run_converter(converter, markdown: str, settings: ConversionSettings) -> Dict[str, object]:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(markdown)
        tmp.flush()
        temp_path = Path(tmp.name)

    try:
        return converter.convert(markdown, temp_path, settings)
    except ReportConversionError:
        raise
    except Exception as exc:  # pragma: no cover - delegated scripts may raise anything
        raise ReportConversionError(str(exc)) from exc
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


"""Converter registry and shared interfaces for Markdown → JSON pipelines."""

from .registry import (
    ReportDescriptor,
    get_converter_registry,
    get_converter_by_id,
    list_report_descriptors,
)

__all__ = [
    "ReportDescriptor",
    "get_converter_registry",
    "get_converter_by_id",
    "list_report_descriptors",
]


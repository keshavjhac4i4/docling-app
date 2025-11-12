"""Registry of available report converters."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List

from .base import BaseReportConverter, ReportDescriptor
from .external import ExternalScriptConverter, ScriptSpec


@dataclass(frozen=True)
class _ConverterRecord:
    spec: ScriptSpec


_BASE_DIR = Path(__file__).resolve().parent.parent

_SCRIPT_REGISTRY: List[_ConverterRecord] = [
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="ballistic",
            display_name="Ballistic Test Report",
            description="Velocity summary tables with V0/V45 metrics and summary statistics.",
            script_path=_BASE_DIR / "1" / "ballistic_script.py",
            entrypoint="extract_lab_report_from_md",
            keywords=(
                "ballistic test",
                "v0",
                "v20",
                "summary results",
                "velocity",
            ),
        )
    ),
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="bump_test",
            display_name="Bump Test Report",
            description="Vibration bump test results with peak and pulse duration.",
            script_path=_BASE_DIR / "1" / "bump_script.py",
            entrypoint="extract_bump_test_from_md",
            keywords=(
                "bump test",
                "accelerometer",
                "pulse duration",
                "total no of bumps",
            ),
        )
    ),
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="vibration",
            display_name="Vibration Test Report",
            description="Swept vibration schedule with control and profile tables.",
            script_path=_BASE_DIR / "1" / "vibration_script.py",
            entrypoint="extract_vibration_report_from_md",
            keywords=(
                "vibration test",
                "control parameters",
                "profile table",
                "schedule",
                "sweep rate",
            ),
        )
    ),
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="ammunition_lab",
            display_name="Ammunition Laboratory Report",
            description="Laboratory analysis report with test parameters and results table.",
            script_path=_BASE_DIR / "2" / "ammn_test_report.py",
            entrypoint="extract_lab_test_from_md",
            keywords=(
                "lab test report",
                "sample name",
                "spec limits",
                "test parameters",
            ),
        )
    ),
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="igniter_test",
            display_name="Igniter Test Report",
            description="Rocket igniter performance report with pressure and timing data.",
            script_path=_BASE_DIR / "2" / "igniter_test_report.py",
            entrypoint="extract_rocket_test_from_md",
            keywords=(
                "igniter test",
                "rocket motor",
                "burn time",
                "volt",
            ),
        )
    ),
    _ConverterRecord(
        spec=ScriptSpec(
            report_id="peak_report",
            display_name="Chromatographic Peak Report",
            description="Chromatography peak table with retention times and areas.",
            script_path=_BASE_DIR / "3" / "inject.py",
            entrypoint="extract_peak_data_from_md",
            keywords=(
                "chromatographic",
                "peak",
                "retention time",
                "peak results",
            ),
        )
    ),
]


@lru_cache(maxsize=1)
def get_converter_registry() -> Dict[str, BaseReportConverter]:
    """Return a mapping of report_id → converter instance."""

    registry: Dict[str, BaseReportConverter] = {}
    for record in _SCRIPT_REGISTRY:
        converter = ExternalScriptConverter(record.spec)
        registry[converter.report_id] = converter
    return registry


def get_converter_by_id(report_id: str) -> BaseReportConverter:
    registry = get_converter_registry()
    if report_id not in registry:
        raise KeyError(report_id)
    return registry[report_id]


def list_report_descriptors() -> List[ReportDescriptor]:
    registry = get_converter_registry()
    return [
        ReportDescriptor(
            report_id=converter.report_id,
            display_name=converter.display_name,
            description=getattr(converter, "description", ""),
            keywords=converter.keywords,
        )
        for converter in registry.values()
    ]


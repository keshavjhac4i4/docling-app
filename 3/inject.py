import requests
import json
from pydantic import BaseModel
from typing import Optional, List, Union
from pathlib import Path
import os

# -----------------------------
# Data Models
# -----------------------------

class TestMetadata(BaseModel):
    plant_name: Optional[str] = None
    name: Optional[str] = None
    position: Optional[str] = None
    instrument_method: Optional[str] = None
    volume: Optional[str] = None
    type: Optional[str] = None
    processor: Optional[str] = None
    function: Optional[str] = None


class PeakResult(BaseModel):
    index: Optional[Union[int, str]] = None
    name: Optional[str] = None
    retention_time: Optional[float] = None
    area: Optional[float] = None
    height: Optional[float] = None
    relative_height: Optional[float] = None


class PeakReport(BaseModel):
    test_metadata: TestMetadata
    peak_results_table: List[PeakResult]


# -----------------------------
# Core Functionality
# -----------------------------

def extract_peak_data_from_md(
    md_file_path: str,
    model: str = "gpt-oss:latest",
    ollama_url: str = "http://localhost:11434"
) -> dict:
    """
    Extract structured chromatographic peak data from a markdown file
    using the Ollama API with structured outputs.
    """

    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    prompt = f"""
You are a data extraction assistant. Extract all relevant information about a **chromatographic analysis report**
from the markdown below and return it as a valid JSON strictly following the schema provided.

Instructions:
1. Extract general test metadata under "test_metadata" — includes plant_name, name, position, instrument_method, volume, type, processor, and function.
2. Extract all peak details under "peak_results_table" — includes index, name, retention_time, area, height, and relative_height. The last row "Total" should be included as a new index appended to the list (for eg: index 1 -> 2 -> total). The index should not be null be 
3. Missing or unavailable values should be null.
4. Output must exactly match the schema below.

JSON Schema:
{json.dumps(PeakReport.model_json_schema(), indent=2)}

Markdown report:
----------------
{md_content}
"""

    api_endpoint = f"{ollama_url}/api/chat"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": PeakReport.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0.0}
    }

    try:
        response = requests.post(api_endpoint, json=payload, timeout=900)
        response.raise_for_status()
        response_data = response.json()
        message_content = response_data.get("message", {}).get("content", "")

        report = PeakReport.model_validate_json(message_content)
        return report.model_dump(by_alias=True)

    except requests.exceptions.ConnectionError:
        raise ConnectionError("❌ Could not connect to Ollama API. Is it running? Try 'ollama serve'.")
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Request timed out — model may be taking too long.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")


def save_to_json(data: dict, output_path: str):
    """Save extracted data to a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------
# Example usage
# -----------------------------

if __name__ == "__main__":
    md_file = r"C:\Users\Admin\Videos\Development\ocr_jsonify\OFBA\inject_test\inject.md"

    try:
        extracted_data = extract_peak_data_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )

        project_root = Path.cwd()
        output_dir = project_root / "OFBA" / "inject_test"
        output_file = output_dir / "inject.json"

        save_to_json(extracted_data, str(output_file))

        print("✅ Extraction successful!")
        print(f"Output saved to: {output_file.resolve()}\n")
        print(json.dumps(extracted_data, indent=2))

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise

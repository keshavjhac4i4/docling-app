import requests
import json
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os


# -----------------------------
# Data Models
# -----------------------------

class TestMetadata(BaseModel):
    test_name: Optional[str] = None
    store_name: Optional[str] = None
    lot_no: Optional[str] = None
    weight_of_propellant: Optional[float] = None
    max_pressure: Optional[float] = None
    delay: Optional[float] = None
    burn_time: Optional[float] = None
    average: Optional[float] = None
    area: Optional[float] = None
    voltage_supplied: Optional[float] = None
    current_supplied: Optional[float] = None


class TestResults(BaseModel):
    pressure: Optional[float] = None
    date: Optional[str] = None


class RocketTestReport(BaseModel):
    test_metadata: TestMetadata
    test_results: TestResults


# -----------------------------
# Core Functionality
# -----------------------------

def extract_rocket_test_from_md(md_file_path: str,
                                model: str = "gpt-oss:latest",
                                ollama_url: str = "http://localhost:11434") -> dict:
    """
    Extract structured rocket test data from a markdown file using the Ollama API with structured outputs.
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    prompt = f"""
You are a data extraction assistant.
Extract all relevant information about a **rocket motor test** from the markdown below, and return it as a valid JSON
strictly following the schema provided.

Instructions:
1. Extract general test metadata under `test_metadata` — includes test name, store name, lot no., propellant weight, max pressure, delay, burn time, average, area, voltage supplied and current supplied (cuurent could have typo as currect etc.).
2. Extract results under `test_results` — includes pressure and date.
3. Missing or unavailable values should be null.
4. Output must exactly match the schema below.

JSON Schema:
{json.dumps(RocketTestReport.model_json_schema(), indent=2)}

Markdown report:
----------------
{md_content}
"""

    api_endpoint = f"{ollama_url}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": RocketTestReport.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0.0}
    }

    try:
        response = requests.post(api_endpoint, json=payload, timeout=900)
        response.raise_for_status()

        response_data = response.json()
        message_content = response_data.get("message", {}).get("content", "")

        report = RocketTestReport.model_validate_json(message_content)
        return report.model_dump(by_alias=True)

    except requests.exceptions.ConnectionError:
        raise ConnectionError("❌ Could not connect to Ollama API. Is it running? Try `ollama serve`.")
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Request timed out — model may be taking too long.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")


def save_to_json(data: dict, output_path: str):
    """Save extracted data to a JSON file."""
    # ensure parent directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    md_file = r"C:\Users\Admin\Downloads\OFCH Igniter Test Report.md"

    try:
        extracted_data = extract_rocket_test_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )

        project_root = Path.cwd()  # change this if you want a different root
        output_dir = project_root / "OFCH" / "igniter_test_report"
        output_file = output_dir / "igniter.json"

        save_to_json(extracted_data, str(output_file))

        print("✅ Extraction successful!")
        print(f"Output saved to: {output_file.resolve()}\n")
        print(json.dumps(extracted_data, indent=2))

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise

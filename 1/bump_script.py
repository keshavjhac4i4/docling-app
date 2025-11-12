import requests
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


# -----------------------------
# Data Models for Bump Test Report
# -----------------------------

class Metadata(BaseModel):
    report_title: Optional[str] = None
    bump_test_number: Optional[int] = None
    time: Optional[str] = None
    date: Optional[str] = None  # can use str for simplicity in JSON serialization
    test_operator: Optional[str] = None
    channel_number: Optional[int] = None
    accelerometer_sensitivity: Optional[float] = None


class TestResult(BaseModel):
    peak: Optional[float] = None
    pulse_duration: Optional[float] = None
    velocity: Optional[float] = None
    filter_cut_off: Optional[int] = None
    rate: Optional[int] = None
    total_no_of_bumps: Optional[int] = None


class BumpTestReport(BaseModel):
    metadata: List[Metadata]
    test_results: List[TestResult]


# -----------------------------
# Core Functionality
# -----------------------------

def extract_bump_test_from_md(md_file_path: str, model: str = "gpt-oss:latest", ollama_url: str = "http://localhost:11434") -> dict:
    """
    Extract structured bump test report data from a markdown file using Ollama API with structured outputs.
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # -----------------------------
    # Updated Prompt
    # -----------------------------
    prompt = f"""You are a data extraction assistant. Extract all information from the bump test report into a strictly valid JSON structure.

The bump test report is written in markdown format. Parse all relevant fields and return it as valid JSON matching the following schema exactly:

{{
  "metadata": [
    {{
      "report_title": str,
      "bump_test_number": int,
      "time": str,
      "date": date,
      "test_operator": str,
      "channel_number": int,
      "accelerometer_sensitivity": float
    }}
  ],
  "test_results": [
    {{
      "peak": float,
      "pulse_duration": float,
      "velocity": float,
      "filter_cut_off": int,
      "rate": int,
      "total_no_of_bumps": int
    }}
  ]
}}

Key extraction rules:
1. Extract the general report information (title, bump test number, date, time, operator name, channel number, accelerometer sensitivity) and place it inside the "metadata" array as a single object.
2. Extract all test result rows (if multiple bumps are listed, include each one separately) under "test_results".
3. Numeric values must be stored as numbers (not strings).
4. Dates must remain in ISO or string date format (e.g., "2025-10-16" or "16-Oct-2025").
5. If any value is missing, use null.
6. The output must be valid JSON, conforming exactly to the schema above.
7. Do not include any extra text, only the JSON.

Here is the markdown content of the bump test report:

{md_content}
"""

    schema = BumpTestReport.model_json_schema()
    api_endpoint = f"{ollama_url}/api/chat"
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.0}
    }

    try:
        response = requests.post(api_endpoint, json=payload, timeout=1500)
        response.raise_for_status()

        response_data = response.json()
        message_content = response_data.get("message", {}).get("content", "")

        report = BumpTestReport.model_validate_json(message_content)
        return report.model_dump(by_alias=True)

    except requests.exceptions.ConnectionError:
        raise ConnectionError("❌ Could not connect to Ollama API. Ensure 'ollama serve' is running.")
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Request timed out — model may be taking too long.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")


# -----------------------------
# Utility Function
# -----------------------------

def save_to_json(data: dict, output_path: str):
    """Save the extracted data to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------
# Example Usage
# -----------------------------
if __name__ == "__main__":
    md_file = r"C:\Users\Admin\Downloads\Bump Report.md"  # Replace with your actual file path

    try:
        extracted_data = extract_bump_test_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )
        save_to_json(extracted_data, "extracted_bump_test_report.json")

        print("✅ Extraction successful!")
        print(f"Output saved to: extracted_bump_test_report.json")
        print("\nExtracted data preview:")
        print(json.dumps(extracted_data, indent=2))

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise

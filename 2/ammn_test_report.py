import requests
import json
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path


# -----------------------------
# Data Models
# -----------------------------

class TestMetadata(BaseModel):
    lab_name: Optional[str] = None
    test_report_no: Optional[str] = None
    sub: Optional[str] = None
    date: Optional[str] = None
    sample_name: Optional[str] = None
    item_code: Optional[int] = None
    spec_no: Optional[str] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    sample_type: Optional[str] = None
    sample_mode: Optional[str] = None
    sample_cd: Optional[str] = None
    specific_req: Optional[str] = None
    spec_req_det: Optional[str] = None
    sampling_plan: Optional[str] = None
    sample_receipt_date: Optional[str] = None
    analysis_completion_date: Optional[str] = None
    test_condition: Optional[str] = None
    remarks: Optional[str] = None
    qc_lab_reg_no: Optional[int] = None


class TestTableEntry(BaseModel):
    test_parameters: Optional[str] = None
    spec_limits: Optional[str] = None
    unit: Optional[str] = None
    results: Optional[str] = None


class LabTestReport(BaseModel):
    test_metadata: TestMetadata
    test_table: List[TestTableEntry]


# -----------------------------
# Core Functionality
# -----------------------------

def extract_lab_test_from_md(md_file_path: str,
                             model: str = "gpt-oss:latest",
                             ollama_url: str = "http://localhost:11434") -> dict:
    """
    Extract structured laboratory test data from a markdown file using the Ollama API with structured outputs.
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    prompt = f"""
You are a data extraction assistant.

Extract all relevant laboratory test information from the markdown below and return it as a valid JSON 
strictly following the schema provided.

Instructions:
1. Extract general test metadata under `test_metadata`.
2. Extract tabular test data under `test_table`, where each row corresponds to test_parameters, spec_limits, unit, and results.
3. Missing or unavailable values should be null.
4. The output must exactly match the schema below.

JSON Schema:
{json.dumps(LabTestReport.model_json_schema(), indent=2)}

Markdown report:
----------------
{md_content}
"""

    api_endpoint = f"{ollama_url}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": LabTestReport.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0.0}
    }

    try:
        response = requests.post(api_endpoint, json=payload, timeout=900)
        response.raise_for_status()

        response_data = response.json()
        message_content = response_data.get("message", {}).get("content", "")

        report = LabTestReport.model_validate_json(message_content)
        return report.model_dump(by_alias=True)

    except requests.exceptions.ConnectionError:
        raise ConnectionError("❌ Could not connect to Ollama API. Is it running? Try `ollama serve`.")
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
    md_file = r"C:\Users\Admin\Downloads\OFCH Ammn Test Report.md"

    try:
        extracted_data = extract_lab_test_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )

        project_root = Path.cwd()
        output_dir = project_root / "OFCH" / "ammn_test_report"
        output_file = output_dir / "ammn.json"

        save_to_json(extracted_data, str(output_file))

        print("✅ Extraction successful!")
        print(f"Output saved to: {output_file.resolve()}\n")
        print(json.dumps(extracted_data, indent=2))

    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise

import requests
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Union

# -----------------------------
# Data Models
# -----------------------------

class ReportMetadata(BaseModel):
    date: Optional[str] = None
    operator: Optional[str] = None


class TestParameters(BaseModel):
    weapon_type: Optional[str] = None
    weapon_sn: Optional[str] = None
    ammunition_type: Optional[str] = None
    ammunition_sn: Optional[str] = None
    air_temperature: Optional[float] = None
    air_pressure: Optional[float] = None
    air_humidity: Optional[float] = None


class TestResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    index: int
    v0_m_s: Optional[float] = Field(None, alias='v0_m/s')
    v5_m_s: Optional[float] = Field(None, alias='v5_m/s')
    v10_m_s: Optional[float] = Field(None, alias='v10_m/s')
    v20_m_s: Optional[float] = Field(None, alias='v20_m/s')
    v30_m_s: Optional[float] = Field(None, alias='v30_m/s')
    v45_m_s: Optional[float] = Field(None, alias='v45_m/s')
    notes: Optional[str] = None


class SummaryRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    index: str  # e.g. avg, max, min, etc.
    v0_m_s: Optional[float] = Field(None, alias='v0_m/s')
    v5_m_s: Optional[float] = Field(None, alias='v5_m/s')
    v10_m_s: Optional[float] = Field(None, alias='v10_m/s')
    v20_m_s: Optional[float] = Field(None, alias='v20_m/s')
    v30_m_s: Optional[float] = Field(None, alias='v30_m/s')
    v45_m_s: Optional[float] = Field(None, alias='v45_m/s')
    notes: Optional[str] = None


class LabReport(BaseModel):
    report_metadata: ReportMetadata
    test_parameters: TestParameters
    test_results: List[TestResult]
    summary_results: List[SummaryRow]  # changed to list of summary rows


# -----------------------------
# Core Functionality
# -----------------------------

def extract_lab_report_from_md(md_file_path: str, model: str = "gpt-oss:latest", ollama_url: str = "http://localhost:11434") -> dict:
    """
    Extract structured lab report data from a markdown file using Ollama API with structured outputs.
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    prompt = f"""You are a data extraction assistant. Extract all information from the lab report into a strictly valid JSON format.

The lab report is in markdown format. Parse all the data carefully and return it as JSON.

Key instructions:
1. Extract metadata (date, operator)
2. Extract test parameters (weapon, ammo, environment)
3. Extract all test results with velocities and notes
4. Extract or calculate summary statistics (avg, max, min, delta, sdev, mdev)
5. Each summary statistic (avg, max, min, delta, sdev, mdev) must be a separate object in an array named "summary_results".
   Example format:
   "summary_results": [
     {{"index": "avg", "v0_m/s": null, "v5_m/s": null, "v10_m/s": null, "v20_m/s": null, "v30_m/s": null, "v45_m/s": null, "notes": null}},
     {{"index": "max", ...}},
     ...
   ]
6. Numeric fields must be numbers, not strings.
7. Missing values must be null.
8. Output must strictly conform to the JSON schema below.

Here is the lab report markdown:

{md_content}
"""
    schema = LabReport.model_json_schema()
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
        
        lab_report = LabReport.model_validate_json(message_content)
        return lab_report.model_dump(by_alias=True)
    
    except requests.exceptions.ConnectionError:
        raise ConnectionError("❌ Could not connect to Ollama API. Is it running? Try 'ollama serve'.")
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Request timed out — model may be taking too long.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")


def save_to_json(data: dict, output_path: str):
    """Save extracted data to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    md_file = r'C:\Users\Admin\Downloads\BALLISTIC TEST REPORT.md'
    
    try:
        extracted_data = extract_lab_report_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )
        save_to_json(extracted_data, "script1.json")
        
        print("✅ Extraction successful!")
        print(f"Output saved to: script1.json")
        print("\nExtracted data preview:")
        print(json.dumps(extracted_data, indent=2))
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise
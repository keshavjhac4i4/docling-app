import requests
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Union

# -----------------------------
# Data Models
# -----------------------------

class TestMetadata(BaseModel):
    test_number: Optional[str] = None
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    client: Optional[str] = None
    test_purpose: Optional[str] = None
    date: Optional[str] = None


class InputChannelParameters(BaseModel):
    input_channel: Optional[int] = None
    type: Optional[str] = None
    range: Optional[int] = None
    weighting: Optional[int] = None
    couple: Optional[str] = None
    transducer: Optional[str] = None
    sensitivity: Optional[str] = None
    polarity: Optional[str] = None
    analyse: Optional[str] = None
    abort_peak: Optional[str] = None
    name: Optional[str] = None
    dc_remove: Optional[str] = None


class OutputChannelParameters(BaseModel):
    output_channel: Optional[str] = None
    type: Optional[str] = None
    range: Optional[int] = None


class LimitParameters(BaseModel):
    description: Optional[str] = None
    maximum_force: Optional[str] = None
    maximum_positive_disp: Optional[str] = None
    maximum_negative_disp: Optional[str] = None
    maximum_velocity: Optional[str] = None
    maximum_acceleration: Optional[str] = None
    minimum_frequency: Optional[str] = None
    maximum_frequency: Optional[str] = None
    maximum_input_voltage: Optional[str] = None
    moving_coil_mass: Optional[str] = None
    fixture_mass: Optional[str] = None
    specimen_mass: Optional[str] = None
    other_mass: Optional[str] = None
    total_weight: Optional[str] = None
    drive_limit: Optional[str] = None
    abort_latency: Optional[str] = None
    max_gain_on_starting: Optional[str] = None
    max_gain_on_running: Optional[str] = None


class ControlParameters(BaseModel):
    control_strategy: Optional[str] = None
    sweep_mode: Optional[str] = None
    lines: Optional[int] = None
    maximum_frequency: Optional[str] = None
    filter_type: Optional[str] = None
    bandwidth: Optional[str] = None
    level_change_rate: Optional[str] = None
    change_level: Optional[str] = None
    abort_rate: Optional[str] = None
    initial_drive: Optional[str] = None
    ramp_up_rate: Optional[str] = None
    pre_test_drive_limit: Optional[str] = None
    resume_from_aborting: Optional[str] = None


class ScheduleItem(BaseModel):
    command: Optional[str] = None
    level: Optional[str] = None
    frequency_low: Optional[str] = None
    frequency_high: Optional[str] = None
    frequency_start: Optional[str] = None
    sweep_rate: Optional[str] = None
    sweep_direction: Optional[str] = None
    sweep_compression_rate: Optional[str] = None
    time_type: Optional[str] = None
    time_value: Optional[str] = None
    rstd_dwell: Optional[str] = None
    parameters: Optional[str] = None


class Profile(BaseModel):
    profile_acceleration_peak: Optional[str] = None
    profile_velocity_peak: Optional[str] = None
    profile_displacement_peak_to_peak: Optional[str] = None
    shaker_acceleration_peak: Optional[str] = None
    shaker_velocity_peak: Optional[str] = None
    shaker_displacement_peak_to_peak: Optional[str] = None


class ProfileTableParameter(BaseModel):
    frequency: Optional[Union[float, int]] = None
    acceleration: Optional[Union[float, int]] = None
    velocity: Optional[Union[float, int]] = None
    displacement_peak_to_peak: Optional[Union[float, int]] = None
    left_slope: Optional[str] = None
    right_slope: Optional[str] = None
    high_alarm: Optional[Union[float, int]] = None
    low_alarm: Optional[Union[float, int]] = None
    high_abort: Optional[Union[float, int]] = None
    low_abort: Optional[Union[float, int]] = None


class SweepRate(BaseModel):
    start_frequency: Optional[int] = None
    sweep_rate_1: Optional[int] = None
    stop_frequency: Optional[int] = None
    sweep_rate_2: Optional[int] = None


class CompressionRate(BaseModel):
    start_frequency: Optional[int] = None
    compression_rate_1: Optional[int] = None
    stop_frequency: Optional[int] = None
    compression_rate_2: Optional[int] = None


class TestInformation(BaseModel):
    level: Optional[str] = None
    demand_peak: Optional[str] = None
    control_peak: Optional[str] = None
    frequency: Optional[str] = None
    sweep_rate: Optional[str] = None
    sweep_type: Optional[str] = None
    total_elapsed_time: Optional[str] = None
    current_level_type: Optional[str] = None
    remaining_time: Optional[str] = None
    file_save_time: Optional[str] = None
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class VibrationTestReport(BaseModel):
    test_metadata: TestMetadata
    input_channel_parameters: InputChannelParameters
    output_channel_parameters: OutputChannelParameters
    limit_parameters: LimitParameters
    control_parameters: ControlParameters
    schedule: List[ScheduleItem]
    profile: Profile
    profile_table_parameters: List[ProfileTableParameter]
    sweep_rate: SweepRate
    compression_rate: CompressionRate
    test_information: TestInformation


# -----------------------------
# Core Functionality
# -----------------------------

def extract_vibration_report_from_md(md_file_path: str, model: str = "gpt-oss:latest", ollama_url: str = "http://localhost:11434") -> dict:
    """
    Extract structured vibration test report data from a markdown file using Ollama API with structured outputs.
    """
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    prompt = f"""You are a data extraction assistant. Extract all information from the vibration test report into a strictly valid JSON format.

The vibration test report is in markdown format. Parse all the data carefully and return it as JSON.

Key instructions:
1. Extract test metadata (test number, object name, object type, client, test purpose, date).
2. Extract input channel parameters (input channel, type, range, weighting, etc.).
3. Extract output channel parameters (output channel, type, range).
4. Extract limit parameters (description -> this may be the header but include its value too, maximum force, displacements, velocity, acceleration, frequencies, etc.).
5. Extract control parameters (control strategy -> this may be the header but include its value too, sweep mode, lines, etc.).
6. Extract schedule items as an array of objects, each containing command, level, frequencies, etc.
7. Extract profile details (profile_acceleration_peak, profile_velocity_peak, profile_displacement_peak_to_peak and shaker_acceleration_peak, shaker_velocity_peak, shaker_displacement_peak_to_peak).
8. Extract profile table parameters as an array of objects with frequency, acceleration, velocity, etc.
9. Extract sweep rate and compression rate details (start/stop frequencies, rates).
10. Extract test information (level, demand/control peaks, frequency, sweep details, times -> do not forget the file_save_time).
11. Missing values must be null.
12. Output must strictly conform to the JSON schema below.

Here is the vibration test report markdown:

{md_content}
"""
    schema = VibrationTestReport.model_json_schema()
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
        
        vibration_report = VibrationTestReport.model_validate_json(message_content)
        return vibration_report.model_dump(by_alias=True)
    
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
    md_file = r'C:\Users\Admin\Videos\Development\ocr_jsonify\vibration_report\ofk_1.md'
    
    try:
        extracted_data = extract_vibration_report_from_md(
            md_file_path=md_file,
            model="gpt-oss:latest"
        )
        save_to_json(extracted_data, "vibration_report1.json")
        
        print("✅ Extraction successful!")
        print(f"Output saved to: vibration_report1.json")
        print("\nExtracted data preview:")
        print(json.dumps(extracted_data, indent=2))
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise
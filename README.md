# Document Processing Application

## Overview

This application converts uploaded documents into structured JSON data using OCR, Markdown conversion, and report-specific processing scripts powered by Ollama LLM.

---

## How The App Works

### 1. Upload & OCR

1. User uploads a document via the UI (`/`)
2. Frontend sends the file (and optional report selection) to `POST /convert`
3. Backend saves the payload and runs **Docling** (`run_docling`) to generate Markdown
4. Original file is stored for preview; Markdown text is kept in memory for processing

### 2. Markdown → JSON Conversion

The `/convert` endpoint calls `convert_markdown_to_json` in `services/json_conversion.py`:

- **Explicit report selection**: Uses the provided `report_id` if specified
- **Auto-detection**: Runs detection across registered converters using keyword matching
- **Converter execution**:
  - Converters are thin wrappers around existing scripts (defined in `converters/registry.py`)
  - Each converter writes Markdown to a temp file
  - Calls the script's core function (e.g., `extract_lab_report_from_md`)
  - Passes configured Ollama URL/model as parameters

**Success Output**:
- `data`: JSON payload from the report script
- `report`: Converter metadata (ID, name, score, matched keywords)

**Error Handling**:
- `400`: Unknown report
- `409`: Detection conflict (multiple candidates)
- `500`: Conversion failure

### 3. Response Payload

The API returns:
- Markdown text
- JSON data (using existing scripts' schema)
- Report metadata
- Original file information
- OCR settings

### 4. Frontend Behavior

- Report types load from `GET /reports` into a dropdown (with "Auto detect" fallback)
- Result panel displays Markdown/JSON tabs
- Auto-switches to JSON tab when data exists
- JSON view shows:
  - Report name & detection score
  - Collapsible content
  - "Copy JSON" button
- Detection conflicts show error UI with buttons to select a specific converter
- Selected report updates the dropdown automatically

---

## Adding a New Report Script

Follow these steps to integrate a custom Markdown→JSON converter:

### Step 1: Place Your Script

Add your script (e.g., `my_report_script.py`) to an appropriate folder:
- `docling/1/`
- `docling/2/`
- `docling/3/`
- Or create `docling/4/` for new categories

**Requirements**:
- Main function must accept: `md_file_path`, `model`, and `ollama_url`
- Function should return a dictionary (Pydantic validations happen inside the script)

### Step 2: Register the Converter

Open `docling/converters/registry.py` and add a new `_ConverterRecord`:

```python
_ConverterRecord(
    spec=ScriptSpec(
        report_id='my_report',
        display_name='My Custom Report',
        description='Short description here.',
        script_path=_BASE_DIR / '4' / 'my_report_script.py',
        entrypoint='extract_my_report_from_md',
        keywords=('my keyword', 'another keyword')
    )
)
```

**Parameters**:
- `report_id`: Unique identifier for the report
- `display_name`: User-friendly name shown in UI
- `description`: Brief explanation of the report type
- `script_path`: Path to your script file
- `entrypoint`: Name of the main function
- `keywords`: Tuple of keywords for auto-detection

### Step 3: Restart the Application

```bash
# Restart your FastAPI server
# The registry will automatically load the new converter
```

The report will now appear in:
- `GET /reports` endpoint response
- UI dropdown menu

### Step 4: Test

1. Upload a document for the new report type
2. Either:
   - Select it explicitly from the dropdown, or
   - Let auto-detection choose it via keywords
3. Verify the JSON output matches expectations

---

## Configuration

### Environment Variables

- `OLLAMA_URL`: Base URL for Ollama API (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model name to use (e.g., `llama2`, `mistral`)

### Detection Scoring

- Detection score = cumulative keyword hits
- Higher score = better match
- Multiple matches with same score trigger conflict resolution UI

---

## Advanced Customization

### Keyword Management

- **Blacklist**: Exclude generic terms that cause false positives
- **Whitelist**: Add specific terms for stronger detection signals
- Adjust weights by using more specific/unique keywords

### Custom Detection Logic

For complex detection requirements:

1. Customize `ExternalScriptConverter.detect()` method
2. Or subclass `BaseReportConverter` for full control

---

## Architecture Notes

- **Converters**: Thin wrappers that reuse existing report scripts with minimal changes
- **Registry**: Auto-loads all converter specs at startup
- **Error Handling**: Clean error surfacing with appropriate HTTP status codes
- **File Management**: Original files preserved for preview; temp files used for processing
- **Schema**: All scripts use their own JSON schema (no enforced standardization)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/convert` | Upload document and convert to JSON |
| `GET` | `/reports` | List all available report types |

---

## Troubleshooting

### Report Not Detected
- Check keywords in `registry.py` match document content
- Verify script path is correct
- Ensure entrypoint function name matches

### Conversion Fails
- Confirm Ollama service is running
- Check `OLLAMA_URL` and `OLLAMA_MODEL` environment variables
- Review script logs for specific errors

### Multiple Reports Detected
- Use more specific keywords
- Manually select report from UI dropdown
- Adjust keyword weights in registry

---

## Contributing

When adding new report types:
1. Follow existing script patterns
2. Include comprehensive keywords for detection
3. Document any special requirements
4. Test with multiple document samples
5. Update this README with any new conventions

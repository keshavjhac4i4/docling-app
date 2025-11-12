#!/usr/bin/env python3
"""
Docling FastAPI App with UI
A FastAPI wrapper for the docling command with automatic device detection and clean UI.
"""

import logging
import mimetypes
import multiprocessing
import os
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from services import (
    ReportConversionError,
    ReportDetectionError,
    UnknownReportError,
    convert_markdown_to_json,
    list_available_reports,
)

app = FastAPI(
    title="Docling API",
    description="Convert documents to Markdown using Docling",
    version="1.0.0"
)

# Static and template setup
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMP_UPLOAD_DIR = BASE_DIR / "temp_uploads"
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_FILE_MAX_AGE = int(os.environ.get("DOC_TEMP_FILE_MAX_AGE", "3600"))

# Global storage for temporary files (for serving original documents)
temp_files = {}
temp_files_lock = threading.Lock()

# Enable CORS for cross-origin usage (e.g., accessing API from other devices)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@lru_cache(maxsize=1)
def detect_device():
    """
    Detect if CUDA is available, otherwise use CPU.
    
    Returns:
        str: 'cuda' or 'cpu'
    """
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return "cuda"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return "cpu"

@lru_cache(maxsize=1)
def get_num_threads():
    """
    Get the number of CPU threads available.
    
    Returns:
        int: Number of CPU threads
    """
    return multiprocessing.cpu_count()

def run_docling(input_file: str, device: Optional[str] = None, num_threads: Optional[int] = None):
    """
    Run docling command with auto-detected or specified settings.
    
    Args:
        input_file: Path to the input file
        device: Device to use ('cuda' or 'cpu'), auto-detected if None
        num_threads: Number of threads, auto-detected if None
        
    Returns:
        tuple: (success: bool, content: str, error: str)
    """
    # Auto-detect device and threads if not provided
    if device is None:
        device = detect_device()
    if num_threads is None:
        num_threads = get_num_threads()
    
    # Validate input file exists
    if not os.path.exists(input_file):
        return False, "", f"Input file '{input_file}' does not exist."
    
    # Create temporary directory for output
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        # Construct the docling command
        cmd = [
            "docling",
            input_file,
            "--output", str(output_dir),
            "--device", device,
            "--ocr-engine", "rapidocr",
            "--image-export-mode", "placeholder",
            "--force-ocr",
            "--num-threads", str(num_threads)
        ]
        
        try:
            # Run the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minute timeout
            )
            
            # Find the output markdown file
            md_files = list(output_dir.glob("*.md"))
            
            if not md_files:
                return False, "", f"No markdown output generated.\nStderr: {result.stderr}"
            
            # Read and return the markdown content
            md_file = md_files[0]
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return True, content, ""
            
        except subprocess.CalledProcessError as e:
            return False, "", f"Error running docling:\n{e.stderr}"
        except subprocess.TimeoutExpired:
            return False, "", "Processing timeout (10 minutes exceeded)"
        except Exception as e:
            return False, "", f"Error: {str(e)}"


def cleanup_expired_files(max_age: Optional[int] = None) -> None:
    """Remove temporary files that have exceeded the allowed lifetime."""
    age_limit = max_age if max_age is not None else TEMP_FILE_MAX_AGE
    if age_limit <= 0:
        return

    now = time.time()
    stale_records = []

    with temp_files_lock:
        for file_id, meta in list(temp_files.items()):
            created_at = meta.get("created_at", now)
            if now - created_at > age_limit:
                stale_records.append((file_id, meta.get("path")))
                temp_files.pop(file_id, None)

    for file_id, path in stale_records:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
            logger.debug("Removed stale temporary file %s", path)
        except OSError as exc:
            logger.debug("Failed to remove stale temp file %s: %s", path, exc)


def register_temp_file(file_id: str, file_path: Path, content_type: str, original_name: str) -> None:
    """Add a new temporary file to the registry and trigger cleanup."""
    cleanup_expired_files()
    entry = {
        "path": str(file_path),
        "content_type": content_type,
        "original_name": original_name,
        "created_at": time.time()
    }
    with temp_files_lock:
        temp_files[file_id] = entry
    logger.debug("Registered temporary file %s -> %s", file_id, file_path)


def resolve_temp_file(file_id: str) -> dict:
    """Retrieve temp file metadata or raise KeyError if unavailable."""
    cleanup_expired_files()
    with temp_files_lock:
        entry = temp_files.get(file_id)
    if not entry:
        raise KeyError(file_id)
    return entry


def infer_content_type(filename: str) -> str:
    """Best-effort content type detection with sensible fallbacks."""
    content_type, _ = mimetypes.guess_type(filename)
    if content_type:
        return content_type

    ext = Path(filename).suffix.lower()
    fallback_map = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tif': 'image/tiff',
        '.tiff': 'image/tiff',
        '.txt': 'text/plain'
    }
    return fallback_map.get(ext, 'application/octet-stream')

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/info")
async def get_info():
    """Get system information about device and threads."""
    return {
        "device": detect_device(),
        "num_threads": get_num_threads()
    }


@app.get("/reports")
async def get_reports():
    """List all available report converters."""
    return {"reports": list_available_reports()}

@app.get("/original/{file_id}")
async def get_original_document(file_id: str):
    """Serve the original uploaded document."""
    try:
        entry = resolve_temp_file(file_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found") from None

    file_path = Path(entry["path"]).resolve()
    content_type = entry.get("content_type", "application/octet-stream")
    original_name = entry.get("original_name")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if content_type == 'application/pdf':
        # For PDFs, use inline display headers to prevent download
        headers = {
            "Content-Disposition": "inline",
            "Cache-Control": "no-cache"
        }
        return FileResponse(
            path=file_path,
            media_type=content_type,
            headers=headers
        )

    download_name = original_name or file_path.name
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=download_name
    )

@app.post("/convert")
async def convert_document(
    file: UploadFile = File(...),
    device: Optional[str] = None,
    num_threads: Optional[int] = None,
    report_id: Optional[str] = Form(None)
):
    """
    Convert a document to Markdown using Docling.
    
    Args:
        file: Document file to convert (PDF, DOCX, etc.)
        device: Optional device override ('cuda' or 'cpu')
        num_threads: Optional thread count override
        
    Returns:
        JSON response with markdown content
    """
    # Validate device parameter if provided
    if device and device not in ["cuda", "cpu"]:
        raise HTTPException(
            status_code=400,
            detail="Device must be 'cuda' or 'cpu'"
        )
    
    # Validate num_threads if provided
    if num_threads and num_threads < 1:
        raise HTTPException(
            status_code=400,
            detail="num_threads must be positive"
        )
    
    original_filename = file.filename or "uploaded_document"
    suffix = Path(original_filename).suffix
    file_id = str(uuid.uuid4())
    temp_file_path = TEMP_UPLOAD_DIR / f"{file_id}{suffix}"

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to read uploaded file") from exc

    try:
        with temp_file_path.open("wb") as temp_file:
            temp_file.write(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to store uploaded file") from exc

    content_type = infer_content_type(original_filename)
    selected_device = device or detect_device()
    selected_threads = num_threads or get_num_threads()

    try:
        success, markdown_content, error = run_docling(
            str(temp_file_path),
            device=selected_device,
            num_threads=selected_threads
        )

        if not success:
            raise HTTPException(status_code=500, detail=error or "Conversion failed")

        register_temp_file(file_id, temp_file_path, content_type, original_filename)

        logger.info(
            "Conversion complete for %s (device=%s, threads=%s)",
            original_filename,
            selected_device,
            selected_threads
        )

        try:
            json_outcome = convert_markdown_to_json(
                markdown_content,
                report_id=report_id,
                original_filename=original_filename,
            )
            json_data = json_outcome.data
            report_info = {
                "id": json_outcome.report_id,
                "name": json_outcome.display_name,
                "score": json_outcome.score,
                "matched_keywords": json_outcome.matched_keywords,
            }
        except UnknownReportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ReportDetectionError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": exc.message,
                    "candidates": [candidate.as_dict() for candidate in exc.candidates],
                },
            ) from exc
        except ReportConversionError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return JSONResponse(content={
            "success": True,
            "filename": original_filename,
            "markdown": markdown_content,
            "json": json_data,
            "report": report_info,
            "original_file": {
                "id": file_id,
                "url": f"/original/{file_id}",
                "content_type": content_type,
                "original_name": original_filename
            },
            "settings": {
                "device": selected_device,
                "num_threads": selected_threads
            }
        })

    except HTTPException:
        temp_file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_file_path.unlink(missing_ok=True)
        logger.exception("Unexpected error during conversion")
        raise HTTPException(status_code=500, detail="Unexpected error during conversion") from exc

if __name__ == "__main__":
    device = detect_device()
    threads = get_num_threads()
    host = os.environ.get("HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        port = 8000
    
    def get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip_addr = s.getsockname()[0]
            finally:
                s.close()
            return ip_addr
        except Exception:
            return "127.0.0.1"
    
    print("="*60)
    print("Docling FastAPI Server")
    print("="*60)
    print(f"Detected Device: {device}")
    print(f"Available Threads: {threads}")
    print("="*60)
    local_ip = get_local_ip()
    print(f"\nStarting server on http://{host}:{port}")
    print(f"Local access:   http://127.0.0.1:{port}")
    print(f"LAN access:     http://{local_ip}:{port}")
    print("Open your browser and navigate to one of the URLs above (ensure firewall allows inbound access on the chosen port)")
    print("="*60 + "\n")
    
    uvicorn.run("app:app", host=host, port=port, reload=True)
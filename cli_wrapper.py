#!/usr/bin/env python3
"""
Docling FastAPI App with UI
A FastAPI wrapper for the docling command with automatic device detection and clean UI.
"""

import subprocess
import os
import tempfile
import multiprocessing
from pathlib import Path
from typing import Optional
import socket
import mimetypes

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

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

# Global storage for temporary files (for serving original documents)
temp_files = {}

# Enable CORS for cross-origin usage (e.g., accessing API from other devices)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            return False, "", "Processing timeout (5 minutes exceeded)"
        except Exception as e:
            return False, "", f"Error: {str(e)}"

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

@app.get("/original/{file_id}")
async def get_original_document(file_id: str):
    """Serve the original uploaded document."""
    if file_id not in temp_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path, content_type = temp_files[file_id]
    if not os.path.exists(file_path):
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
    else:
        # For other files, allow normal download behavior
        return FileResponse(
            path=file_path,
            media_type=content_type,
            filename=os.path.basename(file_path)
        )

@app.post("/convert")
async def convert_document(
    file: UploadFile = File(...),
    device: Optional[str] = None,
    num_threads: Optional[int] = None
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
    
    # Save uploaded file to temporary location
    import uuid
    file_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    # Determine content type
    content_type, _ = mimetypes.guess_type(file.filename)
    if not content_type:
        # Default content types for common document formats
        ext = Path(file.filename).suffix.lower()
        if ext == '.pdf':
            content_type = 'application/pdf'
        elif ext in ['.docx', '.doc']:
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            content_type = f'image/{ext[1:]}'
        elif ext in ['.txt']:
            content_type = 'text/plain'
        else:
            content_type = 'application/octet-stream'

    # Debug logging
    print(f"File uploaded: {file.filename}, detected content_type: {content_type}")

    # Store file info for serving original document
    temp_files[file_id] = (tmp_file_path, content_type)
    
    try:
        # Process the file
        success, markdown_content, error = run_docling(
            tmp_file_path,
            device=device,
            num_threads=num_threads
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=error)
        
        # Get actual settings used
        actual_device = device if device else detect_device()
        actual_threads = num_threads if num_threads else get_num_threads()
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "markdown": markdown_content,
            "original_file": {
                "id": file_id,
                "url": f"/original/{file_id}",
                "content_type": content_type
            },
            "settings": {
                "device": actual_device,
                "num_threads": actual_threads
            }
        })
        
    finally:
        # Note: File cleanup is handled separately to allow serving of original documents
        # Files are cleaned up when the server restarts or when explicitly removed
        pass

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
    
    uvicorn.run(app, host=host, port=port)
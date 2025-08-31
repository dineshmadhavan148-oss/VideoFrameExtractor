import os
import logging
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates  # Not needed

from config import config
from models import VideoJobRequest, VideoJobResponse
from database import DatabaseManager
from cache import CacheManager
from job_manager import JobManager
from dashboard import DashboardService

# Configure logging with absolute paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_dir = os.path.join(project_root, "runtime", "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create necessary directories with absolute paths
frames_dir = os.path.join(project_root, "runtime", "frames")
db_dir = os.path.join(project_root, "runtime", "db")

Path(frames_dir).mkdir(parents=True, exist_ok=True)
Path(db_dir).mkdir(parents=True, exist_ok=True)
Path(log_dir).mkdir(parents=True, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="Video Frame Extraction System",
    version="1.0.0",
    description="A high-performance video frame extraction system with Redis caching and concurrent processing",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize components
db_manager = DatabaseManager(config.DATABASE_PATH)
cache_manager = CacheManager()
job_manager = JobManager(db_manager, cache_manager)
dashboard_service = DashboardService(db_manager, cache_manager)

# Create uploads directory
uploads_dir = os.path.join(project_root, "uploads")
os.makedirs(uploads_dir, exist_ok=True)

# Templates - not needed since we serve HTML directly

@app.post("/video-job", response_model=VideoJobResponse, tags=["Jobs"])
async def submit_video_job(
    video_source: str = None,
    interval: float = 5.0,
    file: UploadFile = File(None)
):
    """
    Submit a new video processing job for frame extraction.
    
    - **video_source**: Path to video file or URL (if no file uploaded)
    - **interval**: Time interval between extracted frames (in seconds)
    - **file**: Video file to upload (optional)
    
    Returns job ID and status for tracking progress.
    """
    try:
        # Determine the video source
        if file:
            # File uploaded - save it and use the saved path
            if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                raise HTTPException(status_code=400, detail="Invalid file type. Please upload a video file.")
            
            file_path = os.path.join(uploads_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            actual_video_source = file_path
            logger.info(f"File uploaded: {file.filename} -> {file_path}")
        elif video_source:
            # Use provided video source path
            actual_video_source = video_source
        else:
            raise HTTPException(status_code=400, detail="Either video_source or file must be provided")
        
        # Submit the job
        job_id = job_manager.submit_job(actual_video_source, interval)
        return VideoJobResponse(
            job_id=job_id,
            status="pending",
            message="Job submitted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a video processing job"""
    job = job_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "video_source": job.video_source,
        "interval": job.interval,
        "total_frames": job.total_frames,
        "processed_frames": job.processed_frames,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "error_message": job.error_message
    }

@app.get("/frames/{job_id}")
async def get_job_frames(job_id: str):
    """List all frames for a specific job"""
    frames = db_manager.get_frames_by_job(job_id)
    if not frames:
        job = job_manager.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"frames": [], "message": "No frames extracted yet"}
    
    return {
        "job_id": job_id,
        "frames": [frame.to_dict() for frame in frames],
        "total_count": len(frames)
    }

@app.get("/dashboard/recent-frames")
async def get_recent_frames(
    since_minutes: int = Query(60, description="Minutes back to look for frames"),
    job_id: str = Query(None, description="Filter by specific job ID")
):
    """Get recent frame metadata for dashboard"""
    try:
        frames = dashboard_service.get_recent_frames(since_minutes, job_id)
        
        return {
            "frames": frames,
            "total_count": len(frames),
            "since_minutes": since_minutes,
            "job_id": job_id,
            "cached": bool(cache_manager.get_recent_frames_cached(job_id))
        }
    except Exception as e:
        logger.error(f"Error getting recent frames: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel and delete a job along with its metadata and frames"""
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or could not be cancelled")
    
    return {"message": f"Job {job_id} cancelled and cleaned up successfully"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "redis_available": cache_manager.use_redis,
        "active_jobs": len(job_manager.active_jobs)
    }

@app.get("/", response_class=HTMLResponse, tags=["System"])
async def root():
    """Interactive API testing interface"""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Main execution
if __name__ == "__main__":
    os.makedirs(config.FRAMES_BASE_PATH, exist_ok=True)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )
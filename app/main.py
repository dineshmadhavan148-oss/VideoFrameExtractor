import os
import json
import time
import uuid
import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict

import cv2
import redis
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ffmpeg

# Configure logging
os.makedirs("runtime/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('runtime/logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Config:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "runtime/db/metadata.db")
    FRAMES_BASE_PATH = os.getenv("FRAMES_BASE_PATH", "runtime/frames")
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 5))
    CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))
    MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", 100))

config = Config()

# Data Models
@dataclass
class FrameMetadata:
    job_id: str
    timestamp: float
    frame_path: str
    file_size: int
    checksum: str
    created_at: datetime
    
    def to_dict(self):
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat()
        }

@dataclass
class JobStatus:
    job_id: str
    status: str  # pending, processing, completed, failed, cancelled
    video_source: str
    interval: float
    total_frames: int
    processed_frames: int
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

# Pydantic models for API
class VideoJobRequest(BaseModel):
    video_source: str  # file path or URL
    interval: float = 5.0  # seconds between frames
    
class VideoJobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class FrameMetadataResponse(BaseModel):
    job_id: str
    timestamp: float
    frame_path: str
    file_size: int
    checksum: str
    created_at: str

Path("runtime/frames").mkdir(parents=True, exist_ok=True)
Path("runtime/db").mkdir(parents=True, exist_ok=True)
Path("runtime/logs").mkdir(parents=True, exist_ok=True)


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    video_source TEXT NOT NULL,
                    interval REAL NOT NULL,
                    total_frames INTEGER DEFAULT 0,
                    processed_frames INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frame_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    frame_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_id ON frame_metadata(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON frame_metadata(timestamp)")
    
    def save_job(self, job: JobStatus):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs 
                (job_id, status, video_source, interval, total_frames, processed_frames, 
                 created_at, updated_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.status, job.video_source, job.interval,
                job.total_frames, job.processed_frames,
                job.created_at.isoformat(), job.updated_at.isoformat(),
                job.error_message
            ))
    
    def get_job(self, job_id: str) -> Optional[JobStatus]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            
            if row:
                return JobStatus(
                    job_id=row['job_id'],
                    status=row['status'],
                    video_source=row['video_source'],
                    interval=row['interval'],
                    total_frames=row['total_frames'],
                    processed_frames=row['processed_frames'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    error_message=row['error_message']
                )
        return None
    
    def save_frame_metadata(self, frame: FrameMetadata):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO frame_metadata 
                (job_id, timestamp, frame_path, file_size, checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                frame.job_id, frame.timestamp, frame.frame_path,
                frame.file_size, frame.checksum, frame.created_at.isoformat()
            ))
    
    def get_frames_by_job(self, job_id: str) -> List[FrameMetadata]:
        frames = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM frame_metadata WHERE job_id = ?
                ORDER BY timestamp
            """, (job_id,))
            
            for row in cursor.fetchall():
                frames.append(FrameMetadata(
                    job_id=row['job_id'],
                    timestamp=row['timestamp'],
                    frame_path=row['frame_path'],
                    file_size=row['file_size'],
                    checksum=row['checksum'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
        return frames
    
    def get_recent_frames(self, since: datetime, job_id: Optional[str] = None) -> List[FrameMetadata]:
        frames = []
        query = "SELECT * FROM frame_metadata WHERE created_at >= ?"
        params = [since.isoformat()]
        
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        
        query += " ORDER BY created_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            for row in cursor.fetchall():
                frames.append(FrameMetadata(
                    job_id=row['job_id'],
                    timestamp=row['timestamp'],
                    frame_path=row['frame_path'],
                    file_size=row['file_size'],
                    checksum=row['checksum'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
        return frames
    
    def delete_job_data(self, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM frame_metadata WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))

class CacheManager:
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                decode_responses=True
            )
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Connected to Redis cache")
        except Exception:
            self.use_redis = False
            self.memory_cache = {}
            logger.warning("Redis unavailable, using in-memory cache")
    
    def set(self, key: str, value: Any, ttl: int = None):
        if self.use_redis:
            self.redis_client.setex(key, ttl or config.CACHE_TTL, json.dumps(value))
        else:
            self.memory_cache[key] = {
                'value': value,
                'expires': time.time() + (ttl or config.CACHE_TTL)
            }
    
    def get(self, key: str) -> Optional[Any]:
        if self.use_redis:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        else:
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if time.time() < entry['expires']:
                    return entry['value']
                else:
                    del self.memory_cache[key]
            return None
    
    def delete(self, key: str):
        if self.use_redis:
            self.redis_client.delete(key)
        else:
            self.memory_cache.pop(key, None)
    
    def set_recent_frames(self, frames: List[FrameMetadata]):
        """Cache recent frames with job-specific keys"""
        for frame in frames:
            cache_key = f"frame:{frame.job_id}:{frame.timestamp}"
            self.set(cache_key, frame.to_dict())
        
        # Also cache by time ranges for dashboard queries
        recent_key = "recent_frames"
        frame_dicts = [frame.to_dict() for frame in frames]
        self.set(recent_key, frame_dicts, ttl=300)  # 5 minutes
    
    def get_recent_frames_cached(self, job_id: Optional[str] = None) -> List[Dict]:
        if job_id:
            # Try to get frames for specific job
            pattern = f"frame:{job_id}:*"
            if self.use_redis:
                keys = self.redis_client.keys(pattern)
                frames = []
                for key in keys:
                    frame_data = self.get(key)
                    if frame_data:
                        frames.append(frame_data)
                return sorted(frames, key=lambda x: x['timestamp'], reverse=True)
            else:
                frames = []
                for key, entry in self.memory_cache.items():
                    if key.startswith(f"frame:{job_id}:") and time.time() < entry['expires']:
                        frames.append(entry['value'])
                return sorted(frames, key=lambda x: x['timestamp'], reverse=True)
        else:
            return self.get("recent_frames") or []

class FrameExtractor:
    def __init__(self, db_manager: DatabaseManager, cache_manager: CacheManager):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        os.makedirs(config.FRAMES_BASE_PATH, exist_ok=True)
    
    def extract_frames_from_video(self, job_id: str, video_source: str, interval: float) -> bool:
        try:
            # Update job status
            job = self.db_manager.get_job(job_id)
            if not job:
                return False
            
            job.status = "processing"
            job.updated_at = datetime.now()
            self.db_manager.save_job(job)
            
            # Create job directory
            job_frames_path = Path(config.FRAMES_BASE_PATH) / job_id
            job_frames_path.mkdir(parents=True, exist_ok=True)
            
            # Open video
            cap = cv2.VideoCapture(video_source)
            if not cap.isOpened():
                raise Exception(f"Could not open video source: {video_source}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            # Calculate frame interval
            frame_interval = int(fps * interval) if fps > 0 else 30
            
            frame_count = 0
            extracted_frames = []
            
            logger.info(f"Processing video {job_id}: {total_frames} total frames, extracting every {frame_interval} frames")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    # Calculate timestamp
                    timestamp = frame_count / fps if fps > 0 else frame_count
                    
                    # Save frame
                    frame_filename = f"{timestamp:.2f}.jpg"
                    frame_path = job_frames_path / frame_filename
                    
                    cv2.imwrite(str(frame_path), frame)
                    
                    # Calculate file stats
                    file_size = frame_path.stat().st_size
                    checksum = self._calculate_checksum(frame_path)
                    
                    # Create metadata
                    frame_metadata = FrameMetadata(
                        job_id=job_id,
                        timestamp=timestamp,
                        frame_path=str(frame_path),
                        file_size=file_size,
                        checksum=checksum,
                        created_at=datetime.now()
                    )
                    
                    # Save to database
                    self.db_manager.save_frame_metadata(frame_metadata)
                    extracted_frames.append(frame_metadata)
                    
                    # Update job progress
                    job.processed_frames = len(extracted_frames)
                    job.updated_at = datetime.now()
                    self.db_manager.save_job(job)
                    
                    logger.info(f"Extracted frame at {timestamp:.2f}s for job {job_id}")
                
                frame_count += 1
            
            cap.release()
            
            # Update job as completed
            job.status = "completed"
            job.total_frames = len(extracted_frames)
            job.updated_at = datetime.now()
            self.db_manager.save_job(job)
            
            # Cache recent frames
            self.cache_manager.set_recent_frames(extracted_frames[-10:])  # Cache last 10 frames
            
            logger.info(f"Job {job_id} completed: extracted {len(extracted_frames)} frames")
            return True
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            
            # Update job as failed
            job = self.db_manager.get_job(job_id)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.updated_at = datetime.now()
                self.db_manager.save_job(job)
            
            return False
    
    def _calculate_checksum(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

class JobManager:
    def __init__(self, db_manager: DatabaseManager, cache_manager: CacheManager):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.frame_extractor = FrameExtractor(db_manager, cache_manager)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_JOBS)
        self.active_jobs = {}
    
    def submit_job(self, video_source: str, interval: float) -> str:
        job_id = str(uuid.uuid4())
        
        # Create job status
        job = JobStatus(
            job_id=job_id,
            status="pending",
            video_source=video_source,
            interval=interval,
            total_frames=0,
            processed_frames=0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Save to database
        self.db_manager.save_job(job)
        
        # Submit to thread pool
        future = self.executor.submit(
            self.frame_extractor.extract_frames_from_video,
            job_id, video_source, interval
        )
        self.active_jobs[job_id] = future
        
        logger.info(f"Submitted job {job_id} for video: {video_source}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        return self.db_manager.get_job(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        try:
            # Cancel future if active
            if job_id in self.active_jobs:
                future = self.active_jobs[job_id]
                future.cancel()
                del self.active_jobs[job_id]
            
            # Delete frames directory
            job_frames_path = Path(config.FRAMES_BASE_PATH) / job_id
            if job_frames_path.exists():
                import shutil
                shutil.rmtree(job_frames_path)
            
            # Delete from database
            self.db_manager.delete_job_data(job_id)
            
            # Clear cache
            self.cache_manager.delete(f"frames:{job_id}")
            
            logger.info(f"Cancelled and cleaned up job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {str(e)}")
            return False

class DashboardService:
    def __init__(self, db_manager: DatabaseManager, cache_manager: CacheManager):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
    
    def get_recent_frames(self, 
                         since_minutes: int = 60,
                         job_id: Optional[str] = None) -> List[Dict]:
        
        # Try cache first
        cached_frames = self.cache_manager.get_recent_frames_cached(job_id)
        if cached_frames:
            logger.info(f"Cache hit for recent frames (job_id: {job_id})")
            return cached_frames
        
        # Fallback to database
        logger.info(f"Cache miss, querying database for recent frames")
        since_time = datetime.now() - timedelta(minutes=since_minutes)
        frames = self.db_manager.get_recent_frames(since_time, job_id)
        
        # Cache the results
        if frames:
            self.cache_manager.set_recent_frames(frames)
        
        return [frame.to_dict() for frame in frames]

app = FastAPI(
    title="Video Frame Extraction System",
    version="1.0.0",
    description="A high-performance video frame extraction system with Redis caching and concurrent processing",
    docs_url="/docs",
    redoc_url="/redoc"
)

db_manager = DatabaseManager(config.DATABASE_PATH)
cache_manager = CacheManager()
job_manager = JobManager(db_manager, cache_manager)
dashboard_service = DashboardService(db_manager, cache_manager)

@app.post("/video-job", response_model=VideoJobResponse, tags=["Jobs"])
async def submit_video_job(
    request: VideoJobRequest, 
    background_tasks: BackgroundTasks
):
    """
    Submit a new video processing job for frame extraction.
    
    - **video_source**: Path to video file or URL
    - **interval**: Time interval between extracted frames (in seconds)
    
    Returns job ID and status for tracking progress.
    """
    try:
        job_id = job_manager.submit_job(request.video_source, request.interval)
        return VideoJobResponse(
            job_id=job_id,
            status="pending",
            message="Job submitted successfully"
        )
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
    job_id: Optional[str] = Query(None, description="Filter by specific job ID")
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
    """
    Interactive API testing interface - similar to FastAPI docs but simpler
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Frame Extraction API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }
            .header { background: #1f2937; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .endpoint { border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; }
            .endpoint-header { padding: 15px; background: #f8f9fa; cursor: pointer; display: flex; align-items: center; }
            .endpoint-header:hover { background: #e9ecef; }
            .endpoint-body { padding: 15px; display: none; }
            .endpoint-body.show { display: block; }
            .method { display: inline-block; padding: 4px 12px; border-radius: 4px; color: white; font-weight: bold; margin-right: 10px; }
            .method.post { background: #28a745; }
            .method.get { background: #007bff; }
            .method.delete { background: #dc3545; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            .btn { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #0056b3; }
            .response { margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; }
            .response pre { background: #2d3748; color: #e2e8f0; padding: 10px; border-radius: 4px; overflow-x: auto; }
            .quick-links { text-align: center; margin-bottom: 20px; }
            .quick-links a { display: inline-block; background: #007bff; color: white; padding: 10px 15px; margin: 0 5px; text-decoration: none; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎬 Video Frame Extraction System API</h1>
            <p>Interactive API testing interface</p>
        </div>

        <div class="quick-links">
            <a href="/docs" target="_blank">📋 Swagger Docs</a>
            <a href="/redoc" target="_blank">📖 ReDoc</a>
            <a href="/health" target="_blank">💚 Health Check</a>
        </div>

        <!-- Submit Video Job -->
        <div class="endpoint">
            <div class="endpoint-header" onclick="toggle('submit-job')">
                <span class="method post">POST</span>
                <span>/video-job - Submit new video processing job</span>
            </div>
            <div class="endpoint-body" id="submit-job">
                <form onsubmit="submitJob(event)">
                    <div class="form-group">
                        <label>Video Source (file path or URL):</label>
                        <input type="text" id="video_source" placeholder="sample.mp4 or http://example.com/video.mp4" required>
                    </div>
                    <div class="form-group">
                        <label>Interval (seconds between frames):</label>
                        <input type="number" id="interval" value="5.0" step="0.1" min="0.1" required>
                    </div>
                    <button type="submit" class="btn">Submit Job</button>
                </form>
                <div class="response" id="submit-response" style="display:none;"></div>
            </div>
        </div>

        <!-- Check Job Status -->
        <div class="endpoint">
            <div class="endpoint-header" onclick="toggle('job-status')">
                <span class="method get">GET</span>
                <span>/job-status/{job_id} - Check job status</span>
            </div>
            <div class="endpoint-body" id="job-status">
                <form onsubmit="checkStatus(event)">
                    <div class="form-group">
                        <label>Job ID:</label>
                        <input type="text" id="job_id_status" placeholder="Enter job ID" required>
                    </div>
                    <button type="submit" class="btn">Check Status</button>
                </form>
                <div class="response" id="status-response" style="display:none;"></div>
            </div>
        </div>

        <!-- Get Job Frames -->
        <div class="endpoint">
            <div class="endpoint-header" onclick="toggle('job-frames')">
                <span class="method get">GET</span>
                <span>/frames/{job_id} - Get all frames for job</span>
            </div>
            <div class="endpoint-body" id="job-frames">
                <form onsubmit="getFrames(event)">
                    <div class="form-group">
                        <label>Job ID:</label>
                        <input type="text" id="job_id_frames" placeholder="Enter job ID" required>
                    </div>
                    <button type="submit" class="btn">Get Frames</button>
                </form>
                <div class="response" id="frames-response" style="display:none;"></div>
            </div>
        </div>

        <!-- Recent Frames Dashboard -->
        <div class="endpoint">
            <div class="endpoint-header" onclick="toggle('recent-frames')">
                <span class="method get">GET</span>
                <span>/dashboard/recent-frames - Get recent frames</span>
            </div>
            <div class="endpoint-body" id="recent-frames">
                <form onsubmit="getRecent(event)">
                    <div class="form-group">
                        <label>Since Minutes:</label>
                        <input type="number" id="since_minutes" value="60" min="1" required>
                    </div>
                    <div class="form-group">
                        <label>Job ID (optional):</label>
                        <input type="text" id="job_id_recent" placeholder="Leave empty for all jobs">
                    </div>
                    <button type="submit" class="btn">Get Recent Frames</button>
                </form>
                <div class="response" id="recent-response" style="display:none;"></div>
            </div>
        </div>

        <!-- Cancel Job -->
        <div class="endpoint">
            <div class="endpoint-header" onclick="toggle('cancel-job')">
                <span class="method delete">DELETE</span>
                <span>/job/{job_id} - Cancel and delete job</span>
            </div>
            <div class="endpoint-body" id="cancel-job">
                <form onsubmit="cancelJob(event)">
                    <div class="form-group">
                        <label>Job ID:</label>
                        <input type="text" id="job_id_cancel" placeholder="Enter job ID to cancel" required>
                    </div>
                    <button type="submit" class="btn" style="background: #dc3545;">Cancel Job</button>
                </form>
                <div class="response" id="cancel-response" style="display:none;"></div>
            </div>
        </div>

        <script>
            function toggle(id) {
                const element = document.getElementById(id);
                element.classList.toggle('show');
            }

            async function makeRequest(url, options = {}) {
                try {
                    const response = await fetch(url, {
                        headers: { 'Content-Type': 'application/json', ...options.headers },
                        ...options
                    });
                    const data = await response.json();
                    return { success: response.ok, data, status: response.status };
                } catch (error) {
                    return { success: false, error: error.message };
                }
            }

            function showResponse(elementId, result) {
                const el = document.getElementById(elementId);
                el.style.display = 'block';
                const status = result.success ? `✅ Success (${result.status})` : `❌ Error (${result.status || 'Network'})`;
                const content = result.error || JSON.stringify(result.data, null, 2);
                el.innerHTML = `<strong>${status}</strong><pre>${content}</pre>`;
            }

            async function submitJob(event) {
                event.preventDefault();
                const data = {
                    video_source: document.getElementById('video_source').value,
                    interval: parseFloat(document.getElementById('interval').value)
                };
                const result = await makeRequest('/video-job', { method: 'POST', body: JSON.stringify(data) });
                showResponse('submit-response', result);
                if (result.success && result.data.job_id) {
                    // Auto-fill job ID in other forms
                    const jobId = result.data.job_id;
                    document.getElementById('job_id_status').value = jobId;
                    document.getElementById('job_id_frames').value = jobId;
                    document.getElementById('job_id_cancel').value = jobId;
                }
            }

            async function checkStatus(event) {
                event.preventDefault();
                const jobId = document.getElementById('job_id_status').value;
                const result = await makeRequest(`/job-status/${jobId}`);
                showResponse('status-response', result);
            }

            async function getFrames(event) {
                event.preventDefault();
                const jobId = document.getElementById('job_id_frames').value;
                const result = await makeRequest(`/frames/${jobId}`);
                showResponse('frames-response', result);
            }

            async function getRecent(event) {
                event.preventDefault();
                const minutes = document.getElementById('since_minutes').value;
                const jobId = document.getElementById('job_id_recent').value;
                let url = `/dashboard/recent-frames?since_minutes=${minutes}`;
                if (jobId) url += `&job_id=${jobId}`;
                const result = await makeRequest(url);
                showResponse('recent-response', result);
            }

            async function cancelJob(event) {
                event.preventDefault();
                const jobId = document.getElementById('job_id_cancel').value;
                if (!confirm(`Cancel job ${jobId}? This will delete all data.`)) return;
                const result = await makeRequest(`/job/${jobId}`, { method: 'DELETE' });
                showResponse('cancel-response', result);
            }
        </script>
    </body>
    </html>
    """

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
import uuid
import logging
import shutil
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
try:
    from .config import config
    from .models import JobStatus
    from .frame_extractor import FrameExtractor
except ImportError:
    from config import config
    from models import JobStatus
    from frame_extractor import FrameExtractor

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, db_manager, cache_manager):
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
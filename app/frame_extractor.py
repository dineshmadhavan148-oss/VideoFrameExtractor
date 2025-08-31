import os
import cv2
import hashlib
import logging
from datetime import datetime
from pathlib import Path
try:
    from .config import config
    from .models import FrameMetadata
except ImportError:
    from config import config
    from models import FrameMetadata

logger = logging.getLogger(__name__)

class FrameExtractor:
    def __init__(self, db_manager, cache_manager):
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
            
            # Open video with better error handling
            logger.info(f"Attempting to open video: {video_source}")
            
            # Check if file exists first
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Absolute path: {os.path.abspath(video_source)}")
            logger.info(f"File exists check: {os.path.exists(video_source)}")
            
            if not os.path.exists(video_source):
                raise Exception(f"Video file does not exist: {video_source}")
            
            # Try to open with OpenCV
            cap = cv2.VideoCapture(video_source)
            if not cap.isOpened():
                # Try different backends
                logger.warning(f"Failed to open with default backend, trying CAP_FFMPEG")
                cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
                
                if not cap.isOpened():
                    logger.warning(f"Failed to open with CAP_FFMPEG, trying CAP_MSMF")
                    cap = cv2.VideoCapture(video_source, cv2.CAP_MSMF)
                    
                    if not cap.isOpened():
                        raise Exception(f"Could not open video source with any backend: {video_source}. "
                                      f"Check if OpenCV has codec support for this video format.")
            
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
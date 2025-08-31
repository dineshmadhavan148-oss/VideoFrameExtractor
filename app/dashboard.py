import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self, db_manager, cache_manager):
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
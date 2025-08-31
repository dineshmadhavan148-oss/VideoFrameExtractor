import json
import time
import logging
from typing import List, Dict, Optional, Any
import redis
try:
    from .config import config
    from .models import FrameMetadata
except ImportError:
    from config import config
    from models import FrameMetadata

logger = logging.getLogger(__name__)

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
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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
import sqlite3
from datetime import datetime
from typing import List, Optional
try:
    from .models import FrameMetadata, JobStatus
except ImportError:
    from models import FrameMetadata, JobStatus

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
import unittest
from datetime import datetime
from dataclasses import asdict
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import FrameMetadata, JobStatus, VideoJobRequest, VideoJobResponse


class TestDataModels(unittest.TestCase):
    """Test data models and Pydantic models"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_job_id = "test-job-123"
        self.test_timestamp = datetime.now()
    
    def test_frame_metadata_creation(self):
        """Test FrameMetadata dataclass creation"""
        frame = FrameMetadata(
            job_id=self.test_job_id,
            timestamp=10.5,
            frame_path="/path/to/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=self.test_timestamp
        )
        
        self.assertEqual(frame.job_id, self.test_job_id)
        self.assertEqual(frame.timestamp, 10.5)
        self.assertEqual(frame.file_size, 1024)
        self.assertEqual(frame.checksum, "abc123")
    
    def test_frame_metadata_to_dict(self):
        """Test FrameMetadata to_dict method"""
        frame = FrameMetadata(
            job_id=self.test_job_id,
            timestamp=10.5,
            frame_path="/path/to/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=self.test_timestamp
        )
        
        frame_dict = frame.to_dict()
        
        self.assertIsInstance(frame_dict, dict)
        self.assertEqual(frame_dict['job_id'], self.test_job_id)
        self.assertEqual(frame_dict['timestamp'], 10.5)
        self.assertEqual(frame_dict['created_at'], self.test_timestamp.isoformat())
    
    def test_job_status_creation(self):
        """Test JobStatus dataclass creation"""
        job = JobStatus(
            job_id=self.test_job_id,
            status="pending",
            video_source="test.mp4",
            interval=5.0,
            total_frames=0,
            processed_frames=0,
            created_at=self.test_timestamp,
            updated_at=self.test_timestamp
        )
        
        self.assertEqual(job.job_id, self.test_job_id)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.video_source, "test.mp4")
        self.assertEqual(job.interval, 5.0)
        self.assertIsNone(job.error_message)
    
    def test_video_job_request_validation(self):
        """Test VideoJobRequest Pydantic model"""
        # Valid request
        request = VideoJobRequest(
            video_source="test.mp4",
            interval=5.0
        )
        self.assertEqual(request.video_source, "test.mp4")
        self.assertEqual(request.interval, 5.0)
        
        # Test default interval
        request_default = VideoJobRequest(video_source="test.mp4")
        self.assertEqual(request_default.interval, 5.0)
    
    def test_video_job_response(self):
        """Test VideoJobResponse model"""
        response = VideoJobResponse(
            job_id=self.test_job_id,
            status="pending",
            message="Job created successfully"
        )
        
        self.assertEqual(response.job_id, self.test_job_id)
        self.assertEqual(response.status, "pending")
        self.assertEqual(response.message, "Job created successfully")


if __name__ == '__main__':
    unittest.main()
import unittest
import sys
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


class TestAPI(unittest.TestCase):
    """Test FastAPI endpoints"""
    
    def setUp(self):
        """Set up test client"""
        # Mock Redis to avoid connection issues in tests
        with patch('cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Redis unavailable")
            
            # Import app after mocking Redis
            from main import app
            self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)
        self.assertIn("redis_available", data)
        self.assertIn("active_jobs", data)
    
    def test_root_endpoint(self):
        """Test root endpoint returns HTML"""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Video Frame Extraction System API", response.text)
    
    @patch('main.job_manager.submit_job')
    def test_submit_video_job_success(self, mock_submit_job):
        """Test successful video job submission"""
        # Mock job submission
        mock_submit_job.return_value = "test-job-123"
        
        response = self.client.post("/video-job", json={
            "video_source": "test.mp4",
            "interval": 5.0
        })
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["job_id"], "test-job-123")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["message"], "Job submitted successfully")
        
        # Verify mock was called with correct parameters
        mock_submit_job.assert_called_once_with("test.mp4", 5.0)
    
    def test_submit_video_job_invalid_data(self):
        """Test video job submission with invalid data"""
        response = self.client.post("/video-job", json={
            "video_source": "",  # Empty source
            "interval": -1.0     # Invalid interval
        })
        
        # Should still accept the request (validation is in Pydantic)
        self.assertEqual(response.status_code, 422)
    
    @patch('main.job_manager.get_job_status')
    def test_get_job_status_success(self, mock_get_job_status):
        """Test successful job status retrieval"""
        from models import JobStatus
        from datetime import datetime
        
        # Mock job status
        mock_job = JobStatus(
            job_id="test-job-123",
            status="processing",
            video_source="test.mp4",
            interval=5.0,
            total_frames=10,
            processed_frames=5,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_get_job_status.return_value = mock_job
        
        response = self.client.get("/job-status/test-job-123")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["job_id"], "test-job-123")
        self.assertEqual(data["status"], "processing")
        self.assertEqual(data["video_source"], "test.mp4")
        self.assertEqual(data["total_frames"], 10)
        self.assertEqual(data["processed_frames"], 5)
    
    @patch('main.job_manager.get_job_status')
    def test_get_job_status_not_found(self, mock_get_job_status):
        """Test job status retrieval for non-existent job"""
        mock_get_job_status.return_value = None
        
        response = self.client.get("/job-status/nonexistent-job")
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Job not found")
    
    @patch('main.db_manager.get_frames_by_job')
    @patch('main.job_manager.get_job_status')
    def test_get_job_frames_success(self, mock_get_job_status, mock_get_frames):
        """Test successful frames retrieval"""
        from models import FrameMetadata, JobStatus
        from datetime import datetime
        
        # Mock frames
        mock_frames = [
            FrameMetadata(
                job_id="test-job-123",
                timestamp=0.0,
                frame_path="/test/frame_0.jpg",
                file_size=1024,
                checksum="abc123",
                created_at=datetime.now()
            ),
            FrameMetadata(
                job_id="test-job-123",
                timestamp=5.0,
                frame_path="/test/frame_5.jpg",
                file_size=1024,
                checksum="def456",
                created_at=datetime.now()
            )
        ]
        mock_get_frames.return_value = mock_frames
        
        response = self.client.get("/frames/test-job-123")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["job_id"], "test-job-123")
        self.assertEqual(data["total_count"], 2)
        self.assertEqual(len(data["frames"]), 2)
        self.assertEqual(data["frames"][0]["timestamp"], 0.0)
        self.assertEqual(data["frames"][1]["timestamp"], 5.0)
    
    @patch('main.db_manager.get_frames_by_job')
    @patch('main.job_manager.get_job_status')
    def test_get_job_frames_no_frames(self, mock_get_job_status, mock_get_frames):
        """Test frames retrieval when no frames exist"""
        from models import JobStatus
        from datetime import datetime
        
        # Mock empty frames but existing job
        mock_get_frames.return_value = []
        mock_get_job_status.return_value = JobStatus(
            job_id="test-job-123",
            status="pending",
            video_source="test.mp4",
            interval=5.0,
            total_frames=0,
            processed_frames=0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        response = self.client.get("/frames/test-job-123")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["frames"], [])
        self.assertEqual(data["message"], "No frames extracted yet")
    
    @patch('main.dashboard_service.get_recent_frames')
    def test_get_recent_frames(self, mock_get_recent_frames):
        """Test recent frames endpoint"""
        # Mock recent frames
        mock_frames = [
            {
                "job_id": "test-job-123",
                "timestamp": 5.0,
                "frame_path": "/test/frame.jpg",
                "file_size": 1024,
                "checksum": "abc123",
                "created_at": "2023-01-01T10:00:00"
            }
        ]
        mock_get_recent_frames.return_value = mock_frames
        
        response = self.client.get("/dashboard/recent-frames?since_minutes=60")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["since_minutes"], 60)
        self.assertEqual(len(data["frames"]), 1)
    
    @patch('main.job_manager.cancel_job')
    def test_cancel_job_success(self, mock_cancel_job):
        """Test successful job cancellation"""
        mock_cancel_job.return_value = True
        
        response = self.client.delete("/job/test-job-123")
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["message"], "Job test-job-123 cancelled and cleaned up successfully")
    
    @patch('main.job_manager.cancel_job')
    def test_cancel_job_not_found(self, mock_cancel_job):
        """Test job cancellation when job not found"""
        mock_cancel_job.return_value = False
        
        response = self.client.delete("/job/nonexistent-job")
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Job not found or could not be cancelled")


if __name__ == '__main__':
    unittest.main()
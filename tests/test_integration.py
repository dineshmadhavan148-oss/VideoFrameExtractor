import unittest
import tempfile
import os
import shutil
import sys
from unittest.mock import patch, Mock
import time

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from database import DatabaseManager
from cache import CacheManager
from job_manager import JobManager
from frame_extractor import FrameExtractor


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system"""
    
    def setUp(self):
        """Set up integration test environment"""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, 'test.db')
        self.temp_frames_path = os.path.join(self.temp_dir, 'frames')
        os.makedirs(self.temp_frames_path, exist_ok=True)
        
        # Mock Redis connection
        with patch('cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Redis unavailable")
            
            # Initialize components
            self.db_manager = DatabaseManager(self.temp_db_path)
            self.cache_manager = CacheManager()
            self.job_manager = JobManager(self.db_manager, self.cache_manager)
    
    def tearDown(self):
        """Clean up test environment"""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_complete_job_lifecycle(self):
        """Test complete job lifecycle from creation to completion"""
        # Submit a job
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("test.mp4", 5.0)
        
        # Verify job was created
        job = self.job_manager.get_job_status(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.video_source, "test.mp4")
        self.assertEqual(job.interval, 5.0)
        
        # Job ID should be a valid UUID
        self.assertEqual(len(job_id), 36)  # UUID length
        self.assertIn('-', job_id)
    
    def test_job_status_updates(self):
        """Test job status updates throughout processing"""
        # Submit a job
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("test.mp4", 5.0)
        
        # Get initial status
        job = self.job_manager.get_job_status(job_id)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.processed_frames, 0)
        
        # Update job status manually (simulating processing)
        job.status = "processing"
        job.processed_frames = 5
        self.db_manager.save_job(job)
        
        # Verify update
        updated_job = self.job_manager.get_job_status(job_id)
        self.assertEqual(updated_job.status, "processing")
        self.assertEqual(updated_job.processed_frames, 5)
    
    def test_frame_metadata_storage(self):
        """Test frame metadata storage and retrieval"""
        from models import FrameMetadata
        from datetime import datetime
        
        # Submit a job
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("test.mp4", 5.0)
        
        # Create and store frame metadata
        frame_metadata = FrameMetadata(
            job_id=job_id,
            timestamp=5.0,
            frame_path=f"{self.temp_frames_path}/{job_id}/5.00.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=datetime.now()
        )
        
        self.db_manager.save_frame_metadata(frame_metadata)
        
        # Retrieve frames for job
        frames = self.db_manager.get_frames_by_job(job_id)
        
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].job_id, job_id)
        self.assertEqual(frames[0].timestamp, 5.0)
        self.assertEqual(frames[0].checksum, "abc123")
    
    def test_cache_integration(self):
        """Test cache integration with frame storage"""
        from models import FrameMetadata
        from datetime import datetime
        
        # Create frame metadata
        frame = FrameMetadata(
            job_id="test-job-123",
            timestamp=5.0,
            frame_path="/test/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=datetime.now()
        )
        
        # Cache frames
        self.cache_manager.set_recent_frames([frame])
        
        # Retrieve from cache
        cached_frames = self.cache_manager.get_recent_frames_cached("test-job-123")
        
        self.assertEqual(len(cached_frames), 1)
        self.assertEqual(cached_frames[0]['job_id'], "test-job-123")
        self.assertEqual(cached_frames[0]['timestamp'], 5.0)
    
    def test_job_cancellation(self):
        """Test job cancellation and cleanup"""
        # Submit a job
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("test.mp4", 5.0)
        
        # Create job directory
        job_dir = os.path.join(self.temp_frames_path, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Create a test file in job directory
        test_file = os.path.join(job_dir, "test_frame.jpg")
        with open(test_file, 'w') as f:
            f.write("test frame data")
        
        # Verify job exists
        job = self.job_manager.get_job_status(job_id)
        self.assertIsNotNone(job)
        self.assertTrue(os.path.exists(job_dir))
        
        # Cancel job
        success = self.job_manager.cancel_job(job_id)
        
        self.assertTrue(success)
        
        # Verify cleanup
        job = self.job_manager.get_job_status(job_id)
        self.assertIsNone(job)
        self.assertFalse(os.path.exists(job_dir))
    
    @patch('frame_extractor.cv2.VideoCapture')
    def test_frame_extractor_error_handling(self, mock_video_capture):
        """Test frame extractor error handling"""
        # Mock failed video opening
        mock_cap = Mock()
        mock_cap.isOpened.return_value = False
        mock_video_capture.return_value = mock_cap
        
        frame_extractor = FrameExtractor(self.db_manager, self.cache_manager)
        
        # Submit job that will fail
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("invalid.mp4", 5.0)
        
        # Attempt to extract frames (should fail)
        result = frame_extractor.extract_frames_from_video(job_id, "invalid.mp4", 5.0)
        
        self.assertFalse(result)
        
        # Check that job status was updated to failed
        job = self.db_manager.get_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.error_message)
    
    def test_concurrent_job_handling(self):
        """Test handling multiple concurrent jobs"""
        job_ids = []
        
        # Submit multiple jobs
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            for i in range(3):
                job_id = self.job_manager.submit_job(f"test_{i}.mp4", 5.0)
                job_ids.append(job_id)
        
        # Verify all jobs were created
        for job_id in job_ids:
            job = self.job_manager.get_job_status(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "pending")
        
        # Verify jobs have different IDs
        self.assertEqual(len(set(job_ids)), 3)
    
    def test_database_consistency(self):
        """Test database consistency across operations"""
        from models import FrameMetadata
        from datetime import datetime
        
        # Create job
        with patch('main.config.FRAMES_BASE_PATH', self.temp_frames_path):
            job_id = self.job_manager.submit_job("test.mp4", 5.0)
        
        # Add multiple frames
        for i in range(5):
            frame = FrameMetadata(
                job_id=job_id,
                timestamp=float(i * 5),
                frame_path=f"/test/frame_{i}.jpg",
                file_size=1024,
                checksum=f"checksum_{i}",
                created_at=datetime.now()
            )
            self.db_manager.save_frame_metadata(frame)
        
        # Verify frame count
        frames = self.db_manager.get_frames_by_job(job_id)
        self.assertEqual(len(frames), 5)
        
        # Update job with frame count
        job = self.db_manager.get_job(job_id)
        job.total_frames = len(frames)
        job.processed_frames = len(frames)
        job.status = "completed"
        self.db_manager.save_job(job)
        
        # Verify consistency
        updated_job = self.db_manager.get_job(job_id)
        frame_count = len(self.db_manager.get_frames_by_job(job_id))
        
        self.assertEqual(updated_job.total_frames, frame_count)
        self.assertEqual(updated_job.processed_frames, frame_count)
        self.assertEqual(updated_job.status, "completed")


if __name__ == '__main__':
    unittest.main()
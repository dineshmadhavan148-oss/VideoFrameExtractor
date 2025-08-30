import unittest
import tempfile
import os
import sqlite3
from datetime import datetime
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import DatabaseManager, JobStatus, FrameMetadata


class TestDatabaseManager(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Set up test database"""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)
        
        # Test data
        self.test_job_id = "test-job-123"
        self.test_timestamp = datetime.now()
        
        self.test_job = JobStatus(
            job_id=self.test_job_id,
            status="pending",
            video_source="test.mp4",
            interval=5.0,
            total_frames=0,
            processed_frames=0,
            created_at=self.test_timestamp,
            updated_at=self.test_timestamp
        )
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database tables are created"""
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
        self.assertIn('jobs', tables)
        self.assertIn('frame_metadata', tables)
    
    def test_save_and_get_job(self):
        """Test saving and retrieving jobs"""
        # Save job
        self.db_manager.save_job(self.test_job)
        
        # Retrieve job
        retrieved_job = self.db_manager.get_job(self.test_job_id)
        
        self.assertIsNotNone(retrieved_job)
        self.assertEqual(retrieved_job.job_id, self.test_job_id)
        self.assertEqual(retrieved_job.status, "pending")
        self.assertEqual(retrieved_job.video_source, "test.mp4")
        self.assertEqual(retrieved_job.interval, 5.0)
    
    def test_get_nonexistent_job(self):
        """Test retrieving non-existent job"""
        job = self.db_manager.get_job("nonexistent-job")
        self.assertIsNone(job)
    
    def test_update_job(self):
        """Test updating job status"""
        # Save initial job
        self.db_manager.save_job(self.test_job)
        
        # Update job
        self.test_job.status = "completed"
        self.test_job.total_frames = 10
        self.test_job.processed_frames = 10
        self.db_manager.save_job(self.test_job)
        
        # Retrieve updated job
        updated_job = self.db_manager.get_job(self.test_job_id)
        
        self.assertEqual(updated_job.status, "completed")
        self.assertEqual(updated_job.total_frames, 10)
        self.assertEqual(updated_job.processed_frames, 10)
    
    def test_save_frame_metadata(self):
        """Test saving frame metadata"""
        frame = FrameMetadata(
            job_id=self.test_job_id,
            timestamp=10.5,
            frame_path="/test/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=self.test_timestamp
        )
        
        self.db_manager.save_frame_metadata(frame)
        
        # Verify frame was saved
        frames = self.db_manager.get_frames_by_job(self.test_job_id)
        
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].job_id, self.test_job_id)
        self.assertEqual(frames[0].timestamp, 10.5)
        self.assertEqual(frames[0].checksum, "abc123")
    
    def test_get_frames_by_job(self):
        """Test retrieving frames by job ID"""
        # Create multiple frames
        for i in range(3):
            frame = FrameMetadata(
                job_id=self.test_job_id,
                timestamp=float(i * 5),
                frame_path=f"/test/frame_{i}.jpg",
                file_size=1024 + i,
                checksum=f"checksum_{i}",
                created_at=self.test_timestamp
            )
            self.db_manager.save_frame_metadata(frame)
        
        frames = self.db_manager.get_frames_by_job(self.test_job_id)
        
        self.assertEqual(len(frames), 3)
        # Should be ordered by timestamp
        self.assertEqual(frames[0].timestamp, 0.0)
        self.assertEqual(frames[1].timestamp, 5.0)
        self.assertEqual(frames[2].timestamp, 10.0)
    
    def test_delete_job_data(self):
        """Test deleting job and associated frames"""
        # Save job and frame
        self.db_manager.save_job(self.test_job)
        
        frame = FrameMetadata(
            job_id=self.test_job_id,
            timestamp=10.5,
            frame_path="/test/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=self.test_timestamp
        )
        self.db_manager.save_frame_metadata(frame)
        
        # Delete job data
        self.db_manager.delete_job_data(self.test_job_id)
        
        # Verify deletion
        job = self.db_manager.get_job(self.test_job_id)
        frames = self.db_manager.get_frames_by_job(self.test_job_id)
        
        self.assertIsNone(job)
        self.assertEqual(len(frames), 0)


if __name__ == '__main__':
    unittest.main()
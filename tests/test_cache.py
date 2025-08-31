import unittest
import time
from unittest.mock import Mock, patch
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from cache import CacheManager
from models import FrameMetadata
from datetime import datetime


class TestCacheManager(unittest.TestCase):
    """Test cache operations"""
    
    def setUp(self):
        """Set up test cache manager (without Redis)"""
        with patch('cache.redis.Redis') as mock_redis:
            # Simulate Redis connection failure
            mock_redis.return_value.ping.side_effect = Exception("Redis unavailable")
            self.cache_manager = CacheManager()
        
        # Test data
        self.test_frame = FrameMetadata(
            job_id="test-job-123",
            timestamp=10.5,
            frame_path="/test/frame.jpg",
            file_size=1024,
            checksum="abc123",
            created_at=datetime.now()
        )
    
    def test_cache_initialization_without_redis(self):
        """Test cache manager falls back to memory cache when Redis unavailable"""
        self.assertFalse(self.cache_manager.use_redis)
        self.assertIsInstance(self.cache_manager.memory_cache, dict)
    
    def test_set_and_get_value(self):
        """Test setting and getting cache values"""
        key = "test_key"
        value = {"test": "data"}
        
        # Set value
        self.cache_manager.set(key, value, ttl=60)
        
        # Get value
        retrieved_value = self.cache_manager.get(key)
        
        self.assertEqual(retrieved_value, value)
    
    def test_get_nonexistent_key(self):
        """Test getting non-existent key returns None"""
        result = self.cache_manager.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        key = "expire_test"
        value = {"test": "data"}
        
        # Set with very short TTL
        self.cache_manager.set(key, value, ttl=1)
        
        # Should exist immediately
        self.assertEqual(self.cache_manager.get(key), value)
        
        # Wait for expiration
        time.sleep(2)
        
        # Should be expired
        self.assertIsNone(self.cache_manager.get(key))
    
    def test_delete_key(self):
        """Test deleting cache keys"""
        key = "delete_test"
        value = {"test": "data"}
        
        # Set and verify
        self.cache_manager.set(key, value)
        self.assertEqual(self.cache_manager.get(key), value)
        
        # Delete and verify
        self.cache_manager.delete(key)
        self.assertIsNone(self.cache_manager.get(key))
    
    def test_set_recent_frames(self):
        """Test caching recent frames"""
        frames = [self.test_frame]
        
        # Set recent frames
        self.cache_manager.set_recent_frames(frames)
        
        # Check individual frame cache
        frame_key = f"frame:{self.test_frame.job_id}:{self.test_frame.timestamp}"
        cached_frame = self.cache_manager.get(frame_key)
        
        self.assertIsNotNone(cached_frame)
        self.assertEqual(cached_frame['job_id'], self.test_frame.job_id)
        self.assertEqual(cached_frame['timestamp'], self.test_frame.timestamp)
        
        # Check recent frames cache
        recent_frames = self.cache_manager.get("recent_frames")
        self.assertIsNotNone(recent_frames)
        self.assertEqual(len(recent_frames), 1)
    
    def test_get_recent_frames_cached(self):
        """Test getting cached recent frames"""
        frames = [self.test_frame]
        
        # Set recent frames
        self.cache_manager.set_recent_frames(frames)
        
        # Get cached frames for specific job
        cached_frames = self.cache_manager.get_recent_frames_cached(self.test_frame.job_id)
        
        self.assertEqual(len(cached_frames), 1)
        self.assertEqual(cached_frames[0]['job_id'], self.test_frame.job_id)
        
        # Get all cached frames
        all_cached_frames = self.cache_manager.get_recent_frames_cached()
        self.assertEqual(len(all_cached_frames), 1)
    
    @patch('cache.redis.Redis')
    def test_redis_cache_manager(self, mock_redis_class):
        """Test cache manager with Redis"""
        # Mock Redis instance
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.ping.return_value = True
        mock_redis.setex.return_value = True
        mock_redis.get.return_value = '{"test": "data"}'
        mock_redis.delete.return_value = True
        
        # Create cache manager with Redis
        cache_manager = CacheManager()
        
        # Should use Redis
        self.assertTrue(cache_manager.use_redis)
        
        # Test set
        cache_manager.set("test_key", {"test": "data"})
        mock_redis.setex.assert_called()
        
        # Test get
        result = cache_manager.get("test_key")
        mock_redis.get.assert_called_with("test_key")
        self.assertEqual(result, {"test": "data"})
        
        # Test delete
        cache_manager.delete("test_key")
        mock_redis.delete.assert_called_with("test_key")


if __name__ == '__main__':
    unittest.main()
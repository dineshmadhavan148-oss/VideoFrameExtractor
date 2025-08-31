import os

class Config:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "runtime/db/metadata.db")
    FRAMES_BASE_PATH = os.getenv("FRAMES_BASE_PATH", "runtime/frames")
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 5))
    CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))
    MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", 100))

config = Config()
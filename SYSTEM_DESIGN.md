# Video Frame Extractor - System Design Document

## System Overview

A microservice that extracts frames from videos at specified time intervals, designed for scalability and concurrent processing.

## Core User Journey

```
User uploads video → System processes → Frames extracted → User gets results
```

### Detailed Flow

1. **User submits video** (via web upload or file path)
2. **System validates** video format and creates job
3. **Background processing** extracts frames at intervals
4. **Frames saved** to disk with metadata in database
5. **User monitors** progress via job status API
6. **Results delivered** as frame metadata with file locations

## System Architecture

### Component Overview

```
┌─────────────────┐
│   Web Client    │ ← User interacts here
└─────────────────┘
         │
         │ HTTP Request
         ▼
┌─────────────────┐
│   FastAPI App   │ ← Entry point, handles requests
└─────────────────┘
         │
         │ Creates job
         ▼
┌─────────────────┐
│  Job Manager    │ ← Manages concurrent processing
└─────────────────┘
         │
         │ Delegates to
         ▼
┌─────────────────┐
│ Frame Extractor │ ← Does the actual video processing
└─────────────────┘
         │
         │ Stores data in
         ▼
┌─────────────────┬─────────────────┐
│  Database       │   File System   │ ← Persistence layers
│  (Metadata)     │   (Frames)      │
└─────────────────┴─────────────────┘
```

## Data Flow

### 1. Job Submission Flow

```
POST /video-job → Validate Input → Create Job Record → Return Job ID
                      │
                      ▼
                Save to Database ← Generate UUID
```

### 2. Processing Flow

```
Job Manager → Get Job from Queue → Frame Extractor → Extract Frames
     │                                    │
     ▼                                    ▼
Update Job Status                   Save Frames + Metadata
```

### 3. Monitoring Flow

```
GET /job-status → Check Database → Return Current Status
                       │
                       ▼
                 Cache Recent Results
```

## Key Components Explained

### 1. FastAPI Application (Entry Point)
- **Purpose**: Handle HTTP requests and responses
- **Responsibilities**: 
  - File upload handling
  - Request validation
  - Route management
- **Files**: `main.py`

### 2. Job Manager (Orchestration)
- **Purpose**: Coordinate video processing jobs
- **Key Features**:
  - Thread pool for concurrent processing
  - Job lifecycle management
  - Resource management
- **Files**: `job_manager.py`

### 3. Frame Extractor (Core Logic)
- **Purpose**: Extract frames from videos
- **Process**:
  ```
  Open Video → Calculate Intervals → Extract Frames → Save Images → Update Progress
  ```
- **Files**: `frame_extractor.py`

### 4. Data Storage
- **Database**: SQLite for job metadata and frame info
- **File System**: Local storage for extracted frame images
- **Cache**: Redis for performance optimization

## Processing Algorithm

### Frame Extraction Logic

```
1. Open video file with OpenCV
2. Get video properties (FPS, total frames, duration)
3. Calculate frame extraction interval:
   frame_interval = FPS × user_specified_seconds
4. Loop through video:
   - Read frame
   - If frame_number % frame_interval == 0:
     - Save frame as JPEG
     - Calculate file checksum
     - Store metadata in database
     - Update job progress
5. Mark job as completed
```

### Example Calculation
```
Video: 30 FPS, 120 seconds duration
User wants: 1 frame every 5 seconds
Calculation: Extract every (30 × 5) = 150th frame
Result: 24 frames total (120 ÷ 5)
```

## Database Schema

### Jobs Table
```sql
jobs (
  job_id          TEXT PRIMARY KEY,
  status          TEXT,           -- pending/processing/completed/failed
  video_source    TEXT,           -- file path or URL
  interval        REAL,           -- seconds between frames
  total_frames    INTEGER,        -- total frames extracted
  processed_frames INTEGER,       -- current progress
  created_at      TEXT,
  updated_at      TEXT,
  error_message   TEXT
)
```

### Frame Metadata Table
```sql
frame_metadata (
  id            INTEGER PRIMARY KEY,
  job_id        TEXT,              -- foreign key to jobs
  timestamp     REAL,              -- time in video (seconds)
  frame_path    TEXT,              -- path to saved frame file
  file_size     INTEGER,           -- frame file size in bytes
  checksum      TEXT,              -- MD5 hash for integrity
  created_at    TEXT,
  FOREIGN KEY (job_id) REFERENCES jobs(job_id)
)
```

## File Organization

### Directory Structure
```
project/
├── app/                    # Application code
│   ├── main.py            # FastAPI app + routes
│   ├── models.py          # Data structures
│   ├── job_manager.py     # Job orchestration
│   ├── frame_extractor.py # Video processing
│   ├── database.py        # Data persistence
│   ├── cache.py           # Performance optimization
│   └── templates/         # Web interface
├── uploads/               # User uploaded videos
├── runtime/
│   ├── frames/           # Extracted frame images
│   │   └── {job_id}/     # Per-job directories
│   ├── db/               # SQLite database
│   └── logs/             # Application logs
└── k8s/                  # Kubernetes deployment
```

## Configuration Management

### Environment-Based Config
```python
REDIS_HOST = "localhost"           # Cache server
DATABASE_PATH = "runtime/db/app.db" # SQLite location
FRAMES_BASE_PATH = "runtime/frames" # Frame storage
MAX_CONCURRENT_JOBS = 5            # Processing limit
```

### Different Environments
- **Development**: Direct file paths, local Redis
- **Docker**: Container paths, linked Redis container
- **Kubernetes**: Mounted volumes, Redis service

## Error Handling Strategy

### Graceful Degradation
```
Redis unavailable → Fall back to in-memory cache
Video unreadable → Mark job as failed with clear message
Disk full → Pause processing, return error
Network issues → Retry with backoff
```

### Error Categories
1. **User Errors**: Invalid file format, missing parameters
2. **System Errors**: Database connection, disk space
3. **Processing Errors**: Corrupted video, codec issues

## Performance Characteristics

### Scalability Factors
- **Concurrent Jobs**: Limited by `MAX_CONCURRENT_JOBS`
- **Memory Usage**: ~50MB per active video processing job
- **Disk Usage**: Depends on video length and frame interval
- **Processing Speed**: ~30 FPS extraction rate

### Bottlenecks
1. **I/O Bound**: Disk writes for frame images
2. **CPU Bound**: Video decoding and image processing
3. **Memory Bound**: Large videos require more RAM

## Security Model

### Input Validation
- File type restrictions (video formats only)
- File size limits
- Path traversal prevention
- Parameter validation

### Data Protection
- Uploaded files isolated in secure directory
- Database uses parameterized queries
- No sensitive data logged
- File permissions properly set

## Deployment Patterns

### Local Development
```
python app/main.py → Direct execution → Local file system
```

### Docker Container
```
Dockerfile → Build image → Mount volumes → Run container
```

### Kubernetes Cluster
```
Docker image → K8s manifests → Auto-scaling → Load balancing
```

## Integration Points

### External Dependencies
- **OpenCV**: Video processing library
- **Redis**: Caching layer (optional)
- **SQLite**: Embedded database
- **FastAPI**: Web framework

### API Integration
- **REST endpoints** for programmatic access
- **File upload** via multipart form data
- **JSON responses** for easy parsing
- **Status polling** for progress tracking

## Monitoring and Observability

### Health Indicators
- Active job count
- Database connectivity
- Cache availability
- Disk space usage

### Logging Strategy
- Structured JSON logs
- Per-request correlation IDs
- Error stack traces
- Performance metrics

---

*This design document captures the current system architecture as of the modular refactoring (August 2025)*
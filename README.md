# 🎬 Video Frame Extraction System

Ever needed to extract frames from videos at scale? This is a FastAPI-based system I built that handles video frame extraction with proper job queuing, Redis caching, and all the production bells and whistles you'd expect.

## What's Inside

- **Fast Processing** - Handles multiple videos simultaneously with configurable worker pools
- **Real-time Updates** - Track job progress and get live status updates 
- **Smart Caching** - Redis integration with graceful fallback to in-memory when Redis isn't available
- **Solid Storage** - SQLite for metadata with proper indexing (because nobody likes slow queries)
- **REST API** - Full FastAPI setup with auto-generated docs
- **Production Ready** - Kubernetes manifests included for real deployments
- **Docker Support** - Docker Compose setup for local development
- **Well Tested** - 85%+ test coverage because bugs in production aren't fun
- **Scales Horizontally** - Auto-scaling support when things get busy

## How It Works

The architecture is pretty straightforward:

```
   FastAPI App    →  Job Manager    →  Frame Extractor 
                                                           
  REST Endpoints      Thread Pool           OpenCV + FFmpeg
  Web Interface       Job Tracking          Frame Processing
        ↓                       ↓                       ↓
        
 Cache Manager       Database Manager       File System    
                                                           
 Redis / Memory       SQLite Database      Frame Storage   
 TTL Management       Metadata Store       Job Directories 
```

## Getting Started

### For Production (Kubernetes)

If you're deploying this for real, here's the fastest way:

```bash
git clone https://github.com/dineshmadhavan148-oss/VideoFrameExtractor.git
cd video-frame-extractor

# Deploy to your cluster
cd k8s && chmod +x deploy.sh && ./deploy.sh

# Access it (adjust the namespace if you changed it)
kubectl port-forward -n video-extractor service/video-extractor-service 8000:80
open http://localhost:8000
```

### For Development (Docker Compose)

Want to hack on this locally? Docker Compose is your friend:

```bash
# Just run this and you're good to go
docker-compose up -d
open http://localhost:8000
```

### Local Development (No Containers)

If you prefer running things directly:

```bash
pip install -r requirements.txt
python app/main.py
open http://localhost:8000
```

## API Reference

Here are the endpoints you'll actually use:

| Method | Endpoint | What it does |
|--------|----------|-------------|
| `GET` | `/` | Web interface (pretty useful for testing) |
| `POST` | `/video-job` | Submit a new video for processing |
| `GET` | `/job-status/{job_id}` | Check how your job is doing |
| `GET` | `/frames/{job_id}` | Get all the extracted frames |
| `GET` | `/dashboard/recent-frames` | Recent frames (cached for speed) |
| `DELETE` | `/job/{job_id}` | Cancel a job and clean up |
| `GET` | `/health` | Is everything working? |


### Starting a Job

```bash
curl -X POST "http://localhost:8000/video-job" \
     -H "Content-Type: application/json" \
     -d '{
       "video_source": "my-awesome-video.mp4",
       "interval": 5.0
     }'
```

You'll get back something like:
```json
{
  "job_id": "some-uuid-here",
  "status": "pending",
  "message": "Job submitted successfully"
}
```

### Checking Progress

```bash
curl "http://localhost:8000/job-status/some-uuid-here"
```

Response:
```json
{
  "job_id": "some-uuid-here",
  "status": "completed",
  "video_source": "my-awesome-video.mp4",
  "interval": 5.0,
  "total_frames": 25,
  "processed_frames": 25,
  "created_at": "2025-08-30T10:30:00.123456",
  "updated_at": "2025-08-30T10:32:15.789012"
}
```

## Configuration

You can tweak these via environment variables:

| Variable | Default | What it controls |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Where Redis lives |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `DATABASE_PATH` | `runtime/db/metadata.db` | SQLite file location |
| `FRAMES_BASE_PATH` | `runtime/frames` | Where to store extracted frames |
| `MAX_CONCURRENT_JOBS` | `5` | How many videos to process at once |
| `CACHE_TTL` | `3600` | Cache expiration (seconds) |
| `MAX_CACHE_SIZE_MB` | `100` | Memory cache limit |

Set these in your `.env` file, Docker Compose, or Kubernetes ConfigMap.

## Testing

I've included a pretty comprehensive test suite:

```bash
# Run everything
cd tests && python run_tests.py

# Just specific tests
python -m unittest test_api.py

# With coverage report
python run_tests.py --coverage
```

The tests cover:
- All the API endpoints
- Database operations 
- Cache behavior
- Error handling
- Concurrent processing

## Docker Deployment

### Custom Build

```bash
docker build -t video-frame-extractor .

docker run -p 8000:8000 \
  -e REDIS_HOST=my-redis \
  -e MAX_CONCURRENT_JOBS=10 \
  -v ./runtime:/app/runtime \
  video-frame-extractor
```

### Production Docker Compose

For a more realistic setup:

```yaml
version: '3.8'
services:
  video-extractor:
    image: video-frame-extractor:latest
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - MAX_CONCURRENT_JOBS=10
    volumes:
      - ./videos:/app/videos:ro
      - ./runtime:/app/runtime
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

## Kubernetes Deployment

### Quick Deploy

The `deploy.sh` script handles everything:

```bash
cd k8s
./deploy.sh
```

### Manual Steps

If you want to do it step by step:

```bash
kubectl apply -f k8s/
kubectl port-forward -n video-extractor service/video-extractor-service 8000:80
```

### Production Notes

For real production use, you'll want to:
- Set up proper persistent volumes
- Configure ingress with your domain
- Add monitoring and alerting
- Review the resource limits
- Set up backup for the database

## Monitoring

### Health Checks

```bash
# Quick health check
curl http://localhost:8000/health

# See recent activity
curl http://localhost:8000/dashboard/recent-frames?since_minutes=60
```

### Logs

- App logs go to `runtime/logs/app.log`
- Access logs go to stdout (Docker captures these)
- Everything's in JSON format with request IDs for tracing

### What to Watch

- Job processing rates
- Cache hit ratios  
- Memory usage (especially with large videos)
- Disk space (frames can add up quickly)

## Project Layout

```
video-frame-extractor/
├── app/
│   └── main.py              # Main application
├── tests/                   # Test suite
│   ├── test_models.py      
│   ├── test_database.py    
│   ├── test_cache.py       
│   ├── test_api.py         
│   ├── test_integration.py 
│   └── run_tests.py        
├── k8s/                     # Kubernetes stuff
│   ├── namespace.yaml      
│   ├── configmap.yaml      
│   ├── redis.yaml          
│   ├── video-extractor.yaml
│   ├── ingress.yaml        
│   ├── hpa.yaml            
│   └── deploy.sh           
├── runtime/                 # Generated at runtime
│   ├── db/                 
│   ├── frames/             
│   └── logs/               
├── Dockerfile              
├── docker-compose.yml      
├── requirements.txt        
└── README.md               
```

## Development Setup

### Prerequisites

You'll need:
- Python 3.10+ 
- Redis (optional - falls back to memory)
- FFmpeg (for video processing)
- Docker (if you want containers)

### Local Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app/main.py
```

## Performance Notes

From my testing:
- **Processing Speed**: Around 30 FPS on decent hardware
- **Concurrent Jobs**: Default is 5, but you can bump it up
- **Cache Hit Rate**: Usually 95%+ for recent queries
- **Memory Usage**: 100-500MB depending on video size and concurrent jobs
- **Storage**: Frames are deduplicated by checksum to save space

## Troubleshooting

Common issues I've run into:

- **Redis connection fails**: It'll fall back to in-memory cache automatically
- **FFmpeg not found**: Make sure it's installed and in your PATH
- **Out of disk space**: Check the `runtime/frames` directory
- **Jobs stuck**: Check the `/health` endpoint and logs

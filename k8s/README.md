# Kubernetes Deployment for Video Frame Extractor

This directory contains Kubernetes manifests for deploying the Video Frame Extraction System.

## 📁 Files Overview

- **`namespace.yaml`** - Creates dedicated namespace
- **`configmap.yaml`** - Environment configuration
- **`redis.yaml`** - Redis cache deployment & service
- **`video-extractor.yaml`** - Main application deployment & service
- **`ingress.yaml`** - Ingress configuration for external access
- **`hpa.yaml`** - Horizontal Pod Autoscaler for scaling
- **`deploy.sh`** - Automated deployment script

## 🚀 Quick Deployment

### Prerequisites
- Kubernetes cluster (minikube, Docker Desktop, or cloud provider)
- kubectl configured
- Docker installed

### Option 1: Automated Script
```bash
cd k8s
chmod +x deploy.sh
./deploy.sh
```

### Option 2: Manual Deployment
```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f video-extractor.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml
```

## 🔧 Configuration

### Environment Variables (ConfigMap)
- `REDIS_HOST`: Redis service hostname
- `REDIS_PORT`: Redis port (6379)
- `DATABASE_PATH`: SQLite database path
- `FRAMES_BASE_PATH`: Frame storage directory
- `MAX_CONCURRENT_JOBS`: Maximum concurrent video processing jobs

### Resource Limits
- **Application**: 512Mi-1Gi RAM, 200m-500m CPU
- **Redis**: 64Mi-128Mi RAM, 50m-100m CPU

### Storage
- **Application Data**: 10Gi PVC for database and frames
- **Video Storage**: 50Gi PVC for input videos
- **Redis Data**: 1Gi PVC for cache persistence

## 📊 Monitoring & Management

### View Deployment Status
```bash
kubectl get pods -n video-extractor
kubectl get services -n video-extractor
kubectl get ingress -n video-extractor
```

### View Logs
```bash
# All application logs
kubectl logs -n video-extractor -l app=video-extractor

# Specific pod logs
kubectl logs -n video-extractor <pod-name>

# Follow logs
kubectl logs -n video-extractor -l app=video-extractor -f
```

### Access Application
```bash
# Port forward to local machine
kubectl port-forward -n video-extractor service/video-extractor-service 8000:80

# Then access: http://localhost:8000
```

### Scaling
```bash
# Manual scaling
kubectl scale -n video-extractor deployment/video-extractor --replicas=5

# View HPA status
kubectl get hpa -n video-extractor
```

## 🌐 Ingress Access

If using ingress controller (like nginx-ingress):

1. Add to `/etc/hosts`:
   ```
   <ingress-ip> video-extractor.local
   ```

2. Access: `http://video-extractor.local`

## 🗑️ Cleanup

```bash
# Delete entire deployment
kubectl delete namespace video-extractor

# Or delete individual components
kubectl delete -f .
```

## 📈 Production Considerations

### Security
- Add network policies
- Configure RBAC
- Use secrets for sensitive data
- Enable TLS/SSL

### Monitoring
- Add Prometheus metrics
- Configure alerting
- Set up health checks
- Monitor resource usage

### Storage
- Use appropriate storage classes
- Configure backup strategies
- Consider distributed storage

### Networking
- Configure proper ingress
- Set up load balancing
- Consider service mesh

## 🔧 Troubleshooting

### Common Issues

**Pods not starting:**
```bash
kubectl describe pod -n video-extractor <pod-name>
kubectl logs -n video-extractor <pod-name>
```

**Storage issues:**
```bash
kubectl get pvc -n video-extractor
kubectl describe pvc -n video-extractor <pvc-name>
```

**Service not accessible:**
```bash
kubectl get endpoints -n video-extractor
kubectl describe service -n video-extractor video-extractor-service
```

**Image pull issues:**
- Ensure Docker image is built: `docker images | grep video-extractor`
- For remote registry, ensure image is pushed and accessible
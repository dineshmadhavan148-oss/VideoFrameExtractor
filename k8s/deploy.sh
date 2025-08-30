#!/bin/bash

# Video Frame Extractor - Kubernetes Deployment Script

set -e

echo "🚀 Deploying Video Frame Extractor to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed or not in PATH"
    exit 1
fi

# Build Docker image (adjust registry as needed)
echo "📦 Building Docker image..."
docker build -t video-extractor:latest ..

# Tag for registry (uncomment and modify for remote registry)
# docker tag video-extractor:latest your-registry/video-extractor:latest
# docker push your-registry/video-extractor:latest

# Apply Kubernetes manifests in order
echo "🎯 Creating namespace..."
kubectl apply -f namespace.yaml

echo "📋 Applying ConfigMap..."
kubectl apply -f configmap.yaml

echo "🔴 Deploying Redis..."
kubectl apply -f redis.yaml

echo "⏳ Waiting for Redis to be ready..."
kubectl wait --namespace=video-extractor --for=condition=available --timeout=300s deployment/redis

echo "🎬 Deploying Video Extractor application..."
kubectl apply -f video-extractor.yaml

echo "⏳ Waiting for Video Extractor to be ready..."
kubectl wait --namespace=video-extractor --for=condition=available --timeout=300s deployment/video-extractor

echo "🌐 Setting up Ingress..."
kubectl apply -f ingress.yaml

echo "📈 Setting up Horizontal Pod Autoscaler..."
kubectl apply -f hpa.yaml

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📊 Checking deployment status..."
kubectl get pods -n video-extractor
echo ""
kubectl get services -n video-extractor
echo ""

# Get service URL
SERVICE_URL=$(kubectl get service video-extractor-service -n video-extractor -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
if [ "$SERVICE_URL" = "pending" ] || [ -z "$SERVICE_URL" ]; then
    echo "🔗 Service URL: http://localhost (port-forward required)"
    echo "   Run: kubectl port-forward -n video-extractor service/video-extractor-service 8000:80"
else
    echo "🔗 Service URL: http://$SERVICE_URL"
fi

echo ""
echo "📖 Useful commands:"
echo "   View logs: kubectl logs -n video-extractor -l app=video-extractor"
echo "   Port forward: kubectl port-forward -n video-extractor service/video-extractor-service 8000:80"
echo "   Scale deployment: kubectl scale -n video-extractor deployment/video-extractor --replicas=5"
echo "   Delete deployment: kubectl delete namespace video-extractor"
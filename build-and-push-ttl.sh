#!/bin/bash

# Build and push LiteLL IRSA test container to ttl.sh
# ttl.sh provides temporary container registry for testing

set -e

# Configuration
IMAGE_NAME="litellm-irsa-test"
TTL_DURATION="1h"  # Container will be available for 1 hour
TTL_IMAGE="ttl.sh/${IMAGE_NAME}:${TTL_DURATION}"

echo "Building LiteLLM IRSA test container..."

# Build the Docker image
docker build -f Dockerfile.irsa-test -t "${TTL_IMAGE}" .

echo "Pushing to ttl.sh registry..."

# Push to ttl.sh (no authentication required)
docker push "${TTL_IMAGE}"

echo "Container pushed successfully!"
echo "Image: ${TTL_IMAGE}"
echo ""
echo "To test in Kubernetes:"
echo "1. Update k8s-irsa-test.yaml with your IAM role ARN"
echo "2. Apply the manifest: kubectl apply -f k8s-irsa-test.yaml"
echo "3. Check the job logs: kubectl logs job/litellm-irsa-test-job"
echo "4. Check the deployment health: kubectl get pods -l app=litellm-irsa-test"
echo ""
echo "To test the health endpoint:"
echo "kubectl port-forward service/litellm-irsa-test-service 8080:80"
echo "curl http://localhost:8080/health"
echo ""
echo "Container will expire in ${TTL_DURATION} from now."
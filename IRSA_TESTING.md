# Testing IRSA (IAM Roles for Service Accounts) Fix

This directory contains files for testing the IRSA role assumption fix in a real Kubernetes cluster.

## Problem Being Fixed

The original IRSA fix was reverted due to a failing test that made real AWS API calls. The issue was that the IRSA detection condition was checking for the absence of explicit credentials, but these were being populated from environment variables even when passed as `None`.

## Solution

The fix changes the IRSA detection logic to check for IRSA-specific environment variables:
- `AWS_ROLE_ARN` (current role)
- `AWS_WEB_IDENTITY_TOKEN_FILE` (IRSA environment indicator)

When these are present and the requested role matches the current role, we skip role assumption and use the existing IRSA credentials.

## Files

- `Dockerfile.irsa-test` - Container for testing IRSA functionality
- `k8s-irsa-test.yaml` - Kubernetes manifests for EKS testing
- `build-and-push-ttl.sh` - Script to build and push to ttl.sh registry
- `IRSA_TESTING.md` - This documentation

## Testing Steps

### 1. Build and Push Container

```bash
# Build and push to ttl.sh (temporary registry)
./build-and-push-ttl.sh
```

### 2. Set Up EKS Cluster with IRSA

You'll need an EKS cluster with IRSA configured. Here's a quick setup:

```bash
# Create IAM role for IRSA (replace ACCOUNT_ID and CLUSTER_NAME)
aws iam create-role \
  --role-name LitellmRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/oidc.eks.REGION.amazonaws.com/id/CLUSTER_OIDC_ID"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
          "StringEquals": {
            "oidc.eks.REGION.amazonaws.com/id/CLUSTER_OIDC_ID:sub": "system:serviceaccount:default:litellm-irsa-test",
            "oidc.eks.REGION.amazonaws.com/id/CLUSTER_OIDC_ID:aud": "sts.amazonaws.com"
          }
        }
      }
    ]
  }'

# Attach a policy (e.g., for Bedrock access)
aws iam attach-role-policy \
  --role-name LitellmRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
```

### 3. Update Kubernetes Manifest

Edit `k8s-irsa-test.yaml` and replace `ACCOUNT_ID` with your AWS account ID:

```yaml
annotations:
  eks.amazonaws.com/role-arn: arn:aws:iam::YOUR_ACCOUNT_ID:role/LitellmRole
```

### 4. Deploy to Kubernetes

```bash
# Apply the manifests
kubectl apply -f k8s-irsa-test.yaml

# Check the job logs (this runs the IRSA test)
kubectl logs job/litellm-irsa-test-job

# Check the deployment status
kubectl get pods -l app=litellm-irsa-test

# Test the health endpoint
kubectl port-forward service/litellm-irsa-test-service 8080:80 &
curl http://localhost:8080/health
```

### 5. Expected Results

**Success Case (IRSA working):**
```
Testing IRSA credentials...
AWS_ROLE_ARN: arn:aws:iam::123456789012:role/LitellmRole
AWS_WEB_IDENTITY_TOKEN_FILE: /var/run/secrets/eks.amazonaws.com/serviceaccount/token
AWS_REGION: us-east-1
Testing with current role: arn:aws:iam::123456789012:role/LitellmRole
Successfully got credentials: ASIAXAMPLE...
IRSA same-role optimization working correctly!
```

**Health Endpoint Response:**
```json
{
  "status": "healthy",
  "aws_role_arn": "arn:aws:iam::123456789012:role/LitellmRole",
  "aws_web_identity_token_file": "/var/run/secrets/eks.amazonaws.com/serviceaccount/token",
  "aws_region": "us-east-1"
}
```

## Troubleshooting

### Container Not Found
The ttl.sh registry is temporary. If the container expires, rebuild and push:
```bash
./build-and-push-ttl.sh
```

### IRSA Not Working
1. Verify OIDC provider is configured for your EKS cluster
2. Check IAM role trust policy includes correct OIDC conditions
3. Ensure service account annotation matches IAM role ARN
4. Check pod has the correct service account: `kubectl describe pod <pod-name>`

### Permission Errors
1. Verify IAM role has necessary permissions for your use case
2. Check CloudTrail logs for AssumeRoleWithWebIdentity calls
3. Ensure role trust policy allows the specific service account

## Manual Testing

You can also test manually by exec'ing into the container:

```bash
# Get pod name
POD_NAME=$(kubectl get pods -l app=litellm-irsa-test -o jsonpath='{.items[0].metadata.name}')

# Exec into the pod
kubectl exec -it $POD_NAME -- /bin/bash

# Run the test script
python3 /app/test_irsa.py

# Check environment variables
env | grep AWS

# Test boto3 directly
python3 -c "import boto3; print(boto3.Session().get_credentials())"
```

## Cleanup

```bash
# Remove Kubernetes resources
kubectl delete -f k8s-irsa-test.yaml

# The ttl.sh container will automatically expire after 1 hour
```
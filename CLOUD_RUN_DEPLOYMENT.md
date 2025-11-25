# Google Cloud Run Deployment Guide

This guide will help you deploy the Data Adaptor API to Google Cloud Run with automatic deployment from GitHub.

## Prerequisites

1. Google Cloud Platform account
2. GitHub account
3. `gcloud` CLI installed (optional, for local testing)
4. Git installed

## Overview

The deployment process:
1. Push code to GitHub repository
2. Google Cloud Build automatically builds Docker image
3. Image is deployed to Cloud Run
4. Service is available at a public URL

## Step-by-Step Deployment

### 1. Prepare Your GitHub Repository

#### Create a new repository on GitHub

1. Go to https://github.com/new
2. Create a new repository (e.g., `dataadaptor`)
3. Don't initialize with README (we already have one)

#### Push your code to GitHub

```bash
cd C:\Users\intit\Desktop\dataadaptor

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: FastAPI data adaptor for Cloud Run"

# Add remote (replace with your GitHub username/repo)
git remote add origin https://github.com/YOUR_USERNAME/dataadaptor.git

# Push to GitHub
git push -u origin main
```

### 2. Set Up Google Cloud Project

#### Create a new project (or use existing)

1. Go to https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Note your PROJECT_ID

#### Enable required APIs

Go to https://console.cloud.google.com/apis/library and enable:
- Cloud Run API
- Cloud Build API
- Container Registry API
- Secret Manager API (optional, for better credential management)

Or use `gcloud` CLI:

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 3. Connect GitHub to Cloud Build

#### Option A: Using Cloud Console (Recommended)

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click **"Connect Repository"**
3. Select **GitHub** as source
4. Authenticate with GitHub
5. Select your repository (`dataadaptor`)
6. Click **"Connect"**

#### Option B: Using gcloud CLI

```bash
# Connect repository
gcloud builds triggers create github \
  --repo-name=dataadaptor \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

### 4. Create Cloud Build Trigger

1. In [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click **"Create Trigger"**
3. Configure:
   - **Name**: `deploy-dataadaptor`
   - **Event**: Push to a branch
   - **Source**: Select your connected repository
   - **Branch**: `^main$` (triggers on push to main branch)
   - **Configuration**: Cloud Build configuration file
   - **Location**: `/cloudbuild.yaml`

4. Click **"Create"**

### 5. Configure Environment Variables (Credentials)

You have two options for managing credentials:

#### Option A: Using Substitution Variables (Simple)

Edit your Cloud Build trigger:
1. Go to the trigger you just created
2. Click **"Edit"**
3. Scroll to **"Substitution variables"**
4. Add your credentials:
   - `_DSM_URL`: `https://drive.int.in.th`
   - `_DSM_USER`: `korkarn`
   - `_DSM_PASS`: `INTit2025!`
   - `_MIKROTIK_2011_URL`: `https://rb2011.int.in.th`
   - `_MIKROTIK_4011_URL`: `https://rb4011.int.in.th`
   - `_MIKROTIK_USER`: `grafana`
   - `_MIKROTIK_PASS`: `INTit2025!`
   - `_NVR_URL`: `http://int.in.th:37080`
   - `_NVR_USER`: `grafana`
   - `_NVR_PASS`: `INTit2025!`

5. Click **"Save"**

#### Option B: Using Secret Manager (More Secure)

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
2. Create secrets for each credential
3. Grant Cloud Run access to secrets
4. Update `cloudbuild.yaml` to use secrets instead of substitution variables

See: https://cloud.google.com/run/docs/configuring/secrets

### 6. Deploy!

Now, every time you push to the `main` branch, Cloud Build will automatically:
1. Build the Docker image
2. Push to Container Registry
3. Deploy to Cloud Run

**Trigger first deployment:**

```bash
# Make a small change
echo "# Cloud Run" >> README.md

# Commit and push
git add .
git commit -m "Trigger Cloud Run deployment"
git push
```

### 7. Monitor Deployment

1. Go to [Cloud Build History](https://console.cloud.google.com/cloud-build/builds)
2. Watch the build progress
3. Once complete, go to [Cloud Run](https://console.cloud.google.com/run)
4. Click on your service `dataadaptor`
5. You'll see the service URL (e.g., `https://dataadaptor-xxxxx-xx.a.run.app`)

### 8. Test Your Deployment

```bash
# Replace with your actual Cloud Run URL
CLOUD_RUN_URL="https://dataadaptor-xxxxx-xx.a.run.app"

# Test endpoints
curl $CLOUD_RUN_URL/
curl $CLOUD_RUN_URL/dsmwatchdog
curl $CLOUD_RUN_URL/2011watchdog
curl $CLOUD_RUN_URL/nvrsummary
```

## Configure Custom Domain (Optional)

1. Go to your Cloud Run service
2. Click **"Manage Custom Domains"**
3. Follow the wizard to add your domain
4. Update DNS records as instructed

## Update Grafana Configuration

Update your Grafana data source to point to the Cloud Run URL:

```
https://dataadaptor-xxxxx-xx.a.run.app/dsmwatchdog
```

## Cost Optimization

Cloud Run pricing is based on:
- Number of requests
- Compute time (CPU/memory)
- Networking

**Optimize costs:**

1. **Set minimum instances to 0** (default) - scale to zero when not in use
2. **Set maximum instances** - prevent runaway costs:
   ```bash
   gcloud run services update dataadaptor --max-instances=10 --region=asia-southeast1
   ```

3. **Adjust CPU/Memory** (default is usually fine):
   ```bash
   gcloud run services update dataadaptor --memory=256Mi --cpu=1 --region=asia-southeast1
   ```

4. **Set request timeout**:
   ```bash
   gcloud run services update dataadaptor --timeout=60s --region=asia-southeast1
   ```

## Troubleshooting

### Build Fails

Check build logs:
```bash
gcloud builds list
gcloud builds log BUILD_ID
```

Common issues:
- Missing API enablement
- Incorrect cloudbuild.yaml syntax
- Dockerfile errors

### Service Fails to Start

Check Cloud Run logs:
```bash
gcloud run services logs read dataadaptor --region=asia-southeast1
```

Common issues:
- Missing environment variables
- Port binding (must listen on PORT env var)
- Incorrect dependencies in requirements.txt

### Connection Errors from Cloud Run

Cloud Run has restrictions:
- Cannot connect to `localhost` (use actual hostnames)
- Egress charges apply for external connections
- VPC connector needed for private network access

If your DSM/Mikrotik/NVR are on a private network, you'll need:
1. Set up [Serverless VPC Access](https://cloud.google.com/vpc/docs/configure-serverless-vpc-access)
2. Configure your VPN or Cloud VPN
3. Attach VPC connector to Cloud Run service

### Update Environment Variables

```bash
gcloud run services update dataadaptor \
  --update-env-vars DSM_PASS=NewPassword123 \
  --region=asia-southeast1
```

## Manual Deployment (Alternative)

If you don't want automatic deployment:

```bash
# Build locally
docker build -t gcr.io/YOUR_PROJECT_ID/dataadaptor .

# Push to Container Registry
docker push gcr.io/YOUR_PROJECT_ID/dataadaptor

# Deploy to Cloud Run
gcloud run deploy dataadaptor \
  --image gcr.io/YOUR_PROJECT_ID/dataadaptor \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars DSM_URL=https://drive.int.in.th,DSM_USER=korkarn,DSM_PASS=INTit2025!
```

## Security Best Practices

1. **Use Secret Manager** instead of plain text environment variables
2. **Enable authentication** on Cloud Run (remove `--allow-unauthenticated`)
3. **Use IAM** to control access
4. **Set up VPC** for private network access
5. **Rotate credentials** regularly
6. **Enable Cloud Armor** for DDoS protection
7. **Use HTTPS only** (enabled by default)

## Monitoring & Logging

- **Logs**: https://console.cloud.google.com/run/detail/[REGION]/dataadaptor/logs
- **Metrics**: https://console.cloud.google.com/run/detail/[REGION]/dataadaptor/metrics
- **Set up alerts** in Cloud Monitoring for errors/latency

## CI/CD Workflow

Your workflow will be:
1. Make code changes locally
2. Test locally: `python main.py`
3. Commit: `git commit -m "Fix: ..."`
4. Push: `git push`
5. Cloud Build automatically deploys
6. Verify: `curl https://your-service.run.app/`

## Useful Commands

```bash
# View service details
gcloud run services describe dataadaptor --region=asia-southeast1

# View service URL
gcloud run services describe dataadaptor --region=asia-southeast1 --format='value(status.url)'

# Update service
gcloud run services update dataadaptor --region=asia-southeast1 [OPTIONS]

# Delete service
gcloud run services delete dataadaptor --region=asia-southeast1

# View logs in real-time
gcloud run services logs tail dataadaptor --region=asia-southeast1
```

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Pricing Calculator](https://cloud.google.com/products/calculator)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/best-practices)

## Support

For issues:
1. Check Cloud Build logs
2. Check Cloud Run logs
3. Review this guide
4. Check Google Cloud Status: https://status.cloud.google.com/

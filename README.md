# ERP Webhook Gateway

FastAPI gateway for Shopify and Parcel Panel webhooks, running on Google Cloud Run.

## Architecture

```
Shopify/Parcel Panel Webhook
    ↓
Cloud Run Gateway (FastAPI)
    ↓
Firestore Lookup: webhook_routing/{shop_domain} → site_name
    ↓
Pub/Sub Publish (attributes: site_name, event_id, source, topic, shop_domain)
    ↓
Per-site Subscription (filter: attributes.site_name = 'site_name')
    ↓
Buffer Consumer (on Frappe VM)
    ↓
Frappe Worker
```

## Endpoints

- `POST /webhooks/shopify` - Shopify webhooks
- `POST /webhooks/parcel-panel` - Parcel Panel webhooks
- `GET /health` - Health check (for Cloud Run)
- `GET /ready` - Readiness check

## Configuration

Environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `PUBSUB_TOPIC_SHOPIFY` | Shopify webhook topic | Yes |
| `PUBSUB_TOPIC_PARCEL_PANEL` | Parcel Panel webhook topic | Yes |
| `PORT` | Server port (default: 8080) | No |

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_CLOUD_PROJECT=apt-phenomenon-458508-m3
export PUBSUB_TOPIC_SHOPIFY=shopify-webhooks
export PUBSUB_TOPIC_PARCEL_PANEL=parcel-panel-webhooks

# Run locally
uvicorn app.main:app --reload --port 8080
```

## Deployment

### 1. Build and push to Artifact Registry

```bash
# Set variables
PROJECT_ID=apt-phenomenon-458508-m3
REGION=europe-west4
REPO=erp-webhook-gateway
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/gateway

# Create repository (one-time)
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION

# Build and push
gcloud builds submit --tag $IMAGE
```

### 2. Deploy to Cloud Run

```bash
# Staging
gcloud run deploy erp-webhook-gateway-staging \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --env-vars-file=env-staging.yaml \
  --service-account=erpnext-staging-sa@$PROJECT_ID.iam.gserviceaccount.com

# Production
gcloud run deploy erp-webhook-gateway \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --env-vars-file=env-production.yaml \
  --service-account=erpnext-prod-sa@$PROJECT_ID.iam.gserviceaccount.com
```

### 3. Update Webhook URLs

Update Shopify/Parcel Panel webhook URLs to point to Cloud Run:

**Staging:**
- `https://erp-webhook-gateway-staging-XXXXX.run.app/webhooks/shopify`
- `https://erp-webhook-gateway-staging-XXXXX.run.app/webhooks/parcel-panel`

**Production:**
- `https://erp-webhook-gateway-XXXXX.run.app/webhooks/shopify`
- `https://erp-webhook-gateway-XXXXX.run.app/webhooks/parcel-panel`

## IAM Permissions

Service accounts need:
- `roles/datastore.user` - Firestore access
- `roles/pubsub.publisher` - Publish to topics

## Monitoring

- Cloud Run logs: `gcloud run logs read --service=erp-webhook-gateway --region=$REGION`
- Pub/Sub metrics: Message throughput, latency
- Cloud Monitoring: Request count, latency, errors

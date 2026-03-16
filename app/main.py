import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
import hmac
import hashlib

from .config import settings
from .firestore_client import get_site_name
from .pubsub_publisher import publish_shopify_webhook, publish_parcel_panel_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ERP Webhook Gateway")


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint"""
    return {"status": "ready"}


@app.post("/webhooks/shopify")
async def handle_shopify_webhook(request: Request):
    """Handle Shopify webhook
    
    Headers:
        X-Shopify-Shop-Domain: Shop domain (e.g., store.myshopify.com)
        X-Shopify-Topic: Webhook topic (e.g., orders/create)
        X-Shopify-Webhook-Id: Unique webhook ID (used as event_id)
        X-Shopify-Hmac-SHA256: HMAC signature for verification
    """
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        topic = request.headers.get("X-Shopify-Topic")
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")
        
        if not shop_domain:
            logger.error("Missing X-Shopify-Shop-Domain header")
            raise HTTPException(status_code=400, detail="Missing shop domain")
        
        if not topic:
            logger.error("Missing X-Shopify-Topic header")
            raise HTTPException(status_code=400, detail="Missing topic")
        
        payload = await request.json()
        
        site_name = get_site_name(shop_domain, settings.google_cloud_project)
        
        if not site_name:
            logger.error(f"No site found for shop_domain={shop_domain}")
            raise HTTPException(status_code=404, detail="Shop not configured")
        
        future = publish_shopify_webhook(
            payload=payload,
            site_name=site_name,
            topic=topic,
            shop_domain=shop_domain,
            event_id=webhook_id
        )
        
        future.result(timeout=10)
        
        logger.info(f"Shopify webhook published: shop={shop_domain}, topic={topic}")
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Shopify webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/webhooks/parcel-panel")
async def handle_parcel_panel_webhook(request: Request):
    """Handle Parcel Panel webhook
    
    Headers:
        X-Parcel-Panel-Shop-Domain: Shop domain
        X-Parcel-Panel-Event: Event type (e.g., tracking_updated)
    """
    try:
        shop_domain = request.headers.get("X-Parcel-Panel-Shop-Domain")
        event_type = request.headers.get("X-Parcel-Panel-Event", "tracking_updated")
        
        if not shop_domain:
            logger.error("Missing X-Parcel-Panel-Shop-Domain header")
            raise HTTPException(status_code=400, detail="Missing shop domain")
        
        payload = await request.json()
        
        site_name = get_site_name(shop_domain, settings.google_cloud_project)
        
        if not site_name:
            logger.error(f"No site found for shop_domain={shop_domain}")
            raise HTTPException(status_code=404, detail="Shop not configured")
        
        future = publish_parcel_panel_webhook(
            payload=payload,
            site_name=site_name,
            topic=event_type,
            shop_domain=shop_domain
        )
        
        future.result(timeout=10)
        
        logger.info(f"Parcel Panel webhook published: shop={shop_domain}, event={event_type}")
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Parcel Panel webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

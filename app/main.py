import time
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse

from .config import settings
from .firestore_client import get_site_name_async
from .pubsub_publisher import publish_shopify_webhook, publish_parcel_panel_webhook
from .rate_limiter import get_rate_limiter
from .structured_logging import setup_logging, set_correlation_id, LogContext, correlation_id

setup_logging()
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
    start_time = time.time()
    cid = set_correlation_id()
    
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        topic = request.headers.get("X-Shopify-Topic")
        webhook_id = request.headers.get("X-Shopify-Webhook-Id")
        signature = request.headers.get("X-Shopify-Hmac-SHA256")
        
        log_ctx = LogContext(logger, shop_domain=shop_domain, topic=topic, source='shopify')
        
        if not shop_domain:
            log_ctx.error("Missing X-Shopify-Shop-Domain header")
            raise HTTPException(status_code=400, detail="Missing shop domain")
        
        if not topic:
            log_ctx.error("Missing X-Shopify-Topic header")
            raise HTTPException(status_code=400, detail="Missing topic")
        
        if not signature:
            log_ctx.error("Missing X-Shopify-Hmac-SHA256 signature header")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        rate_limiter = get_rate_limiter()
        allowed, retry_after = await rate_limiter.is_allowed(shop_domain)
        if not allowed:
            log_ctx.warning(f"Rate limit exceeded, retry_after={retry_after}s")
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
                headers={"Retry-After": str(retry_after)}
            )
        
        payload_bytes = await request.body()
        
        if len(payload_bytes) > settings.max_payload_size_bytes:
            log_ctx.error(f"Payload too large: {len(payload_bytes)} bytes")
            raise HTTPException(status_code=413, detail="Payload too large")
        
        if not payload_bytes:
            log_ctx.error("Empty payload")
            raise HTTPException(status_code=400, detail="Empty payload")
        
        site_name = await get_site_name_async(shop_domain, settings.google_cloud_project)
        
        if not site_name:
            log_ctx.error(f"No site found for shop_domain={shop_domain}")
            raise HTTPException(status_code=404, detail="Shop not configured")
        
        log_ctx.extra['site_name'] = site_name
        log_ctx.extra['event_id'] = webhook_id
        
        event_id = webhook_id or str(uuid.uuid4())
        
        future = publish_shopify_webhook(
            payload_bytes=payload_bytes,
            site_name=site_name,
            topic=topic,
            shop_domain=shop_domain,
            event_id=event_id,
            signature=signature
        )
        
        future.result(timeout=10)
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_ctx.extra['duration_ms'] = duration_ms
        log_ctx.info(f"Shopify webhook published successfully")
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        LogContext(logger, shop_domain=locals().get('shop_domain'), 
                   duration_ms=duration_ms).error(f"Error processing Shopify webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/webhooks/parcel-panel")
async def handle_parcel_panel_webhook(request: Request):
    """Handle Parcel Panel webhook
    
    Headers:
        X-Parcel-Panel-Shop-Domain: Shop domain
        X-Parcel-Panel-Event: Event type (e.g., tracking_updated)
        X-Parcel-Panel-Signature: HMAC signature (if provided)
    """
    start_time = time.time()
    cid = set_correlation_id()
    
    try:
        shop_domain = request.headers.get("X-Parcel-Panel-Shop-Domain")
        event_type = request.headers.get("X-Parcel-Panel-Event", "tracking_updated")
        signature = request.headers.get("X-Parcel-Panel-Signature")
        
        log_ctx = LogContext(logger, shop_domain=shop_domain, topic=event_type, source='parcel_panel')
        
        if not shop_domain:
            log_ctx.error("Missing X-Parcel-Panel-Shop-Domain header")
            raise HTTPException(status_code=400, detail="Missing shop domain")
        
        rate_limiter = get_rate_limiter()
        allowed, retry_after = await rate_limiter.is_allowed(shop_domain)
        if not allowed:
            log_ctx.warning(f"Rate limit exceeded, retry_after={retry_after}s")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
                headers={"Retry-After": str(retry_after)}
            )
        
        payload_bytes = await request.body()
        
        if len(payload_bytes) > settings.max_payload_size_bytes:
            log_ctx.error(f"Payload too large: {len(payload_bytes)} bytes")
            raise HTTPException(status_code=413, detail="Payload too large")
        
        if not payload_bytes:
            log_ctx.error("Empty payload")
            raise HTTPException(status_code=400, detail="Empty payload")
        
        site_name = await get_site_name_async(shop_domain, settings.google_cloud_project)
        
        if not site_name:
            log_ctx.error(f"No site found for shop_domain={shop_domain}")
            raise HTTPException(status_code=404, detail="Shop not configured")
        
        event_id = str(uuid.uuid4())
        log_ctx.extra['site_name'] = site_name
        log_ctx.extra['event_id'] = event_id
        
        future = publish_parcel_panel_webhook(
            payload_bytes=payload_bytes,
            site_name=site_name,
            topic=event_type,
            shop_domain=shop_domain,
            event_id=event_id,
            signature=signature
        )
        
        future.result(timeout=10)
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_ctx.extra['duration_ms'] = duration_ms
        log_ctx.info(f"Parcel Panel webhook published successfully")
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        LogContext(logger, shop_domain=locals().get('shop_domain'),
                   duration_ms=duration_ms).error(f"Error processing Parcel Panel webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    LogContext(logger).error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

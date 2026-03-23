import json
import uuid
import logging
from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.publisher.futures import Future

from .config import settings

logger = logging.getLogger(__name__)

_publisher_client: Optional[pubsub_v1.PublisherClient] = None


def get_publisher_client() -> pubsub_v1.PublisherClient:
    """Get or create Pub/Sub publisher client (singleton)"""
    global _publisher_client
    
    if _publisher_client is None:
        _publisher_client = pubsub_v1.PublisherClient()
    
    return _publisher_client


def publish_webhook(
    topic_name: str,
    payload_bytes: bytes,
    site_name: str,
    source: str,
    topic: str,
    shop_domain: str,
    event_id: Optional[str] = None,
    signature: Optional[str] = None,
    signature_header: Optional[str] = None
) -> Future:
    """Publish webhook to Pub/Sub
    
    Args:
        topic_name: Pub/Sub topic name
        payload_bytes: Raw webhook payload bytes (preserved exactly for signature verification)
        site_name: Target site name
        source: Source identifier (shopify/parcel_panel)
        topic: Webhook topic (e.g., orders/create)
        shop_domain: Shop domain
        event_id: Optional event ID (generated if not provided)
        signature: HMAC signature for verification
        signature_header: Header name for signature (e.g., X-Shopify-Hmac-SHA256)
        
    Returns:
        Pub/Sub publish future
    """
    if event_id is None:
        event_id = str(uuid.uuid4())
    
    publisher = get_publisher_client()
    topic_path = publisher.topic_path(settings.google_cloud_project, topic_name)
    
    data = payload_bytes
    
    attributes = {
        'event_id': event_id,
        'source': source,
        'webhook_topic': topic,
        'shop_domain': shop_domain,
        'site_name': site_name,
    }
    
    if signature:
        attributes['signature'] = signature
    if signature_header:
        attributes['signature_header'] = signature_header
    
    logger.info(
        f"Publishing to {topic_name}: event_id={event_id}, site_name={site_name}, "
        f"source={source}, topic={topic}, has_signature={signature is not None}, "
        f"payload_size={len(payload_bytes)}"
    )
    
    future = publisher.publish(topic_path, data, **attributes)
    
    return future


def publish_shopify_webhook(
    payload_bytes: bytes,
    site_name: str,
    topic: str,
    shop_domain: str,
    event_id: Optional[str] = None,
    signature: Optional[str] = None
) -> Future:
    """Publish Shopify webhook to Pub/Sub"""
    return publish_webhook(
        topic_name=settings.pubsub_topic_shopify,
        payload_bytes=payload_bytes,
        site_name=site_name,
        source='Shopify',
        topic=topic,
        shop_domain=shop_domain,
        event_id=event_id,
        signature=signature,
        signature_header='X-Shopify-Hmac-SHA256'
    )


def publish_parcel_panel_webhook(
    payload_bytes: bytes,
    site_name: str,
    topic: str,
    shop_domain: str,
    event_id: Optional[str] = None,
    signature: Optional[str] = None
) -> Future:
    """Publish Parcel Panel webhook to Pub/Sub"""
    return publish_webhook(
        topic_name=settings.pubsub_topic_parcel_panel,
        payload_bytes=payload_bytes,
        site_name=site_name,
        source='Parcel Panel',
        topic=topic,
        shop_domain=shop_domain,
        event_id=event_id,
        signature=signature,
        signature_header='X-Parcel-Panel-Signature'
    )

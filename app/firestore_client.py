from google.cloud import firestore
from google.cloud.firestore_v1 import async_client
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

_firestore_client: Optional[firestore.Client] = None
_async_firestore_client: Optional[async_client.AsyncClient] = None


def get_firestore_client(project_id: str) -> firestore.Client:
    """Get or create Firestore client (singleton) - sync version"""
    global _firestore_client
    
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=project_id)
    
    return _firestore_client


def get_async_firestore_client(project_id: str) -> async_client.AsyncClient:
    """Get or create async Firestore client (singleton) - thread-safe for async"""
    global _async_firestore_client
    
    if _async_firestore_client is None:
        _async_firestore_client = async_client.AsyncClient(project=project_id)
    
    return _async_firestore_client


async def get_site_name_async(shop_domain: str, project_id: str) -> Optional[str]:
    """Look up site name for a shop domain from Firestore (async)
    
    Args:
        shop_domain: Shopify store domain (e.g., 'store.myshopify.com')
        project_id: GCP project ID
        
    Returns:
        Site name if found, None otherwise
    """
    db = get_async_firestore_client(project_id)
    
    doc_ref = db.collection('webhook_routing').document(shop_domain)
    doc = await doc_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        site_name = data.get('site_name') if data else None
        logger.info(f"Found site_name={site_name} for shop_domain={shop_domain}")
        return site_name
    
    logger.warning(f"No routing found for shop_domain={shop_domain}")
    return None


def get_site_name(shop_domain: str, project_id: str) -> Optional[str]:
    """Look up site name for a shop domain from Firestore (sync)
    
    Args:
        shop_domain: Shopify store domain (e.g., 'store.myshopify.com')
        project_id: GCP project ID
        
    Returns:
        Site name if found, None otherwise
    """
    db = get_firestore_client(project_id)
    
    doc = db.collection('webhook_routing').document(shop_domain).get()
    
    if doc.exists:
        data = doc.to_dict()
        site_name = data.get('site_name') if data else None
        logger.info(f"Found site_name={site_name} for shop_domain={shop_domain}")
        return site_name
    
    logger.warning(f"No routing found for shop_domain={shop_domain}")
    return None

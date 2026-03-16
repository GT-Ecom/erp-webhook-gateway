from google.cloud import firestore
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_firestore_client: Optional[firestore.Client] = None


def get_firestore_client(project_id: str) -> firestore.Client:
    """Get or create Firestore client (singleton)"""
    global _firestore_client
    
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=project_id)
    
    return _firestore_client


def get_site_name(shop_domain: str, project_id: str) -> Optional[str]:
    """Look up site name for a shop domain from Firestore
    
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

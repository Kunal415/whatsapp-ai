# security.py
import os
import hmac
import hashlib
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Security configurations
APP_SECRET = os.getenv("APP_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

def validate_whatsapp_signature(payload, signature):
    """Validates the signature to ensure the request is from Meta."""
    if not APP_SECRET:
        logger.warning("⚠️ APP_SECRET not set. Skipping validation.")
        return True

    expected_signature = hmac.new(
        bytes(APP_SECRET, "latin-1"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

def verify_webhook_token(token):
    """Verifies the webhook token during setup."""
    return token == VERIFY_TOKEN
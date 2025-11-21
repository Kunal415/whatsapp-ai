# whatsapp_service.py
import os
import json
import requests
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# WhatsApp configurations
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")

def send_whatsapp_message(recipient_wa_id, text_message):
    """Sends a WhatsApp message using the Meta Graph API."""
    logger.info(f"🔄 Attempting to send message to {recipient_wa_id}: {text_message[:50]}...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    data = json.dumps({
        "messaging_product": "whatsapp",
        "to": recipient_wa_id,
        "type": "text",
        "text": {"body": text_message},
    })
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        logger.info(f"📤 WhatsApp API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ Message sent successfully")
            return True
        else:
            logger.error(f"❌ WhatsApp API Error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send WhatsApp message: {e}")
        return False

def send_template_message(recipient_wa_id, template_name, parameters=None):
    """Sends a template message (for future use)"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    
    template_data = {
        "messaging_product": "whatsapp",
        "to": recipient_wa_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"}
        }
    }
    
    if parameters:
        template_data["template"]["components"] = parameters
        
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    
    try:
        response = requests.post(url, data=json.dumps(template_data), headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Template message sent to {recipient_wa_id}")
            return True
        else:
            logger.error(f"❌ Template message failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to send template message: {e}")
        return False
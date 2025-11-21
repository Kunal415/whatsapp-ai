# hyperstack_client.py
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Hyperstack configurations
HYPERSTACK_API_KEY = os.getenv("HYPERSTACK_API_KEY")
HYPERSTACK_MODEL_NAME = os.getenv("HYPERSTACK_MODEL_NAME")
HYPERSTACK_BASE_URL = os.getenv("HYPERSTACK_BASE_URL")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a friendly and helpful WhatsApp assistant.")

# Initialize Hyperstack client
try:
    client = OpenAI(
        base_url=HYPERSTACK_BASE_URL,
        api_key=HYPERSTACK_API_KEY
    )
    logger.info("✅ Hyperstack client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Hyperstack client: {e}")
    client = None

def generate_hyperstack_response(message_body):
    """Generates a response from the Hyperstack AI model."""
    if not client:
        logger.error("❌ Hyperstack client not available")
        return "AI service is currently unavailable."
    
    try:
        logger.info(f"🧠 Sending to Hyperstack: '{message_body}'")
        logger.info(f"🧠 Using model: {HYPERSTACK_MODEL_NAME}")
        
        response = client.chat.completions.create(
            model=HYPERSTACK_MODEL_NAME,
            messages=[
                {
                    "role": "system", 
                    "content": SYSTEM_PROMPT + " Keep responses under 200 characters for WhatsApp."
                },
                {
                    "role": "user", 
                    "content": message_body
                }
            ],
            max_tokens=100,
            temperature=0.7,
        )
        
        logger.info(f"🧠 Raw AI response object: {response}")
        
        ai_response = response.choices[0].message.content.strip()
        logger.info(f"🤖 AI Response: '{ai_response}'")
        return ai_response
        
    except Exception as e:
        logger.error(f"❌ AI Error: {e}", exc_info=True)
        
        # More specific error handling
        if "authentication" in str(e).lower():
            return "AI authentication failed. Please check API key."
        elif "rate limit" in str(e).lower():
            return "AI service is busy. Please try again in a moment."
        elif "not found" in str(e).lower():
            return "AI model not available. Please check model name."
        else:
            return f"Thanks for your message! I'm here to help with '{message_body}'"

def test_hyperstack_connection():
    """Test function to check if Hyperstack is working."""
    if not client:
        return "❌ Hyperstack client not initialized"
    
    try:
        response = client.chat.completions.create(
            model=HYPERSTACK_MODEL_NAME,
            messages=[
                {"role": "system", "content": "Respond with 'AI Connection Test Successful'"},
                {"role": "user", "content": "Test connection"}
            ],
            max_tokens=20,
        )
        return f"✅ {response.choices[0].message.content.strip()}"
    except Exception as e:
        return f"❌ Connection test failed: {e}"
# services.py

import os
import json
import logging
import hashlib
import hmac
import requests
from openai import OpenAI

logger = logging.getLogger(__name__)

ACCESS_TOKEN = None
WHATSAPP_API_VERSION = None
PHONE_NUMBER_ID = None
APP_SECRET = None
HYPERSTACK_MODEL_NAME = None
client = None

def initialize_services():
    """Initializes all service configurations and the OpenAI client."""
    global ACCESS_TOKEN, WHATSAPP_API_VERSION, PHONE_NUMBER_ID, APP_SECRET, HYPERSTACK_MODEL_NAME, client
    
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    HYPERSTACK_MODEL_NAME = os.getenv("HYPERSTACK_MODEL_NAME")
    
    client = OpenAI(
        base_url=os.getenv("HYPERSTACK_BASE_URL"),
        api_key=os.getenv("HYPERSTACK_API_KEY")
    )
    logger.info("Services and OpenAI client initialized successfully.")


# --- UPDATED: Accepts conversation history for context ---
def get_intent(user_query: str, history: list) -> dict:
    """
    Uses the LLM to classify intent and extract entities, now with conversation context.
    """
    # --- UPDATED: Added 'general_knowledge' intent ---
    system_prompt = """
    You are an intelligent routing agent for an e-commerce WhatsApp bot.
    Your task is to analyze the user's latest query, considering the conversation history, and classify it into ONE of the following intents:
    'product_search', 'order_status', 'cancel_order', 'customer_support', 'order_placing', 'general_knowledge', or 'unclassified'.

    - 'general_knowledge' is for chit-chat, greetings, or questions not related to our e-commerce store.
    
    You must also extract relevant entities:
    - 'product_search': 'keywords' (list of strings).
    - 'order_status': 'order_id' (string).
    - 'cancel_order': 'order_id' (string).
    - 'customer_support': 'topic' (brief summary string).
    - 'order_placing': 'product_name' or 'product_id' and 'quantity'.
    
    Respond ONLY with a valid JSON object in the format:
    {"intent": "...", "entities": {"key1": "value1"}}
    If no entities are found, return {"entities": {}}.
    If intent is unclear, use 'unclassified'.
    """
    
    # Prepend the system prompt to the conversation history
    messages = [{"role": "system", "content": system_prompt}] + history
    
    try:
        response = client.chat.completions.create(
            model=HYPERSTACK_MODEL_NAME,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        intent_json = json.loads(response.choices[0].message.content)
        logger.info(f"LLM classified intent: {intent_json} with history context.")
        return intent_json

    except Exception as e:
        logger.error(f"Error getting intent from LLM: {e}")
        return {"intent": "unclassified", "entities": {}}


def get_support_answer(user_query: str, context: str) -> str:
    """(No changes) Uses RAG for customer support questions."""
    system_prompt = f"""
    You are a helpful customer support agent. Using the provided knowledge base below, answer the user's question.
    If the answer is not in the knowledge base, say "I'm sorry, I don't have information on that topic. How else can I help?".

    --- KNOWLEDGE BASE ---
    {context}
    --------------------
    """
    
    try:
        response = client.chat.completions.create(
            model=HYPERSTACK_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting support answer from LLM: {e}")
        return "I'm having trouble accessing my knowledge base right now. Please try again later."


# --- NEW: Function for handling general knowledge/chit-chat ---
def get_general_answer(user_query: str, history: list) -> str:
    """
    Uses the LLM to generate a conversational response for non-e-commerce queries.
    """
    system_prompt = "You are a friendly and helpful conversational AI for an e-commerce store. Keep your answers brief and on-topic if possible, but you can answer general questions."
    
    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        response = client.chat.completions.create(
            model=HYPERSTACK_MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting general answer from LLM: {e}")
        return "I'm sorry, I can't answer that right now."


# --- WhatsApp Service Functions (No changes) ---
def send_whatsapp_message(recipient_wa_id: str, text_message: str):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
    data = json.dumps({
        "messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient_wa_id,
        "type": "text", "text": {"preview_url": False, "body": text_message},
    })
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"WhatsApp message sent to {recipient_wa_id}. Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False

def validate_whatsapp_signature(payload: bytes, signature: str):
    if not APP_SECRET:
        logger.warning("APP_SECRET is not set. Skipping signature validation.")
        return True
    expected_signature = hmac.new(bytes(APP_SECRET, "latin-1"), msg=payload, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, signature)
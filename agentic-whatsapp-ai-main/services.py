# services.py

import os
import json
import logging
import hashlib
import hmac
import requests
import re
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
    
    # Initialize Hyperstack client only if credentials are available
    hyperstack_api_key = os.getenv("HYPERSTACK_API_KEY")
    hyperstack_base_url = os.getenv("HYPERSTACK_BASE_URL")
    
    if hyperstack_api_key and hyperstack_base_url:
        client = OpenAI(
            base_url=hyperstack_base_url,
            api_key=hyperstack_api_key
        )
        logger.info("✅ Hyperstack AI client initialized successfully.")
    else:
        logger.warning("⚠️ Hyperstack AI credentials not found. Using rule-based classification only.")
        client = None
    
    logger.info("Services initialized successfully.")

def get_intent(user_query: str, history: list) -> dict:
    """
    Uses the LLM to classify intent and extract entities, with fallback to rule-based.
    """
    # First, try rule-based matching for common patterns
    rule_based_intent = rule_based_intent_classification(user_query)
    if rule_based_intent["intent"] != "unclassified":
        logger.info(f"Rule-based classified intent: {rule_based_intent}")
        return rule_based_intent
    
    # If rule-based fails, try AI classification
    return ai_intent_classification(user_query, history)

def rule_based_intent_classification(user_query: str) -> dict:
    """
    Rule-based intent classification as fallback when AI is unavailable.
    """
    if not user_query or not isinstance(user_query, str):
        return {"intent": "unclassified", "entities": {}}
    
    query_lower = user_query.lower().strip()
    
    # Greetings
    if any(word in query_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'hola', 'namaste']):
        return {"intent": "greeting", "entities": {}}
    
    # Thanks
    if any(word in query_lower for word in ['thanks', 'thank you', 'thank u', 'thx', 'appreciate', 'grateful']):
        return {"intent": "thanks", "entities": {}}
    
    # Product search
    if any(word in query_lower for word in ['search', 'find', 'look for', 'show me', 'looking for', 'want to buy', 'need', 'product', 'products', 'show', 'find me']):
        keywords = extract_search_keywords(query_lower)
        return {"intent": "product_search", "entities": {"keywords": keywords}}
    
    # Order status
    if any(word in query_lower for word in ['order status', 'where is my order', 'track order', 'order tracking', 'status of order', 'my order', 'order update', 'when will it arrive']):
        order_id = extract_order_id(query_lower)
        return {"intent": "order_status", "entities": {"order_id": order_id}}
    
    # Order placing
    if any(phrase in query_lower for phrase in ['i want to buy', 'i want to purchase', 'i want to order', 'buy', 'purchase', 'order', 'i want', 'get me', 'add to cart', 'i need']):
        product_id, product_name = extract_product_info(query_lower)
        return {"intent": "order_placing", "entities": {"product_id": product_id, "product_name": product_name}}
    
    # Customer support
    if any(word in query_lower for word in ['return', 'refund', 'shipping', 'policy', 'support', 'help', 'warranty', 'contact', 'delivery', 'exchange', 'complaint']):
        return {"intent": "customer_support", "entities": {"topic": query_lower}}
    
    # Cancel order
    if any(phrase in query_lower for phrase in ['cancel order', 'cancel my order', 'want to cancel', 'remove order', 'delete order']):
        order_id = extract_order_id(query_lower)
        return {"intent": "cancel_order", "entities": {"order_id": order_id}}
    
    # General knowledge - common questions
    if any(phrase in query_lower for phrase in ['how are you', 'what can you do', 'who are you', 'what are you', 'help me', 'what do you do']):
        return {"intent": "general_knowledge", "entities": {}}
    
    return {"intent": "unclassified", "entities": {}}

def extract_search_keywords(query: str) -> list:
    """Extract search keywords from query"""
    stop_words = ['search', 'find', 'look', 'for', 'me', 'show', 'want', 'to', 'buy', 'need', 'product', 'products', 'looking', 'something', 'please']
    words = query.split()
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return keywords if keywords else ['general']

def extract_order_id(query: str) -> str:
    """Extract order ID from query"""
    # Look for ORD- pattern
    order_match = re.search(r'ORD-?\s*(\d+)', query.upper())
    if order_match:
        return f"ORD-{order_match.group(1)}"
    
    # Try to find any 4+ digit numbers that might be order IDs
    number_match = re.search(r'(\d{4,})', query)
    if number_match:
        return f"ORD-{number_match.group(1)}"
    
    return ""

def extract_product_info(query: str) -> tuple:
    """Extract product ID or name from query"""
    # Look for product IDs like PROD-001
    product_id_match = re.search(r'PROD-?\s*(\d+)', query.upper())
    if product_id_match:
        return f"PROD-{product_id_match.group(1)}", ""
    
    # Extract potential product names (words after buy/purchase/get)
    action_words = ['buy', 'purchase', 'get', 'want', 'order', 'need']
    words = query.split()
    
    for i, word in enumerate(words):
        if word.lower() in action_words and i + 1 < len(words):
            # Get words after the action word, but stop at common connectors
            product_words = []
            for j in range(i + 1, len(words)):
                if words[j].lower() in ['a', 'an', 'the', 'some', 'for', 'please', 'thanks']:
                    continue
                product_words.append(words[j])
            if product_words:
                product_name = ' '.join(product_words)
                return "", product_name
    
    # If no action words found, assume the whole query is about a product
    stop_words = ['show', 'me', 'find', 'search', 'for', 'please', 'hello', 'hi']
    product_words = [word for word in words if word.lower() not in stop_words]
    if product_words:
        return "", ' '.join(product_words)
    
    return "", ""

def ai_intent_classification(user_query: str, history: list) -> dict:
    """
    AI-based intent classification (original method)
    """
    system_prompt = """
    You are an intelligent routing agent for an e-commerce WhatsApp bot.
    Analyze the user's query and classify into ONE of these intents:
    - 'greeting': hello, hi, hey, good morning/afternoon
    - 'thanks': thanks, thank you, appreciate
    - 'product_search': searching, finding, looking for products
    - 'order_status': order tracking, status, where is my order
    - 'cancel_order': canceling orders, remove order
    - 'customer_support': returns, refunds, shipping, policies, help
    - 'order_placing': buying, purchasing, want to buy
    - 'general_knowledge': general questions, how are you, what can you do
    - 'unclassified': everything else

    Extract relevant entities:
    - For product_search: 'keywords' as list
    - For order_status/cancel_order: 'order_id'
    - For order_placing: 'product_id' or 'product_name'

    Respond ONLY with valid JSON: {"intent": "...", "entities": {...}}
    """
    
    messages = [{"role": "system", "content": system_prompt}] 
    if history:
        messages.extend(history[-2:])
    else:
        messages.append({"role": "user", "content": user_query})
    
    try:
        # Only use AI if credentials are available
        if client and HYPERSTACK_MODEL_NAME:
            response = client.chat.completions.create(
                model=HYPERSTACK_MODEL_NAME,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            intent_json = json.loads(response.choices[0].message.content)
            logger.info(f"AI classified intent: {intent_json}")
            return intent_json
        else:
            logger.warning("AI client not available, using rule-based fallback")
            return {"intent": "unclassified", "entities": {}}
            
    except Exception as e:
        logger.error(f"Error in AI intent classification: {e}")
        return {"intent": "unclassified", "entities": {}}

def get_support_answer(user_query: str, context: str) -> str:
    """Uses RAG for customer support questions."""
    # First, try to answer common questions directly
    direct_answer = get_direct_support_answer(user_query)
    if direct_answer:
        return direct_answer
    
    # If no direct answer, use AI if available
    system_prompt = f"""
    You are a helpful customer support agent. Using the provided knowledge base below, answer the user's question.
    If the answer is not in the knowledge base, say "I'm sorry, I don't have information on that topic. How else can I help?".

    --- KNOWLEDGE BASE ---
    {context}
    --------------------
    
    Keep your response concise and helpful. Use emojis where appropriate for WhatsApp.
    """
    
    try:
        if client and HYPERSTACK_MODEL_NAME:
            response = client.chat.completions.create(
                model=HYPERSTACK_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.5
            )
            return response.choices[0].message.content
        else:
            return "I'd be happy to help with customer support questions! Please contact our support team at support@store.com or call +1-800-HELP-NOW for immediate assistance."
    except Exception as e:
        logger.error(f"Error getting support answer from LLM: {e}")
        return "I'm having trouble accessing my knowledge base right now. Please try again later."

def get_direct_support_answer(user_query: str) -> str:
    """Provide direct answers for common support questions without AI"""
    query_lower = user_query.lower()
    
    if any(word in query_lower for word in ['shipping', 'delivery', 'when will it arrive']):
        return "🚚 We offer:\n• Standard shipping: 3-5 days ($5.99)\n• Express shipping: 1-2 days ($15.99)\n• Free shipping on orders over $75!"
    
    elif any(word in query_lower for word in ['return', 'refund']):
        return "🔄 30-day return policy! Return any unopened item within 30 days for full refund. Return shipping is customer's responsibility unless item was damaged."
    
    elif any(word in query_lower for word in ['contact', 'support', 'help', 'phone', 'email']):
        return "📞 Contact us:\n• Email: support@store.com\n• Phone: +1-800-HELP-NOW\n• Hours: Mon-Fri 9AM-5PM EST"
    
    elif any(word in query_lower for word in ['payment', 'pay', 'credit card']):
        return "💳 We accept: Visa, MasterCard, American Express, and PayPal. All transactions are secure and encrypted!"
    
    return ""

def get_general_answer(user_query: str, history: list) -> str:
    """
    Uses the LLM to generate a conversational response for non-e-commerce queries.
    """
    # First, try direct answers for common questions
    direct_answer = get_direct_general_answer(user_query)
    if direct_answer:
        return direct_answer
    
    # If no direct answer, use AI if available
    system_prompt = """You are a friendly and helpful conversational AI for an e-commerce store. 
    You're talking to customers on WhatsApp, so keep responses conversational and engaging.
    
    Guidelines:
    - Be warm, friendly, and human-like
    - Use appropriate emojis occasionally 
    - Keep responses concise (1-2 sentences usually)
    - Be helpful but don't make up information about products or policies
    - If you can't help with something, gently guide them to what you can do
    - Show personality but stay professional
    
    Remember: You're a shopping assistant first, but you can have friendly conversations too!"""
    
    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        if client and HYPERSTACK_MODEL_NAME:
            response = client.chat.completions.create(
                model=HYPERSTACK_MODEL_NAME,
                messages=messages,
                temperature=0.8
            )
            return response.choices[0].message.content
        else:
            return "I'm here to help with your shopping needs! I can help you find products, check orders, or answer questions about our store. What would you like to do today? 😊"
    except Exception as e:
        logger.error(f"Error getting general answer from LLM: {e}")
        return "I'm here to help with your shopping needs! What can I assist you with today? 😊"

def get_direct_general_answer(user_query: str) -> str:
    """Provide direct answers for common general questions without AI"""
    query_lower = user_query.lower()
    
    if any(phrase in query_lower for phrase in ['how are you', 'how are u']):
        return "I'm doing great! 😊 Thanks for asking! I'm excited to help you with your shopping today. What can I help you find?"
    
    elif any(phrase in query_lower for phrase in ['what can you do', 'what do you do']):
        return "I'm your shopping assistant! 🤖 I can:\n• Find products 🔍\n• Check order status 📦\n• Help you buy items 🛒\n• Answer questions ❓\nWhat would you like to do?"
    
    elif any(phrase in query_lower for phrase in ['who are you', 'what are you']):
        return "I'm your friendly AI shopping assistant! 🤖 I'm here to make your shopping experience amazing. Think of me as your personal shopping buddy! 😊"
    
    elif any(phrase in query_lower for phrase in ['how old are you']):
        return "I'm as old as the latest AI technology! 😄 But more importantly, I'm here to help you shop. What can I assist you with today?"
    
    return ""

def send_whatsapp_message(recipient_wa_id: str, text_message: str):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
    data = json.dumps({
        "messaging_product": "whatsapp", 
        "recipient_type": "individual", 
        "to": recipient_wa_id,
        "type": "text", 
        "text": {"preview_url": False, "body": text_message},
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
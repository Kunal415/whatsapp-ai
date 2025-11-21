# app.py
import os
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from collections import deque

# Import all our custom modules and handlers
from data_loader import load_data
from services import initialize_services, get_intent, send_whatsapp_message, validate_whatsapp_signature
from handlers import (
    handle_product_search,
    handle_order_status,
    handle_order_cancellation,
    handle_customer_support,
    handle_order_placing_start,
    handle_order_confirmation,
    handle_shipping_address,
    handle_general_knowledge,
    handle_unclassified,
    handle_greeting,
    handle_thanks
)

# Initialize the Flask application
app = Flask(__name__)

# Configure logging for clear, informative output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- In-Memory Storage ---
# A dictionary to track users in multi-step processes (e.g., placing an order)
user_sessions = {} 
# A dictionary to store recent conversation history for each user
conversation_history = {} 
MAX_HISTORY_LENGTH = 10 # How many message pairs to remember

# --- Run Initialization routines ---
load_dotenv() # Load secrets from .env file
initialize_services() # Setup API clients
load_data() # Load product/order data into memory

# --- Main Message Processing Logic ---
def process_whatsapp_message(body):
    """The core function that orchestrates the bot's response."""
    try:
        # Extract necessary information from the incoming webhook payload
        value = body["entry"][0]["changes"][0]["value"]
        if not value.get("messages"):
            logger.info("Received a non-message event (e.g., status update). Ignoring.")
            return

        message = value["messages"][0]
        whatsapp_id = message["from"]
        message_body = message["text"]["body"]
        logger.info(f"Received message from {whatsapp_id}: '{message_body}'")

        # Check if the user is in an active session
        session = user_sessions.get(whatsapp_id)
        # Get or create conversation history for the user
        history = conversation_history.setdefault(whatsapp_id, deque(maxlen=MAX_HISTORY_LENGTH))
        
        reply_message = ""

        # PATH 1: User is in a multi-step session (e.g., placing an order)
        if session:
            state = session.get('state')
            logger.info(f"User {whatsapp_id} in session state: {state}")
            
            if state == 'awaiting_order_confirmation':
                reply_message = handle_order_confirmation(message_body, session, whatsapp_id, user_sessions)
            
            elif state == 'awaiting_shipping_address':
                reply_message = handle_shipping_address(message_body, session['data'], whatsapp_id)
                # The process is complete, so we clear the user's session
                user_sessions.pop(whatsapp_id, None)
                logger.info(f"Order process completed for {whatsapp_id}")

        # PATH 2: User is not in a session, so we need to determine their intent
        else:
            # Add the new message to the history for context
            history.append({"role": "user", "content": message_body})
            # Call the AI to get the intent
            intent_data = get_intent(message_body, list(history))
            intent = intent_data.get("intent", "unclassified")
            entities = intent_data.get("entities", {})
            
            logger.info(f"Detected intent: {intent}, entities: {entities}")

            # A clean way to map intents to their handler functions
            intent_handlers = {
                'greeting': handle_greeting,  
                'thanks': handle_thanks, 
                'product_search': lambda: handle_product_search(entities),
                'order_status': lambda: handle_order_status(entities, whatsapp_id),
                'cancel_order': lambda: handle_order_cancellation(entities, whatsapp_id),
                'customer_support': lambda: handle_customer_support(message_body),
                'order_placing': lambda: handle_order_placing_start(entities, whatsapp_id, user_sessions),
                'general_knowledge': lambda: handle_general_knowledge(message_body, list(history)),
                'unclassified': handle_unclassified
            }
            # Get the correct handler function from the dictionary, or the default one
            handler = intent_handlers.get(intent, handle_unclassified)
            # Execute the handler to get the reply message
            reply_message = handler()

        # Finally, send the generated reply and update the history
        logger.info(f"Sending reply to {whatsapp_id}: '{reply_message}'")
        send_whatsapp_message(whatsapp_id, reply_message)
        history.append({"role": "assistant", "content": reply_message})

    except Exception as e:
        logger.error(f"Error processing webhook message: {e}", exc_info=True)
        # If something breaks, clear the user's session so they aren't stuck
        if 'whatsapp_id' in locals():
            user_sessions.pop(whatsapp_id, None)
            send_whatsapp_message(whatsapp_id, "Sorry, something went wrong on my end. Please try again.")

# --- Flask Routes ---
@app.route("/webhook", methods=["GET"])
def webhook_get():
    """Handles the webhook verification GET request from Meta."""
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    # Check that the token from Meta matches our secret token
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("WEBHOOK_VERIFIED")
        return challenge, 200 # Respond with the challenge to confirm
    else:
        logger.warning("Webhook verification failed.")
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook_post():
    """Handles incoming WhatsApp messages via POST request."""
    # First, validate the signature to ensure the request is authentic
    signature = request.headers.get("X-Hub-Signature-256", "")[7:] # remove 'sha256='
    if not validate_whatsapp_signature(request.data, signature):
        logger.warning("Signature verification failed for POST request.")
        return "Invalid signature", 403
    
    # If the signature is valid, process the message
    body = request.get_json()
    if body.get("object") == "whatsapp_business_account":
        process_whatsapp_message(body)
        return jsonify({"status": "ok"}), 200
    else:
        # If it's not a WhatsApp event, ignore it
        logger.warning("Received a non-WhatsApp or unhandled event.")
        return "Not a WhatsApp event", 404

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({"status": "healthy", "service": "agentic-whatsapp-ai"})

# --- Run the Flask App ---
if __name__ == "__main__":
    logger.info("Starting Flask app...")
    app.run(host="0.0.0.0", port=8000, debug=False)
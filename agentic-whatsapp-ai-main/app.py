# app.py

import os
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from collections import deque

# --- App Initialization ---
load_dotenv()

# Import our custom modules
from data_loader import load_data
from services import initialize_services, get_intent, send_whatsapp_message, validate_whatsapp_signature
from handlers import (
    handle_product_search,
    handle_order_status,
    handle_order_cancellation,
    handle_customer_support,
    handle_order_placing_start,
    handle_order_confirmation,
    handle_shipping_address,    # ### NEW ### Import the new handler
    handle_general_knowledge,
    handle_unclassified
)

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- In-Memory Storage (No changes here) ---
user_sessions = {}
conversation_history = {}
MAX_HISTORY_LENGTH = 10

# --- Initialize Services and Load Data ---
initialize_services()
load_data()

# --- Main Message Processing Logic (Updated for new state) ---
def process_whatsapp_message(body):
    try:
        value = body["entry"][0]["changes"][0]["value"]
        if not value.get("messages"):
            logger.info("Received a non-message event (e.g., status update). Ignoring.")
            return

        message = value["messages"][0]
        whatsapp_id = message["from"]
        message_body = message["text"]["body"]
        logger.info(f"Received message from {whatsapp_id}: '{message_body}'")

        session = user_sessions.get(whatsapp_id)
        history = conversation_history.setdefault(whatsapp_id, deque(maxlen=MAX_HISTORY_LENGTH))
        
        reply_message = ""

        # 1. Check if the user is in the middle of a specific workflow
        if session:
            state = session.get('state')
            if state == 'awaiting_order_confirmation':
                reply_message = handle_order_confirmation(message_body, session, whatsapp_id, user_sessions)
                # Session state is updated inside the handler now
            
            # ### NEW ### Handle the new state for collecting address
            elif state == 'awaiting_shipping_address':
                reply_message = handle_shipping_address(message_body, session['data'], whatsapp_id)
                # The session is now complete, so we clear it
                user_sessions.pop(whatsapp_id, None)

        # 2. If not in a specific workflow, use the LLM to determine intent
        else:
            history.append({"role": "user", "content": message_body})
            intent_data = get_intent(message_body, list(history))
            intent = intent_data.get("intent", "unclassified")
            entities = intent_data.get("entities", {})

            # 3. Route to the appropriate handler
            intent_handlers = {
                'product_search': lambda: handle_product_search(entities),
                'order_status': lambda: handle_order_status(entities, whatsapp_id),
                'cancel_order': lambda: handle_order_cancellation(entities, whatsapp_id),
                'customer_support': lambda: handle_customer_support(message_body),
                'order_placing': lambda: handle_order_placing_start(entities, whatsapp_id, user_sessions),
                'general_knowledge': lambda: handle_general_knowledge(message_body, list(history)),
                'unclassified': handle_unclassified
            }
            handler = intent_handlers.get(intent, handle_unclassified)
            reply_message = handler()

        # 4. Send the response and update history
        logger.info(f"Sending reply to {whatsapp_id}: '{reply_message}'")
        send_whatsapp_message(whatsapp_id, reply_message)
        history.append({"role": "assistant", "content": reply_message})

    except Exception as e:
        logger.error(f"Error processing webhook message: {e}", exc_info=True)
        # Clear session on error to prevent user from getting stuck
        if 'whatsapp_id' in locals():
            user_sessions.pop(whatsapp_id, None)
        send_whatsapp_message(whatsapp_id, "Sorry, something went wrong on my end. Please try again.")


# --- Flask Routes (No changes here) ---
@app.route("/webhook", methods=["GET"])
def webhook_get():
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("WEBHOOK_VERIFIED")
        return challenge, 200
    else:
        logger.warning("Webhook verification failed.")
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook_post():
    signature = request.headers.get("X-Hub-Signature-256", "")[7:]
    if not validate_whatsapp_signature(request.data, signature):
        logger.warning("Signature verification failed for POST request.")
        return "Invalid signature", 403
    body = request.get_json()
    logger.debug(f"Received webhook body: {json.dumps(body, indent=2)}")
    if body.get("object") == "whatsapp_business_account":
        process_whatsapp_message(body)
        return jsonify({"status": "ok"}), 200
    else:
        logger.warning("Received a non-WhatsApp or unhandled event.")
        return "Not a WhatsApp event", 404

# --- Run App (No changes here) ---
if __name__ == "__main__":
    logger.info("Starting Flask app...")
    app.run(host="0.0.0.0", port=8000, debug=False)
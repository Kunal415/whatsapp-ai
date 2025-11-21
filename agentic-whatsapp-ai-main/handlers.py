import logging
import pandas as pd
from datetime import datetime
from data_loader import get_products, get_orders, get_faq_content, update_orders_dataframe
from services import get_support_answer, get_general_answer

logger = logging.getLogger(__name__)

def handle_greeting() -> str:
    """Handles greeting messages with human-like responses"""
    greetings = [
        "Hello! 👋 Welcome to our store! I'm your friendly shopping assistant. How can I help you today?",
        "Hi there! 😊 Great to see you! What can I help you find today?",
        "Hey! 👋 Thanks for reaching out! Looking for something specific or just browsing?",
        "Good day! 🌟 How can I assist you with your shopping today?",
        "Hello there! 🛍️ Ready to find some amazing products? What brings you here today?"
    ]
    import random
    return random.choice(greetings)

def handle_thanks() -> str:
    """Handles thank you messages"""
    responses = [
        "You're very welcome! 😊 Happy to help! Is there anything else you need?",
        "My pleasure! 🌟 Let me know if you need anything else!",
        "Anytime! 😄 I'm here whenever you need assistance!",
        "Glad I could help! 💫 Don't hesitate to reach out if you have more questions!",
        "You're welcome! 🛍️ Enjoy your shopping experience!"
    ]
    import random
    return random.choice(responses)

def handle_product_search(entities: dict) -> str:
    products_df = get_products()
    keywords = entities.get('keywords', [])
    
    if not keywords or not isinstance(keywords, list):
        return "Please tell me what product you're looking for. For example: 'I want to buy coffee' or 'Show me laptops'"
    
    search_cols = ['product_name', 'keywords', 'category', 'description']
    results_df = products_df.copy()
    
    # Convert all searchable columns to lowercase for case-insensitive search
    for col in search_cols:
        results_df[f'{col}_lower'] = results_df[col].astype(str).str.lower()
    
    # Search across all columns for any of the keywords
    mask = False
    for keyword in keywords:
        keyword_lower = keyword.lower()
        keyword_mask = results_df.apply(
            lambda row: any(keyword_lower in str(row[f'{col}_lower']) for col in search_cols), 
            axis=1
        )
        mask = mask | keyword_mask
    
    filtered_df = results_df[mask]
    
    if filtered_df.empty:
        suggestion = "\n\nTry searching with different keywords or browse by category: electronics, groceries, home, beauty, apparel, sports."
        return f"Sorry, I couldn't find any products matching '{' '.join(keywords)}'.{suggestion}"
    
    # Sort by stock quantity (in-stock first) and then by price
    filtered_df = filtered_df.sort_values(['stock_quantity', 'price'], ascending=[False, True])
    
    response_lines = [f"I found {len(filtered_df)} product(s) matching '{' '.join(keywords)}':\n"]
    
    for _, row in filtered_df.head(5).iterrows():
        stock_status = "✅ In Stock" if row['stock_quantity'] > 0 else "❌ Out of Stock"
        response_lines.append(
            f"• {row['product_name']}\n"
            f"  ID: {row['product_id']} | Price: ${row['price']:.2f} | {stock_status}\n"
            f"  Category: {row['category']}"
        )
    
    if len(filtered_df) > 5:
        response_lines.append(f"\n... and {len(filtered_df) - 5} more products. Please refine your search to see more.")
    
    response_lines.append("\n💡 To order any product, reply with: 'I want to buy [Product ID]'")
    
    return "\n".join(response_lines)

def handle_order_status(entities: dict, whatsapp_id: str) -> str:
    orders_df = get_orders()
    order_id = entities.get('order_id')
    if not order_id:
        return "Please provide an order ID to check the status. For example: 'What is the status of order ORD-1001?'"
    
    # Clean order ID format
    order_id = order_id.upper().strip()
    if not order_id.startswith('ORD-'):
        order_id = f"ORD-{order_id.lstrip('ORD-')}"
    
    order = orders_df[orders_df['order_id'] == order_id]
    if order.empty:
        return f"Sorry, I couldn't find an order with the ID: {order_id}."
    
    # FIX: Convert both to string for comparison
    if str(order.iloc[0]['whatsapp_id']) != whatsapp_id:
        return f"Sorry, I couldn't find order {order_id} associated with your account."
    
    status = order.iloc[0]['status']
    delivery_date = order.iloc[0]['estimated_delivery']
    product_ids = order.iloc[0]['product_ids']
    
    # Get product names for better response
    products_df = get_products()
    product_info = []
    for pid in str(product_ids).split(','):
        product = products_df[products_df['product_id'] == pid.strip()]
        if not product.empty:
            product_info.append(product.iloc[0]['product_name'])
    
    product_list = ", ".join(product_info) if product_info else f"Product ID: {product_ids}"
    
    status_emoji = {
        'Pending': '⏳',
        'Processing': '🔄', 
        'Shipped': '🚚',
        'Delivered': '✅',
        'Cancelled': '❌'
    }.get(status, '📦')
    
    return (
        f"{status_emoji} Order #{order_id}\n"
        f"Status: {status}\n"
        f"Products: {product_list}\n"
        f"Estimated Delivery: {delivery_date}\n\n"
        f"Need help with this order? Just ask!"
    )

def handle_order_cancellation(entities: dict, whatsapp_id: str) -> str:
    orders_df = get_orders()
    order_id = entities.get('order_id')
    if not order_id:
        return "Please provide the order ID you wish to cancel. For example: 'Cancel order ORD-1001'"
    
    # Clean order ID format
    order_id = order_id.upper().strip()
    if not order_id.startswith('ORD-'):
        order_id = f"ORD-{order_id.lstrip('ORD-')}"
    
    order_mask = orders_df['order_id'] == order_id
    if not order_mask.any():
        return f"Sorry, I couldn't find an order with the ID: {order_id}."
    
    order_index = orders_df[order_mask].index[0]
    order = orders_df.loc[order_index]
    
    # FIX: Convert both to string for comparison
    if str(order['whatsapp_id']) != whatsapp_id:
        return f"Sorry, I couldn't find order {order_id} associated with your account."
    
    if order['status'] in ['Pending', 'Processing']:
        updated_orders_df = orders_df.copy()
        updated_orders_df.loc[order_index, 'status'] = 'Cancelled'
        if update_orders_dataframe(updated_orders_df):
            return (
                f"✅ Order #{order_id} has been successfully cancelled.\n\n"
                f"Your refund will be processed within 3-5 business days.\n\n"
                f"Is there anything else I can help you with?"
            )
        else:
            return "I'm sorry, there was an error trying to cancel your order. Please contact support."
    elif order['status'] in ['Shipped', 'Delivered']:
        return (
            f"Sorry, order #{order_id} has already been '{order['status']}' and cannot be cancelled.\n\n"
            f"If there's an issue with your order, please contact customer support for assistance."
        )
    else:
        return f"Order #{order_id} is in a '{order['status']}' state and cannot be cancelled at this time."

def handle_customer_support(user_query: str) -> str:
    faq_context = get_faq_content()
    return get_support_answer(user_query, faq_context)

def handle_order_placing_start(entities: dict, whatsapp_id: str, user_sessions: dict) -> str:
    products_df = get_products()
    product_id = entities.get('product_id')
    product_name = entities.get('product_name')
    
    product_to_order = None
    
    # Try by product ID first (more precise)
    if product_id:
        product_to_order = products_df[products_df['product_id'] == product_id.upper()]
    
    # If no match by ID, try by name
    if product_to_order is None or product_to_order.empty:
        if product_name:
            product_to_order = products_df[
                products_df['product_name'].str.contains(product_name, case=False, na=False)
            ]
    
    if product_to_order is None or product_to_order.empty:
        return (
            f"Sorry, I couldn't find a product matching your request.\n\n"
            f"Please try:\n"
            f"• Searching for products first using: 'search [product name]'\n"
            f"• Using the exact product ID from search results\n"
            f"• Being more specific with the product name"
        )
    
    if len(product_to_order) > 1:
        product_list = "\n".join([f"- {row['product_name']} (ID: {row['product_id']})" 
                                for _, row in product_to_order.head(3).iterrows()])
        return (
            f"I found multiple products matching that name:\n{product_list}\n\n"
            f"Please specify which one you want using the product ID."
        )
    
    product_data = product_to_order.iloc[0]
    
    if product_data['stock_quantity'] <= 0:
        return (
            f"I'm sorry, but '{product_data['product_name']}' is currently out of stock.\n\n"
            f"Would you like me to suggest similar available products?"
        )
    
    # Set session to await confirmation
    user_sessions[whatsapp_id] = {
        'state': 'awaiting_order_confirmation',
        'data': {
            'product_id': product_data['product_id'],
            'product_name': product_data['product_name'],
            'price': product_data['price'],
            'category': product_data['category']
        }
    }
    
    return (
        f"🛒 Order Summary:\n"
        f"Product: {product_data['product_name']}\n"
        f"Category: {product_data['category']}\n"
        f"Price: ${product_data['price']:.2f}\n\n"
        f"Would you like to proceed with this order?\n\n"
        f"Please reply with 'yes' to confirm or 'no' to cancel."
    )

def handle_order_confirmation(user_response: str, session: dict, whatsapp_id: str, user_sessions: dict) -> str:
    """
    Handles the user's confirmation. If 'yes', transitions to the address collection state.
    If 'no', cancels the process.
    """
    if 'yes' in user_response.lower():
        # Transition the state to the next step
        session['state'] = 'awaiting_shipping_address'
        user_sessions[whatsapp_id] = session  # Update the session in the main dictionary
        logger.info(f"User {whatsapp_id} confirmed order. Now awaiting shipping address.")
        return (
            "Great! Your order is almost complete. 🎉\n\n"
            "Please provide your full shipping address including:\n"
            "• Street address\n"
            "• City\n" 
            "• State/Province\n"
            "• ZIP/Postal code\n"
            "• Country\n\n"
            "Example: 123 Main St, New York, NY 10001, USA"
        )
    else:
        # User cancelled, so clear the session
        user_sessions.pop(whatsapp_id, None)
        return (
            "Okay, I've cancelled the order process. ❌\n\n"
            "Is there anything else I can help you with? You can:\n"
            "• Search for other products\n"
            "• Check order status\n"
            "• Ask about shipping policies\n"
            "• Contact support"
        )

def handle_shipping_address(address: str, order_data: dict, whatsapp_id: str) -> str:
    """
    Receives the shipping address, creates the new order, and saves it to the CSV.
    This is the final step of the order placement flow.
    """
    logger.info(f"Received shipping address '{address}' from {whatsapp_id}. Finalizing order.")
    orders_df = get_orders().copy()
    
    # Generate a new unique order ID
    if not orders_df.empty and 'order_id' in orders_df.columns:
        try:
            # Extract numeric part from existing order IDs
            numeric_parts = orders_df['order_id'].str.extract(r'ORD-(\d+)').dropna()
            if not numeric_parts.empty:
                last_order_id = numeric_parts[0].astype(int).max()
                new_order_id = f"ORD-{last_order_id + 1}"
            else:
                new_order_id = "ORD-1100"  # Fallback starting point
        except:
            new_order_id = "ORD-1100"  # Fallback if extraction fails
    else:
        new_order_id = "ORD-1100"  # First order
    
    new_order = {
        'order_id': new_order_id,
        'whatsapp_id': int(whatsapp_id),
        'product_ids': order_data['product_id'],
        'order_date': datetime.now().strftime('%Y-%m-%d'),
        'status': 'Pending',
        'estimated_delivery': (datetime.now() + pd.Timedelta(days=5)).strftime('%Y-%m-%d'),
        'shipping_address': address  # Store the collected address
    }
    
    new_order_df = pd.DataFrame([new_order])
    
    # Handle empty orders dataframe case
    if orders_df.empty:
        updated_df = new_order_df
    else:
        updated_df = pd.concat([orders_df, new_order_df], ignore_index=True)
    
    if update_orders_dataframe(updated_df):
        return (
            f"🎉 Thank you! Your order has been successfully placed!\n\n"
            f"📦 Order Details:\n"
            f"• Order ID: {new_order_id}\n"
            f"• Product: {order_data['product_name']}\n"
            f"• Total: ${order_data['price']:.2f}\n"
            f"• Status: Pending\n"
            f"• Shipping to: {address}\n\n"
            f"📬 You'll receive a confirmation email shortly.\n"
            f"🔄 Use your order ID to track status anytime!\n\n"
            f"Thank you for shopping with us! 💝"
        )
    else:
        return (
            "I'm sorry, there was a critical error placing your order. 😔\n\n"
            "Please contact our support team directly for assistance:\n"
            "• Email: support@store.com\n"
            "• Phone: +1-800-HELP-NOW\n\n"
            "We apologize for the inconvenience."
        )

def handle_general_knowledge(user_query: str, history: list) -> str:
    """Handles general conversation with more human-like responses"""
    # For common questions, provide canned responses
    user_query_lower = user_query.lower()
    
    if any(word in user_query_lower for word in ['how are you', 'how do you do', "how's it going"]):
        responses = [
            "I'm doing great, thanks for asking! 😊 Just here helping people find amazing products. How can I assist you today?",
            "I'm wonderful! 🌟 So excited to help you shop. What can I do for you?",
            "Doing awesome! 💫 Ready to help you find some great deals. What are you looking for today?"
        ]
        import random
        return random.choice(responses)
    
    elif any(word in user_query_lower for word in ['what can you do', 'what do you do', 'help me']):
        return (
            "I'm your shopping assistant! 🤖 Here's what I can help with:\n\n"
            "• 🔍 Find products - Just tell me what you're looking for!\n"
            "• 📦 Check order status - Got an order ID? I can track it!\n"
            "• 🛒 Place orders - Found something you like? I'll help you buy it!\n"
            "• ❌ Cancel orders - Changed your mind? I can help with that\n"
            "• 📞 Support - Questions about returns, shipping, etc.\n\n"
            "So, what would you like to do today? 😊"
        )
    
    elif any(word in user_query_lower for word in ['who are you', 'what are you']):
        return (
            "I'm your friendly AI shopping assistant! 🤖\n\n"
            "I'm here to make your shopping experience amazing by helping you find products, "
            "check orders, and answer any questions you have about our store.\n\n"
            "Think of me as your personal shopping buddy! 😊 What can I help you with today?"
        )
    
    # For other general questions, use the AI
    return get_general_answer(user_query, history)

def handle_unclassified() -> str:
    responses = [
        "I'm not quite sure what you're looking for! 🤔\n\nHere's what I can help with:\n• Finding products 🔍\n• Order status 📦\n• Placing orders 🛒\n• Returns & support 📞\n\nWhat would you like to do?",
        "Hmm, I want to make sure I help you properly! 😊\n\nI'm great at:\n• Product searches\n• Order tracking\n• Shopping assistance\n• Answering questions\n\nHow can I assist you today?",
        "Let me help you better! 🌟 I can:\n• Find products for you\n• Check your orders\n• Help you buy items\n• Answer store questions\n\nWhat would you like me to do?",
        "I'd love to help! 🛍️ Try asking me to:\n• 'Show me laptops'\n• 'Where is my order?'\n• 'I want to buy coffee'\n• 'What's your return policy?'\n\nWhat can I do for you?"
    ]
    import random
    return random.choice(responses)
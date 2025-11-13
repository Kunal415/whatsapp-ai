import logging
import pandas as pd
from datetime import datetime
from data_loader import get_products, get_orders, get_faq_content, update_orders_dataframe
from services import get_support_answer, get_general_answer

logger = logging.getLogger(__name__)

# --- handle_product_search and others are unchanged ---

def handle_product_search(entities: dict) -> str:
    products_df = get_products()
    keywords = entities.get('keywords', [])
    if not keywords or not isinstance(keywords, list):
        return "Please tell me what product you're looking for."
    search_cols = ['product_name', 'keywords', 'category', 'description']
    results_df = products_df[
        products_df.apply(lambda row: all(keyword.lower() in ' '.join(str(row[col]) for col in search_cols).lower() for keyword in keywords), axis=1)
    ]
    if results_df.empty:
        return f"Sorry, I couldn't find any products matching '{' '.join(keywords)}'."
    response_lines = ["Here's what I found:\n"]
    for _, row in results_df.head(5).iterrows():
        stock_status = "In Stock" if row['stock_quantity'] > 0 else "Out of Stock"
        response_lines.append(f"- {row['product_name']} (ID: {row['product_id']})\n  Price: ${row['price']:.2f} ({stock_status})")
    response_lines.append("\nYou can place an order using the Product ID.")
    return "\n".join(response_lines)

def handle_order_status(entities: dict, whatsapp_id: str) -> str:
    orders_df = get_orders()
    order_id = entities.get('order_id')
    if not order_id:
        return "Please provide an order ID to check the status."
    order = orders_df[orders_df['order_id'] == order_id]
    if order.empty:
        return f"Sorry, I couldn't find an order with the ID: {order_id}."
    if order.iloc[0]['whatsapp_id'] != int(whatsapp_id):
        return f"Sorry, I couldn't find order {order_id} associated with your account."
    status = order.iloc[0]['status']
    delivery_date = order.iloc[0]['estimated_delivery']
    return f"Order #{order_id} is currently '{status}'. The estimated delivery date is {delivery_date}."

def handle_order_cancellation(entities: dict, whatsapp_id: str) -> str:
    orders_df = get_orders()
    order_id = entities.get('order_id')
    if not order_id:
        return "Please provide the order ID you wish to cancel."
    order_mask = orders_df['order_id'] == order_id
    if not order_mask.any():
        return f"Sorry, I couldn't find an order with the ID: {order_id}."
    order_index = orders_df[order_mask].index[0]
    order = orders_df.loc[order_index]
    if order['whatsapp_id'] != int(whatsapp_id):
        return f"Sorry, I couldn't find order {order_id} associated with your account."
    if order['status'] in ['Pending', 'Processing']:
        updated_orders_df = orders_df.copy()
        updated_orders_df.loc[order_index, 'status'] = 'Cancelled'
        if update_orders_dataframe(updated_orders_df):
            return f"Order #{order_id} has been successfully cancelled."
        else:
            return "I'm sorry, there was an error trying to cancel your order. Please contact support."
    elif order['status'] in ['Shipped', 'Delivered']:
        return f"Sorry, order #{order_id} has already been '{order['status']}' and cannot be cancelled."
    else:
        return f"Order #{order_id} is in a '{order['status']}' state and cannot be cancelled at this time."

def handle_customer_support(user_query: str) -> str:
    faq_context = get_faq_content()
    return get_support_answer(user_query, faq_context)

# --- handle_order_placing_start is unchanged ---
def handle_order_placing_start(entities: dict, whatsapp_id: str, user_sessions: dict) -> str:
    products_df = get_products()
    product_id = entities.get('product_id')
    product_name = entities.get('product_name')
    product_to_order = None
    if product_id:
        product_to_order = products_df[products_df['product_id'] == product_id.upper()]
    elif product_name:
        product_to_order = products_df[products_df['product_name'].str.contains(product_name, case=False)]
    if product_to_order is None or product_to_order.empty:
        return f"Sorry, I couldn't find a product matching your request. Please try searching for the product first to get its ID."
    if len(product_to_order) > 1:
        return "I found multiple products matching that name. Please be more specific or provide the product ID."
    product_data = product_to_order.iloc[0]
    if product_data['stock_quantity'] <= 0:
        return f"I'm sorry, but '{product_data['product_name']}' is currently out of stock."
    
    # Set session to await confirmation
    user_sessions[whatsapp_id] = {
        'state': 'awaiting_order_confirmation',
        'data': {
            'product_id': product_data['product_id'],
            'product_name': product_data['product_name'],
            'price': product_data['price']
        }
    }
    return (f"You want to order '{product_data['product_name']}' for ${product_data['price']:.2f}. "
            f"Is that correct? (Please reply with 'yes' or 'no')")


# ### UPDATED ### This handler now transitions to the next state instead of creating the order
def handle_order_confirmation(user_response: str, session: dict, whatsapp_id: str, user_sessions: dict) -> str:
    """
    Handles the user's confirmation. If 'yes', transitions to the address collection state.
    If 'no', cancels the process.
    """
    if 'yes' in user_response.lower():
        # Transition the state to the next step
        session['state'] = 'awaiting_shipping_address'
        user_sessions[whatsapp_id] = session # Update the session in the main dictionary
        logger.info(f"User {whatsapp_id} confirmed order. Now awaiting shipping address.")
        return "Great! Please provide your full shipping address."
    else:
        # User cancelled, so clear the session
        user_sessions.pop(whatsapp_id, None)
        return "Okay, I've cancelled the order process. Is there anything else I can help with?"


# ### NEW ### This is the final step in the order process
def handle_shipping_address(address: str, order_data: dict, whatsapp_id: str) -> str:
    """
    Receives the shipping address, creates the new order, and saves it to the CSV.
    This is the final step of the order placement flow.
    """
    logger.info(f"Received shipping address '{address}' from {whatsapp_id}. Finalizing order.")
    orders_df = get_orders().copy()
    
    # Generate a new unique order ID
    last_order_id = orders_df['order_id'].str.extract(r'(\d+)').astype(int).max().values[0]
    new_order_id = f"ORD-{last_order_id + 1}"
    
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
    updated_df = pd.concat([orders_df, new_order_df], ignore_index=True)
    
    if update_orders_dataframe(updated_df):
        return (f"Thank you! Your order for '{order_data['product_name']}' has been placed. "
                f"Your order ID is {new_order_id}. It will be shipped to: {address}")
    else:
        return "I'm sorry, there was a critical error placing your order. Please contact our support team directly."


# --- handle_general_knowledge and handle_unclassified are unchanged ---
def handle_general_knowledge(user_query: str, history: list) -> str:
    return get_general_answer(user_query, history)

def handle_unclassified() -> str:
    return "I'm sorry, I'm not sure how to help with that. You can ask me to search for products, check an order status, or ask about our policies."
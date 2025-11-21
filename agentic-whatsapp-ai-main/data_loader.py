import pandas as pd
import logging
import os
import threading

logger = logging.getLogger(__name__)

# Define file paths relative to the project root
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PRODUCTS_CSV_PATH = os.path.join(DATA_DIR, 'products.csv')
ORDERS_CSV_PATH = os.path.join(DATA_DIR, 'orders.csv')
FAQ_TXT_PATH = os.path.join(DATA_DIR, 'faq.txt')

products_df = None
orders_df = None
faq_content = ""

# A lock to prevent race conditions when writing to files
csv_lock = threading.Lock()

def load_data():
    """
    Loads all data files into memory. This function is called once when the app starts.
    """
    global products_df, orders_df, faq_content
    try:
        products_df = pd.read_csv(PRODUCTS_CSV_PATH)
        logger.info(f"Successfully loaded {len(products_df)} products from products.csv")
        
        # Load orders with better error handling for empty files
        try:
            orders_df = pd.read_csv(ORDERS_CSV_PATH)
            logger.info(f"Successfully loaded {len(orders_df)} orders from orders.csv")
        except pd.errors.EmptyDataError:
            orders_df = pd.DataFrame(columns=['order_id', 'whatsapp_id', 'product_ids', 'order_date', 'status', 'estimated_delivery', 'shipping_address'])
            logger.warning("orders.csv is empty, created empty DataFrame")
        
        with open(FAQ_TXT_PATH, 'r', encoding='utf-8') as f:
            faq_content = f.read()
        
        logger.info("Successfully loaded faq.txt")
        
        # Data validation
        validate_data()
        
    except FileNotFoundError as e:
        logger.error(f"Error loading data file: {e}. Make sure the 'data' directory and files exist.")
        # Create empty DataFrames if files don't exist
        products_df = pd.DataFrame(columns=['product_id', 'product_name', 'category', 'price', 'stock_quantity', 'description', 'keywords'])
        orders_df = pd.DataFrame(columns=['order_id', 'whatsapp_id', 'product_ids', 'order_date', 'status', 'estimated_delivery', 'shipping_address'])
        faq_content = "No FAQ content available."
        logger.warning("Created empty DataFrames due to missing files")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading data: {e}")
        exit()

def validate_data():
    """Validates the loaded data for common issues"""
    if products_df is not None:
        # Check for duplicate product IDs
        duplicate_products = products_df[products_df.duplicated('product_id')]
        if not duplicate_products.empty:
            logger.warning(f"Found {len(duplicate_products)} duplicate product IDs")
        
        # Check for products with negative stock
        negative_stock = products_df[products_df['stock_quantity'] < 0]
        if not negative_stock.empty:
            logger.warning(f"Found {len(negative_stock)} products with negative stock quantity")
    
    if orders_df is not None and not orders_df.empty:
        # Check for duplicate order IDs
        duplicate_orders = orders_df[orders_df.duplicated('order_id')]
        if not duplicate_orders.empty:
            logger.warning(f"Found {len(duplicate_orders)} duplicate order IDs")

def get_products():
    """Returns the loaded products DataFrame."""
    if products_df is None:
        load_data()
    return products_df

def get_orders():
    """Returns the loaded orders DataFrame."""
    if orders_df is None:
        load_data()
    return orders_df

def get_faq_content():
    """Returns the loaded FAQ content as a string."""
    if not faq_content:
        load_data()
    return faq_content

def update_orders_dataframe(updated_df: pd.DataFrame):
    """
    Updates the global orders_df and persists the changes to orders.csv.
    This function is now the single point of truth for any order modification.
    """
    global orders_df
    with csv_lock:
        try:
            orders_df = updated_df
            # Ensure directory exists
            os.makedirs(os.path.dirname(ORDERS_CSV_PATH), exist_ok=True)
            orders_df.to_csv(ORDERS_CSV_PATH, index=False)
            logger.info(f"Successfully updated and saved orders.csv. Total orders: {len(orders_df)}")
            return True
        except Exception as e:
            logger.error(f"Failed to save updated orders to CSV: {e}")
            return False
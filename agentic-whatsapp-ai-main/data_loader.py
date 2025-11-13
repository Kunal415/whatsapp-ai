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

# --- NEW: A lock to prevent race conditions when writing to files ---
# This is important if your server handles multiple requests concurrently.
csv_lock = threading.Lock()

def load_data():
    """
    Loads all data files into memory. This function is called once when the app starts.
    """
    global products_df, orders_df, faq_content
    try:
        products_df = pd.read_csv(PRODUCTS_CSV_PATH)
        orders_df = pd.read_csv(ORDERS_CSV_PATH)
        with open(FAQ_TXT_PATH, 'r') as f:
            faq_content = f.read()
        
        logger.info("Successfully loaded products.csv, orders.csv, and faq.txt")
        logger.info(f"Loaded {len(products_df)} products and {len(orders_df)} orders.")
        
    except FileNotFoundError as e:
        logger.error(f"Error loading data file: {e}. Make sure the 'data' directory and files exist.")
        exit()
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading data: {e}")
        exit()

def get_products():
    """Returns the loaded products DataFrame."""
    return products_df

def get_orders():
    """Returns the loaded orders DataFrame."""
    return orders_df

def get_faq_content():
    """Returns the loaded FAQ content as a string."""
    return faq_content

# --- NEW: Function to update the orders DataFrame and save to CSV ---
def update_orders_dataframe(updated_df: pd.DataFrame):
    """
    Updates the global orders_df and persists the changes to orders.csv.
    This function is now the single point of truth for any order modification.
    """
    global orders_df
    with csv_lock:
        try:
            orders_df = updated_df
            orders_df.to_csv(ORDERS_CSV_PATH, index=False)
            logger.info(f"Successfully updated and saved orders.csv. Total orders: {len(orders_df)}")
            return True
        except Exception as e:
            logger.error(f"Failed to save updated orders to CSV: {e}")
            # In a real app, you might want to try reverting the change in memory
            return False
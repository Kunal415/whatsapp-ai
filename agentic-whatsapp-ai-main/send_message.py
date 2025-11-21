import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
RECIPIENT_WAID = os.getenv('RECIPIENT_WAID')
WHATSAPP_API_VERSION = os.getenv('WHATSAPP_API_VERSION')

# Returns the JSON object for a text message
def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

# Sends a message to the WhatsApp API
def send_message(data):
    # Set up the headers for the API request
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
    # Construct the API URL
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{PHONE_NUMBER_ID}/messages"
    # Send the POST request
    response = requests.post(url, data=data, headers=headers)
    
    # Check if the request was successful
    if response.status_code == 200:
        print("Status:", response.status_code)
        print("Content-type:", response.headers["content-type"])
        print("Body:", response.text)
        return response
    else:
        # Print error details if the request failed
        print(response.status_code)
        print(response.text)
        return response
# Create the data payload for the message
data = get_text_message_input(
    recipient=RECIPIENT_WAID, text="Hello, this is a test message."
)
# Send the message using the send_message function
response = send_message(data)
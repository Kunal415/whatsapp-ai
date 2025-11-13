# agentic-whatsapp-ai

Codebase is organized as follows:
```
└── ecommerce_bot/
    ├── app.py             # The main Flask app, our central conductor.
    ├── data_loader.py     # Handles loading and saving our CSV data.
    ├── handlers.py        # Contains the logic for each specific intent.
    ├── requirements.txt   # Lists all the Python packages we need.
    ├── services.py        # Manages external services (WhatsApp API, Hyperstack AI).
    └── data/
        ├── faq.txt        # Our knowledge base for customer support.
        ├── orders.csv     # A database of customer orders.
        └── products.csv   # Our product catalog.
```
To get started with the Agentic WhatsApp AI project, follow these steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/FareedKhan-dev/agentic-whatsapp-ai.git
    cd agentic-whatsapp-ai
    ```

2. **Install Dependencies**:
   Make sure you have Python installed. Then, install the required packages:
   ```bash
    pip install -r requirements.txt
    ```

3. **Set Up Environment Variables**:
   Make sure to set up your environment variables for [Hypestack AI Studio key](https://www.hyperstack.cloud/) and Meta developer token.

4. **Run the Application**:
   You can start the application using:
   ```bash
    python app.py
   ```


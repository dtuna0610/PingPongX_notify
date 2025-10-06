import os
import logging
import requests
import json
import schedule
import time
from datetime import datetime, timedelta
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PINGPONGX_APP_ID = os.getenv('PINGPONGX_APP_ID')
PINGPONGX_APP_SECRET = os.getenv('PINGPONGX_APP_SECRET')
PINGPONGX_BASE_URL = 'https://sandbox-gateway.pingpongx.com'

class PingPongXAPI:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.get_access_token()

    def get_access_token(self):
        """Get access token from PingPongX API"""
        url = f"{PINGPONGX_BASE_URL}/v2/token/get"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        data = {
            "app_id": PINGPONGX_APP_ID,
            "app_secret": PINGPONGX_APP_SECRET,
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            # Log response details for debugging
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Headers: {response.headers}")
            logger.info(f"API Response Content: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            # Handle different response structures
            if result.get('code') == 0 and 'data' in result and 'access_token' in result['data']:
                self.access_token = result['data']['access_token']
            else:
                logger.error(f"Unexpected response format: {result}")
                raise ValueError("Invalid response format from authentication API")
                
            # Set token expiry to 1 hour 45 minutes to refresh before the 2-hour limit
            self.token_expiry = datetime.now() + timedelta(minutes=105)
            logger.info("Successfully obtained new access token")
            
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise

    def check_token(self):
        """Check if token needs refresh"""
        if not self.access_token or not self.token_expiry or datetime.now() >= self.token_expiry:
            self.get_access_token()

    def get_headers(self):
        """Get headers with current access token"""
        self.check_token()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def get_cards(self):
        """Get all cards information"""
        url = f"{PINGPONGX_BASE_URL}/v2/virtual/cards"
        response = requests.get(url, headers=self.get_headers())
        return response.json()

    def get_card_balance(self, card_id):
        """Get balance for specific card"""
        url = f"{PINGPONGX_BASE_URL}/v2/virtual/cards/{card_id}/balance"
        response = requests.get(url, headers=self.get_headers())
        return response.json()

    def get_card_transactions(self, card_id):
        """Get transactions for specific card"""
        url = f"{PINGPONGX_BASE_URL}/v2/virtual/cards/{card_id}/transactions"
        response = requests.get(url, headers=self.get_headers())
        return response.json()

    def test_connection(self):
        """Test connection to PingPongX API"""
        try:
            self.get_access_token()
            return True, "Successfully connected to PingPongX API"
        except Exception as e:
            return False, f"Failed to connect to PingPongX API: {str(e)}"

class TelegramBot:
    def __init__(self):
        self.api = PingPongXAPI()
        self.subscribed_chats = set()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        chat_id = update.effective_chat.id
        self.subscribed_chats.add(chat_id)
        welcome_message = (
            "Welcome to PingPongX Monitor Bot!\n\n"
            "Available commands:\n"
            "/start - Start the bot and subscribe to updates\n"
            "/cards - Get all cards information\n"
            "/balance - Get balance for all cards\n"
            "/transactions - Get recent transactions for all cards\n"
            "/test - Test all connections and endpoints\n"
            "/stop - Stop receiving updates"
        )
        await context.bot.send_message(chat_id=chat_id, text=welcome_message)

    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop command handler"""
        chat_id = update.effective_chat.id
        self.subscribed_chats.discard(chat_id)
        await context.bot.send_message(chat_id=chat_id, text="You've unsubscribed from updates.")

    async def get_cards_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for cards command"""
        try:
            cards_data = self.api.get_cards()
            if not cards_data.get('data'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No cards found."
                )
                return

            for card in cards_data['data']:
                message = (
                    f"🎴 Card Details:\n"
                    f"Card ID: {card.get('cardId', 'N/A')}\n"
                    f"Status: {card.get('status', 'N/A')}\n"
                    f"Card Number: {card.get('cardNumber', 'N/A')}\n"
                    f"Expiry: {card.get('expiryDate', 'N/A')}\n"
                    f"Currency: {card.get('currency', 'N/A')}"
                )
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message
                )
        except Exception as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Error fetching cards: {str(e)}"
            )

    async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for balance command"""
        try:
            cards_data = self.api.get_cards()
            if not cards_data.get('data'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No cards found."
                )
                return

            for card in cards_data['data']:
                card_id = card['cardId']
                balance_data = self.api.get_card_balance(card_id)
                
                if balance_data.get('data'):
                    balance = balance_data['data']
                    message = (
                        f"💰 Balance for Card {card_id}:\n"
                        f"Available Balance: {balance.get('availableBalance', 'N/A')}\n"
                        f"Currency: {balance.get('currency', 'N/A')}\n"
                        f"Last Updated: {balance.get('updateTime', 'N/A')}"
                    )
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message
                    )
        except Exception as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Error fetching balances: {str(e)}"
            )

    async def get_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for transactions command"""
        try:
            cards_data = self.api.get_cards()
            if not cards_data.get('data'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No cards found."
                )
                return

            for card in cards_data['data']:
                card_id = card['cardId']
                transactions_data = self.api.get_card_transactions(card_id)
                
                if transactions_data.get('data'):
                    message = f"📊 Recent Transactions for Card {card_id}:\n\n"
                    
                    for tx in transactions_data['data']:
                        message += (
                            f"Amount: {tx.get('amount', 'N/A')} {tx.get('currency', 'N/A')}\n"
                            f"Type: {tx.get('type', 'N/A')}\n"
                            f"Status: {tx.get('status', 'N/A')}\n"
                            f"Date: {tx.get('transactionTime', 'N/A')}\n"
                            f"Description: {tx.get('description', 'N/A')}\n\n"
                        )
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message
                    )
        except Exception as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Error fetching transactions: {str(e)}"
            )

    async def test_connections(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test all connections and API endpoints"""
        chat_id = update.effective_chat.id
        
        # Test message
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 Testing connections..."
        )

        # Test Telegram connection
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Telegram Bot API connection successful"
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Telegram Bot API connection failed: {str(e)}"
            )

        # Test PingPongX connection
        success, message = self.api.test_connection()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{'✅' if success else '❌'} {message}"
        )

        # Test card endpoints
        try:
            cards_data = self.api.get_cards()
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Successfully retrieved cards data"
            )

            if cards_data.get('data') and len(cards_data['data']) > 0:
                card_id = cards_data['data'][0]['cardId']
                # Test balance endpoint
                self.api.get_card_balance(card_id)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ Successfully tested balance endpoint"
                )

                # Test transactions endpoint
                self.api.get_card_transactions(card_id)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ Successfully tested transactions endpoint"
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ No cards found to test balance and transaction endpoints"
                )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error testing card endpoints: {str(e)}"
            )

    async def periodic_update(self, context: ContextTypes.DEFAULT_TYPE):
        """Send periodic updates to all subscribed chats"""
        for chat_id in self.subscribed_chats:
            try:
                # Update cards info
                cards_data = self.api.get_cards()
                if cards_data.get('data'):
                    for card in cards_data['data']:
                        card_id = card['cardId']
                        
                        # Get balance
                        balance_data = self.api.get_card_balance(card_id)
                        if balance_data.get('data'):
                            balance = balance_data['data']
                            message = (
                                f"🔄 Periodic Update\n"
                                f"Card: {card_id}\n"
                                f"Balance: {balance.get('availableBalance', 'N/A')} {balance.get('currency', 'N/A')}\n"
                                f"Status: {card.get('status', 'N/A')}"
                            )
                            await context.bot.send_message(chat_id=chat_id, text=message)
                        
                        # Get recent transactions
                        transactions_data = self.api.get_card_transactions(card_id)
                        if transactions_data.get('data'):
                            recent_tx = transactions_data['data'][0]  # Most recent transaction
                            message = (
                                f"Latest Transaction:\n"
                                f"Amount: {recent_tx.get('amount', 'N/A')} {recent_tx.get('currency', 'N/A')}\n"
                                f"Type: {recent_tx.get('type', 'N/A')}\n"
                                f"Status: {recent_tx.get('status', 'N/A')}\n"
                                f"Date: {recent_tx.get('transactionTime', 'N/A')}"
                            )
                            await context.bot.send_message(chat_id=chat_id, text=message)
                            
            except Exception as e:
                logger.error(f"Error in periodic update for chat {chat_id}: {str(e)}")

def main():
    """Main function to run the bot"""
    # Initialize bot
    bot = TelegramBot()
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(CommandHandler("cards", bot.get_cards_info))
    application.add_handler(CommandHandler("balance", bot.get_balances))
    application.add_handler(CommandHandler("transactions", bot.get_transactions))
    application.add_handler(CommandHandler("test", bot.test_connections))

    # Set up periodic updates (every 5 minutes)
    application.job_queue.run_repeating(bot.periodic_update, interval=300)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)

if __name__ == "__main__":
    main()
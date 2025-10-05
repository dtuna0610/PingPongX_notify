import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Lấy từ biến môi trường
TELEGRAM_BOT_TOKEN = os.getenv('8344245904:AAH-AAYhWC_52h8kU5j9T1GLz9p9d4wXZ9I')
TELEGRAM_CHAT_ID = os.getenv('7338193028')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'E894016C2D254F1986D6E9A1')

def send_telegram_message(message):
    """Gửi tin nhắn đến Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        print(f"Lỗi khi gửi Telegram: {e}")
        return None

@app.route('/')
def home():
    return "PingPong Telegram Notifier đang chạy! ✅"

@app.route('/webhook/pingpong', methods=['POST'])
def pingpong_webhook():
    """Nhận webhook từ PingPong"""
    try:
        # Kiểm tra secret key (nếu PingPong hỗ trợ)
        auth_header = request.headers.get('Authorization', '')
        if WEBHOOK_SECRET not in auth_header and request.args.get('secret') != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Lấy dữ liệu từ webhook
        data = request.json
        
        # Tạo tin nhắn thông báo
        message = format_transaction_message(data)
        
        # Gửi đến Telegram
        send_telegram_message(message)
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": str(e)}), 500

def format_transaction_message(data):
    """Định dạng tin nhắn giao dịch"""
    # Điều chỉnh theo cấu trúc dữ liệu thực tế từ PingPong
    message = "🔔 <b>THÔNG BÁO GIAO DỊCH PINGPONG</b>\n\n"
    
    # Kiểm tra các trường phổ biến
    if 'transaction_type' in data or 'type' in data:
        trans_type = data.get('transaction_type') or data.get('type')
        message += f"📋 Loại: <b>{trans_type}</b>\n"
    
    if 'amount' in data:
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        message += f"💰 Số tiền: <b>{amount} {currency}</b>\n"
    
    if 'balance' in data or 'new_balance' in data:
        balance = data.get('balance') or data.get('new_balance')
        message += f"💳 Số dư: <b>{balance}</b>\n"
    
    if 'status' in data:
        status = data.get('status')
        message += f"✅ Trạng thái: <b>{status}</b>\n"
    
    if 'description' in data or 'memo' in data:
        desc = data.get('description') or data.get('memo')
        message += f"📝 Mô tả: {desc}\n"
    
    if 'transaction_id' in data or 'id' in data:
        trans_id = data.get('transaction_id') or data.get('id')
        message += f"🔖 Mã GD: <code>{trans_id}</code>\n"
    
    # Thời gian
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    message += f"\n⏰ Thời gian: {timestamp}"
    
    # Nếu không có dữ liệu được parse, hiển thị raw data
    if message.count('\n') <= 3:
        message += f"\n\n📦 Dữ liệu: <code>{str(data)}</code>"
    
    return message

@app.route('/test', methods=['GET'])
def test_notification():
    """Endpoint để test gửi thông báo"""
    test_data = {
        "transaction_type": "Nhận tiền",
        "amount": "100.00",
        "currency": "USD",
        "balance": "1,234.56 USD",
        "status": "Thành công",
        "description": "Test notification",
        "transaction_id": "TEST123456"
    }
    
    message = format_transaction_message(test_data)
    result = send_telegram_message(message)
    
    if result:
        return jsonify({"status": "success", "message": "Đã gửi thông báo test!"}), 200
    else:
        return jsonify({"status": "error", "message": "Không thể gửi thông báo"}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
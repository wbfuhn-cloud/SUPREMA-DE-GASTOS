import sys
import os
import time

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config_manager import ConfigManager
from recommendation_learner import get_learner

def mock_process_single_ticker(ticker):
    return {
        'Ticker': ticker,
        'Price': 150.50,
        'Score': 85.0, # Buy score
        'Viabilidad': '🟢 EXCELENTE',
        'Sector': 'Technology',
        'RSI': 45.0,
        'Nota': 'Fake buy trigger para pruebas'
    }

def test_alert_loop():
    print("Testing live alert loop simulation...")
    config_mgr = ConfigManager()
    cfg = config_mgr.config.get('live_alerts', {})
    print("Config:", cfg)
    
    learner = get_learner()
    print("Learner initialized")
    
    ticker = "DJT" # Test with Trump stock
    r = mock_process_single_ticker(ticker)
    
    score = r.get('Score', 0)
    price = r.get('Price', 0.0)
    viabilidad = r.get('Viabilidad', '')
    
    # Mock high confidence for testing
    ai_confidence = 0.95
    min_confidence = cfg.get('min_confidence', 0.8)
    
    action = None
    reason = ""
    if score >= 75 and ai_confidence >= min_confidence:
        action = "buy"
        reason = f"Score alto ({score}) y confianza AI ({ai_confidence:.2f}). {r.get('Nota', '')}"
        
    print(f"Evaluated Action: {action}, Reason: {reason}")
    
    if action and not learner.has_recent_alert(ticker, action, hours=0.001): # very short cooldown for test
        print("Sending telegram alert...")
        import requests
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root_dir, '.env'))
        
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not chat_id:
            try:
                with open(os.path.join(root_dir, "data", "chat_id.txt"), "r") as f:
                    chat_id = f.read().strip()
            except Exception as e:
                print("Could not read chat_id.txt", e)
                
        print(f"Token: {token[:5]}..., Chat_ID: {chat_id}")
        if token and chat_id:
            emoji = "🟢 COMPRAR" if action == "buy" else "🔴 VENDER"
            msg = f"⚡ *ALERTA EN VIVO DE PRUEBA: {ticker}* {emoji}\n\n"
            msg += f"*Precio:* ${price}\n"
            msg += f"*Score:* {score} ({viabilidad})\n"
            msg += f"*Confianza IA:* {ai_confidence*100:.1f}%\n"
            msg += f"*Razón:* {reason}\n"
            
            res = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
            print("Telegram Response:", res.status_code, res.text)
            if res.status_code == 200:
                learner.record_live_alert(ticker, action, price, ai_confidence, reason)
                print("Alert recorded successfully in DB.")
        else:
            print("No telegram credentials.")
    else:
        print("No action or already alerted.")

if __name__ == '__main__':
    test_alert_loop()

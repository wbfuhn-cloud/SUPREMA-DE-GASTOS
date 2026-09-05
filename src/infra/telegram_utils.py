import os
import logging
import requests as http_requests

logger = logging.getLogger(__name__)


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to Telegram. Unified function for the entire project."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = _get_chat_id()

    if not token or not chat_id:
        logger.warning("Telegram not configured (missing token or chat_id)")
        return False

    try:
        resp = http_requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def _get_chat_id() -> str:
    """Get the chat_id from .env or persistent file."""
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        try:
            chat_id_file = "chat_id.txt"
            if not os.path.exists(chat_id_file):
                chat_id_file = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data", "chat_id.txt"
                )
            if os.path.exists(chat_id_file):
                with open(chat_id_file, "r") as f:
                    chat_id = f.read().strip()
        except Exception:
            pass
    return chat_id

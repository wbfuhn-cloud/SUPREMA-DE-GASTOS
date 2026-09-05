import datetime
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.bot import ExpenseBot

# Mock classes for Telegram objects (Updating for Text Messages)
class MockTextUpdate:
    def __init__(self, text, chat_id=123):
        self.effective_chat = MagicMock()
        self.effective_chat.id = chat_id
        self.message = MagicMock()
        self.message.text = text
        self.message.from_user = MagicMock()
        self.message.from_user.first_name = "TestUser"

class MockContext:
    def __init__(self):
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()

@pytest.mark.asyncio
async def test_bot_text_edit():
    # Setup
    bot = ExpenseBot("fake_token", "fake_key")
    chat_id = 123
    
    # 1. State: Pending expense exists
    bot.pending_expenses[chat_id] = {
        "data": {
            "date": "2026-01-01", 
            "merchant": "Old Store", 
            "total": 100, 
            "details": "Old Details",
            "category": "Otros",
            "week": 1,
            "payment_method": "Tarjeta"
        },
        "ts": datetime.datetime.now().timestamp()
    }
    
    context = MockContext()
    
    # 2. Test: "Cambia detalles por: cafe grande"
    update_1 = MockTextUpdate("Cambia detalles por: cafe grande", chat_id)
    await bot.handle_text(update_1, context)
    
    assert bot.pending_expenses[chat_id]['data']['details'] == "cafe grande"
    assert context.bot.send_message.call_count >= 1 # Ack + Confirmation
    
    # 3. Test: "monto: 500"
    update_2 = MockTextUpdate("monto: 500", chat_id)
    await bot.handle_text(update_2, context)
    
    assert str(bot.pending_expenses[chat_id]['data']['total']) == "500"
    
    # 4. Test: "cambiar fecha por 2026-02-15" (Should trigger recalc)
    update_3 = MockTextUpdate("cambiar fecha por 2026-02-15", chat_id)
    await bot.handle_text(update_3, context)
    
    assert bot.pending_expenses[chat_id]['data']['date'] == "2026-02-15"
    assert bot.pending_expenses[chat_id]['data']['month'] == "FEBRERO" # Recalculated
    
    print("[OK] Text Edit Tests Passed")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_bot_text_edit())
    except ImportError:
        print("Pytest/Asyncio issues, refer to pytest run")

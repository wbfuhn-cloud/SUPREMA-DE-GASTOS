from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.bot import ExpenseBot
import datetime

# Mock classes for Telegram objects
class MockUpdate:
    def __init__(self, callback_data=None, chat_id=123):
        self.effective_chat = MagicMock()
        self.effective_chat.id = chat_id
        if callback_data:
            self.callback_query = MagicMock()
            self.callback_query.data = callback_data
            self.callback_query.message = MagicMock()
            self.callback_query.answer = AsyncMock()
            self.callback_query.edit_message_text = AsyncMock()
            self.callback_query.delete_message = AsyncMock()
        else:
            self.message = MagicMock()
            self.message.from_user = MagicMock()
            self.message.from_user.first_name = "TestUser"

class MockContext:
    def __init__(self):
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.delete_message = AsyncMock()

@pytest.mark.asyncio
async def test_bot_confirmation_flow():
    # Setup
    bot = ExpenseBot("fake_token", "fake_key")
    bot.excel = MagicMock()
    bot.excel.add_expense.return_value = (True, "Saved")
    
    chat_id = 123
    test_data = {"date": "2026-01-01", "total": 100, "category": "Otros", "merchant": "Test", "details": "Test"}
    
    # 1. Simulate finding data (Analyst mocked out or bypassed by injecting state directly)
    bot.pending_expenses[chat_id] = test_data
    
    # 2. Test "Change Category"
    update_change = MockUpdate(callback_data="change_category", chat_id=chat_id)
    context = MockContext()
    await bot.handle_callback(update_change, context)
    
    # Verify it showed category menu
    assert update_change.callback_query.edit_message_text.called
    args, kwargs = update_change.callback_query.edit_message_text.call_args
    assert "Selecciona la nueva categoría" in kwargs['text']
    
    # 3. Test "Set Category"
    update_set = MockUpdate(callback_data="set_cat_Alimentos", chat_id=chat_id)
    await bot.handle_callback(update_set, context)
    
    # Verify state updated
    assert bot.pending_expenses[chat_id]['category'] == "Alimentos"
    # Verify it tried to show confirmation again
    assert context.bot.send_message.called
    
    # 4. Test "Confirm"
    # Capture data before it's deleted
    data_to_save = bot.pending_expenses[chat_id]
    
    update_confirm = MockUpdate(callback_data="confirm", chat_id=chat_id)
    await bot.handle_callback(update_confirm, context)
    
    # Verify excel called with the captured data
    bot.excel.add_expense.assert_called_with(data_to_save)
    
    # Check that it was deleted from pending
    assert chat_id not in bot.pending_expenses
    assert update_confirm.callback_query.edit_message_text.called
    args, kwargs = update_confirm.callback_query.edit_message_text.call_args
    assert "Gasto Guardado" in kwargs['text']
    
    print("[OK] Test passed!")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_bot_confirmation_flow())
    except ImportError:
        # If pytest not installed, run basic check
        print("Pytest not found, manual run...") 

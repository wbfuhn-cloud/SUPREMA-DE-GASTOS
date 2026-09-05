import pytest
from unittest.mock import AsyncMock, MagicMock
from src.bot import ExpenseBot

@pytest.mark.asyncio
async def test_bot_type_setting_loan_and_debt():
    # Setup bot with mock excel (no actual file operations)
    bot = ExpenseBot('fake_token', 'fake_key')
    bot.excel = MagicMock()
    chat_id = 123
    # Initialize pending expense with minimal data
    bot.pending_expenses[chat_id] = {
        'date': '2026-01-01',
        'total': 100,
        'category': 'Otros',
        'merchant': 'Test',
        'details': 'Detalle',
        'type': 'Normal'
    }
    # Mock context
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()

    # Simulate callback to set type to loan
    update_loan = MagicMock()
    update_loan.effective_chat.id = chat_id
    update_loan.callback_query = MagicMock()
    update_loan.callback_query.data = 'set_type_loan'
    update_loan.callback_query.answer = AsyncMock()
    update_loan.callback_query.edit_message_text = AsyncMock()

    await bot.handle_callback(update_loan, context)
    assert bot.pending_expenses[chat_id]['type'] == 'Prestamo'
    # Ensure confirmation message was sent again
    assert update_loan.callback_query.edit_message_text.called

    # Simulate callback to set type to debt
    update_debt = MagicMock()
    update_debt.effective_chat.id = chat_id
    update_debt.callback_query = MagicMock()
    update_debt.callback_query.data = 'set_type_debt'
    update_debt.callback_query.answer = AsyncMock()
    update_debt.callback_query.edit_message_text = AsyncMock()

    await bot.handle_callback(update_debt, context)
    assert bot.pending_expenses[chat_id]['type'] == 'Deuda'
    assert update_debt.callback_query.edit_message_text.called

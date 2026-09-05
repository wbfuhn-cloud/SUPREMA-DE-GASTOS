from src.config import Config
from src.bot import ExpenseBot
from src.analyzer import AnalysisService

print("Testing imports...")
assert Config.TELEGRAM_TOKEN is not None
assert Config.GOOGLE_API_KEY is not None

try:
    bot = ExpenseBot("TEST_TOKEN", "TEST_KEY")
    print("ExpenseBot initialized successfully.")
except Exception as e:
    print(f"Failed to init bot: {e}")
    exit(1)
    
print("[OK] Architecture seems valid.")

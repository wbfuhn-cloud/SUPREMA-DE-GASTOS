import sqlite3
import os
import sys

# Add project root to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from src.config import Config

def migrate():
    db_path = Config.DATABASE_PATH
    print(f"Migrating database at: {db_path}")
    
    if not os.path.exists(db_path):
        print("Database file not found. Nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if unit column exists
        cursor.execute("PRAGMA table_info(expenses)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'unit' not in columns:
            print("Column 'unit' not found. Already migrated?")
            return

        print("Removing 'unit' column from 'expenses' table...")
        
        # SQLite doesn't support DROP COLUMN in older versions (< 3.35.0)
        # Safe way to do it: Recreate the table
        
        # 1. Get current schema for recreation but without 'unit'
        # We'll use the one from schema.sql later or just manually define it
        
        cursor.execute("BEGIN TRANSACTION")
        
        # 2. Create a new table without 'unit'
        cursor.execute("""
            CREATE TABLE expenses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL,
                month TEXT NOT NULL,
                week INTEGER NOT NULL,
                date TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                category TEXT NOT NULL,
                merchant TEXT NOT NULL,
                subcategory TEXT,
                details TEXT,
                total REAL NOT NULL,
                type TEXT NOT NULL DEFAULT 'Normal',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Copy data from old table to new table
        cursor.execute("""
            INSERT INTO expenses_new (id, day, month, week, date, payment_method, category, merchant, subcategory, details, total, type, status, created_at, updated_at)
            SELECT id, day, month, week, date, payment_method, category, merchant, subcategory, details, total, type, status, created_at, updated_at
            FROM expenses
        """)
        
        # 4. Drop old table
        cursor.execute("DROP TABLE expenses")
        
        # 5. Rename new table
        cursor.execute("ALTER TABLE expenses_new RENAME TO expenses")
        
        # 6. Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_type ON expenses(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_month ON expenses(month)")
        
        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

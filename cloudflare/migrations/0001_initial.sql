CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  merchant TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'OTRO',
  payment_method TEXT NOT NULL DEFAULT 'EFECTIVO',
  details TEXT NOT NULL DEFAULT '',
  total REAL NOT NULL CHECK (total >= 0),
  type TEXT NOT NULL DEFAULT 'Normal',
  status TEXT NOT NULL DEFAULT 'pending',
  source TEXT NOT NULL DEFAULT 'web',
  source_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status);

CREATE TABLE IF NOT EXISTS email_log (
  message_id TEXT PRIMARY KEY,
  subject TEXT,
  received_at TEXT,
  expense_id INTEGER,
  amount REAL,
  merchant TEXT,
  status TEXT NOT NULL,
  processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

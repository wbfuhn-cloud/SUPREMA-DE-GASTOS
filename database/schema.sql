-- Asistente Financiero - Database Schema
-- SQLite Database for Financial Tracking

-- Main expenses table
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    month TEXT NOT NULL,
    week INTEGER NOT NULL,
    date TEXT NOT NULL,  -- Format: YYYY-MM-DD
    payment_method TEXT NOT NULL,
    category TEXT NOT NULL,
    merchant TEXT NOT NULL,
    subcategory TEXT,
    details TEXT,
    total REAL NOT NULL,
    type TEXT NOT NULL DEFAULT 'Normal',  -- 'Normal', 'Prestamo', 'Deuda'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'paid'
    project TEXT,  -- Label for grouping (e.g., sheet name or project ID)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Categories lookup table (for normalization and analytics)
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payment methods lookup table
CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date DESC);
CREATE INDEX IF NOT EXISTS idx_expenses_type ON expenses(type);
CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_month ON expenses(month);
CREATE INDEX IF NOT EXISTS idx_expenses_merchant ON expenses(merchant);

-- Trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_expenses_timestamp 
AFTER UPDATE ON expenses
BEGIN
    UPDATE expenses SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Insert default categories
INSERT OR IGNORE INTO categories (name) VALUES 
    ('COMIDA'),
    ('TRANSPORTE'),
    ('HOGAR'),
    ('ROPA'),
    ('SALUD'),
    ('ENTRETENIMIENTO'),
    ('SERVICIOS'),
    ('EDUCACION'),
    ('OTRO');

-- Insert default payment methods
INSERT OR IGNORE INTO payment_methods (name) VALUES 
    ('TARJETA'),
    ('EFECTIVO'),
    ('TRANSFERENCIA');

-- Budgets table for monthly spending limits
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT UNIQUE NOT NULL,
    monthly_limit REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to update budgets timestamp
CREATE TRIGGER IF NOT EXISTS update_budgets_timestamp 
AFTER UPDATE ON budgets
BEGIN
    UPDATE budgets SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;


-- App settings table (Key-Value pairs)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to update app_settings timestamp
CREATE TRIGGER IF NOT EXISTS update_app_settings_timestamp 
AFTER UPDATE ON app_settings
BEGIN
    UPDATE app_settings SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
END;

-- ================================================================
-- Email log table: evitar procesar el mismo correo dos veces
-- ================================================================
CREATE TABLE IF NOT EXISTS email_log (
    message_id  TEXT PRIMARY KEY,
    subject     TEXT,
    received_at TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expense_id  INTEGER,
    amount      REAL,
    merchant    TEXT,
    status      TEXT  -- 'imported', 'skipped', 'error'
);

CREATE INDEX IF NOT EXISTS idx_email_log_processed ON email_log(processed_at);

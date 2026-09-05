-- Paginación eficiente por fecha+id
CREATE INDEX IF NOT EXISTS idx_expenses_date_id ON expenses(date DESC, id DESC);

-- Filtro de deudas/préstamos pendientes (summary endpoint)
CREATE INDEX IF NOT EXISTS idx_expenses_type_status ON expenses(type, status);

-- Agregación por categoría (categories endpoint)
CREATE INDEX IF NOT EXISTS idx_expenses_category_total ON expenses(category, total);

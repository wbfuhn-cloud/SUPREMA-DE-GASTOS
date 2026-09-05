-- Los gastos importados por correo deben revisarse antes de confirmarlos.
UPDATE expenses
SET status = 'unconfirmed', source = 'email'
WHERE UPPER(COALESCE(details, '')) LIKE 'AUTO-BAZ:%';

-- Los gastos normales historicos se consideran pagados.
UPDATE expenses
SET status = 'paid', type = 'Normal'
WHERE source = 'legacy'
  AND LOWER(type) = 'normal'
  AND LOWER(status) IN ('pending', 'completed');

-- Normalizar los valores restantes sin cambiar deudas o prestamos pendientes.
UPDATE expenses
SET status = LOWER(status)
WHERE status IN ('PENDING', 'COMPLETED');

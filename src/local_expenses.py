"""Lectura del respaldo local: nunca crea, migra o modifica la base."""
import sqlite3
from contextlib import closing
from pathlib import Path


def read_local_expenses(path, year=None, limit=None):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('No existe una copia local de los gastos.')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        count, last_date = db.execute('SELECT COUNT(*), MAX(date) FROM expenses').fetchone()
        years = [row[0] for row in db.execute("SELECT DISTINCT CAST(strftime('%Y',date) AS INTEGER) y FROM expenses WHERE y IS NOT NULL ORDER BY y DESC")]
        categories = [row[0] for row in db.execute("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL ORDER BY category")]
        sql, params = 'SELECT * FROM expenses', []
        if year is not None:
            sql += ' WHERE date LIKE ?'
            params.append(f'{year}-%')
        sql += ' ORDER BY date DESC, id DESC'
        if limit is not None:
            sql += ' LIMIT ?'
            params.append(limit)
        rows = [dict(row) for row in db.execute(sql, params)]
    return {'expenses': rows, 'count': count, 'last_date': last_date,
            'years': years, 'categories': categories}

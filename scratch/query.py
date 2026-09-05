import sqlite3

conn = sqlite3.connect('database/expenses.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT id, date, total, status FROM expenses WHERE id <= 765 ORDER BY id DESC LIMIT 20;")
for row in cursor.fetchall():
    print(dict(row))

conn.close()

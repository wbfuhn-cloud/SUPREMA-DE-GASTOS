import os
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import threading
import logging
import sqlite3

try:
    import httpx
except ImportError:
    httpx = None


class BaseDatabaseManager:
    """Clase base para asegurar la compatibilidad de métodos."""
    storage_mode = "unknown"
    def add_expense(self, data: Dict) -> Tuple[bool, str]: pass
    def update_expense(self, expense_id: int, data: Dict) -> Tuple[bool, str]: pass
    def delete_expense(self, expense_id: int) -> Tuple[bool, str]: pass
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]: pass
    def set_setting(self, key: str, value: str) -> Tuple[bool, str]: pass
    def get_setting_status(self, key: str) -> Tuple[bool, Optional[str]]:
        try:
            return True, self.get_setting(key)
        except Exception:
            return False, None

SPANISH_MONTHS = [
    'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
    'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'
]

def _normalize_expense_data(data: Dict) -> Dict:
    norm = dict(data)
    date_str = norm.get('date')
    if date_str:
        try:
            dt = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
            if not norm.get('day') or not str(norm.get('day')).isdigit():
                norm['day'] = dt.day
            if not norm.get('month') or str(norm.get('month')).upper() in ('', 'GENERIC', 'UNKNOWN'):
                norm['month'] = SPANISH_MONTHS[dt.month - 1]
            if not norm.get('week') or not str(norm.get('week')).isdigit() or int(norm.get('week')) == 0:
                norm['week'] = dt.isocalendar()[1]
        except Exception:
            pass
    return norm
    def get_dashboard_summary(self) -> dict: pass
    def get_available_years(self) -> List[int]: pass
    def get_expenses_by_year(self, year: int, include_paid: bool = True) -> List[Dict]: pass
    def get_all_expenses(self, include_paid: bool = True) -> List[Dict]: pass
    def get_expenses(self, limit: int = 200, offset: int = 0, include_paid: bool = True) -> List[Dict]: pass
    def get_categories(self) -> List[str]: pass
    def get_budgets(self) -> List[Dict]: pass
    def get_monthly_spending_by_category(self, month: str, year: int) -> Dict[str, float]: pass
    def get_pending_debts(self) -> List[Dict]: pass
    def get_weekly_expenses(self, start_date: str, end_date: str) -> List[Dict]: pass
    def get_category_stats(self, category: str) -> Dict: pass
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]: pass
    def set_setting(self, key: str, value: str) -> Tuple[bool, str]: pass
    def get_most_frequent_category(self, merchant: str) -> Tuple[Optional[str], Optional[str]]: pass
    def add_budget(self, category: str, limit: float) -> Tuple[bool, str]: pass
    def get_all_settings(self) -> Dict[str, str]: pass
    def ensure_email_log_table(self): pass
    def is_email_processed(self, message_id: str) -> bool: pass
    def log_email(self, message_id: str, subject: str, received_at: str, expense_id, amount, merchant, status): pass

class LocalDatabaseManager(BaseDatabaseManager):
    """Implementación original con SQLite local."""
    storage_mode = "local"
    _PROTECTED_CATEGORIES = frozenset({"GENERAL", "ADMIN", "MANTENIMIENTO"})

    def __init__(self, db_path: Optional[str] = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.path.join(project_root, 'database')
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path or os.path.join(db_dir, 'expenses.db')

        self._cache_data: List[Dict] = []
        self._cache_key = None
        self._cache_last_check: float = 0.0
        self._cache_ttl: float = 8.0
        self._write_lock = threading.RLock()
        self._cache_lock = threading.RLock()
        self._local = threading.local()

        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn = conn
        return conn

    def _initialize_database(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        schema_path = os.path.join(base_dir, 'database', 'schema.sql')
        conn = self._get_connection()
        try:
            if os.path.exists(schema_path):
                with open(schema_path, encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.commit()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(expenses)")
            columns = [row['name'] for row in cursor.fetchall()]
            if 'subcategory' not in columns:
                cursor.execute("ALTER TABLE expenses ADD COLUMN subcategory TEXT")
                conn.commit()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'")
            if not cursor.fetchone():
                cursor.execute('''CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
                conn.commit()
        except sqlite3.Error as e:
            self._logger.error(f"Error inicializando DB: {e}")

    # (Aquí se copian todos los métodos de SQLite que estaban originalmente, por brevedad los resumiré. 
    # Mantenemos las implementaciones principales intactas).
    def add_expense(self, data: Dict) -> Tuple[bool, str]:
        data = _normalize_expense_data(data)
        with self._write_lock:
            conn = self._get_connection()
            try:
                conn.execute('''
                    INSERT INTO expenses (day, month, week, date, payment_method, category, merchant, subcategory, details, total, type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(data.get('day', 1)) if str(data.get('day', '')).isdigit() else 1,
                    str(data.get('month', '')).upper(),
                    int(data.get('week', 0)) if str(data.get('week', '')).isdigit() else 0,
                    data.get('date'), str(data.get('payment_method', 'TARJETA')).upper(),
                    str(data.get('category', 'OTRO')).upper(), str(data.get('merchant', '')).upper(),
                    str(data.get('subcategory', '')).upper(), str(data.get('details', '')).upper(),
                    float(data.get('total', 0)), data.get('type', 'Normal'), data.get('status', 'pending')
                ))
                conn.commit()
                self._cache_last_check = 0.0
                last_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                return True, f"Gasto guardado (ID: {last_id})"
            except sqlite3.Error as e:
                return False, f"Error al guardar: {e}"

    def update_expense(self, expense_id: int, data: Dict) -> Tuple[bool, str]:
        with self._write_lock:
            conn = self._get_connection()
            try:
                fields = {k: v for k, v in data.items() if k != 'id'}
                if not fields: return False, "No hay campos para actualizar"
                set_clause = ', '.join(f"{k} = ?" for k in fields)
                values = list(fields.values()) + [expense_id]
                conn.execute(f"UPDATE expenses SET {set_clause} WHERE id = ?", values)
                conn.commit()
                self._cache_last_check = 0.0
                return True, f"Gasto {expense_id} actualizado"
            except sqlite3.Error as e:
                return False, f"Error al actualizar: {e}"

    def delete_expense(self, expense_id: int) -> Tuple[bool, str]:
        with self._write_lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
                conn.commit()
                self._cache_last_check = 0.0
                return True, f"Gasto {expense_id} eliminado"
            except sqlite3.Error as e:
                return False, f"Error al eliminar: {e}"

    def get_dashboard_summary(self) -> dict:
        conn = self._get_connection()
        try:
            now = datetime.now()
            current_month_str = now.strftime('%Y-%m')
            row = conn.execute('''
                SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total,
                COALESCE(SUM(CASE WHEN type='Deuda' AND status='pending' THEN total ELSE 0 END), 0) as debt,
                COALESCE(SUM(CASE WHEN type='Prestamo' AND status='pending' THEN total ELSE 0 END), 0) as loan,
                COALESCE(SUM(CASE WHEN date LIKE ? AND type NOT IN ('Prestamo', 'Deuda') THEN total ELSE 0 END), 0) as month_total
                FROM expenses
            ''', (f'{current_month_str}%',)).fetchone()
            return dict(row) if row else {'count':0, 'total':0, 'debt':0, 'loan':0, 'month_total':0}
        except sqlite3.Error as e:
            return {'count':0, 'total':0, 'debt':0, 'loan':0, 'month_total':0}

    def get_available_years(self) -> List[int]:
        try:
            conn = self._get_connection()
            rows = conn.execute("SELECT DISTINCT CAST(strftime('%Y', date) AS INTEGER) as year FROM expenses ORDER BY year DESC").fetchall()
            return [row['year'] for row in rows]
        except sqlite3.Error as e:
            self._logger.error(f"Error getting years: {e}")
            return []

    def get_expenses_by_year(self, year: int, include_paid: bool = True) -> List[Dict]:
        try:
            conn = self._get_connection()
            query = 'SELECT * FROM expenses WHERE date LIKE ? ' + ('' if include_paid else "AND status = 'pending' ") + 'ORDER BY date DESC, id DESC'
            rows = conn.execute(query, (f'{year}-%',)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error(f"Error getting expenses by year: {e}")
            return []

    def get_all_expenses(self, include_paid: bool = True) -> List[Dict]:
        return self.get_expenses(limit=-1, include_paid=include_paid)

    def get_expenses(self, limit: int = 200, offset: int = 0, include_paid: bool = True) -> List[Dict]:
        cache_key = (limit, offset, include_paid)
        if (time.time() - self._cache_last_check) < self._cache_ttl and self._cache_data and self._cache_key == cache_key:
            return self._cache_data
        try:
            conn = self._get_connection()
            query = 'SELECT * FROM expenses ' + ('' if include_paid else "WHERE status = 'pending' ") + 'ORDER BY date DESC, id DESC'
            if limit > 0: query += f' LIMIT {limit} OFFSET {offset}'
            rows = conn.execute(query).fetchall()
            expenses = [dict(r) for r in rows]
            with self._cache_lock:
                self._cache_data = expenses
                self._cache_key = cache_key
                self._cache_last_check = time.time()
            return expenses
        except sqlite3.Error as e:
            self._logger.error(f"Error getting expenses: {e}")
            return []

    def get_categories(self) -> List[str]:
        try:
            conn = self._get_connection()
            rows = conn.execute("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL AND TRIM(category) != '' ORDER BY category").fetchall()
            return sorted(list(set(str(row['category']).strip().upper() for row in rows if row['category'] and str(row['category']).strip())))
        except sqlite3.Error as e:
            self._logger.error(f"Error getting categories: {e}")
            return []

    def get_budgets(self) -> List[Dict]:
        try:
            conn = self._get_connection()
            rows = conn.execute('SELECT category, monthly_limit FROM budgets').fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error(f"Error getting budgets: {e}")
            return []

    def get_monthly_spending_by_category(self, month: str, year: int) -> Dict[str, float]:
        try:
            conn = self._get_connection()
            rows = conn.execute('''SELECT category, SUM(total) AS total FROM expenses WHERE month = ? AND strftime('%Y', date) = ? AND status = 'pending' GROUP BY category''', (month.upper(), str(year))).fetchall()
            return {r['category']: float(r['total']) for r in rows}
        except sqlite3.Error as e:
            self._logger.error(f"Error getting monthly spending: {e}")
            return {}

    def get_pending_debts(self) -> List[Dict]:
        try:
            conn = self._get_connection()
            rows = conn.execute("SELECT * FROM expenses WHERE type IN ('Deuda', 'Prestamo') AND status = 'pending' ORDER BY date ASC").fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error(f"Error getting debts: {e}")
            return []

    def get_weekly_expenses(self, start_date: str, end_date: str) -> List[Dict]:
        try:
            conn = self._get_connection()
            rows = conn.execute("SELECT * FROM expenses WHERE date BETWEEN ? AND ? AND status = 'pending' ORDER BY date DESC", (start_date, end_date)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error(f"Error getting weekly expenses: {e}")
            return []

    def get_category_stats(self, category: str) -> Dict:
        try:
            conn = self._get_connection()
            row = conn.execute("SELECT AVG(total) AS avg, MAX(total) AS max, COUNT(*) AS count FROM expenses WHERE category = ? AND status = 'pending'", (category.upper().strip(),)).fetchone()
            return {'avg': round(row['avg'] or 0, 2), 'max': round(row['max'] or 0, 2), 'count': row['count'] or 0}
        except sqlite3.Error as e:
            self._logger.error(f"Error getting category stats: {e}")
            return {'avg': 0, 'max': 0, 'count': 0}

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            conn = self._get_connection()
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
            return row['value'] if row else default
        except sqlite3.Error as e:
            self._logger.error(f"Error getting setting {key}: {e}")
            return default

    def get_setting_status(self, key: str) -> Tuple[bool, Optional[str]]:
        try:
            conn = self._get_connection()
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
            return True, row['value'] if row else None
        except sqlite3.Error as exc:
            self._logger.error("Error getting setting %s: %s", key, exc)
            return False, None

    def set_setting(self, key: str, value: str) -> Tuple[bool, str]:
        with self._write_lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP', (key, value))
            conn.commit()
            return True, f"Ajuste guardado."

    def get_most_frequent_category(self, merchant: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            conn = self._get_connection()
            row = conn.execute('SELECT category, subcategory, COUNT(*) as count FROM expenses WHERE merchant = ? GROUP BY category, subcategory ORDER BY count DESC LIMIT 1', (merchant.upper().strip(),)).fetchone()
            return (row['category'], row['subcategory']) if row else (None, None)
        except sqlite3.Error as e:
            self._logger.error(f"Error getting frequent category: {e}")
            return (None, None)

    def add_budget(self, category: str, limit: float) -> Tuple[bool, str]:
        with self._write_lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO budgets (category, monthly_limit) VALUES (?, ?) ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit', (category.upper(), limit))
            conn.commit()
            return True, f"Presupuesto guardado."

    def get_all_settings(self) -> Dict[str, str]:
        try:
            conn = self._get_connection()
            rows = conn.execute('SELECT key, value FROM app_settings').fetchall()
            return {r['key']: r['value'] for r in rows}
        except sqlite3.Error as e:
            self._logger.error(f"Error getting settings: {e}")
            return {}

    def ensure_email_log_table(self):
        with self._write_lock:
            try:
                conn = self._get_connection()
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS email_log (
                        message_id   TEXT PRIMARY KEY,
                        subject      TEXT,
                        received_at  TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expense_id   INTEGER,
                        amount       REAL,
                        merchant     TEXT,
                        status       TEXT
                    )
                """)
                conn.commit()
            except sqlite3.Error as e:
                self._logger.error(f"Error creating email log table: {e}")

    def is_email_processed(self, message_id: str) -> bool:
        try:
            conn = self._get_connection()
            row = conn.execute("SELECT 1 FROM email_log WHERE message_id = ?", (message_id,)).fetchone()
            return row is not None
        except sqlite3.Error as e:
            self._logger.error(f"Error checking email process status: {e}")
            return False

    def log_email(self, message_id: str, subject: str, received_at: str, expense_id, amount, merchant, status):
        with self._write_lock:
            try:
                conn = self._get_connection()
                conn.execute("""
                    INSERT OR REPLACE INTO email_log
                    (message_id, subject, received_at, expense_id, amount, merchant, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (message_id, subject, received_at, expense_id, amount, merchant, status))
                conn.commit()
            except sqlite3.Error as e:
                self._logger.error(f"Error logging email: {e}")


class CloudflareDatabaseManager(BaseDatabaseManager):
    """Implementación conectada a Cloudflare D1 vía HTTP REST API."""
    storage_mode = "cloud"

    def __init__(self, account_id: str, db_id: str, api_token: str):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.account_id = account_id
        self.db_id = db_id
        self.api_token = api_token
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{db_id}/query"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        self._cache_data: List[Dict] = []
        self._cache_key = None
        self._cache_last_check: float = 0.0
        self._cache_ttl: float = 15.0
        self._cache_lock = threading.RLock()

        if not httpx:
            self._logger.error("La librería 'httpx' no está instalada. Ejecuta 'pip install httpx'")
        
        self._logger.info("CloudflareDatabaseManager inicializado.")

    def _query(self, sql: str, params: list = None) -> List[Dict]:
        """Ejecuta una consulta SQL en Cloudflare D1 y devuelve los resultados."""
        if not httpx:
            return []
        
        payload = {"sql": sql}
        if params:
            payload["params"] = params

        try:
            resp = httpx.post(self.url, headers=self.headers, json=payload, timeout=10.0)
            if resp.status_code != 200:
                self._logger.error(f"Error D1 HTTP {resp.status_code}: {resp.text}")
                return []
            
            data = resp.json()
            if data.get("success") and "result" in data:
                return data["result"][0].get("results", [])
            return []
        except Exception as e:
            self._logger.error(f"Excepción D1: {e}")
            return []

    def _execute(self, sql: str, params: list = None) -> bool:
        """Ejecuta una inserción/actualización/borrado en Cloudflare D1."""
        if not httpx:
            return False

        payload = {"sql": sql}
        if params:
            payload["params"] = params

        try:
            resp = httpx.post(self.url, headers=self.headers, json=payload, timeout=10.0)
            if resp.status_code != 200:
                self._logger.error(f"Error D1 HTTP {resp.status_code}: {resp.text}")
                return False
            data = resp.json()
            return data.get("success", False)
        except Exception as e:
            self._logger.error(f"Excepción D1 Execute: {e}")
            return False

    def add_expense(self, data: Dict) -> Tuple[bool, str]:
        data = _normalize_expense_data(data)
        sql = '''
            INSERT INTO expenses (day, month, week, date, payment_method, category, merchant, subcategory, details, total, type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = [
            int(data.get('day', 1)) if str(data.get('day', '')).isdigit() else 1,
            str(data.get('month', '')).upper(),
            int(data.get('week', 0)) if str(data.get('week', '')).isdigit() else 0,
            data.get('date'), str(data.get('payment_method', 'TARJETA')).upper(),
            str(data.get('category', 'OTRO')).upper(), str(data.get('merchant', '')).upper(),
            str(data.get('subcategory', '')).upper(), str(data.get('details', '')).upper(),
            float(data.get('total', 0)), data.get('type', 'Normal'), data.get('status', 'pending')
        ]
        success = self._execute(sql, params)
        if success:
            self._cache_last_check = 0.0
            return True, "Gasto guardado en la nube"
        return False, "Error al guardar en la nube"

    def update_expense(self, expense_id: int, data: Dict) -> Tuple[bool, str]:
        fields = {k: v for k, v in data.items() if k != 'id'}
        if not fields: return False, "No hay campos para actualizar"
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [expense_id]
        success = self._execute(f"UPDATE expenses SET {set_clause} WHERE id = ?", values)
        if success:
            self._cache_last_check = 0.0
            return True, f"Gasto {expense_id} actualizado en la nube"
        return False, "Error al actualizar en la nube"

    def delete_expense(self, expense_id: int) -> Tuple[bool, str]:
        success = self._execute("DELETE FROM expenses WHERE id = ?", [expense_id])
        if success:
            self._cache_last_check = 0.0
            return True, f"Gasto {expense_id} eliminado de la nube"
        return False, "Error al eliminar de la nube"

    def get_dashboard_summary(self) -> dict:
        now = datetime.now()
        current_month_str = now.strftime('%Y-%m')
        sql = '''
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total,
            COALESCE(SUM(CASE WHEN type='Deuda' AND status='pending' THEN total ELSE 0 END), 0) as debt,
            COALESCE(SUM(CASE WHEN type='Prestamo' AND status='pending' THEN total ELSE 0 END), 0) as loan,
            COALESCE(SUM(CASE WHEN date LIKE ? AND type NOT IN ('Prestamo', 'Deuda') THEN total ELSE 0 END), 0) as month_total
            FROM expenses
        '''
        res = self._query(sql, [f'{current_month_str}%'])
        return res[0] if res else {'count':0, 'total':0, 'debt':0, 'loan':0, 'month_total':0}

    def get_available_years(self) -> List[int]:
        res = self._query("SELECT DISTINCT CAST(strftime('%Y', date) AS INTEGER) as year FROM expenses ORDER BY year DESC")
        return [r['year'] for r in res]

    def get_expenses_by_year(self, year: int, include_paid: bool = True) -> List[Dict]:
        query = 'SELECT * FROM expenses WHERE date LIKE ? ' + ('' if include_paid else "AND status = 'pending' ") + 'ORDER BY date DESC, id DESC'
        return self._query(query, [f'{year}-%'])

    def get_all_expenses(self, include_paid: bool = True) -> List[Dict]:
        return self.get_expenses(limit=-1, include_paid=include_paid)

    def get_expenses(self, limit: int = 200, offset: int = 0, include_paid: bool = True) -> List[Dict]:
        cache_key = (limit, offset, include_paid)
        if (time.time() - self._cache_last_check) < self._cache_ttl and self._cache_data and self._cache_key == cache_key:
            return self._cache_data
            
        query = 'SELECT * FROM expenses ' + ('' if include_paid else "WHERE status = 'pending' ") + 'ORDER BY date DESC, id DESC'
        if limit > 0: query += f' LIMIT {limit} OFFSET {offset}'
        
        expenses = self._query(query)
        with self._cache_lock:
            self._cache_data = expenses
            self._cache_key = cache_key
            self._cache_last_check = time.time()
        return expenses

    def get_categories(self) -> List[str]:
        res = self._query("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL AND TRIM(category) != '' ORDER BY category")
        return sorted(list(set(str(r['category']).strip().upper() for r in res if r['category'] and str(r['category']).strip())))

    def get_budgets(self) -> List[Dict]:
        return self._query('SELECT category, monthly_limit FROM budgets')

    def get_monthly_spending_by_category(self, month: str, year: int) -> Dict[str, float]:
        res = self._query("SELECT category, SUM(total) AS total FROM expenses WHERE month = ? AND strftime('%Y', date) = ? AND status = 'pending' GROUP BY category", [month.upper(), str(year)])
        return {r['category']: float(r['total']) for r in res}

    def get_pending_debts(self) -> List[Dict]:
        return self._query("SELECT * FROM expenses WHERE type IN ('Deuda', 'Prestamo') AND status = 'pending' ORDER BY date ASC")

    def get_weekly_expenses(self, start_date: str, end_date: str) -> List[Dict]:
        return self._query("SELECT * FROM expenses WHERE date BETWEEN ? AND ? AND status = 'pending' ORDER BY date DESC", [start_date, end_date])

    def get_category_stats(self, category: str) -> Dict:
        res = self._query("SELECT AVG(total) AS avg, MAX(total) AS max, COUNT(*) AS count FROM expenses WHERE category = ? AND status = 'pending'", [category.upper().strip()])
        row = res[0] if res else {}
        return {'avg': round(row.get('avg') or 0, 2), 'max': round(row.get('max') or 0, 2), 'count': row.get('count') or 0}

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        res = self._query('SELECT value FROM app_settings WHERE key = ?', [key])
        return res[0]['value'] if res else default

    def get_setting_status(self, key: str) -> Tuple[bool, Optional[str]]:
        """Distingue una clave inexistente de una falla de conexión con D1."""
        if not httpx:
            return False, None
        try:
            response = httpx.post(
                self.url,
                headers=self.headers,
                json={"sql": "SELECT value FROM app_settings WHERE key = ?", "params": [key]},
                timeout=10.0,
            )
            if response.status_code != 200:
                self._logger.error("Error D1 HTTP %s leyendo ajuste %s", response.status_code, key)
                return False, None
            data = response.json()
            if not data.get("success") or not data.get("result"):
                return False, None
            rows = data["result"][0].get("results", [])
            return True, rows[0].get("value") if rows else None
        except Exception as exc:
            self._logger.error("Excepción D1 leyendo ajuste %s: %s", key, exc)
            return False, None

    def set_setting(self, key: str, value: str) -> Tuple[bool, str]:
        success = self._execute('INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP', [key, value])
        return success, "Ajuste guardado en la nube" if success else "Error al guardar ajuste"

    def get_most_frequent_category(self, merchant: str) -> Tuple[Optional[str], Optional[str]]:
        res = self._query('SELECT category, subcategory, COUNT(*) as count FROM expenses WHERE merchant = ? GROUP BY category, subcategory ORDER BY count DESC LIMIT 1', [merchant.upper().strip()])
        return (res[0]['category'], res[0]['subcategory']) if res else (None, None)

    def add_budget(self, category: str, limit: float) -> Tuple[bool, str]:
        success = self._execute('INSERT INTO budgets (category, monthly_limit) VALUES (?, ?) ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit', [category.upper(), limit])
        return success, "Presupuesto guardado en la nube" if success else "Error guardando presupuesto"

    def get_all_settings(self) -> Dict[str, str]:
        res = self._query('SELECT key, value FROM app_settings')
        return {r['key']: r['value'] for r in res}

    def ensure_email_log_table(self):
        sql = """
            CREATE TABLE IF NOT EXISTS email_log (
                message_id   TEXT PRIMARY KEY,
                subject      TEXT,
                received_at  TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expense_id   INTEGER,
                amount       REAL,
                merchant     TEXT,
                status       TEXT
            )
        """
        self._execute(sql)

    def is_email_processed(self, message_id: str) -> bool:
        res = self._query("SELECT 1 FROM email_log WHERE message_id = ?", [message_id])
        return len(res) > 0

    def log_email(self, message_id: str, subject: str, received_at: str, expense_id, amount, merchant, status):
        sql = """
            INSERT OR REPLACE INTO email_log
            (message_id, subject, received_at, expense_id, amount, merchant, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self._execute(sql, [message_id, subject, received_at, expense_id, amount, merchant, status])

# ---
# Factoría inteligente que determina qué BD usar basándose en el .env
# ---
def get_database_manager(db_path: Optional[str] = None) -> BaseDatabaseManager:
    import os
    from dotenv import load_dotenv
    load_dotenv('.env')

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    db_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if account_id and db_id and api_token:
        print("[DB] Configuración de Cloudflare D1 detectada. Usando base de datos en la NUBE.")
        return CloudflareDatabaseManager(account_id, db_id, api_token)
    else:
        print("[DB] Usando base de datos SQLite LOCAL.")
        return LocalDatabaseManager(db_path)

# Compatibilidad hacia atrás para módulos que importan "DatabaseManager"
DatabaseManager = get_database_manager

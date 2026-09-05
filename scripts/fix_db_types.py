import sqlite3
import os

def fix_database_types():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'database', 'expenses.db')
    
    if not os.path.exists(db_path):
        print(f"Error: No se encontró la base de datos en {db_path}")
        return

    print(f"Conectando a la base de datos: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Corregir columna 'week'
        print("Corrigiendo columna 'week'...")
        cursor.execute("SELECT id, week FROM expenses")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row_id, week_val in rows:
            try:
                if week_val is not None:
                    # Intentar convertir a entero
                    new_val = int(week_val)
                    cursor.execute("UPDATE expenses SET week = ? WHERE id = ?", (new_val, row_id))
                    updated_count += 1
            except (ValueError, TypeError):
                # Si falla la conversión (ej: era un string no numérico), poner 0 o null
                cursor.execute("UPDATE expenses SET week = 0 WHERE id = ?", (row_id,))
                updated_count += 1
        
        print(f"[OK] {updated_count} registros actualizados en 'week'.")

        # 2. Corregir columna 'day' (por si acaso)
        print("Corrigiendo columna 'day'...")
        cursor.execute("SELECT id, day FROM expenses")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row_id, day_val in rows:
            try:
                if day_val is not None:
                    new_val = int(day_val)
                    cursor.execute("UPDATE expenses SET day = ? WHERE id = ?", (new_val, row_id))
                    updated_count += 1
            except (ValueError, TypeError):
                cursor.execute("UPDATE expenses SET day = 1 WHERE id = ?", (row_id,))
                updated_count += 1
        
        print(f"[OK] {updated_count} registros actualizados en 'day'.")

        conn.commit()
        print("\n[OK] Limpieza de tipos completada exitosamente.")

    except Exception as e:
        print(f"Error durante la limpieza: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database_types()

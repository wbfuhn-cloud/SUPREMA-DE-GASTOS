import sqlite3
import os

def export_database():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'database', 'expenses.db')
    export_dir = os.path.join(project_root, 'cloudflare')
    export_path = os.path.join(export_dir, 'd1_export.sql')

    os.makedirs(export_dir, exist_ok=True)

    if not os.path.exists(db_path):
        print(f"Error: No se encontró la base de datos en {db_path}")
        return

    print(f"Exportando base de datos desde: {db_path}")
    conn = sqlite3.connect(db_path)
    
    with open(export_path, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            # Cloudflare D1 compatibility tweaks if needed
            if line.startswith('PRAGMA') or line.startswith('BEGIN TRANSACTION') or line.startswith('COMMIT'):
                continue
            f.write(f"{line}\n")
            
    conn.close()
    print(f"Exportación exitosa. Archivo guardado en: {export_path}")
    print("Sube este archivo a Cloudflare D1 desde el panel o usando Wrangler.")

if __name__ == '__main__':
    export_database()

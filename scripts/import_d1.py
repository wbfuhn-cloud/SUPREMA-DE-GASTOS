import requests
import os
from dotenv import load_dotenv

def import_to_d1():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path)

    acc = os.getenv('CLOUDFLARE_ACCOUNT_ID')
    db = os.getenv('CLOUDFLARE_D1_DATABASE_ID')
    tok = os.getenv('CLOUDFLARE_API_TOKEN')
    
    if not acc or not db or not tok:
        print("Faltan credenciales en .env")
        return

    sql_file = os.path.join(project_root, 'cloudflare', 'd1_export.sql')
    if not os.path.exists(sql_file):
        print("No se encontró el archivo de exportación d1_export.sql")
        return

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    url = f'https://api.cloudflare.com/client/v4/accounts/{acc}/d1/database/{db}/query'
    headers = {
        'Authorization': f'Bearer {tok}',
        'Content-Type': 'application/json'
    }
    payload = {'sql': sql_content}
    
    print(f"Importando datos a Cloudflare D1... ({len(sql_content)} bytes)")
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code == 200:
        print("¡Importación completada con éxito!")
    else:
        print(f"Error ({resp.status_code}): {resp.text}")

if __name__ == '__main__':
    import_to_d1()

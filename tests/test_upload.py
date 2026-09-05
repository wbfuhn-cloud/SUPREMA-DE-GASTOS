# -*- coding: utf-8 -*-
import os
from google import genai
from dotenv import load_dotenv
from PIL import Image

print("=" * 50)
print("TEST DE SUBIDA DE IMAGEN A GEMINI")
print("=" * 50)

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Crear imagen de prueba si no existe
test_image_path = "test_image.jpg"
if not os.path.exists(test_image_path):
    print("Creando imagen de prueba dummy...")
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(test_image_path)

try:
    print("Inectando cliente...")
    client = genai.Client(api_key=api_key)
    
    print(f"Subiendo archivo: {test_image_path}...")
    # ESTA ES LA LINEA CORREGIDA QUE QUEREMOS PROBAR
    uploaded_file = client.files.upload(file=test_image_path)
    
    print(f"✅ EXITO! Archivo subido.")
    print(f"URI: {uploaded_file.name}")
    print(f"Display Name: {uploaded_file.display_name}")
    
    # Limpieza
    print("Eliminando archivo de Gemini...")
    client.files.delete(name=uploaded_file.name)
    print("Eliminado.")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print(f"Tipo de error: {type(e).__name__}")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(test_image_path):
        os.remove(test_image_path)

# -*- coding: utf-8 -*-
import os
from google import genai
from dotenv import load_dotenv

print("=" * 50)
print("PRUEBA DE CONEXION CON GOOGLE GEMINI")
print("=" * 50)

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERROR: No se encontro GOOGLE_API_KEY en .env")
    exit(1)

print(f"OK - API Key cargada: {api_key[:10]}...{api_key[-5:]}")

try:
    client = genai.Client(api_key=api_key)
    model_name = 'gemini-2.5-flash'
    
    print(f"\nProbando modelo: {model_name}")
    print("Enviando solicitud...")
    
    response = client.models.generate_content(
        model=model_name,
        contents="Di 'Hola' en 5 idiomas diferentes"
    )
    
    print("\n" + "=" * 50)
    print("CONEXION EXITOSA!")
    print("=" * 50)
    print("Respuesta de Gemini:")
    print(response.text)
    print("=" * 50)
    
except Exception as e:
    print(f"\nERROR: {e}")
    print(f"Tipo de error: {type(e).__name__}")
    import traceback
    traceback.print_exc()

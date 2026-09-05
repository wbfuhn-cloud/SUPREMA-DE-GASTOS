# -*- coding: utf-8 -*-
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

print("Listando modelos disponibles...")
print("=" * 60)

try:
    client = genai.Client(api_key=api_key)
    
    # Listar modelos usando el endpoint correcto
    response = client.models.list()
    
    print("\nModelos disponibles:\n")
    for model in response:
        print(f"- {model.name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"  Metodos soportados: {model.supported_generation_methods}")
        print()
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

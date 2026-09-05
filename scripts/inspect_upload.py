# -*- coding: utf-8 -*-
import os
import inspect
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

try:
    client = genai.Client(api_key=api_key)
    print("Method signature for client.files.upload:")
    print(inspect.signature(client.files.upload))
    print("\nDocstring:")
    print(client.files.upload.__doc__)
except Exception as e:
    print(f"Error: {e}")

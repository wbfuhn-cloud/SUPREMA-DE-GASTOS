"""Prueba manual y opt-in de conectividad con Google Gemini.

Esta prueba nunca se ejecuta durante la colección normal: requiere la marca
``live`` y la variable ``RUN_LIVE_GEMINI_TESTS=1``. Tampoco imprime ni parcial
ni completamente la credencial usada.
"""

import os

import pytest


@pytest.mark.live
def test_gemini_connection():
    if os.getenv("RUN_LIVE_GEMINI_TESTS") != "1":
        pytest.skip("Prueba externa desactivada; usa RUN_LIVE_GEMINI_TESTS=1")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY no está configurada")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Responde únicamente con la palabra OK",
    )

    assert response.text

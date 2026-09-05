import os
import json
import logging
from google import genai
from google.genai import types
from datetime import datetime

# Configurar logger
logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self, api_key):
        """
        Inicializa el servicio de análisis con Google Gemini.
        """
        try:
            # Configurar el cliente con la nueva API
            self.client = genai.Client(api_key=api_key)
            # Usar Gemini 2.5 para evitar problemas de cuota
            self.model_name = 'gemini-2.5-flash'
            logger.info(f"[OK] AnalysisService inicializado con modelo: {self.model_name}")
        except Exception as e:
            logger.error(f"[FAIL] Error al inicializar AnalysisService: {e}", exc_info=True)
            raise

    def _clean_gemini_response(self, text: str) -> str:
        content = text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return content

    def analyze_receipt(self, image_path):
        """
        Envía la imagen del recibo a Google Gemini para su análisis y extrae datos estructurados.
        
        Parámetros:
        image_path (str): Ruta absoluta a la imagen del recibo.
        
        Retorna:
        dict: Diccionario JSON con los datos extraídos (fecha, total, comercio, etc.) o None si falla.
        """
        logger.info(f"[PHOTO] Iniciando analisis de imagen: {image_path}")
        
        try:
            # Validar existencia del archivo
            if not os.path.exists(image_path):
                logger.error(f"[FAIL] El archivo no existe: {image_path}")
                return None
            
            file_size = os.path.getsize(image_path)
            logger.info(f"[INFO] Tamano de archivo: {file_size} bytes")
            
            # Subir archivo usando la API de Gemini
            logger.info("[UPLOAD] Subiendo imagen a la nube de Gemini...")
            uploaded_file = self.client.files.upload(file=image_path)
            logger.info(f"[OK] Imagen subida exitosamente. URI: {uploaded_file.name}")

            # Prompt (Instrucción) para el modelo
            prompt = f"""
            Actúa como una API experta en extracción de datos de tickets de compra para un edificio de departamentos.
            Analiza la imagen proporcionada y retorna SOLAMENTE un objeto JSON válido.
            No incluyas markdown (```json ... ```) ni texto adicional.
            
            Campos requeridos:
            1. "date": Fecha en formato YYYY-MM-DD. Si no tiene año, asume 2026.
            2. "merchant": Nombre de la tienda o comercio.
            3. "category": Clasificación del gasto (Alimentos, Transporte, Hogar, Ropa, Salud, Entretenimiento, Servicios, Otros).
            4. "subcategory": Segunda clasificación más específica (Ej: Alimentos -> Restaurante, Supermercado; Transporte -> Gasolina, Uber). Null si no es obvio.
            5. "total": Número decimal con el total pagado (solo el número, ej: 150.50).
            6. "currency": Moneda (MXN, USD, EUR).
            9. "details": Breve descripción de los productos (máx 5 palabras).
            10. "payment_method": Método de pago (Efectivo, Tarjeta, Transferencia). Default: "Tarjeta".

            Si un campo es ilegible, usa null (excepto payment_method).
            """

            logger.info("[AI] Enviando solicitud de procesamiento a Gemini...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, uploaded_file]
            )
            
            logger.info("[OK] Respuesta recibida de Gemini")
            logger.debug(f"Respuesta cruda: {response.text[:200]}...")
            
            content = self._clean_gemini_response(response.text)
            
            logger.info("[PARSE] Interpretando JSON...")
            logger.debug(f"JSON limpio: {content}")
            
            data = json.loads(content)
            
                
            logger.info(f"[OK] Datos extraidos correctamente: {data}")
            
            # Limpieza de recursos en la nube
            logger.info("[CLEAN] Eliminando archivo temporal de los servidores de Gemini...")
            self.client.files.delete(name=uploaded_file.name)
            logger.info("[OK] Archivo temporal eliminado")
            
            return data

        except json.JSONDecodeError as e:
            logger.error(f"[FAIL] Error al interpretar el JSON de Gemini: {e}", exc_info=True)
            logger.error(f"Contenido problemático: {content if 'content' in locals() else 'N/A'}")
            return None
            
        except Exception as e:
            logger.error(f"[FAIL] Error general durante el analisis: {e}", exc_info=True)
            logger.error(f"Tipo de error: {type(e).__name__}")
            return None

    def analyze_audio(self, audio_path):
        """
        Envía un archivo de audio a Google Gemini para su análisis y extracción de datos.
        
        Parámetros:
        audio_path (str): Ruta absoluta al archivo de audio (.ogg, .mp3, etc).
        
        Retorna:
        dict: Diccionario JSON con los datos extraídos o None.
        """
        logger.info(f"[VOICE] Iniciando analisis de audio: {audio_path}")
        
        try:
            if not os.path.exists(audio_path):
                logger.error(f"[FAIL] El archivo de audio no existe: {audio_path}")
                return None
            
            current_date = datetime.now().strftime("%Y-%m-%d")

            prompt = f"""
            Actúa como un asistente contable experto para la administración de un edificio. 
            Escucha el siguiente audio donde un usuario describe un gasto o ingreso.
            Extrae la información y estructura los datos en un objeto JSON válido.
            
            Campos requeridos:
            1. "date": Fecha mencionada (YYYY-MM-DD). Si dice "hoy", usa la fecha actual ({current_date}). Si no menciona fecha, usa la fecha de hoy.
            2. "merchant": Nombre del lugar, tienda o persona.
            3. "category": Clasificación (Alimentos, Transporte, Hogar, Ropa, Salud, Entretenimiento, Servicios, Otros). Infiérela del contexto.
            4. "subcategory": Segunda clasificación más específica.
            5. "total": Monto numérico del gasto.
            6. "currency": Moneda (MXN, USD). Por defecto MXN.
            7. "details": Transcripción resumida de qué se compró.
            8. "payment_method": Metodo de pago (Efectivo, Tarjeta, Transferencia). Si no se menciona, usa "Tarjeta".

            Retorna SOLAMENTE el JSON.
            """

            logger.info("[AI] Subiendo audio a Gemini...")
            uploaded_file = self.client.files.upload(file=audio_path)
            
            logger.info("[AI] Enviando audio a Gemini...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, uploaded_file]
            )
            
            logger.info("[OK] Respuesta recibida de Gemini (Audio)")
            content = self._clean_gemini_response(response.text)
            
            logger.info(f"Contenido extraído: {content}")
            data = json.loads(content)
            
                
            # Limpieza
            self.client.files.delete(name=uploaded_file.name)
            
            return data

        except Exception as e:
            logger.error(f"[FAIL] Error analizando audio: {e}", exc_info=True)
            return None

    def analyze_email_body(self, body_text):
        """
        Usa Gemini para extraer datos de una notificación bancaria enviada por correo.
        """
        logger.info("[EMAIL] Analizando cuerpo de correo con Gemini...")
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            prompt = f"""
            Actúa como un experto en finanzas personales.
            Analiza el siguiente texto de un correo de notificación bancaria y extrae los datos del gasto.
            
            Texto del correo:
            ---
            {body_text}
            ---
            
            Retorna SOLAMENTE un objeto JSON válido. No incluyas markdown.
            Campos:
            1. "date": Fecha del movimiento (YYYY-MM-DD). Hoy es {current_date}.
            2. "merchant": Nombre del comercio o destinatario.
            3. "total": Monto numérico (solo el número).
            4. "category": Categoría sugerida (Alimentos, Transporte, Hogar, Ropa, Salud, Entretenimiento, Servicios, Otros).
            5. "subcategory": Subcategoría sugerida.
            6. "details": Breve descripción (máx 10 palabras).
            7. "type": "Normal", "Deuda" o "Prestamo". Default: "Normal".
            
            Si el correo no es una notificación de gasto, retiro o transferencia, retorna null.
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            content = self._clean_gemini_response(response.text)
            if content.lower() == 'null':
                return None
                
            data = json.loads(content)
            return data

        except Exception as e:
            logger.error(f"[FAIL] Error analizando correo con Gemini: {e}")
            return None

    def query_data(self, user_query, database_context):
        """
        Usa Gemini para responder preguntas sobre los datos de gastos del usuario.
        """
        logger.info(f"[SEARCH] Procesando consulta de datos: {user_query}")
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            prompt = f"""
            Actúa como un analista financiero personal experto. 
            Responde a la pregunta del usuario basándote EXCLUSIVAMENTE en los datos proporcionados a continuación.
            
            Contexto del Sistema:
            - Fecha actual: {current_date}
            - Moneda: Pesos Mexicanos (MXN)
            
            Datos de la Base de Datos (Resumen de Gastos):
            ---
            {database_context}
            ---
            
            Pregunta del Usuario: "{user_query}"
            
            Instrucciones:
            1. Sé preciso y directo.
            2. Usa negritas para resaltar montos y categorías.
            3. Si la pregunta requiere un cálculo (ej: suma), realízalo.
            4. Si no hay datos suficientes para responder, indícalo amablemente.
            5. Mantén un tono profesional pero cercano.
            6. Responde en Español.
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            return response.text.strip()
        except Exception as e:
            logger.error(f"[FAIL] Error en query_data: {e}")
            return "Lo siento, tuve un problema al analizar tus datos. Inténtalo de nuevo más tarde."

    def check_unusual_expense(self, current_expense, historical_stats):
        """
        Determina si un gasto es inusual comparándolo con el promedio histórico de la categoría.
        """
        logger.info(f"[CHECK] Evaluando si el gasto es inusual: {current_expense['merchant']} - ${current_expense['total']}")
        try:
            prompt = f"""
            Actúa como un guardián de finanzas personales.
            Determina si el siguiente gasto nuevo es "Inusual" o "Alarmante" comparado con el historial de esa categoría.
            
            Gasto Nuevo:
            - Comercio: {current_expense['merchant']}
            - Categoría: {current_expense['category']}
            - Monto: ${current_expense['total']}
            
            Estadísticas Históricas de la Categoría ({current_expense['category']}):
            - Promedio de gasto: ${historical_stats.get('avg', 0)}
            - Gasto máximo anterior: ${historical_stats.get('max', 0)}
            - Total de registros: {historical_stats.get('count', 0)}
            
            Instrucciones:
            1. Considera inusual si supera el promedio por más del 100% o si es significativamente más alto que el máximo anterior.
            2. Si es inusual, genera una breve alerta (máx 20 palabras) que sea amigable pero de advertencia.
            3. Si NO es inusual, retorna simplemente la palabra "NORMAL".
            4. Retorna SOLAMENTE la alerta o la palabra "NORMAL".
            """
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            result = response.text.strip()
            return None if "NORMAL" in result.upper() else result
            
        except Exception as e:
            logger.error(f"[FAIL] Error en check_unusual_expense: {e}")
            return None

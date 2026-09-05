import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from src.analyzer import AnalysisService
from src.database import DatabaseManager
import datetime
import requests
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.notifications import NotificationService

import re

# Configurar logger
logger = logging.getLogger(__name__)

class ExpenseBot:
    def __init__(self, token, api_key, dashboard_url=None, on_pause_callback=None, on_resume_callback=None):
        from src.config import Config
        # Configuración robusta para evitar errores de red en Windows
        # - connect_timeout: tiempo máximo para establecer conexión TCP
        # - read_timeout:    tiempo máximo esperando respuesta de Telegram
        # - write_timeout:   tiempo máximo enviando datos
        # - pool_timeout:    tiempo esperando un slot libre del pool de conexiones
        request_config = HTTPXRequest(
            connect_timeout=30,
            read_timeout=30,
            write_timeout=30,
            pool_timeout=10,
        )
        self.application = (
            ApplicationBuilder()
            .token(token)
            .request(request_config)
            .build()
        )
        self.analyzer = AnalysisService(api_key)
        self.dashboard_url = dashboard_url if dashboard_url else Config.DASHBOARD_URL
        self.api_url = "http://127.0.0.1:5050/api/add-expense" # Internal API URL
        self.downloads_dir = "downloads"
        
        # Initialize Database Manager for Smart Categories
        self.db_manager = DatabaseManager()
        
        # Initialize Notification Service
        self.notification_service = NotificationService(self.db_manager)
        
        # Initialize Scheduler for notifications
        self.scheduler = AsyncIOScheduler()
        self.chat_id = self._load_chat_id()  # Load from persistence
        
        # Callbacks para controlar la GUI/Servicios
        self.on_pause_callback = on_pause_callback
        self.on_resume_callback = on_resume_callback
        self.paused = False
        
        # Estado temporal para gastos pendientes de confirmación: {chat_id: {data}}
        self.pending_expenses = self._load_pending_expenses()
        
        # Setup Handlers
        start_handler = CommandHandler('start', self.start)
        help_handler = CommandHandler('help', self.help)
        stop_handler = CommandHandler('stop', self.handle_stop_command)
        budget_handler = CommandHandler('presupuesto', self.handle_budget_command)
        budgets_handler = CommandHandler('presupuestos', self.handle_budgets_command)
        summary_handler = CommandHandler('resumen', self.handle_summary_command)
        photo_handler = MessageHandler(filters.PHOTO, self.handle_photo)
        voice_handler = MessageHandler(filters.VOICE, self.handle_voice)
        text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        callback_handler = CallbackQueryHandler(self.handle_callback)
        
        self.application.add_handler(text_handler)
        self.application.add_handler(start_handler)
        self.application.add_handler(help_handler)
        self.application.add_handler(stop_handler)
        self.application.add_handler(budget_handler)
        self.application.add_handler(budgets_handler)
        self.application.add_handler(summary_handler)
        self.application.add_handler(photo_handler)
        self.application.add_handler(voice_handler)
        self.application.add_handler(callback_handler)
        
        # Handler global de errores: registra errores de red como advertencia simple
        # en lugar de un traceback completo, ya que la librería los reintenta sola.
        from telegram.error import NetworkError, TimedOut
        async def _global_error_handler(update, context: ContextTypes.DEFAULT_TYPE):
            err = context.error
            if isinstance(err, (NetworkError, TimedOut)):
                logger.warning(f"[NET] Error de red transitorio (se reintentara): {type(err).__name__}")
            else:
                logger.error(f"[BOT] Error no manejado: {err}", exc_info=err)
        self.application.add_error_handler(_global_error_handler)

    def _load_pending_expenses(self) -> dict:
        path = os.path.join("database", "pending_expenses.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando gastos pendientes: {e}")
        return {}

    def _save_pending_expenses(self):
        path = os.path.join("database", "pending_expenses.json")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.pending_expenses, f, indent=4)
        except Exception as e:
            logger.error(f"Error guardando gastos pendientes: {e}")

    def run(self):
        logger.info("Bot iniciado con Gemini... Presiona Stop en la GUI para detener.")
        
        # Corrección para Windows: Usar SelectorEventLoopPolicy
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Guardar referencia al loop para poder detenerlo después
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._start_polling())
        except Exception as e:
            logger.error(f"Error en el bot: {e}")
            raise e
        finally:
            self._loop.close()
    
    async def _start_polling(self):
        """Inicia el polling de forma asíncrona."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        # Mantener corriendo hasta que se llame stop
        self._running = True
        while self._running:
            await asyncio.sleep(0.5)
        
        # Limpieza
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    def stop(self):
        """Detiene el bot de forma segura desde otro hilo."""
        logger.info("Deteniendo bot...")
        self._running = False

    async def send_photo(self, photo_path, caption=None):
        """Envía una foto al chat activo del bot."""
        if not self.chat_id:
            logger.error("No hay chat_id configurado para enviar foto.")
            return False, "Bot no inicializado por el usuario (/start)"
        
        try:
            with open(photo_path, 'rb') as photo:
                await self.application.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown'
                )
            return True, "Enviado exitosamente"
        except Exception as e:
            logger.error(f"Error enviando foto a Telegram: {e}")
            return False, str(e)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        logger.info(f"Comando /start recibido de {update.effective_user.first_name}")
        
        # Save chat_id for notifications and persistence
        self.chat_id = chat_id
        self._save_chat_id(chat_id)
        
        # Start notification scheduler if not already running
        if not self.scheduler.running:
            self._setup_notification_scheduler()
            self.scheduler.start()
            logger.info("Notification scheduler started")
        
        if self.paused:
            self.paused = False
            logger.info("Bot reanudado por el usuario.")
            if self.on_resume_callback:
                if asyncio.iscoroutinefunction(self.on_resume_callback):
                    await self.on_resume_callback()
                else:
                    self.on_resume_callback()
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="▶️ **Bot Reanudado**\n\n✅ **¡Ya todo está corriendo en orden!**\nLos procesos han sido iniciados correctamente. ¡Ya puedes enviarme tus gastos!",
                parse_mode='Markdown'
            )
            return

        await context.bot.send_message(
            chat_id=chat_id,
            text="¡Hola! Soy tu asistente de gastos.\n\n✅ **¡Ya todo está corriendo en orden!**\nLos procesos han sido iniciados correctamente.\n\nEnvíame:\n"
                 "📸 **Una foto** de tu ticket, o\n"
                 "🎤 **Una nota de voz** dictando el gasto.\n\n"
                 f"📊 **Dashboard Interactivo:**\n{self.dashboard_url}\n\n"
                 "🔔 **Notificaciones Inteligentes:**\n"
                 "• /presupuesto [categoría] [monto] - Establecer presupuesto\n"
                 "• /presupuestos - Ver presupuestos actuales\n"
                 "• /resumen - Resumen semanal\n\n"
                 "Si necesito confirmar algo, puedes escribir 'cambia detalles por: ...' para corregir."
        )

    def _save_chat_id(self, chat_id):
        try:
            with open("chat_id.txt", "w") as f:
                f.write(str(chat_id))
        except Exception as e:
            logger.error(f"Error guardando chat_id: {e}")

    def _load_chat_id(self):
        try:
            if os.path.exists("chat_id.txt"):
                with open("chat_id.txt", "r") as f:
                    return int(f.read().strip())
        except Exception as e:
            logger.error(f"Error cargando chat_id: {e}")
        return None

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="1. Envía foto del ticket o nota de voz.\n2. Revisa los datos.\n3. Si algo está mal, escribe ej: 'cambia total por 500'.\n4. Confirma."
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto para edición."""
        chat_id = update.effective_chat.id
        text = update.message.text.lower().strip()
        
        if text == "visual":
            await self.handle_visual_command(chat_id, context)
            return

        if text == "stop":
            await self.handle_stop_command(update, context)
            return

        if self.paused:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ **Bot en Pausa**\n\nEl sistema está detenido temporalmente. Envía `/start` para reactivarlo.",
                parse_mode='Markdown'
            )
            return

        if chat_id not in self.pending_expenses:
            # Si no hay gasto pendiente, ignorar o dar respuesta genérica
            return

        expense_data = self.pending_expenses[chat_id]
        updated = False

        # Regex básica para: "cambia(r) [campo] por/: [valor]"
        # Ejemplos: "cambia detalles por cafe", "cambiar monto: 50", "cambia detalles por: cafe"
        pattern = r"(?:cambia|cambiar)?\s*(\w+)\s*(?:por|:)\s*:?\s*(.+)"
        match = re.search(pattern, text)
        
        if match:
            field_raw = match.group(1)
            value = match.group(2).strip()
            
            # Mapeo de campos
            field_map = {
                "detalles": "details", "detalle": "details", "descripción": "details", "descripcion": "details",
                "tienda": "merchant", "comercio": "merchant", "lugar": "merchant", "empresa": "merchant",
                "monto": "total", "total": "total", "precio": "total", "costo": "total",
                "fecha": "date",
                "subcategoria": "subcategory", "subcat": "subcategory", "tipo": "subcategory"
            }
            
            target_field = field_map.get(field_raw)
            
            if target_field:
                expense_data[target_field] = value
                self._save_pending_expenses()
                updated = True
                
                # Si cambió la fecha, recalcular derivados
                if target_field == "date":
                    self._enrich_date_details(expense_data)
                
                # Update visual confirmation
                await context.bot.send_message(chat_id=chat_id, text=f"✏️ Campo actualizado: **{target_field}** -> `{value}`", parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ No reconocí el campo '{field_raw}'. Pruba 'detalles', 'monto', 'tienda' o 'fecha'.")
        else:
             # Intento simple si solo ponen "campo: valor" sin "cambia"
             pass 

        if updated:
            # Reenviar confirmación actualizada
            await self.send_confirmation_message(chat_id, context, expense_data)
            
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja la recepción de notas de voz.
        """
        user = update.message.from_user
        chat_id = update.effective_chat.id

        if self.paused:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ **Bot en Pausa**\n\nEl sistema está detenido temporalmente. Envía `/start` para reactivarlo.",
                parse_mode='Markdown'
            )
            return

        logger.info(f"[MIC] Nota de voz recibida de {user.first_name}")

        processing_msg = await context.bot.send_message(chat_id=chat_id, text="Escuchando y procesando audio... 🎧")

        try:
            # Obtener el archivo de audio (Telegram envía OGG/Opus por defecto en voice notes)
            voice_file = await update.message.voice.get_file()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.downloads_dir}/audio_{timestamp}.ogg"
            
            os.makedirs(self.downloads_dir, exist_ok=True)
            
            await voice_file.download_to_drive(filename)
            logger.info(f"[SAVE] Audio guardado en: {filename}")
            
            # Analizar con Gemini
            analysis_result = self.analyzer.analyze_audio(filename)
            
            # Limpiar archivo
            if os.path.exists(filename):
                os.remove(filename)
                
            if analysis_result:
                # Enriquecer datos
                self._enrich_date_details(analysis_result)
                
                # Smart Categories: Override with historical data if available
                self._apply_smart_category(analysis_result)
                
                # Guardar pendiente
                self.pending_expenses[chat_id] = analysis_result
                self._save_pending_expenses()
                
                # Eliminar mensaje de espera
                await context.bot.delete_message(chat_id=chat_id, message_id=processing_msg.message_id)
                
                # Confirmar
                await self.send_confirmation_message(chat_id, context, analysis_result)
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_msg.message_id,
                    text="[X] No pude entender el audio. Intenta hablar más claro."
                )

        except Exception as e:
            logger.error(f"Error procesando audio: {e}", exc_info=True)
            await context.bot.send_message(chat_id=chat_id, text="[WARN] Error al procesar el audio.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja la recepción de imágenes (tickets).
        Envía la foto a Gemini para análisis e inicia el flujo de confirmación.
        """
        user = update.message.from_user
        chat_id = update.effective_chat.id

        if self.paused:
            await context.bot.send_message(
                chat_id=chat_id,
                text="[WARN] **Bot en Pausa**\n\nEl sistema está detenido temporalmente. Envía `/start` para reactivarlo.",
                parse_mode='Markdown'
            )
            return

        logger.info(f"[CAMERA] Foto recibida de {user.first_name}")
        
        # Enviar mensaje de espera
        processing_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="Procesando imagen con IA... [HOURGLASS]"
        )

        try:
            # Descargar la foto de mayor resolución (la última en la lista)
            photo_file = await update.message.photo[-1].get_file()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.downloads_dir}/ticket_{timestamp}.jpg"
            
            # Crear directorio si no existe
            os.makedirs(self.downloads_dir, exist_ok=True)
            
            # Guardar archivo localmente
            await photo_file.download_to_drive(filename)
            logger.info(f"[SAVE] Imagen guardada en: {filename}")

            # Analizar con Gemini
            analysis_result = self.analyzer.analyze_receipt(filename)
            
            # Eliminar archivo local para ahorrar espacio
            if os.path.exists(filename):
                os.remove(filename)

            if analysis_result:
                chat_id = update.effective_chat.id
                
                # Enriquecer datos (calcular Día, Mes, Semana)
                self._enrich_date_details(analysis_result)
                
                # Smart Categories: Override with historical data if available
                self._apply_smart_category(analysis_result)
                
                # Guardar en memoria temporal para confirmación
                self.pending_expenses[chat_id] = analysis_result
                self._save_pending_expenses()
                
                # Eliminar mensaje de "Procesando..."
                await context.bot.delete_message(chat_id=chat_id, message_id=processing_msg.message_id)
                
                # Iniciar flujo de confirmación
                await self.send_confirmation_message(chat_id, context, analysis_result)
                
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=processing_msg.message_id,
                    text="[X] No pude entender el ticket. Intenta con una foto más clara."
                )

        except Exception as e:
            logger.error(f"Error procesando foto: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="[WARN] Ocurrió un error al procesar la imagen."
            )

    def _enrich_date_details(self, data):
        """
        Calcula campos derivados de la fecha:
        - day (Día del mes)
        - month (Nombre del mes en Español)
        - week (Semana del año)
        
        Si la fecha es inválida, usa la fecha actual.
        """
        date_str = data.get('date')
        try:
            # Intentar parsear fecha YYYY-MM-DD
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            # Fallback a hoy si falla
            dt = datetime.datetime.now()
            data['date'] = dt.strftime("%Y-%m-%d")
        
        days_es = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
        months_es = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", 
                     "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        
        data['day'] = dt.day
        data['month'] = months_es[dt.month - 1]
        data['week'] = dt.isocalendar()[1]

    def _apply_smart_category(self, data):
        """
        Consulta la base de datos para ver si este comercio ya tiene 
        una categoría/subcategoría frecuente.
        """
        merchant = data.get('merchant')
        if merchant:
            suggested_cat, suggested_sub = self.db_manager.get_most_frequent_category(merchant)
            if suggested_cat:
                logger.info(f"[BULB] Smart Category aplicada para {merchant}: {suggested_cat} ({suggested_sub})")
                data['category'] = suggested_cat
                if suggested_sub:
                    data['subcategory'] = suggested_sub
            else:
                logger.info(f"new merchant found: {merchant}")

    async def send_confirmation_message(self, chat_id, context, data):
        """
        Envía un mensaje con el resumen del gasto y botones interactivos.
        """
        # Formatear mensaje resumen
        subcategory = data.get('subcategory')
        sub_info = f"({subcategory})" if subcategory else ""

        msg_text = (
            f"📝 **Confirma los datos del Gasto**:\n\n"
            f"📅 **Fecha**: {data.get('date')} ({data.get('day')} {data.get('month')})\n"
            f"🏪 **Tienda**: {data.get('merchant')}\n"
            f"💰 **Total**: ${data.get('total')}\n"
            f"🏷️ **Categoría**: {data.get('category')} {sub_info}\n"
            f"💳 **Método**: {data.get('payment_method')}\n"
            f"🔄 **Tipo**: {data.get('type', 'Normal')}\n"
            f"📄 **Detalle**: {data.get('details')}\n\n"
            f"¿Es correcto? 👇"
        )
        
        # Teclado Inline (Botones)
        keyboard = [
            [InlineKeyboardButton("✅ Confirmar y Guardar", callback_data="confirm")],
            [InlineKeyboardButton("📂 Cambiar Categoría", callback_data="edit_category")],
            [InlineKeyboardButton("🏷️ Cambiar Subcategoría", callback_data="ask_subcategory")],
            [InlineKeyboardButton("💳 Cambiar Método", callback_data="edit_payment")],
            [InlineKeyboardButton("💰 Préstamo o Deuda", callback_data="edit_type")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=chat_id, text=msg_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja los clics en los botones inline (Confirmar, Editar, Cancelar).
        """
        query = update.callback_query
        chat_id = update.effective_chat.id
        
        if self.paused:
            await query.answer("⚠️ El bot está en pausa. Envía /start.")
            return

        await query.answer()
        
        data = query.data
        
        if chat_id not in self.pending_expenses:
            await query.edit_message_text(text="⚠️ La sesión ha expirado o el gasto ya fue procesado. Por favor sube el ticket de nuevo.")
            return

        expense_data = self.pending_expenses[chat_id]

        if data == "confirm":
             # Limpiar campos auxiliares antes de guardar
            save_data = expense_data.copy()
            if 'type' not in save_data:
                save_data['type'] = 'normal'
                
            # Enviar a la API del Server en lugar de escribir directo
            try:
                response = requests.post(self.api_url, json=save_data, timeout=5)
                
                if response.status_code == 200 and response.json().get('success'):
                    final_text = (
                        f"✅ **Gasto Guardado Exitosamente (vía API)**\n"
                        f"📅 {expense_data.get('date')} | 💰 ${expense_data.get('total')}\n"
                        f"📂 {expense_data.get('category')} | {expense_data.get('subcategory', '')}\n"
                        f"💳 {expense_data.get('payment_method')}\n"
                        f"🏪 {expense_data.get('merchant')}"
                    )
                    logger.info("[OK] Gasto guardado vía API.")
                else:
                    err_msg = response.json().get('message') if response.headers.get('content-type') == 'application/json' else response.text
                    final_text = f"[WARN] Error del Servidor: {err_msg}"
                    logger.error(f"Error API: {response.status_code} - {response.text}")

            except requests.exceptions.RequestException as e:
                final_text = f"[WARN] Error de Conexión con Servidor: {str(e)}"
                logger.error(f"Error de conexión API: {e}")
            
            await query.edit_message_text(text=final_text, parse_mode='Markdown')
            # Limpiar estado
            del self.pending_expenses[chat_id]
            self._save_pending_expenses()

        elif data == "cancel":
            await query.edit_message_text(text="[X] Operación cancelada. El gasto ha sido descartado.")
            del self.pending_expenses[chat_id]
            self._save_pending_expenses()

        elif data == "ask_subcategory":
            await query.edit_message_text(
                text=(
                    f"🏷️ **Cambiar Subcategoría**\n\n"
                    f"Escribe en el chat:\n"
                    f"`cambia subcategoria por: [Tu subcategoría]`\n\n"
                    f"Ejemplos: Restaurante, Supermercado, Uber, Gasolina, etc."
                ),
                parse_mode='Markdown'
            )


        elif data == "edit_category":
            # Mostrar menú de categorías
            categories = ["Alimentos", "Transporte", "Hogar", "Ropa", "Salud", "Entretenimiento", "Otros"]
            keyboard = []
            
            # Crear grid de botones (2 columnas)
            row = []
            for cat in categories:
                row.append(InlineKeyboardButton(cat, callback_data=f"set_cat_{cat}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="back_to_confirm")])
            
            await query.edit_message_text(
                text=f"📂 **Selecciona la nueva categoría**\n(Actual: {expense_data.get('category')}):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "edit_payment":
            methods = ["Tarjeta", "Efectivo", "Transferencia"]
            keyboard = [[InlineKeyboardButton(m, callback_data=f"set_method_{m}") for m in methods]]
            keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="back_to_confirm")])
            
            await query.edit_message_text(
                text=f"💳 **Selecciona el método de pago**\n(Actual: {expense_data.get('payment_method')}):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif data == "edit_type":
            keyboard = [
                [InlineKeyboardButton("🟡 Préstamo (Por Cobrar)", callback_data="set_type_loan")],
                [InlineKeyboardButton("🔴 Deuda (Por Pagar)", callback_data="set_type_debt")],
                [InlineKeyboardButton("⚪ Normal (Gasto)", callback_data="set_type_normal")],
                [InlineKeyboardButton("🔙 Volver", callback_data="back_to_confirm")]
            ]
            await query.edit_message_text(
                text=f"🔄 **Selecciona el tipo de movimiento**\n(Actual: {expense_data.get('type', 'Normal')}):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif data.startswith("set_type_"):
            new_type = data.split("_", 2)[2]
            # Mapear a nombres más bonitos
            type_map = {'debt': 'Deuda', 'loan': 'Prestamo', 'normal': 'Normal'}
            self.pending_expenses[chat_id]['type'] = type_map.get(new_type, new_type)
            self._save_pending_expenses()
            await self.send_confirmation_message(chat_id, context, self.pending_expenses[chat_id])

        elif data.startswith("set_cat_"):
            new_cat = data.split("_", 2)[2]
            self.pending_expenses[chat_id]['category'] = new_cat
            self._save_pending_expenses()
            await self.send_confirmation_message(chat_id, context, self.pending_expenses[chat_id])
            
        elif data.startswith("set_method_"):
            new_method = data.split("_", 2)[2]
            self.pending_expenses[chat_id]['payment_method'] = new_method
            self._save_pending_expenses()
            await self.send_confirmation_message(chat_id, context, self.pending_expenses[chat_id])


        elif data == "back_to_confirm":
            await self.send_confirmation_message(chat_id, context, expense_data)

    async def handle_visual_command(self, chat_id, context):
        """Genera y envía el link al dashboard web."""
        await context.bot.send_message(
            chat_id=chat_id, 
            text="📊 **Dashboard Interactivo**\n\n"
                 "Abre el dashboard en tu navegador:\n"
                 f"🔗 {self.dashboard_url}\n\n"
                 "✨ **Nuevas funciones:**\n"
                 "• Ver todos tus gastos organizados\n"
                 "• Marcar préstamos/deudas como pagados\n"
                 "• Gráficos interactivos por categoría y semana\n\n"
                 "[BULB] Asegúrate de que la aplicación esté corriendo.",
            parse_mode='Markdown'
        )

    async def handle_stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detiene los servicios externos y pone el bot en pausa."""
        chat_id = update.effective_chat.id
        
        if self.paused:
            await context.bot.send_message(chat_id=chat_id, text="El bot ya está en pausa.")
            return

        self.paused = True
        logger.info(f"Bot puesto en pausa por el usuario {update.effective_user.first_name}")

        # Notificar a la GUI/Servicios
        if self.on_pause_callback:
            if asyncio.iscoroutinefunction(self.on_pause_callback):
                await self.on_pause_callback()
            else:
                self.on_pause_callback()

        await context.bot.send_message(
            chat_id=chat_id,
            text="🛑 **Bot en Pausa**\n\n"
                 "Todos los procesos han sido detenidos temporalmente.\n\n"
                 "👉 Para volver a activar el bot, envía `/start`.",
            parse_mode='Markdown'
        )

    def stop(self):
        """Detiene el bot permanentemente (Cierre de aplicación)."""
        logger.info("Cerrando aplicación del bot...")
        if self.scheduler.running:
            self.scheduler.shutdown()
        self._running = False

    # ===== Notification Command Handlers =====
    
    async def handle_budget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /presupuesto command to set budget for a category.
        Usage: /presupuesto ALIMENTOS 5000
        """
        chat_id = update.effective_chat.id
        
        if not context.args or len(context.args) < 2:
            await context.bot.send_message(
                chat_id=chat_id,
                text="[X] **Uso incorrecto**\\n\\n"
                     "Formato: `/presupuesto [CATEGORÍA] [MONTO]`\\n\\n"
                     "Ejemplo: `/presupuesto ALIMENTOS 5000`",
                parse_mode='Markdown'
            )
            return
        
        category = context.args[0].upper()
        try:
            amount = float(context.args[1])
            
            success, message = self.db_manager.add_budget(category, amount)
            
            if success:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ {message}",
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {message}",
                    parse_mode='Markdown'
                )
        except ValueError:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ El monto debe ser un número válido.",
                parse_mode='Markdown'
            )
    
    async def handle_budgets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /presupuestos command to view all budgets."""
        chat_id = update.effective_chat.id
        
        budgets = self.db_manager.get_budgets()
        
        if not budgets:
            await context.bot.send_message(
                chat_id=chat_id,
                text="📊 **Presupuestos**\\n\\n"
                     "No tienes presupuestos configurados.\\n\\n"
                     "Usa `/presupuesto [CATEGORÍA] [MONTO]` para crear uno.",
                parse_mode='Markdown'
            )
            return
        
        # Get current month spending
        now = datetime.datetime.now()
        months_es = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        current_month = months_es[now.month - 1]
        spending = self.db_manager.get_monthly_spending_by_category(current_month, now.year)
        
        msg = f"📊 **Presupuestos - {current_month} {now.year}**\\n\\n"
        
        for budget in budgets:
            cat = budget['category']
            limit = budget['monthly_limit']
            spent = spending.get(cat, 0.0)
            percentage = (spent / limit * 100) if limit > 0 else 0
            
            emoji = "🟢" if percentage < 70 else "🟡" if percentage < 90 else "🔴"
            
            msg += f"{emoji} **{cat}**\\n"
            msg += f"   Gastado: ${spent:.2f} / ${limit:.2f}\\n"
            msg += f"   Progreso: {percentage:.1f}%\\n\\n"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode='Markdown'
        )
    
    async def handle_summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resumen command to get weekly summary."""
        chat_id = update.effective_chat.id
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="[CHART_BAR] Generando resumen semanal...",
            parse_mode='Markdown'
        )
        
        summary = self.notification_service.generate_weekly_summary()
        message = self.notification_service.format_weekly_summary_message(summary)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown'
        )
    
    # ===== Notification Scheduler Methods =====
    
    def _setup_notification_scheduler(self):
        """Setup scheduled notifications."""
        # Daily budget check at 8 PM (Mexico City time)
        self.scheduler.add_job(
            self._send_budget_alerts,
            CronTrigger(hour=20, minute=0, timezone='America/Mexico_City'),
            id='budget_alerts',
            replace_existing=True
        )
        
        # Weekly summary on Sundays at 6 PM
        self.scheduler.add_job(
            self._send_weekly_summary,
            CronTrigger(day_of_week='sun', hour=18, minute=0, timezone='America/Mexico_City'),
            id='weekly_summary',
            replace_existing=True
        )
        
        # Debt reminders every Monday at 9 AM
        self.scheduler.add_job(
            self._send_debt_reminders,
            CronTrigger(day_of_week='mon', hour=9, minute=0, timezone='America/Mexico_City'),
            id='debt_reminders',
            replace_existing=True
        )
        
        logger.info("Notification scheduler configured")
    
    async def _send_budget_alerts(self):
        """Send budget alert notifications."""
        if not self.chat_id:
            logger.warning("No chat_id configured for notifications")
            return
        
        try:
            alerts = self.notification_service.check_budget_alerts()
            
            if alerts:
                message = self.notification_service.format_budget_alert_message(alerts)
                await self.application.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Sent {len(alerts)} budget alerts")
        except Exception as e:
            logger.error(f"Error sending budget alerts: {e}", exc_info=True)
    
    async def _send_weekly_summary(self):
        """Send weekly summary notification."""
        if not self.chat_id:
            logger.warning("No chat_id configured for notifications")
            return
        
        try:
            summary = self.notification_service.generate_weekly_summary()
            message = self.notification_service.format_weekly_summary_message(summary)
            
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("Sent weekly summary")
        except Exception as e:
            logger.error(f"Error sending weekly summary: {e}", exc_info=True)
    
    async def _send_debt_reminders(self):
        """Send debt reminder notifications."""
        if not self.chat_id:
            logger.warning("No chat_id configured for notifications")
            return
        
        try:
            debts = self.notification_service.check_debt_reminders()
            
            if debts:
                message = self.notification_service.format_debt_reminder_message(debts)
                await self.application.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Sent reminders for {len(debts)} pending debts/loans")
        except Exception as e:
            logger.error(f"Error sending debt reminders: {e}", exc_info=True)


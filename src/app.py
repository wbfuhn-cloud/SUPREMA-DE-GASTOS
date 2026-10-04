import customtkinter as ctk
import sys
import os

# Ensure project root is on sys.path when running as script
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.infra.encoding import force_utf8_encoding

force_utf8_encoding()

import logging
import threading
import webbrowser
import time
import socket
import ctypes
import queue

ES_CONTINUOUS       = 0x80000000
ES_SYSTEM_REQUIRED  = 0x00000001

def prevent_sleep():
    if os.name == 'nt':
        def _task():
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                logging.info("Prevención de reposo activada (Windows).")
            except Exception as e:
                logging.warning(f"Error al activar prevención de reposo: {e}")
        threading.Thread(target=_task, daemon=True).start()

def allow_sleep():
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            logging.info("Prevención de reposo desactivada.")
        except Exception as e:
            logging.warning(f"Error al desactivar prevención de reposo: {e}")

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

from src.bot import ExpenseBot
from src.config import Config
from src.server import run_server
from src.tunnel import TunnelManager
from src.monitor import hilo_baz, stop_event as monitor_stop_event
from src.updater import start_background_update_check
from src.service_supervisor import start_bolsa_worker, stop_bolsa_worker


class TextHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class ConfigurationWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_save_callback=None):
        super().__init__(parent)
        self.on_save_callback = on_save_callback

        self.units, self.default_unit, self.setup_completed = Config.get_units_config()

        title = "Modificar Datos de Configuración" if self.setup_completed else "Configuración Inicial - Departamentos"
        self.title(title)
        self.geometry("500x600")
        self._init_ui()
        self.attributes("-topmost", True)

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_text = "Modificar Unidades / Departamentos" if self.setup_completed else "Gestión de Unidades / Departamentos"
        ctk.CTkLabel(self, text=header_text, font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=20, pady=20
        )

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Unidades Actuales")
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self._refresh_unit_list()

        add_frame = ctk.CTkFrame(self)
        add_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.unit_entry = ctk.CTkEntry(add_frame, placeholder_text="Nombre de Unidad (Ej: A-101)")
        self.unit_entry.pack(side="left", padx=10, pady=10, expand=True, fill="x")

        ctk.CTkButton(add_frame, text="Agregar", width=80, command=self.add_unit).pack(
            side="right", padx=10, pady=10
        )

        btn_text = "Actualizar Configuración" if self.setup_completed else "Guardar Cambios y Finalizar"
        ctk.CTkButton(self, text=btn_text, fg_color="green", command=self.save_config).grid(
            row=3, column=0, padx=20, pady=20
        )

    def _refresh_unit_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        _PROTECTED = {"GENERAL", "ADMIN", "MANTENIMIENTO"}
        for unit in self.units:
            frame = ctk.CTkFrame(self.scroll_frame)
            frame.pack(fill="x", pady=2, padx=5)
            ctk.CTkLabel(frame, text=unit, anchor="w").pack(side="left", padx=10, pady=5)
            if unit not in _PROTECTED:
                ctk.CTkButton(
                    frame, text="", width=30, height=20, fg_color="red",
                    command=lambda u=unit: self.remove_unit(u)
                ).pack(side="right", padx=5)

    def add_unit(self):
        new_unit = self.unit_entry.get().strip().upper()
        if not new_unit:
            return
        if new_unit in self.units:
            logging.warning(f"La unidad '{new_unit}' ya existe.")
            return
        self.units.append(new_unit)
        self.units.sort()
        self.unit_entry.delete(0, "end")
        self._refresh_unit_list()

    def remove_unit(self, unit: str):
        if unit in self.units:
            self.units.remove(unit)
            self._refresh_unit_list()

    def save_config(self):
        success, msg = Config.save_units_config(self.units, self.default_unit, setup_completed=True)
        if success:
            logging.info(f"{msg}")
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        else:
            logging.error(f"{msg}")


class BotGUI(ctk.CTk):
    _HEARTBEAT_INTERVAL = 600

    def __init__(self):
        super().__init__()

        self.title("Asistente Financiero - Monitor")
        self.geometry("900x600")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.token      = Config.TELEGRAM_TOKEN
        self.google_key = Config.GOOGLE_API_KEY

        self.bot_thread:   threading.Thread | None = None
        self.bot_instance: ExpenseBot | None       = None
        self.bolsa_worker_process = None
        self.stop_event = threading.Event()
        self.log_queue: queue.Queue = queue.Queue()

        self._init_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._setup_logging()

        self.after(100, self.process_log_queue)
        self.after(500, self.check_initial_setup)

    def check_initial_setup(self):
        _, _, setup_completed = Config.get_units_config()
        if setup_completed:
            self.start_bot()
        else:
            logging.info("Primera ejecución detectada. Por favor configura las unidades.")
            self._open_config_window()

    def _open_config_window(self):
        ConfigurationWindow(self, on_save_callback=self.start_bot)

    def _setup_logging(self):
        handler = TextHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.start_button = ctk.CTkButton(btn_frame, text=" Iniciar Bot", command=self.start_bot)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ctk.CTkButton(btn_frame, text=" Detener", state="disabled",
                                          fg_color="red", command=self.stop_bot)
        self.stop_button.pack(side="left", padx=5)

        ctk.CTkButton(btn_frame, text=" Config", command=self._open_config_window).pack(
            side="left", padx=5
        )

        self.status_label = ctk.CTkLabel(btn_frame, text="Estado: DETENIDO", text_color="red")
        self.status_label.pack(side="right", padx=10)

        self.log_text = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.log_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

    def start_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            logging.warning("El bot ya está en ejecución.")
            return

        self.stop_event.clear()
        self.start_button.configure(state="disabled", text="Iniciando...")
        self.stop_button.configure(state="normal")
        self.status_label.configure(text="Estado: INICIANDO...", text_color="yellow")

        def background_init():
            try:
                def find_free_port(start_port, max_port=5150):
                    import socket
                    for p in range(start_port, max_port):
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.bind(('0.0.0.0', p))
                            return p
                        except OSError:
                            pass
                    return start_port

                base_port = int(os.environ.get("APP_PORT", 5050))
                port = find_free_port(base_port)
                os.environ["APP_PORT"] = str(port)  # Guardar para el túnel y reinicios
                
                logging.info(f"Iniciando Servidor Web (Puerto {port}) de inmediato...")
                local_ip = get_local_ip()
                dashboard_url = f"http://{local_ip}:{port}/dashboard"
                
                # Instanciar el bot primero para pasarlo al servidor
                logging.info("Cargando componentes del Bot...")
                self.bot_instance = ExpenseBot(
                    self.token,
                    self.google_key,
                    dashboard_url=dashboard_url, # Se actualizará luego si hay túnel
                    on_pause_callback=self.pause_services,
                    on_resume_callback=self.resume_services,
                )
                self.bot_instance._tunnel_manager = TunnelManager
                
                from src.server import app as flask_app
                flask_app.config['BOT_INSTANCE'] = self.bot_instance
                
                server_thread = threading.Thread(
                    target=run_server,
                    kwargs={'port': port, 'bot_instance': self.bot_instance, 'start_jobs': False},
                    daemon=True
                )
                server_thread.start()

                # Bolsa ejecuta descargas, indicadores y seguimiento en otro
                # proceso para no retrasar Telegram, correo BAZ ni la GUI.
                self.bolsa_worker_process = start_bolsa_worker()
                logging.info("Worker de Bolsa iniciado como proceso independiente (PID %s).",
                             self.bolsa_worker_process.pid)

                # Mostrar "EN LÍNEA" casi de inmediato ya que el servidor levanta rápido
                self.after(0, lambda: self.status_label.configure(
                    text="Estado: EN LÍNEA", text_color="green"
                ))

                # Abrir dashboard local
                logging.info(f"Dashboard local: {dashboard_url}")
                logging.info("=" * 60)
                self.after(1000, lambda: webbrowser.open(dashboard_url))

                # Iniciar el monitor de correos de gastos.
                logging.info("Iniciando Monitor BAZ...")
                monitor_stop_event.clear()
                t_baz = threading.Thread(target=hilo_baz, daemon=True)
                t_baz.start()

                # Lanzar el túnel en un hilo paralelo para NO BLOQUEAR
                def _start_tunnel_async():
                    logging.info("Iniciando Túnel Cloudflare en segundo plano...")
                    public_url = TunnelManager.start_tunnel(port=port)
                    if public_url:
                        logging.info(f"URL PÚBLICA (TÚNEL): {public_url}/dashboard")
                        self.bot_instance.dashboard_url = f"{public_url}/dashboard"
                
                threading.Thread(target=_start_tunnel_async, daemon=True).start()

                logging.info("--- SISTEMA ACTIVO ---")
                self.bot_instance.run()

            except Exception as e:
                logging.error(f"Error fatal en bot/túnel: {e}", exc_info=True)
                from tkinter import messagebox
                self.after(0, lambda: messagebox.showerror("Error del Bot", f"El bot se detuvo por un error:\n{e}"))
            finally:
                monitor_stop_event.set()
                stop_bolsa_worker(self.bolsa_worker_process)
                self.bolsa_worker_process = None
                self.after(0, self._reset_ui)

        self.bot_thread = threading.Thread(target=background_init, daemon=True)
        self.bot_thread.start()

        prevent_sleep()
        self.after(2000, self.start_heartbeat)

    def start_heartbeat(self):
        def _loop():
            tick = 0
            while not self.stop_event.wait(timeout=10):
                tick += 1
                if tick * 10 < self._HEARTBEAT_INTERVAL:
                    continue
                tick = 0

                now = time.strftime("%H:%M")
                url = TunnelManager.get_url()
                if url:
                    try:
                        import requests
                        requests.get(f"{url}/dashboard", timeout=10)
                        logging.info(f"[{now}] Sistema activo — túnel {url} refrescado.")
                    except Exception:
                        logging.warning(f"[{now}] Sistema activo — no se pudo contactar el túnel.")
                else:
                    logging.warning("Túnel inactivo. Reinicia si el link no responde.")

        threading.Thread(target=_loop, daemon=True).start()

    def _reset_ui(self):
        self.start_button.configure(state="normal", text=" Iniciar Bot")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Estado: DETENIDO", text_color="red")

    def stop_bot(self):
        if "DETENIENDO" in self.status_label.cget("text"):
            return

        logging.info("Deteniendo bot y cerrando servicios...")
        self.status_label.configure(text="Estado: DETENIENDO...", text_color="orange")
        self.stop_event.set()
        monitor_stop_event.set()

        def _trigger():
            if self.bot_instance:
                try:
                    self.bot_instance.stop()
                except Exception as e:
                    logging.error(f"Error al detener bot: {e}")
            self.pause_services()
            stop_bolsa_worker(self.bolsa_worker_process)
            self.bolsa_worker_process = None

        threading.Thread(target=_trigger, daemon=True).start()
        allow_sleep()
        self._wait_for_stop()

    def _wait_for_stop(self):
        if self.bot_thread and self.bot_thread.is_alive():
            self.after(200, self._wait_for_stop)
        else:
            self._reset_ui()
            logging.info("Bot detenido completamente.")

    def pause_services(self):
        logging.info("Pausando servicios externos...")
        TunnelManager.stop_tunnel()
        self.after(0, lambda: self.status_label.configure(text="Estado: EN PAUSA", text_color="orange"))
        logging.info("Túnel detenido. Servidor web permanece activo.")

    def resume_services(self):
        logging.info("Reanudando servicios externos...")

        def _restart():
            port = int(os.environ.get("APP_PORT", 5050))
            public_url = TunnelManager.start_tunnel(port=port)
            if public_url and self.bot_instance:
                self.bot_instance._dashboard_url_static = f"{public_url}/dashboard"
                logging.info(f"URL del Bot actualizada: {public_url}/dashboard")
            self.after(0, lambda: self.status_label.configure(text="Estado: EN LÍNEA", text_color="green"))
            logging.info("Servicios reanudados.")

        threading.Thread(target=_restart, daemon=True).start()

    def on_closing(self):
        logging.info("Cerrando aplicación...")
        try:
            if self.bot_instance:
                threading.Thread(target=self.bot_instance.stop, daemon=True).start()
            stop_bolsa_worker(self.bolsa_worker_process)
            self.bolsa_worker_process = None
            TunnelManager.stop_tunnel()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_log_queue)


if __name__ == "__main__":
    # Consulta GitHub en segundo plano. Un fallo de red nunca bloquea el programa.
    start_background_update_check()
    app = BotGUI()
    app.mainloop()

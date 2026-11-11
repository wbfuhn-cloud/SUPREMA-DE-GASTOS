import logging
import subprocess
import time
import re
import os
import threading
import sys

# Configurar logger
logger = logging.getLogger(__name__)

class TunnelManager:
    _public_url = None
    _process = None
    _stop_event = None
    _thread = None

    @classmethod
    def start_tunnel(cls, port=5050):
        """
        Inicia un tunel Cloudflare al puerto especificado.
        """
        # Detener cualquier instancia previa
        cls.stop_tunnel()

        logger.info("[TUNNEL] Iniciando Cloudflare Tunnel...")
        
        # Comando para ejecutar cloudflared
        # Asumimos que cloudflared está en el PATH o en la raíz del proyecto
        # Buscamos si existe cloudflared.exe en la carpeta actual o en tools/
        
        # Rutas posibles
        possible_paths = [
            "cloudflared", 
            "cloudflared.exe",
            os.path.join(os.getcwd(), "cloudflared.exe"),
            os.path.join(os.getcwd(), "tools", "cloudflared.exe")
        ]
        
        executable = "cloudflared" # Default system path
        
        # Verificar si existe en rutas locales
        for path in possible_paths:
            if os.path.isabs(path) and os.path.exists(path):
                executable = path
                break
        
        cmd = [executable, "tunnel", "--url", f"http://127.0.0.1:{port}"]

        try:
            # check if cloudflared exists/runs
            try:
                # Si es ruta absoluta, chequeamos archivo. Si es comando, chequeamos execution
                if os.path.isabs(executable):
                     if not os.path.exists(executable):
                         raise FileNotFoundError
                else:
                    subprocess.run([executable, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.info("[WARN] 'cloudflared' no encontrado localmente. Intentando descargar automaticamente...")
                
                # Check Architecture (Assuming 64bit windows for this user context, but being safe)
                download_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
                filename = "cloudflared.exe"
                
                try:
                    import requests  # type: ignore
                    logger.info(f"[DOWNLOAD] Descargando cloudflared desde {download_url}...")
                    response = requests.get(download_url, timeout=30)
                    response.raise_for_status()
                    
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                        
                    logger.info("[OK] Cloudflared descargado exitosamente.")
                    executable = os.path.abspath(filename)
                    cmd[0] = executable # Update command with new path
                    
                except Exception as dl_error:
                    logger.error(f"[FAIL] Error al descargar cloudflared: {dl_error}")
                    print("[FAIL] Error: No se pudo descargar 'cloudflared.exe' automaticamente.")
                    return None

            # Usar Popen para capturar salida en tiempo real
            # Cloudflare escribe a stderr
            cls._process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
            
            # Hilo para leer logs y extraer URL
            cls._stop_event = threading.Event()
            cls._public_url = None
            
            # Función para leer el output y buscar la URL
            def read_stream():
                url_mined = False
                while TunnelManager._stop_event and not TunnelManager._stop_event.is_set():
                    proc = TunnelManager._process
                    if not proc or proc.poll() is not None:
                        break
                        
                    # Leer linea de stderr
                    if not proc.stderr:
                        break
                        
                    line = proc.stderr.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                        
                    # Loguear salida para debug (opcional, puede ser ruidoso)
                    # logger.debug(f"Cloudflare: {line.strip()}")
                    
                    # Buscar URL .trycloudflare.com
                    # Ejemplo regex: https://[a-z0-9-]+\.trycloudflare\.com
                    if not url_mined:
                        match = re.search(r'\|\s*(https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com)\s*\|\s*$', line, re.IGNORECASE)
                        if match:
                            TunnelManager._public_url = match.group(1)
                            url_mined = True
                            logger.info(f"[TUNNEL] Tunel Cloudflare Activo: {TunnelManager._public_url}")
                            print(f"\n[TUNNEL] DASHBOARD PUBLICO: {TunnelManager._public_url}/dashboard\n")
            
            cls._thread = threading.Thread(target=read_stream, daemon=True)
            cls._thread.start()
            
            # Esperar un momento a que se genere la URL
            print("[WAIT] Esperando URL de Cloudflare...")
            for i in range(15): # Esperar hasta 15 segundos
                if cls._public_url:
                    return cls._public_url
                time.sleep(1)
                
            if not cls._public_url:
                 logger.warning("[WARN] Cloudflare inició pero no se pudo obtener la URL en 15 segundos. Revisa tu conexión.")
                 # No matamos el proceso, tal vez aparezca despues, pero retornamos None
            
            return cls._public_url

        except Exception as e:
            logger.error(f"Error CRITICO al iniciar Cloudflare: {e}")
            return None

    @classmethod
    def get_url(cls):
        return cls._public_url

    @classmethod
    def stop_tunnel(cls):
        """Detiene el proceso de Cloudflare"""
        if cls._stop_event:
            cls._stop_event.set()
            
        if cls._process:
            try:
                logger.info("Deteniendo proceso Cloudflare...")
                # Intentar terminar suavemente
                cls._process.terminate()
                try:
                    cls._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    logger.warning("Cloudflare no respondió a terminate, forzando kill...")
                    cls._process.kill()
                    
                logger.info("Cloudflare detenido.")
            except Exception as e:
                logger.error(f"Error stopping cloudflare: {e}")
            finally:
                cls._process = None

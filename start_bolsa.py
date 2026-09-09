import subprocess
import time
import urllib.request
import webbrowser
import sys
import os

def check_health(url):
    try:
        response = urllib.request.urlopen(url, timeout=2)
        return response.getcode() == 200
    except Exception:
        return False

def main():
    print("=====================================")
    print(" Iniciando Escáner de Bolsa (Fase 1) ")
    print("=====================================")
    
    # Iniciar el servidor
    # Usamos sys.executable para mantener el entorno virtual activo si lo hay
    server_process = subprocess.Popen([sys.executable, 'src/server.py'])
    
    health_url = "http://127.0.0.1:5050/api/bolsa/health"
    max_retries = 30
    ready = False
    
    print("Esperando a que el servidor reporte estado 'ready'...")
    for i in range(max_retries):
        if check_health(health_url):
            ready = True
            break
        time.sleep(1)
        print(".", end="", flush=True)
        
    print()
    if ready:
        print("¡Servidor diagnosticado como OK! Abriendo visor...")
        webbrowser.open("http://127.0.0.1:5050/bolsa")
        
        print("Presiona Ctrl+C para detener el servidor.")
        try:
            server_process.wait()
        except KeyboardInterrupt:
            print("\nDeteniendo servidor de bolsa...")
            server_process.terminate()
    else:
        print("Error: El servidor no respondió en el tiempo esperado.")
        print("Posibles causas: puerto 5050 en uso, falta de dependencias o error de sintaxis en src/server.py")
        server_process.terminate()
        sys.exit(1)

if __name__ == '__main__':
    main()

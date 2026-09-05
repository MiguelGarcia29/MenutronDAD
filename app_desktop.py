import sys
import os
import threading
import time
import subprocess
import tempfile
from pathlib import Path
import uvicorn
from backend.main import app

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=18492, log_level="error")

def open_edge_fallback(url):
    print("PyWebView falló. Iniciando ventana alternativa en Microsoft Edge...")
    
    # Creamos una ruta para un perfil temporal dedicado a la app
    temp_profile_dir = Path(tempfile.gettempdir()) / "GestorCocinaEdgeProfile"
    
    # Lanzamos Edge en modo App con un perfil aislado
    cmd = [
        "msedge",
        f"--app={url}",
        f"--user-data-dir={temp_profile_dir}",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    
    try:
        # subprocess.run SIN shell=True BLOQUEA la ejecución de Python 
        # hasta que el usuario cierra la ventana de Edge
        subprocess.run(cmd, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Si por alguna razón extraña no tiene Edge, abre el navegador por defecto
        import webbrowser
        webbrowser.open(url)
        
        # Mantenemos el servidor vivo esperando un Ctrl+C en consola
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    url = "http://127.0.0.1:18492"
    
    # 1. Inicia el servidor FastAPI en un hilo en segundo plano (daemon=True)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    time.sleep(1)  # Tiempo de espera para que arranque FastAPI

    # 2. Intenta abrir con PyWebView (Plan A)
    try:
        import webview
        
        webview.create_window(
            title="MenutronDAD - Por favor reportarme todo lo que necesiteis, bug, mejoras, etc. - MiguelDAD",
            url=url,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
        
        # Si esto lanza un RuntimeError (error de .NET/DLL), saltará al except
        webview.start(gui='edgechromium')
        
    except Exception as e:
        # 3. Plan B: Si pywebview falla por cualquier motivo, usa Edge
        print(f"Error detectado en PyWebView: {e}")
        open_edge_fallback(url)

    # Cuando se cierra PyWebView o Edge, el hilo principal llega aquí
    # y el programa se cierra de forma limpia finalizando el servidor.
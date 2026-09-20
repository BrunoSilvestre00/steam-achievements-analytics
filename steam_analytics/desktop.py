"""Inicializador da versão desktop para Windows."""

import os
import threading
import time
import webbrowser
from urllib.request import urlopen

import uvicorn

from steam_analytics.config import load_env
from steam_analytics.web import app


def main():
    load_env()
    host = os.environ.get("STEAM_ANALYTICS_HOST", "127.0.0.1")
    port = int(os.environ.get("STEAM_ANALYTICS_PORT", "8000"))
    url = f"http://{host}:{port}"

    def open_browser():
        for _ in range(40):
            try:
                with urlopen(url, timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=host, port=port, reload=False, log_config=None, access_log=False)


if __name__ == "__main__":
    main()

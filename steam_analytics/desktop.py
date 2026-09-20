"""Janela desktop mínima para controlar o servidor local."""

import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import uvicorn
from PIL import Image

from steam_analytics.config import ROOT, load_env
from steam_analytics.web import app

# Shared with the web application's cool-blue theme.
BG = "#050d1c"
SURFACE = "#0b1a30"
SURFACE_ALT = "#0b2445"
TEXT = "#eef7ff"
MUTED = "#9cb6cc"
ACCENT = "#8ddcff"
BLUE = "#61d4f5"
DANGER = "#f0a3a8"


def resource_path(relative_path):
    """Resolve assets both from source and from a PyInstaller distribution."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / relative_path


def find_available_port(host, preferred):
    for port in range(preferred, preferred + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"Não foi encontrada uma porta livre entre {preferred} e {preferred + 29}.")


class DesktopController:
    def __init__(self):
        load_env()
        self.host = os.environ.get("STEAM_ANALYTICS_HOST", "127.0.0.1")
        preferred_port = int(os.environ.get("STEAM_ANALYTICS_PORT", "80"))
        self.port = find_available_port(self.host, preferred_port)
        self.url = f"http://{self.host}:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(app, host=self.host, port=self.port, reload=False, log_config=None, access_log=False)
        )
        self.server_thread = threading.Thread(target=self._run_server, name="steam-analytics-server", daemon=True)
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("Steam Achievement Analytics")
        self.root.geometry("640x760")
        self.root.minsize(600, 700)
        self.root.configure(fg_color=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self._build_ui()
        self._set_icon()
        self.server_thread.start()
        self.root.after(250, self._poll_server)

    @property
    def env_path(self):
        return ROOT / ".env"

    @property
    def server_error_path(self):
        return ROOT / "desktop-server-error.log"

    def _run_server(self):
        try:
            self.server.run()
        except Exception as error:
            self.server_error_path.write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")

    def _label(self, parent, text, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=kwargs.pop("text_color", TEXT), **kwargs)

    def _build_ui(self):
        root = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        root.pack(fill="both", expand=True, padx=26, pady=24)
        header = ctk.CTkFrame(root, fg_color="transparent", corner_radius=0)
        header.pack(fill="x")
        logo_title_path = resource_path("steam_analytics/static/assets/logo-title.png")
        if logo_title_path.exists():
            self.logo_title_image = ctk.CTkImage(
                light_image=Image.open(logo_title_path),
                dark_image=Image.open(logo_title_path),
                size=(420, 51),
            )
            ctk.CTkLabel(header, text="", image=self.logo_title_image).pack(anchor="center", pady=(0, 8))
        card = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=16)
        card.pack(fill="x", pady=(10, 0))
        status_row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        status_row.pack(fill="x", padx=18, pady=(18, 0))
        self._label(status_row, "SERVIDOR LOCAL", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.status = self._label(status_row, "INICIANDO...", text_color=ACCENT, fg_color=SURFACE_ALT, corner_radius=7, font=ctk.CTkFont(size=12, weight="bold"))
        self.status.pack(side="right", padx=8, pady=4)
        self._label(card, self.url, text_color=MUTED, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=18, pady=(10, 18))
        self.open_button = ctk.CTkButton(card, text="Abrir aplicação no navegador", corner_radius=8, fg_color=ACCENT, hover_color=BLUE, text_color="#062538", border_width=1, border_color=ACCENT, font=ctk.CTkFont(size=13, weight="bold"), command=self.open_browser, state="disabled")
        self.open_button.pack(fill="x", padx=18, pady=(0, 18))

        config = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=16)
        config.pack(fill="x", pady=14)
        self._label(config, "CONFIGURAÇÃO", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=18, pady=(18, 0))
        self._label(config, "Steam Web API Key", text_color=MUTED, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=18, pady=(10, 5))
        ctk.CTkButton(
            config,
            text="Como gerar minha chave de API Steam?",
            height=24,
            fg_color="transparent",
            hover_color="#12304d",
            text_color=BLUE,
            font=ctk.CTkFont(size=11, underline=True),
            anchor="w",
            command=self.open_api_key_page,
        ).pack(anchor="w", padx=14, pady=(2, 6))
        self.api_key = tk.StringVar(value=os.environ.get("STEAM_API_KEY", ""))
        self.api_visible = False
        api_row = ctk.CTkFrame(config, fg_color="transparent", corner_radius=0)
        api_row.pack(fill="x", padx=18)
        self.api_entry = ctk.CTkEntry(api_row, textvariable=self.api_key, show="•", height=44, corner_radius=8, fg_color="#092333", border_color="#37708e", text_color=TEXT, font=ctk.CTkFont(size=13))
        self.api_entry.pack(side="left", fill="x", expand=True)
        self.eye_button = ctk.CTkButton(api_row, text="◉", width=48, height=44, corner_radius=8, fg_color="transparent", hover_color=SURFACE, border_width=1, border_color="#1c5b86", text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold"), command=self.toggle_api_visibility)
        self.eye_button.pack(side="left", padx=(8, 0))
        ctk.CTkButton(config, text="Salvar chave", height=42, corner_radius=8, fg_color="transparent", hover_color="#12304d", border_width=1, border_color="#1c5b86", text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"), command=self.save_config).pack(fill="x", padx=18, pady=(10, 0))
        ctk.CTkFrame(config, height=18, fg_color="transparent", corner_radius=0).pack()

        self.shortcut_button = ctk.CTkButton(
            root,
            text="Criar atalho na área de trabalho",
            height=24,
            corner_radius=8,
            fg_color="transparent",
            hover_color=SURFACE,
            text_color=BLUE,
            font=ctk.CTkFont(size=12, underline=True),
            command=self.create_shortcut,
        )
        self.shortcut_button.pack(anchor="w", pady=(0, 8))

        footer = ctk.CTkFrame(root, fg_color="transparent", corner_radius=0)
        footer.pack(fill="x", side="bottom", pady=(0, 0))
        footer_info = ctk.CTkFrame(footer, fg_color="transparent", corner_radius=0)
        footer_info.pack(side="left", anchor="w")
        self._label(footer_info, "Os dados ficam salvos localmente no SQLite.", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
        self._label(footer_info, "© 2026 Bruno Silvestre", text_color="#648ca4", font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(3, 0))
        ctk.CTkButton(footer, text="Encerrar aplicação", height=40, corner_radius=8, fg_color="transparent", hover_color="#3b2027", border_width=1, border_color="#8c4a51", text_color=DANGER, font=ctk.CTkFont(size=12, weight="bold"), command=self.request_close).pack(side="right")

    def _set_icon(self):
        assets = resource_path("steam_analytics/static/assets")
        icon_ico = assets / "favicon.ico"
        icon_png = assets / "favicon.png"
        if icon_ico.exists():
            try:
                self.root.iconbitmap(default=str(icon_ico))
            except tk.TclError:
                pass
        if icon_png.exists():
            self.icon = tk.PhotoImage(file=str(icon_png))
            self.root.iconphoto(True, self.icon)

    def _poll_server(self):
        if self.server.started:
            self.status.configure(text="ONLINE", text_color=ACCENT)
            self.open_button.configure(state="normal")
        elif self.server_thread.is_alive():
            self.root.after(250, self._poll_server)
        else:
            self.status.configure(text="ERRO AO INICIAR", text_color=DANGER)

    def open_browser(self):
        webbrowser.open(self.url)

    def open_api_key_page(self):
        webbrowser.open("https://steamcommunity.com/dev/apikey")

    def toggle_api_visibility(self):
        self.api_visible = not self.api_visible
        self.api_entry.configure(show="" if self.api_visible else "•")
        self.eye_button.configure(text="◌" if self.api_visible else "◉")

    def save_config(self):
        key = self.api_key.get().strip()
        self.env_path.write_text(f"STEAM_API_KEY={key}\n", encoding="utf-8")
        os.environ["STEAM_API_KEY"] = key
        messagebox.showinfo("Configuração salva", "A chave foi salva no arquivo .env.", parent=self.root)

    def create_shortcut(self):
        if getattr(self, "shortcut_in_progress", False):
            return
        self.shortcut_in_progress = True
        self.shortcut_button.configure(state="disabled", text="Criando atalho...")
        threading.Thread(target=self._create_shortcut_worker, name="steam-analytics-shortcut", daemon=True).start()

    def _create_shortcut_worker(self):
        target = Path(os.path.abspath(sys.executable))
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        shortcut = desktop / "Steam Achievement Analytics.lnk"

        def quote(value):
            return str(value).replace("'", "''")

        command = (
            "$shell=New-Object -ComObject WScript.Shell;"
            f"$link=$shell.CreateShortcut('{quote(shortcut)}');"
            f"$link.TargetPath='{quote(target)}';"
            f"$link.WorkingDirectory='{quote(target.parent)}';"
            f"$link.IconLocation='{quote(target)},0';$link.Save()"
        )
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
                check=True,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.root.after(0, self._shortcut_finished, None)
        except (OSError, subprocess.CalledProcessError) as error:
            self.root.after(0, self._shortcut_finished, error)

    def _shortcut_finished(self, error):
        self.shortcut_in_progress = False
        self.shortcut_button.configure(state="normal", text="Criar atalho na área de trabalho")
        if error is None:
            messagebox.showinfo("Atalho criado", "O atalho foi criado na área de trabalho.", parent=self.root)
        else:
            messagebox.showerror("Não foi possível criar o atalho", str(error), parent=self.root)

    def request_close(self):
        if messagebox.askyesno("Encerrar aplicação", "Deseja encerrar o servidor local e fechar o Steam Achievement Analytics?", parent=self.root):
            self.close()

    def close(self):
        if self.server_thread.is_alive():
            self.server.should_exit = True
            self.server_thread.join(timeout=5)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    DesktopController().run()

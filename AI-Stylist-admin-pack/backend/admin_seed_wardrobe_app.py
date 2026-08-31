"""
AI Stylist - Mini app local para cargar prendas a una cuenta.

Interfaz visual simple para armar el armario de otra persona sin entrar en la
terminal ni depender del script de consola. La lógica se reutiliza del script
admin_seed_wardrobe.py.
"""

import os
import io
import glob
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except Exception:
    rembg_remove = None
    REMBG_AVAILABLE = False

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

try:
    from database import guardar_prenda, get_connection
    import storage
    from ai import get_provider
except ImportError as e:
    raise SystemExit(f"❌ Error al importar módulos del backend: {e}")


def listar_todos_los_usuarios():
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, name FROM users ORDER BY id ASC")
        filas = [dict(f) for f in cur.fetchall()]
        cur.close()
        conn.close()
        return filas
    except Exception as e:
        raise RuntimeError(f"No se pudo leer la base de datos: {e}")


def _redimensionar_si_es_necesario(image_bytes: bytes, max_dim: int = 1920) -> bytes:
    if Image is None:
        raise RuntimeError("Falta Pillow. Instala dependencias con: pip install -r requirements.txt")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width > max_dim or height > max_dim or (width * height > 16000000):
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            fmt = img.format if img.format in ("PNG", "JPEG", "WEBP") else "JPEG"
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format=fmt, quality=85)
            return output.getvalue()
    except Exception:
        pass
    return image_bytes


def _quitar_fondo_local(image_bytes: bytes):
    if Image is None:
        raise RuntimeError("Falta Pillow. Instala dependencias con: pip install -r requirements.txt")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            return image_bytes, "image/png"
    except Exception:
        pass

    if rembg_remove is None:
        return image_bytes, "image/jpeg"

    try:
        output_png = rembg_remove(image_bytes)
        if output_png and len(output_png) > 100:
            return output_png, "image/png"
    except Exception:
        pass

    return image_bytes, "image/jpeg"


class WardrobeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Stylist — Panel de administración")
        self.geometry("1180x820")
        self.minsize(1080, 720)
        self.configure(bg="#0c0f14")
        self.iconbitmap(default=None)

        self.user_map = {}
        self.user_counts = {}
        self.folder_path = tk.StringVar(value="")
        self.use_rembg = tk.BooleanVar(value=REMBG_AVAILABLE)
        self.status_text = tk.StringVar(value="Listo para cargar prendas.")
        self.progress_var = tk.DoubleVar(value=0)
        self.total_images = 0
        self.processed_images = 0
        self.files_to_process = []
        self.failed_files = []
        self.preview_photo = None
        self.file_listbox = None

        if Image is None:
            self.status_text.set("Falta Pillow: instala las dependencias del proyecto.")

        self._build_ui()
        self._load_users()

    def _build_ui(self):
        bg = "#0c0f14"
        card = "#171f2c"
        soft = "#1d2735"
        accent = "#d9b569"
        accent2 = "#7a6cf2"
        success = "#3ecf8e"
        text = "#f4efe9"
        muted = "#c5bda7"

        ttk.Style().theme_use("clam")
        ttk.Style().configure("TFrame", background=bg)
        ttk.Style().configure("TLabel", background=bg, foreground=text)
        ttk.Style().configure("TEntry", fieldbackground="#101922", foreground=text)
        ttk.Style().configure("TButton", padding=(16, 10), relief="flat", background=accent2, foreground="white")
        ttk.Style().map("TButton", background=[("active", "#614fe1")])
        ttk.Style().configure("Primary.TButton", background=accent2, foreground="white")
        ttk.Style().map("Primary.TButton", background=[("active", "#604bdf")])
        ttk.Style().configure("Secondary.TButton", background=soft, foreground=text)
        ttk.Style().map("Secondary.TButton", background=[("active", "#283548")])
        ttk.Style().configure("TCheckbutton", background=bg, foreground=text)
        ttk.Style().map("TCheckbutton", background=[("active", bg)])
        ttk.Style().configure("Horizontal.TProgressbar", troughcolor="#111928", background=success)

        root_frame = tk.Frame(self, bg=bg)
        root_frame.pack(fill="both", expand=True, padx=18, pady=18)

        header = tk.Frame(root_frame, bg=card, padx=18, pady=18)
        header.pack(fill="x")

        title = tk.Label(header, text="AI Stylist", font=("Segoe UI", 22, "bold"), fg=text, bg=card)
        title.pack(anchor="w")

        subtitle = tk.Label(header, text="Panel administrativo para cargar ropa a la cuenta de tu novia", fg=muted, bg=card, font=("Segoe UI", 10))
        subtitle.pack(anchor="w", pady=(4, 0))

        main = tk.Frame(root_frame, bg=bg)
        main.pack(fill="both", expand=True, pady=(16, 0))

        left = tk.Frame(main, bg=card, padx=18, pady=18)
        left.pack(side="left", fill="y", expand=False, ipadx=10)

        right = tk.Frame(main, bg=card, padx=18, pady=18)
        right.pack(side="right", fill="both", expand=True, padx=(16, 0))

        tk.Label(left, text="Cuenta destino", fg=muted, bg=card, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.user_combo = ttk.Combobox(left, state="readonly", width=34, justify="center")
        self.user_combo.pack(fill="x", pady=(6, 8))
        self.user_combo.bind("<<ComboboxSelected>>", self.on_user_changed)

        self.user_count_label = tk.Label(left, text="Prendas cargadas: 0", fg=accent, bg=card, font=("Segoe UI", 10, "bold"))
        self.user_count_label.pack(anchor="w", pady=(0, 12))

        tk.Label(left, text="Carpeta de imágenes", fg=muted, bg=card, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        entry_wrap = tk.Frame(left, bg=card)
        entry_wrap.pack(fill="x", pady=(6, 10))
        self.folder_entry = tk.Entry(entry_wrap, textvariable=self.folder_path, width=32, fg=text, bg="#0d141d", borderwidth=1, relief="flat", highlightthickness=0)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self.folder_button = ttk.Button(entry_wrap, text="Explorar", command=self.select_folder, style="Secondary.TButton")
        self.folder_button.pack(side="right", padx=(8, 0))

        if not REMBG_AVAILABLE:
            self.status_text.set("rembg no está instalado; se subirá la imagen original.")
            self.rembg_check = ttk.Checkbutton(left, text="Quitar fondo con rembg local (no disponible)", variable=self.use_rembg, state="disabled", style="TCheckbutton")
        else:
            self.rembg_check = ttk.Checkbutton(left, text="Quitar fondo con rembg local", variable=self.use_rembg, style="TCheckbutton")
        self.rembg_check.pack(anchor="w", pady=(12, 4))

        process_row = tk.Frame(left, bg=card)
        process_row.pack(fill="x", pady=(18, 8))
        self.process_button = ttk.Button(process_row, text="Procesar todas", command=self.process_images, style="Primary.TButton")
        self.process_button.pack(side="left", fill="x", expand=True)

        self.process_selected_button = ttk.Button(process_row, text="Procesar seleccionadas", command=self.process_selected_images, style="Secondary.TButton")
        self.process_selected_button.pack(side="right", fill="x", expand=True, padx=(8, 0))

        retry_row = tk.Frame(left, bg=card)
        retry_row.pack(fill="x", pady=(0, 10))
        self.retry_button = ttk.Button(retry_row, text="Reintentar errores", command=self.retry_failed_images, style="Secondary.TButton")
        self.retry_button.pack(fill="x")

        self.status_text_label = tk.Label(left, textvariable=self.status_text, fg=accent, bg=card, font=("Segoe UI", 10, "bold"), justify="left")
        self.status_text_label.pack(anchor="w", pady=(8, 0))

        self.progress = ttk.Progressbar(left, variable=self.progress_var, maximum=100, orient="horizontal", mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(12, 0))

        self.summary_label = tk.Label(left, text="0/0 prendas procesadas", fg=muted, bg=card, font=("Segoe UI", 9, "bold"))
        self.summary_label.pack(anchor="w", pady=(8, 0))

        self.preview_frame = tk.Frame(right, bg="#0d141d", padx=16, pady=16, highlightthickness=1, highlightbackground="#202a3d")
        self.preview_frame.pack(fill="x", pady=(0, 10))
        self.preview_frame.pack_propagate(False)
        self.preview_frame.configure(height=430)
        self.preview_label = tk.Label(self.preview_frame, bg="#0d141d", fg=muted, text="Vista previa a tamaño real", font=("Segoe UI", 11, "bold"), anchor="center")
        self.preview_label.pack(fill="x", pady=(0, 10))

        self.preview_canvas = tk.Label(self.preview_frame, bg="#0d141d", text="Seleccioná una carpeta para ver una imagen de ejemplo.", width=26, height=16, compound="center", anchor="center")
        self.preview_canvas.pack(fill="both", expand=True)

        list_header = tk.Frame(right, bg=card)
        list_header.pack(fill="x", pady=(0, 6))
        tk.Label(list_header, text="Imágenes encontradas", fg=muted, bg=card, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.file_listbox = tk.Listbox(right, bg="#0d141d", fg="#edf1f5", selectbackground="#2d3b5c", selectmode="extended", height=8, activestyle="none", exportselection=False, bd=0)
        self.file_listbox.pack(fill="x", expand=False)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        tk.Label(right, text="Registro de actividad", fg=muted, bg=card, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 6))
        self.log_widget = scrolledtext.ScrolledText(
            right,
            wrap=tk.WORD,
            width=62,
            height=12,
            bg="#0d141d",
            fg="#edf1f5",
            insertbackground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
        )
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")

    def _load_users(self):
        try:
            usuarios = listar_todos_los_usuarios()
        except Exception as exc:
            self.user_combo.set("Sin conexión a la base de datos")
            self.user_combo.config(state="disabled")
            self.process_button.config(state="disabled")
            self.process_selected_button.config(state="disabled")
            self.retry_button.config(state="disabled")
            self.log("❌ Error: " + str(exc))
            return

        if not usuarios:
            self.user_combo.set("No hay usuarios registrados")
            self.user_combo.config(state="disabled")
            self.process_button.config(state="disabled")
            self.process_selected_button.config(state="disabled")
            self.retry_button.config(state="disabled")
            self.log("⚠️ No hay usuarios registrados en la base de datos.")
            return

        opciones = []
        for u in usuarios:
            self.user_map[f"{u['name']} ({u['email']})"] = u
            opciones.append(f"{u['name']} ({u['email']})")

        self.user_combo.config(values=opciones)
        self.user_combo.current(0)
        self._refresh_user_stats()
        self.log(f"✓ Se encontraron {len(usuarios)} cuentas disponibles.")

    def _refresh_user_stats(self, user_id=None):
        try:
            selected_label = self.user_combo.get()
            target_user = self.user_map.get(selected_label)
            if not target_user:
                self.user_count_label.config(text="Prendas cargadas: 0")
                return

            user_id = user_id if user_id is not None else target_user["id"]
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS total FROM prendas WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            total = row["total"] if row else 0
            cur.close()
            conn.close()
            self.user_count_label.config(text=f"Prendas cargadas: {total}")
            self.user_counts[user_id] = total
        except Exception as exc:
            self.user_count_label.config(text="Prendas cargadas: no disponible")
            self.log(f"⚠️ No se pudo leer el total de prendas: {exc}")

    def on_user_changed(self, event=None):
        self._refresh_user_stats()

    def log(self, message: str):
        self.log_widget.configure(state="normal")
        self.log_widget.insert(tk.END, message + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.configure(state="disabled")

    def _scan_folder(self):
        folder = self.folder_path.get().strip()
        if not folder or not os.path.exists(folder):
            self.files_to_process = []
            self.file_listbox.delete(0, tk.END)
            self.preview_canvas.configure(text="Seleccioná una carpeta válida.", image="")
            self.preview_photo = None
            return

        extensiones = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.PNG", "*.WEBP")
        archivos = []
        for ext in extensiones:
            archivos.extend(glob.glob(os.path.join(folder, ext)))
        self.files_to_process = sorted(list(set(archivos)))
        self.file_listbox.delete(0, tk.END)
        for filepath in self.files_to_process:
            self.file_listbox.insert(tk.END, os.path.basename(filepath))

        if self.files_to_process:
            self._show_preview(self.files_to_process[0])
        else:
            self.preview_canvas.configure(text="No encontré imágenes en la carpeta.", image="")
            self.preview_photo = None

    def _show_preview(self, filepath: str):
        if Image is None:
            self.preview_canvas.configure(text="Pillow no está instalado.\nInstalá las dependencias.", image="")
            self.preview_photo = None
            return

        try:
            with Image.open(filepath) as img:
                img.thumbnail((700, 420), Image.Resampling.LANCZOS)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                tk_image = ImageTk.PhotoImage(img)
                self.preview_canvas.configure(image=tk_image, text="")
                self.preview_photo = tk_image
        except Exception:
            self.preview_canvas.configure(text="No se pudo crear la vista previa.\nLa imagen puede estar dañada.", image="")
            self.preview_photo = None

    def on_file_select(self, event=None):
        selection = self.file_listbox.curselection()
        if not selection:
            return
        filepath = self.files_to_process[selection[0]]
        self._show_preview(filepath)

    def select_folder(self):
        carpeta = filedialog.askdirectory(title="Elegí la carpeta con las prendas")
        if carpeta:
            self.folder_path.set(carpeta)
            self.status_text.set(f"Carpeta seleccionada: {carpeta}")
            self.log(f"📂 Carpeta elegida: {carpeta}")
            self._scan_folder()

    def _prepare_files_for_processing(self):
        folder = self.folder_path.get().strip()
        if not folder or not os.path.exists(folder):
            messagebox.showwarning("Carpeta inválida", "Seleccioná una carpeta válida con imágenes.")
            return []

        if self.file_listbox.curselection():
            return [self.files_to_process[i] for i in self.file_listbox.curselection()]

        if self.files_to_process:
            return self.files_to_process

        self._scan_folder()
        return self.files_to_process

    def process_selected_images(self):
        archivos = self._prepare_files_for_processing()
        if not archivos:
            messagebox.showinfo("Sin imágenes seleccionadas", "Elegí algunas imágenes o usa 'Procesar todas'.")
            return
        self.process_images(archivos)

    def process_images(self, archivos=None):
        if self.user_combo.cget("state") == "disabled":
            messagebox.showwarning("Sin usuarios", "Primero crea al menos una cuenta en la app web.")
            return

        selected_label = self.user_combo.get()
        target_user = self.user_map.get(selected_label)
        if not target_user:
            messagebox.showerror("Cuenta no válida", "Elegí una cuenta válida.")
            return

        if archivos is None:
            archivos = self._prepare_files_for_processing()
        if not archivos:
            messagebox.showinfo("Sin imágenes", "No encontré fotos en esa carpeta.")
            return

        self.failed_files = []
        self.total_images = len(archivos)
        self.processed_images = 0
        self.progress_var.set(0)
        self.summary_label.config(text=f"0/{self.total_images} prendas procesadas")

        provider = get_provider()
        exitosas = 0
        errores = 0

        self.process_button.config(state="disabled")
        self.process_selected_button.config(state="disabled")
        self.retry_button.config(state="disabled")
        self.status_text.set("Procesando imágenes...")
        self.log(f"▶ Iniciando carga para {target_user['name']} ({target_user['email']})")
        self.log(f"▶ Se encontraron {self.total_images} imágenes seleccionadas.")

        for index, filepath in enumerate(archivos, 1):
            name = os.path.basename(filepath)
            self.status_text.set(f"Procesando {index}/{self.total_images}: {name}")
            self.log(f"\n[{index}/{self.total_images}] {name}")

            try:
                with open(filepath, "rb") as f:
                    raw_bytes = f.read()

                raw_bytes = _redimensionar_si_es_necesario(raw_bytes)

                if self.use_rembg.get():
                    processed_bytes, mime_type = _quitar_fondo_local(raw_bytes)
                else:
                    processed_bytes, mime_type = raw_bytes, "image/jpeg"

                ext_final = ".png" if mime_type == "image/png" else ".jpg"
                self.log("   🤖 Analizando prenda con IA...")
                analysis = provider.analyze_garment(processed_bytes, mime_type)

                tipo = analysis.tipo or "prenda sin identificar"
                colores = ", ".join(analysis.colores) if analysis.colores else ""
                categoria = analysis.categoria if analysis.categoria in (
                    "tops", "pantalones", "vestidos", "calzado", "abrigos", "accesorios", "otros"
                ) else "otros"

                self.log("   ☁️ Subiendo a Supabase Storage...")
                url_publica = storage.subir_bytes(
                    processed_bytes,
                    carpeta="prendas",
                    extension=ext_final,
                    content_type=mime_type,
                )

                guardar_prenda(
                    archivo=url_publica,
                    tipo=tipo,
                    colores=colores,
                    estilo=analysis.estilo,
                    descripcion=tipo,
                    categoria=categoria,
                    user_id=target_user["id"],
                )

                exitosas += 1
                self.processed_images += 1
                self.progress_var.set((self.processed_images / self.total_images) * 100)
                self.summary_label.config(text=f"{self.processed_images}/{self.total_images} prendas procesadas")
                self.log(f"   ✅ OK -> {tipo} ({colores}) [{categoria}]")
            except Exception as exc:
                self.failed_files.append(filepath)
                errores += 1
                self.processed_images += 1
                self.progress_var.set((self.processed_images / self.total_images) * 100)
                self.summary_label.config(text=f"{self.processed_images}/{self.total_images} prendas procesadas")
                self.log(f"   ❌ Error: {exc}")

        self.process_button.config(state="normal")
        self.process_selected_button.config(state="normal")
        self.retry_button.config(state="normal")
        self.status_text.set("Proceso finalizado.")
        self.log(f"\n🎉 Finalizado: {exitosas} prendas cargadas correctamente. Errores: {errores}.")
        self._refresh_user_stats()
        if self.failed_files:
            self.log(f"⚠️ Archivos con error: {len(self.failed_files)}. Usá 'Reintentar errores' para volver a intentar.")
        messagebox.showinfo(
            "Carga finalizada",
            f"Se agregaron {exitosas} prendas correctamente.\nErrores: {errores}.",
        )

    def retry_failed_images(self):
        if not self.failed_files:
            messagebox.showinfo("Sin errores", "No hay imágenes pendientes para reintentar.")
            return

        self.log(f"🔁 Reintentando {len(self.failed_files)} imágenes fallidas...")
        self.process_images(self.failed_files)


if __name__ == "__main__":
    app = WardrobeApp()
    app.mainloop()

"""
AI Stylist - Almacenamiento de imágenes (Supabase Storage)

Reemplaza la carpeta local uploads/. Las imágenes ahora viven en un
bucket de Supabase Storage y se acceden por URL pública, en vez de
un archivo en el disco del servidor. Esto es necesario porque Render
(donde va a correr el backend) no garantiza que los archivos locales
sobrevivan entre reinicios.
"""

import os
import uuid
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")


class StorageError(Exception):
    pass


def _headers(content_type: str = None) -> dict:
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


from PIL import Image
import io

def _optimizar_imagen(contenido: bytes, extension: str, max_dim: int = 1600) -> tuple[bytes, str, str]:
    """
    Redimensiona y comprime imágenes antes de subirlas a Supabase Storage:
    - Reduce fotos gigantes de 8MB-15MB a ~150-250KB (10x más rápido en móviles).
    - Preserva la transparencia en archivos PNG.
    """
    try:
        img = Image.open(io.BytesIO(contenido))
        width, height = img.size
        ext_lower = extension.lower()

        if width > max_dim or height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        output = io.BytesIO()

        if ext_lower == ".png" or img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img.save(output, format="PNG", optimize=True)
            return output.getvalue(), ".png", "image/png"
        else:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue(), ".jpg", "image/jpeg"
    except Exception:
        pass

    return contenido, extension, ("image/png" if extension.lower() == ".png" else "image/jpeg")


def subir_bytes(contenido: bytes, carpeta: str, extension: str, content_type: str = "image/jpeg") -> str:
    """
    Sube un archivo binario optimizado al bucket de Supabase Storage y devuelve
    su URL pública. `carpeta` organiza las imágenes por tipo.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise StorageError(
            "Falta configurar SUPABASE_URL / SUPABASE_SERVICE_KEY en el archivo .env"
        )

    if not extension.startswith("."):
        extension = f".{extension}"

    contenido_opt, extension, content_type = _optimizar_imagen(contenido, extension)

    nombre = f"{carpeta}/{uuid.uuid4().hex}{extension}"

    response = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{nombre}",
        headers=_headers(content_type),
        data=contenido_opt,
        timeout=60,
    )

    if response.status_code not in (200, 201):
        raise StorageError(
            f"No se pudo subir la imagen a Supabase Storage: "
            f"{response.status_code} {response.text}"
        )

    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{nombre}"


def eliminar_archivo(url_publica: str) -> None:
    """
    Elimina un archivo del bucket a partir de su URL pública.
    No lanza error si el archivo ya no existe o la URL es inválida
    (borrar algo que ya no está no debería romper el resto del flujo).
    """
    if not url_publica or not SUPABASE_URL:
        return

    marcador = f"/storage/v1/object/public/{SUPABASE_BUCKET}/"
    if marcador not in url_publica:
        return

    ruta_interna = url_publica.split(marcador, 1)[1]

    try:
        requests.delete(
            f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{ruta_interna}",
            headers=_headers(),
            timeout=30,
        )
    except Exception:
        pass


def descargar_bytes(url: str) -> bytes:
    """Descarga el contenido binario de una URL (ej: un resultado de Fashn AI)."""
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        raise StorageError(f"No se pudo descargar el archivo: {response.status_code}")
    return response.content
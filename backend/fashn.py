"""
AI Stylist - FASHN Virtual Try-On

Integra FASHN Try-On v1.6 (ropa) y Try-On Max (calzado/accesorios).
Ahora trabaja con URLs públicas de Supabase Storage en vez de rutas
de archivo locales — Fashn acepta URLs directamente, así que ya no
hace falta convertir nada a base64.
"""

import os
import time
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

FASHN_API_KEY = os.getenv("FASHN_API_KEY")
FASHN_BASE_URL = "https://api.fashn.ai/v1"


class FashnError(Exception):
    pass


def crear_tryon(
    model_image_url: str,
    garment_image_url: str,
    mode: str = "balanced",
    categoria: str = None,
):
    """
    Ejecuta un Virtual Try-On con FASHN.

    model_image_url:
        URL pública de la foto de la persona (Supabase Storage).

    garment_image_url:
        URL pública de la foto de la prenda (Supabase Storage).

    mode:
        performance / balanced / quality (solo aplica al modelo tryon-v1.6).

    categoria:
        Categoria de la prenda. Decide qué modelo de FASHN usar:
        - calzado / accesorios -> tryon-max (soporta zapatos, joyas, carteras, etc.)
        - el resto -> tryon-v1.6 (mas barato, pensado para ropa)
    """

    if not FASHN_API_KEY:
        raise FashnError("No existe FASHN_API_KEY en el archivo .env")

    usar_max = categoria in ("calzado", "accesorios")

    if usar_max:
        payload = {
            "model_name": "tryon-max",
            "inputs": {
                "model_image": model_image_url,
                "product_image": garment_image_url,
                "generation_mode": "fast",
                "resolution": "1k",
            },
        }
    else:
        if mode not in {"performance", "balanced", "quality"}:
            mode = "balanced"

        categoria_fashn = {
            "tops": "tops",
            "pantalones": "bottoms",
            "vestidos": "one-pieces",
        }.get(categoria, "auto")

        payload = {
            "model_name": "tryon-v1.6",
            "inputs": {
                "model_image": model_image_url,
                "garment_image": garment_image_url,
                "category": categoria_fashn,
                "garment_photo_type": "auto",
                "mode": mode,
                "num_samples": 1,
            },
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FASHN_API_KEY}",
    }

    response = requests.post(
        f"{FASHN_BASE_URL}/run",
        json=payload,
        headers=headers,
        timeout=120,
    )

    try:
        data = response.json()
    except Exception:
        raise FashnError(f"FASHN devolvió una respuesta inválida: {response.text}")

    if response.status_code >= 400:
        raise FashnError(f"FASHN API {response.status_code}: {data}")

    prediction_id = data.get("id")
    if not prediction_id:
        raise FashnError(f"FASHN no devolvió prediction ID: {data}")

    for intento in range(40):
        time.sleep(2)

        status_response = requests.get(
            f"{FASHN_BASE_URL}/status/{prediction_id}",
            headers=headers,
            timeout=60,
        )

        try:
            status_data = status_response.json()
        except Exception:
            raise FashnError("FASHN devolvió un estado inválido.")

        status = status_data.get("status")
        print(f"FASHN Try-On ({'max' if usar_max else 'v1.6'}) → intento {intento + 1}/40 → {status}")

        if status == "completed":
            output = status_data.get("output")
            if not output:
                raise FashnError("FASHN terminó correctamente pero no devolvió ninguna imagen.")
            return {"prediction_id": prediction_id, "status": "completed", "output": output}

        if status == "failed":
            error = status_data.get("error")
            raise FashnError(f"FASHN falló: {error}")

    raise FashnError("FASHN tardó demasiado en responder.")


def obtener_creditos() -> dict:
    """Consulta el saldo actual de créditos en Fashn AI. No gasta créditos por consultarlo."""
    if not FASHN_API_KEY:
        raise FashnError("No existe FASHN_API_KEY en el archivo .env")

    headers = {"Authorization": f"Bearer {FASHN_API_KEY}"}
    response = requests.get(f"{FASHN_BASE_URL}/credits", headers=headers, timeout=30)

    try:
        data = response.json()
    except Exception:
        raise FashnError(f"FASHN devolvió una respuesta inválida: {response.text}")

    if response.status_code >= 400:
        raise FashnError(f"FASHN API {response.status_code}: {data}")

    return data.get("credits", {})
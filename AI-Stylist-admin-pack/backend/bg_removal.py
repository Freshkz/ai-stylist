"""
AI Stylist - Remoción de fondo (remove.bg)

Reemplaza los intentos anteriores (rembg local en Render -> se quedaba
sin memoria; @imgly/background-removal en el navegador -> fallaba
silenciosamente por falta de headers COOP/COEP). Esta es una API externa:
no consume memoria de Render ni depende de nada especial del navegador.

Plan gratis de remove.bg: 50 imágenes por mes.
"""

import os
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")


class RemoveBgError(Exception):
    pass


def quitar_fondo(image_bytes: bytes) -> bytes:
    """
    Manda una imagen a remove.bg y devuelve los bytes del PNG resultante
    con fondo transparente. Si falla (sin API key, sin créditos del mes,
    error de red, etc.) lanza RemoveBgError; quien llama decide si sigue
    con la imagen original o corta el flujo.
    """
    if not REMOVE_BG_API_KEY:
        raise RemoveBgError("No existe REMOVE_BG_API_KEY en el archivo .env")

    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        files={"image_file": image_bytes},
        data={"size": "auto"},
        headers={"X-Api-Key": REMOVE_BG_API_KEY},
        timeout=30,
    )

    if response.status_code != 200:
        try:
            detalle = response.json().get("errors", [{}])[0].get("title", response.text)
        except Exception:
            detalle = response.text
        raise RemoveBgError(f"remove.bg devolvió un error ({response.status_code}): {detalle}")

    return response.content


def obtener_creditos_removebg() -> dict:
    """
    Consulta el saldo de créditos/llamadas gratis de remove.bg.
    Solo consulta el saldo, no gasta créditos por sí sola.
    """
    if not REMOVE_BG_API_KEY:
        raise RemoveBgError("No existe REMOVE_BG_API_KEY en el archivo .env")

    response = requests.get(
        "https://api.remove.bg/v1.0/account",
        headers={"X-Api-Key": REMOVE_BG_API_KEY},
        timeout=15,
    )

    try:
        data = response.json()
    except Exception:
        raise RemoveBgError(f"remove.bg devolvió una respuesta inválida: {response.text}")

    if response.status_code >= 400:
        raise RemoveBgError(f"remove.bg API {response.status_code}: {data}")

    attrs = data.get("data", {}).get("attributes", {})
    creditos = attrs.get("credits", {})
    llamadas_gratis = attrs.get("api", {}).get("free_calls", 0)

    return {
        "creditos_pagos": creditos.get("total", 0),
        "llamadas_gratis_restantes": llamadas_gratis,
        "total_disponible": creditos.get("total", 0) + llamadas_gratis,
    }

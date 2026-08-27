"""
AI Stylist - Proveedor de IA: Groq (Fase 2)

Usa el modelo multimodal qwen/qwen3.6-27b de Groq, que corre en
hardware LPU (muy rápido) y tiene tier gratis sin tarjeta de crédito.
"""

import os
import json
import base64
import io
from PIL import Image
from groq import Groq
from .base import AIProvider, StyleAnalysis, OutfitSuggestions, OUTFIT_PROMPT_TEMPLATE, GarmentAnalysis, GARMENT_PROMPT


def _redimensionar_si_excede_limite(image_bytes: bytes, max_dim: int = 1920) -> bytes:
    """
    Garantiza que la imagen no exceda los límites de resolución de la API de Groq
    (evita el error 400 Image too large de 33M px) y acelera el tiempo de respuesta.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width > max_dim or height > max_dim or (width * height > 16000000):
            print(f"[RESIZE] Redimensionando imagen de {width}x{height} a max {max_dim}px para evitar limite de API Groq...")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            fmt = img.format if img.format in ("PNG", "JPEG", "WEBP") else "JPEG"
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format=fmt, quality=85)
            return output.getvalue()
    except Exception as e:
        print(f"[RESIZE INFO] Aviso al optimizar dimensiones: {e}")
    return image_bytes


STYLIST_PROMPT = """
Sos un asistente de moda. Analiza la foto de cuerpo completo de esta persona
y devolve UNICAMENTE un objeto JSON (sin texto adicional, sin markdown) con
esta forma exacta:

{
  "prendas": ["prenda 1", "prenda 2"],
  "colores": ["color 1", "color 2"],
  "estilo": "estilo en 2-3 palabras",
  "descripcion": "una sola oracion breve",
  "recomendaciones": ["sugerencia 1 breve", "sugerencia 2 breve"]
}

Se breve en cada campo: cada prenda y color como una sola palabra o frase
corta, la descripcion en una sola oracion, y solo 2 recomendaciones breves
(no 3). Esto es importante porque hay un limite de espacio en la respuesta.
No inventes detalles que no puedas ver claramente en la imagen. Generá
siempre las 5 claves del JSON completas, sin cortar el texto a la mitad.
"""


# Guarda el último estado conocido de los límites de uso de Groq.
# Se actualiza cada vez que se hace una llamada real a la API
# (no gastamos una llamada extra solo para consultarlo).
_ultimo_estado_groq = {
    "limite_requests_dia": None,
    "restantes_requests_dia": None,
    "limite_tokens_minuto": None,
    "restantes_tokens_minuto": None,
}


def _actualizar_estado_groq(headers) -> None:
    """Lee los headers de rate limit que Groq manda en cada respuesta."""
    global _ultimo_estado_groq
    try:
        _ultimo_estado_groq = {
            "limite_requests_dia": int(headers.get("x-ratelimit-limit-requests", 0)),
            "restantes_requests_dia": int(headers.get("x-ratelimit-remaining-requests", 0)),
            "limite_tokens_minuto": int(headers.get("x-ratelimit-limit-tokens", 0)),
            "restantes_tokens_minuto": int(headers.get("x-ratelimit-remaining-tokens", 0)),
        }
    except (TypeError, ValueError):
        pass


def obtener_estado_groq() -> dict:
    """Devuelve el último estado conocido (puede tener valores None si todavía no se hizo ninguna llamada)."""
    return dict(_ultimo_estado_groq)

def _categorizar_prenda(tipo: str) -> str:
    """Clasifica una prenda por palabras clave, igual que el frontend."""
    texto = (tipo or "").lower()

    tops = ["remera", "camisa", "musculosa", "buzo", "sweater", "top", "blusa", "polera", "chomba"]
    pantalones = ["pantalon", "pantalón", "jean", "short", "bermuda", "falda", "pollera", "calza"]
    vestidos = ["vestido", "mono", "enterizo", "jumpsuit"]
    calzado = ["zapatilla", "zapato", "bota", "sandalia", "ojota", "mocasin", "mocasín"]
    abrigos = ["campera", "abrigo", "saco", "tapado", "chaqueta", "piloto", "parka"]
    accesorios = ["cartera", "gorra", "collar", "anteojo", "cinturon", "cinturón", "bufanda", "reloj", "gorro", "sombrero", "guante"]

    if any(palabra in texto for palabra in accesorios):
        return "accesorios"
    if any(palabra in texto for palabra in abrigos):
        return "abrigos"
    if any(palabra in texto for palabra in calzado):
        return "calzado"
    if any(palabra in texto for palabra in vestidos):
        return "vestidos"
    if any(palabra in texto for palabra in pantalones):
        return "pantalones"
    if any(palabra in texto for palabra in tops):
        return "tops"
    return "otros"

class GroqProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "No se encontró GROQ_API_KEY. Revisá el archivo .env "
                "en la carpeta backend/."
            )
        self.client = Groq(api_key=api_key)

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> StyleAnalysis:
        image_bytes = _redimensionar_si_excede_limite(image_bytes)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        raw_response = self.client.chat.completions.with_raw_response.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": STYLIST_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_completion_tokens=512,
            response_format={"type": "json_object"},
            reasoning_effort="none",
        )
        _actualizar_estado_groq(raw_response.headers)
        completion = raw_response.parse()

        raw_json = completion.choices[0].message.content
        data = json.loads(raw_json)
        return StyleAnalysis(**data)

    def analyze_garment(self, image_bytes: bytes, mime_type: str) -> GarmentAnalysis:
        image_bytes = _redimensionar_si_excede_limite(image_bytes)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        raw_response = self.client.chat.completions.with_raw_response.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GARMENT_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.4,
            max_completion_tokens=512,
            response_format={"type": "json_object"},
            reasoning_effort="none",
        )
        _actualizar_estado_groq(raw_response.headers)
        completion = raw_response.parse()

        raw_json = completion.choices[0].message.content
        data = json.loads(raw_json)
        return GarmentAnalysis(**data)

    def generate_outfits(self, prendas: list[dict], ocasion: str = "todas", clima: str = "cualquiera") -> OutfitSuggestions:
        prendas_compactas = [
            {
                "id": p["id"],
                "tipo": p["tipo"],
                "colores": p["colores"],
                "estilo": p["estilo"],
                "categoria": _categorizar_prenda(p["tipo"]),
            }
            for p in prendas
        ]

        partes_contexto = []
        if ocasion and ocasion != "todas":
            partes_contexto.append(f"Ocasión preferida: '{ocasion}'")
        if clima and clima != "cualquiera":
            partes_contexto.append(f"Clima preferido: '{clima}'")

        contexto_str = ""
        if partes_contexto:
            contexto_str = "PREFERENCIAS DEL USUARIO: " + ", ".join(partes_contexto) + ". Generá outfits que encajen prioritariamente con esta ocasión y clima."

        prompt = OUTFIT_PROMPT_TEMPLATE.format(
            prendas_json=json.dumps(prendas_compactas, ensure_ascii=False),
            contexto_extra=contexto_str,
        )

        raw_response = self.client.chat.completions.with_raw_response.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_completion_tokens=1024,
            response_format={"type": "json_object"},
            reasoning_effort="none",
        )
        _actualizar_estado_groq(raw_response.headers)
        completion = raw_response.parse()

        raw_json = completion.choices[0].message.content
        data = json.loads(raw_json)

        for outfit in data.get("outfits", []):
            tags = []
            if ocasion and ocasion != "todas":
                tags.append(ocasion.capitalize())
            if clima and clima != "cualquiera":
                tags.append(f"Clima {clima}")
            if tags:
                etiqueta = " · ".join(tags)
                if not outfit.get("ocasion"):
                    outfit["ocasion"] = etiqueta
                elif etiqueta.lower() not in outfit["ocasion"].lower():
                    outfit["ocasion"] = f"{outfit['ocasion']} ({etiqueta})"

        return OutfitSuggestions(**data)
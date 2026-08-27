"""
AI Stylist - Proveedor de IA: Google Gemini (Fase 2)
"""

import os
import json
from google import genai
from google.genai import types
from .base import (
    AIProvider,
    StyleAnalysis,
    GarmentAnalysis,
    OutfitSuggestions,
    GARMENT_PROMPT,
    OUTFIT_PROMPT_TEMPLATE,
)

STYLIST_PROMPT = """
Sos un asistente de moda. Analizá la foto de cuerpo completo de esta persona
y devolvé un análisis de estilo: prendas visibles, colores predominantes,
estilo aproximado (casual, formal, deportivo, streetwear, etc.) y una breve
descripción general. No inventes detalles que no puedas ver claramente
en la imagen.
"""


class GeminiProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "No se encontró GOOGLE_API_KEY. Revisá el archivo .env "
                "en la carpeta backend/."
            )
        self.client = genai.Client(api_key=api_key)

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> StyleAnalysis:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                STYLIST_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StyleAnalysis,
            ),
        )
        return response.parsed

    def analyze_garment(self, image_bytes: bytes, mime_type: str) -> GarmentAnalysis:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                GARMENT_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GarmentAnalysis,
            ),
        )
        return response.parsed

    def generate_outfits(self, prendas: list[dict], ocasion: str = "todas", clima: str = "cualquiera") -> OutfitSuggestions:
        contexto_extra = ""
        if ocasion and ocasion != "todas":
            contexto_extra += f"Ocasión deseada: {ocasion}. "
        if clima and clima != "cualquiera":
            contexto_extra += f"Clima esperado: {clima}. "

        prendas_compactas = [
            {
                "id": p["id"],
                "tipo": p["tipo"],
                "colores": p["colores"],
                "estilo": p["estilo"],
                "categoria": p.get("categoria", "otros"),
            }
            for p in prendas
        ]

        prompt = OUTFIT_PROMPT_TEMPLATE.format(
            prendas_json=json.dumps(prendas_compactas, ensure_ascii=False),
            contexto_extra=contexto_extra,
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OutfitSuggestions,
            ),
        )
        return response.parsed
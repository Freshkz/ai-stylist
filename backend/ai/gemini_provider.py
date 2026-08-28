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
    StructuredStyleAnalysis,
    GarmentAnalysis,
    OutfitSuggestions,
    GARMENT_PROMPT,
    OUTFIT_PROMPT_TEMPLATE,
)

STYLIST_PROMPT = """
Sos una estilista personal experta, cálida y detallista. Analizá la imagen
principal y detectá automáticamente si muestra una persona con outfit, varias
prendas o una sola prenda. No asumas que siempre hay una persona.

Devolvé UNICAMENTE un objeto JSON con estas claves:
{
  "prendas": ["prendas visibles"],
  "colores": ["colores y combinaciones"],
  "estilo": "estilo principal y subestilos",
  "descripcion": "descripción extensa y clara de lo que se ve",
  "recomendaciones": ["recomendación específica 1", "recomendación específica 2", "recomendación específica 3"],
  "tipo_imagen": "outfit, prenda o conjunto",
  "detalles_prenda": "materiales, corte, textura, calidad aparente y características de la prenda",
  "como_favorece": "explicación personalizada sobre silueta, colores, piel, ojos y cabello SOLO si son visibles",
  "combinaciones": ["tres combinaciones concretas, aunque no existan en el armario"],
  "ocasiones": ["ocasión o lugar recomendado"],
  "busqueda_compra": "términos concretos para buscar una prenda similar"
}

La segunda imagen, si existe, es la referencia privada de "Mi modelo". Usala
solo para personalizar proporciones, colores y sugerencias; no describas
rasgos que no puedas ver. Dirigite a la persona por su nombre si fue indicado.
El tono debe sentirse amoroso, como un regalo pensado especialmente para ella.
No inventes detalles. Sé extensa y específica: cada explicación debe tener
varias oraciones y las listas deben ser útiles, no genéricas.
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

    def analyze_image(self, image_bytes, mime_type, reference_image=None, reference_mime_type="image/jpeg", user_name=""):
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            STYLIST_PROMPT + (f"\nNombre de la persona: {user_name}" if user_name else ""),
        ]
        if reference_image:
            contents.insert(1, types.Part.from_bytes(data=reference_image, mime_type=reference_mime_type))
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StructuredStyleAnalysis,
            ),
        )
        return StyleAnalysis(**response.parsed.model_dump())

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
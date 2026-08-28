"""
AI Stylist - Interfaz base para proveedores de IA (Fase 2)

Cualquier proveedor de IA (Gemini, OpenAI, Claude, etc.) que
queramos usar en el futuro debe implementar esta misma interfaz.
Asi, el resto de la aplicacion (main.py) no necesita saber
que proveedor esta usando por detras.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import List


class StyleAnalysis(BaseModel):
    """Resultado estructurado del analisis universal de estilo."""

    prendas: List[str]
    colores: List[str]
    estilo: str
    descripcion: str
    recomendaciones: List[str] = []
    tipo_imagen: str = "outfit"
    detalles_prenda: str = ""
    como_favorece: str = ""
    combinaciones: List[str] = []
    ocasiones: List[str] = []
    busqueda_compra: str = ""


class Outfit(BaseModel):
    """Una combinacion de outfit sugerida."""

    nombre: str
    prendas_ids: List[int]
    ocasion: str
    descripcion: str


class OutfitSuggestions(BaseModel):
    """Resultado de generar combinaciones de outfits."""

    outfits: List[Outfit]


class GarmentAnalysis(BaseModel):
    """Resultado del catalogo de UNA prenda individual."""

    tipo: str
    colores: List[str]
    estilo: str
    categoria: str  # "tops" | "pantalones" | "vestidos" | "calzado" | "abrigos" | "accesorios" | "otros"


OUTFIT_PROMPT_TEMPLATE = """
Sos un asistente de moda. Tenes esta lista de prendas en el armario del
usuario, en formato JSON (cada una con su "id", "tipo", "colores", "estilo",
"categoria"). La "categoria" puede ser: tops, pantalones, vestidos, calzado,
abrigos, accesorios, u otros.

{prendas_json}

{contexto_extra}

REGLA OBLIGATORIA: cada outfit que generes DEBE incluir al menos una prenda
de categoria "pantalones" O una prenda de categoria "vestidos" (algo que
cubra la parte inferior del cuerpo), siempre que exista al menos una de
esas dos categorias en la lista. Si el outfit ya incluye un "vestido", NO
hace falta que tambien incluya un pantalon (el vestido cubre el cuerpo
completo por si solo). Si el armario no tiene ninguna prenda de categoria
"pantalones" ni "vestidos", entonces no generes ningun outfit y devolve
una lista vacia.

Genera combinaciones de outfits usando SOLO estas prendas (podes repetir
prendas en distintos outfits si tiene sentido). Devolve UNICAMENTE un
objeto JSON con esta forma exacta:

{{
  "outfits": [
    {{
      "nombre": "nombre corto del outfit",
      "prendas_ids": [1, 3],
      "ocasion": "ocasion breve, ej: casual, formal, trabajo",
      "descripcion": "una sola oracion breve"
    }}
  ]
}}

Genera entre 2 y 4 outfits distintos, si hay prendas suficientes y variadas.
No inventes prendas que no esten en la lista. Se breve.
"""

GARMENT_PROMPT = """
Sos un catalogador de moda. Esta foto muestra UNA SOLA prenda de ropa
(no una persona vistiendola, solo la prenda). Analizala y devolve
UNICAMENTE un objeto JSON (sin texto adicional, sin markdown) con esta
forma exacta:

{
  "tipo": "nombre corto y preciso de la prenda, ej: remera, campera, jean, zapatilla",
  "colores": ["color principal", "color secundario si lo hay"],
  "estilo": "estilo en 2-3 palabras",
  "categoria": "una de estas 7 opciones exactas: tops, pantalones, vestidos, calzado, abrigos, accesorios, otros"
}

REGLAS IMPORTANTES:
- "tipo" debe describir SOLO esta prenda, nunca varias prendas juntas.
- Observa el color real de la prenda con precision, no asumas colores tipicos.
- "categoria" debe ser: tops (remeras, camisas, buzos, sweaters, musculosas),
  pantalones (jeans, shorts, polleras, calzas), vestidos (vestidos y monos
  enterizos, prendas de una sola pieza que cubren todo el cuerpo), calzado
  (zapatillas, botas, sandalias), abrigos (camperas, sacos, tapados),
  accesorios (carteras, gorras, collares, anteojos, cinturones, bufandas,
  relojes, joyas) u otros (cualquier cosa que no encaje en las anteriores).
"""


class AIProvider(ABC):
    """Interfaz que debe cumplir cualquier proveedor de IA."""

    @abstractmethod
    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        reference_image: bytes | None = None,
        reference_mime_type: str = "image/jpeg",
        user_name: str = "",
    ) -> StyleAnalysis:
        """
        Recibe los bytes de una imagen y devuelve un StyleAnalysis.
        Cada proveedor concreto implementa esto a su manera.
        """
        ...

    @abstractmethod
    def generate_outfits(self, prendas: list[dict], ocasion: str = "todas", clima: str = "cualquiera") -> OutfitSuggestions:
        """
        Recibe la lista de prendas guardadas en el armario y devuelve
        combinaciones de outfits usando esas prendas, filtradas por
        ocasión y clima si se especifican.
        """
        ...

    @abstractmethod
    def analyze_garment(self, image_bytes: bytes, mime_type: str) -> GarmentAnalysis:
        """Cataloga UNA prenda individual (no un outfit completo)."""
        ...
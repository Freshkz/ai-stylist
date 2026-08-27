"""
AI Stylist - Factory de proveedores de IA (Fase 2)

Este archivo decide, según la configuración, qué proveedor
de IA usar. Es el ÚNICO lugar del proyecto que necesita
cambiarse para agregar o cambiar de proveedor.
"""

import os
from .base import AIProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider
_provider_instance: AIProvider | None = None


def get_provider() -> AIProvider:
    """
    Devuelve una instancia del proveedor de IA configurado.
    Reutiliza la misma instancia entre llamadas (no la recrea
    en cada request).
    """
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    provider_name = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider_name == "gemini":
        _provider_instance = GeminiProvider()
    elif provider_name == "groq":
        _provider_instance = GroqProvider()
    else:
        raise ValueError(f"Proveedor de IA desconocido: '{provider_name}'")

    return _provider_instance
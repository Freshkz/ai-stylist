"""
AI Stylist - Autenticación (registro, login, sesiones)

Maneja el hasheo seguro de contraseñas (con bcrypt) y la generación
y verificación de tokens de sesión (JWT).
"""

import os
import bcrypt
import jwt
from fastapi import Depends
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

JWT_SECRET = os.getenv("JWT_SECRET", "clave-de-desarrollo-cambiar")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 30  # 30 días, para no pedir login todo el tiempo


def hash_password(password: str) -> str:
    """Convierte una contraseña en texto plano en un hash seguro (nunca se guarda la contraseña real)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    """Verifica si una contraseña coincide con el hash guardado."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def crear_token(user_id: int) -> str:
    """Genera un token de sesión (JWT) para un usuario ya autenticado."""
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


_bearer_scheme = HTTPBearer()


def obtener_usuario_actual(credenciales: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> int:
    """
    Dependency de FastAPI: lee el token Bearer del pedido y devuelve el user_id.
    Al usar HTTPBearer, Swagger UI muestra un botón 'Authorize' con candado.
    """
    token = credenciales.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Volvé a iniciar sesión.")

    return payload.get("user_id")
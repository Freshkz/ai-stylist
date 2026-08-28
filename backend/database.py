"""
AI Stylist - Base de datos (Postgres / Supabase)

Reemplaza la versión anterior basada en SQLite local. Ahora la base
de datos vive en Supabase, así que los datos sobreviven aunque el
servidor (Render) se reinicie o "duerma".

Usa psycopg2 para hablar con Postgres. La cadena de conexión sale
de la variable de entorno DATABASE_URL (ver .env).

IMPORTANTE - SEGURIDAD:
Todas las funciones que reciben `user_id` ahora lo usan de verdad en
el WHERE de la consulta (antes algunas no lo hacían, lo que permitía
que un usuario viera o editara datos de otro usuario con solo saber
el id). Cada función deja un comentario aclarando esto donde aplica.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import psycopg2.pool
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

_pool = None


def get_pool():
    global _pool
    if _pool is None or _pool.closed:
        if not DATABASE_URL:
            raise RuntimeError("Falta DATABASE_URL en el archivo .env.")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
    return _pool


class PooledConnection:
    """Wrapper transparente para devolver la conexión al Pool al llamar a .close()."""
    def __init__(self, real_conn):
        self._conn = real_conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        try:
            pool = get_pool()
            if pool and not pool.closed:
                pool.putconn(self._conn)
                return
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            conn.rollback()


def get_connection():
    """Devuelve una conexión reutilizable desde el Pool de Postgres."""
    if not DATABASE_URL:
        raise RuntimeError("Falta DATABASE_URL en el archivo .env.")
    try:
        pool = get_pool()
        real_conn = pool.getconn()
        return PooledConnection(real_conn)
    except Exception:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Crea las tablas si no existen y asegura columnas faltantes."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            avatar TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Migraciones seguras para asegurar columnas en Supabase
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;")
        cur.execute("ALTER TABLE prendas ADD COLUMN IF NOT EXISTS categoria TEXT DEFAULT 'otros';")
        cur.execute("ALTER TABLE outfits ADD COLUMN IF NOT EXISTS imagen TEXT;")
        conn.commit()
    except Exception:
        pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            body_photo TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prendas (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            archivo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            colores TEXT NOT NULL,
            estilo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'otros',
            favorito BOOLEAN NOT NULL DEFAULT FALSE,
            fecha TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("ALTER TABLE prendas ADD COLUMN IF NOT EXISTS favorito BOOLEAN NOT NULL DEFAULT FALSE;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outfits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            ocasion TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            prendas_ids TEXT NOT NULL,
            favorito BOOLEAN NOT NULL DEFAULT FALSE,
            imagen TEXT,
            fecha TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS virtual_tryons (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body_photo TEXT NOT NULL,
            garment_id INTEGER NOT NULL,
            result_image TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combo_tryons (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body_photo TEXT NOT NULL,
            prendas_key TEXT NOT NULL,
            result_image TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# USUARIOS & AUTENTICACIÓN
# =====================================================

def crear_usuario(email: str, password_hash: str, name: str) -> int:
    """Crea un usuario nuevo. Devuelve su id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (email, password_hash, name)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (email.lower().strip(), password_hash, name),
    )
    nuevo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return nuevo_id


def obtener_usuario_por_email(email: str) -> dict | None:
    """Busca un usuario por email."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE email = %s", (email.lower().strip(),)
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return dict(fila) if fila else None


def obtener_usuario_por_id(user_id: int) -> dict | None:
    """Busca un usuario por id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return dict(fila) if fila else None


def actualizar_avatar(user_id: int, archivo: str) -> None:
    """Guarda el nombre/URL del avatar del usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar = %s WHERE id = %s", (archivo, user_id))
    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# PERFIL CORPORAL ("MI MODELO")
# =====================================================

def guardar_foto_corporal(user_id: int, body_photo: str) -> bool:
    """Guarda o actualiza la foto corporal del usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_profile (user_id, body_photo, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            body_photo = EXCLUDED.body_photo,
            updated_at = NOW()
        """,
        (user_id, body_photo),
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def obtener_foto_corporal(user_id: int) -> str | None:
    """Devuelve el nombre/URL de la foto corporal del usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT body_photo FROM user_profile WHERE user_id = %s", (user_id,)
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila["body_photo"] if fila else None


def eliminar_foto_corporal(user_id: int) -> str | None:
    """Elimina el registro de foto corporal y devuelve el nombre/URL anterior."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT body_photo FROM user_profile WHERE user_id = %s", (user_id,)
    )
    fila = cur.fetchone()
    if fila:
        cur.execute("DELETE FROM user_profile WHERE user_id = %s", (user_id,))
        conn.commit()
    cur.close()
    conn.close()
    return fila["body_photo"] if fila else None


# =====================================================
# PRENDAS
# =====================================================

def guardar_prenda(
    archivo: str, tipo: str, colores: str, estilo: str, descripcion: str,
    categoria: str = "otros", user_id: int = 1,
) -> int:
    """Guarda una prenda nueva. Devuelve el id generado."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO prendas (archivo, tipo, colores, estilo, descripcion, categoria, user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (archivo, tipo, colores, estilo, descripcion, categoria, user_id),
    )
    nuevo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return nuevo_id


def listar_prendas(user_id: int = 1) -> list[dict]:
    """Devuelve todas las prendas del usuario, la más reciente primero."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM prendas WHERE user_id = %s ORDER BY id DESC", (user_id,)
    )
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(f) for f in filas]


def marcar_favorito_prenda(prenda_id: int, favorito: bool, user_id: int = 1) -> bool:
    """Marca o desmarca una prenda favorita, solo si pertenece al usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE prendas SET favorito = %s WHERE id = %s AND user_id = %s",
        (favorito, prenda_id, user_id),
    )
    actualizado = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return actualizado


def obtener_prenda(prenda_id: int, user_id: int = 1) -> dict | None:
    """Devuelve una prenda por id, SOLO si pertenece a ese usuario.

    (Antes esta función ignoraba `user_id` y devolvía la prenda de
    cualquier usuario — corregido acá.)
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM prendas WHERE id = %s AND user_id = %s",
        (prenda_id, user_id),
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return dict(fila) if fila else None


def eliminar_prenda(prenda_id: int, user_id: int = 1) -> bool:
    """Elimina una prenda, SOLO si pertenece a ese usuario.

    (Corregido: antes borraba por id sin chequear el dueño.)
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM prendas WHERE id = %s AND user_id = %s",
        (prenda_id, user_id),
    )
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return eliminado


def actualizar_prenda(
    prenda_id: int, tipo: str, colores: str, estilo: str, descripcion: str,
    user_id: int = 1,
) -> bool:
    """Actualiza los datos editables de una prenda, SOLO si es del usuario.

    (Corregido: antes editaba por id sin chequear el dueño.)
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE prendas
        SET tipo = %s, colores = %s, estilo = %s, descripcion = %s
        WHERE id = %s AND user_id = %s
        """,
        (tipo, colores, estilo, descripcion, prenda_id, user_id),
    )
    actualizado = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return actualizado


# =====================================================
# OUTFITS & HISTORIAL
# =====================================================

def guardar_outfit(
    nombre: str, ocasion: str, descripcion: str, prendas_ids: list[int],
    user_id: int = 1, imagen: str | None = None,
) -> int:
    """Guarda un outfit generado en el historial."""
    ids_str = ",".join(str(i) for i in prendas_ids)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO outfits (user_id, nombre, ocasion, descripcion, prendas_ids, favorito, imagen)
        VALUES (%s, %s, %s, %s, %s, FALSE, %s)
        RETURNING id
        """,
        (user_id, nombre, ocasion, descripcion, ids_str, imagen),
    )
    nuevo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return nuevo_id


def listar_outfits(solo_favoritos: bool = False, user_id: int = 1) -> list[dict]:
    """Devuelve los outfits guardados del usuario."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM outfits WHERE user_id = %s"
    params = [user_id]
    if solo_favoritos:
        query += " AND favorito = TRUE"
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(f) for f in filas]


def marcar_favorito(outfit_id: int, favorito: bool, user_id: int = 1) -> bool:
    """Marca o desmarca un outfit como favorito, SOLO si es del usuario.

    (Corregido: antes marcaba por id sin chequear el dueño.)
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE outfits SET favorito = %s WHERE id = %s AND user_id = %s",
        (favorito, outfit_id, user_id),
    )
    actualizado = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return actualizado


def eliminar_outfit(outfit_id: int, user_id: int) -> bool:
    """Elimina un outfit del historial, solo si es del usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM outfits WHERE id = %s AND user_id = %s",
        (outfit_id, user_id),
    )
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return eliminado


# =====================================================
# CACHÉ DE VIRTUAL TRY-ON (AHORRO DE CRÉDITOS FASHN AI)
# =====================================================

def obtener_tryon_cache(user_id: int, body_photo: str, garment_id: int) -> dict | None:
    """Busca si ya se generó un Try-On con esta foto + esta prenda."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM virtual_tryons
        WHERE user_id = %s AND body_photo = %s AND garment_id = %s
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, body_photo, garment_id),
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return dict(fila) if fila else None


def guardar_tryon_cache(user_id: int, body_photo: str, garment_id: int, result_image: str) -> int:
    """Guarda el resultado de un Virtual Try-On en caché."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO virtual_tryons (user_id, body_photo, garment_id, result_image)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, body_photo, garment_id, result_image),
    )
    nuevo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return nuevo_id


def listar_ids_prendas_probadas(user_id: int, body_photo: str) -> list[int]:
    """Ids de prendas que ya tienen un Try-On cacheado con esta foto corporal."""
    if not body_photo:
        return []
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT garment_id FROM virtual_tryons WHERE user_id = %s AND body_photo = %s",
        (user_id, body_photo),
    )
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return [f["garment_id"] for f in filas]


def _clave_combo(prenda_ids: list[int]) -> str:
    """Genera una clave única para un conjunto de prendas, sin importar el orden."""
    return ",".join(str(i) for i in sorted(prenda_ids))


def obtener_combo_cache(user_id: int, body_photo: str, prenda_ids: list[int]) -> dict | None:
    """Busca si este combo exacto ya fue generado antes con esta foto corporal."""
    clave = _clave_combo(prenda_ids)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM combo_tryons
        WHERE user_id = %s AND body_photo = %s AND prendas_key = %s
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, body_photo, clave),
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return dict(fila) if fila else None


def guardar_combo_cache(user_id: int, body_photo: str, prenda_ids: list[int], result_image: str) -> None:
    """Guarda el resultado final de un combo, para no regenerarlo si se repite."""
    clave = _clave_combo(prenda_ids)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO combo_tryons (user_id, body_photo, prendas_key, result_image)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, body_photo, clave, result_image),
    )
    conn.commit()
    cur.close()
    conn.close()

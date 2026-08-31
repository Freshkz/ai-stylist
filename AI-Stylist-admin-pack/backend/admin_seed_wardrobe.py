"""
AI Stylist - Herramienta de Carga Masiva y Sembrado de Armario (Admin Tool)

Este programa:
1. Corre 100% LOCAL en tu computadora.
2. Usa la IA local 'rembg' para quitar el fondo a un lote de fotos de ropa (0 créditos de API, 100% GRATIS).
3. Analiza cada prenda con Groq (tipo, colores, categoría).
4. Sube la prenda recortada (PNG transparente) a Supabase Storage.
5. Asigna el pack de prendas directamente a la cuenta del usuario seleccionado en Supabase Postgres.
"""

import os
import sys
import glob
import io
from PIL import Image
from dotenv import load_dotenv

# Cargar variables de entorno del backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

try:
    from database import get_connection, guardar_prenda, obtener_usuario_por_email, obtener_usuario_por_id
    import storage
    from ai import get_provider
except ImportError as e:
    print(f"❌ Error al importar módulos del backend: {e}")
    sys.exit(1)


def _redimensionar_si_es_necesario(image_bytes: bytes, max_dim: int = 1920) -> bytes:
    """Asegura que la imagen no supere 1920px para acelerar el procesamiento y evitar límites de Groq."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width > max_dim or height > max_dim or (width * height > 16000000):
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            fmt = img.format if img.format in ("PNG", "JPEG", "WEBP") else "JPEG"
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format=fmt, quality=85)
            return output.getvalue()
    except Exception:
        pass
    return image_bytes


def _quitar_fondo_local(image_bytes: bytes) -> tuple[bytes, str]:
    """
    Remueve el fondo usando rembg local en tu PC (0 créditos API).
    Si la imagen ya es un PNG transparente, omite el proceso para ahorrar tiempo.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            print("   ✨ La imagen ya tiene fondo transparente — omitiendo recorte.")
            return image_bytes, "image/png"
    except Exception:
        pass

    try:
        from rembg import remove
        print("   ✂️ Procesando borrado de fondo con IA local (rembg)...")
        output_png = remove(image_bytes)
        if output_png and len(output_png) > 100:
            print("   ✓ Fondo eliminado correctamente (PNG transparente).")
            return output_png, "image/png"
    except Exception as e:
        print(f"   ⚠️ No se pudo usar rembg local ({e}), se mantendrá la foto original.")

    return image_bytes, "image/jpeg"


def listar_todos_los_usuarios() -> list[dict]:
    """Obtiene la lista de usuarios registrados en Supabase Postgres."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, name FROM users ORDER BY id ASC")
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(f) for f in filas]


def main():
    print("=" * 65)
    print("        AI STYLIST — HERRAMIENTA DE CARGA MASIVA DE ARMARIO")
    print("=" * 65)
    print("")

    # 1. Obtener lista de usuarios
    try:
        usuarios = listar_todos_los_usuarios()
    except Exception as e:
        print(f"❌ Error de conexión a la base de datos Supabase: {e}")
        return

    if not usuarios:
        print("❌ No hay usuarios registrados en la base de datos.")
        print("Registrá primero una cuenta en la aplicación web.")
        return

    print("👤 Cuentas encontradas en Supabase Postgres:")
    for idx, u in enumerate(usuarios, 1):
        print(f"   [{idx}] ID {u['id']}: {u['name']} ({u['email']})")
    print("")

    # 2. Selección de usuario de destino
    destino = input("👉 Seleccioná el número o email del usuario destino [por defecto: 1]: ").strip()
    target_user = None

    if not destino:
        target_user = usuarios[0]
    elif destino.isdigit():
        idx_val = int(destino)
        if 1 <= idx_val <= len(usuarios):
            target_user = usuarios[idx_val - 1]
        else:
            target_user = obtener_usuario_por_id(int(destino))
    else:
        target_user = obtener_usuario_por_email(destino)

    if not target_user:
        print(f"❌ No se encontró ningún usuario que coincida con '{destino}'.")
        return

    print(f"🎯 Usuario seleccionado: ID {target_user['id']} — {target_user['name']} ({target_user['email']})")
    print("")

    # 3. Directorio de fotos de prendas
    default_dir = os.path.join(BASE_DIR, "prendas_para_subir")
    os.makedirs(default_dir, exist_ok=True)

    folder_input = input(f"📁 Ruta de la carpeta con las fotos de ropa [por defecto: {default_dir}]: ").strip()
    target_folder = folder_input if folder_input else default_dir

    if not os.path.exists(target_folder):
        print(f"❌ La carpeta '{target_folder}' no existe.")
        return

    # Buscar imágenes
    extensiones = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.PNG", "*.WEBP")
    archivos = []
    for ext in extensiones:
        archivos.extend(glob.glob(os.path.join(target_folder, ext)))

    # Ordenar y eliminar duplicados
    archivos = sorted(list(set(archivos)))

    if not archivos:
        print(f"⚠️ No se encontraron fotos (.jpg, .png, .webp) dentro de: {target_folder}")
        print(f"💡 Guardá las fotos de ropa en esa carpeta y volvé a ejecutar el programa.")
        return

    print(f"📸 Se encontraron {len(archivos)} foto(s) de ropa para procesar.")
    print("-" * 65)

    provider = get_provider()
    exitosas = 0

    for i, filepath in enumerate(archivos, 1):
        filename = os.path.basename(filepath)
        print(f"\n[{i}/{len(archivos)}] Procesando: {filename}")

        try:
            with open(filepath, "rb") as f:
                raw_bytes = f.read()

            # A. Redimensionar si es gigante (para evitar límite de Groq)
            raw_bytes = _redimensionar_si_es_necesario(raw_bytes)

            # B. Borrado de fondo local con rembg (0 créditos de API)
            processed_bytes, mime_type = _quitar_fondo_local(raw_bytes)
            ext_final = ".png" if mime_type == "image/png" else ".jpg"

            # C. Análisis de prendas con Groq AI
            print("   🤖 Analizando prenda con Groq AI...")
            analysis = provider.analyze_garment(processed_bytes, mime_type)

            tipo = analysis.tipo or "prenda sin identificar"
            colores = ", ".join(analysis.colores) if analysis.colores else ""
            categoria = analysis.categoria if analysis.categoria in (
                "tops", "pantalones", "vestidos", "calzado", "abrigos", "accesorios", "otros"
            ) else "otros"

            # D. Subir a Supabase Storage
            print("   ☁️ Subiendo PNG transparente a Supabase Storage...")
            url_publica = storage.subir_bytes(
                processed_bytes,
                carpeta="prendas",
                extension=ext_final,
                content_type=mime_type,
            )

            # E. Guardar en Supabase Postgres
            nuevo_id = guardar_prenda(
                archivo=url_publica,
                tipo=tipo,
                colores=colores,
                estilo=analysis.estilo,
                descripcion=tipo,
                categoria=categoria,
                user_id=target_user["id"],
            )

            print(f"   ✅ Carga exitosa (ID Prenda: {nuevo_id}) -> {tipo} ({colores}) [{categoria}]")
            exitosas += 1

        except Exception as e:
            print(f"   ❌ Error al procesar {filename}: {e}")

    print("\n" + "=" * 65)
    print(f"🎉 ¡PROCESO COMPLETADO! {exitosas} de {len(archivos)} prendas agregadas al armario de {target_user['name']}.")
    print("=" * 65)


if __name__ == "__main__":
    main()

"""
AI Stylist - Backend (Digital Atelier + FASHN Virtual Try-On & Credit Caching)

Este backend:
- Maneja registro, login y sesiones de usuario (cada uno con su propio armario).
- Administra el perfil corporal del usuario ("Mi Modelo").
- Recibe y analiza fotos de prendas y las guarda en el armario.
- Realiza el Virtual Try-On conectándose con Fashn AI.
- Implementa sistema de Caché Inteligente para evitar consumos duplicados de créditos Fashn AI.
- Permite guardar los resultados probados directamente en el Historial de Outfits.
- Las imágenes viven en Supabase Storage (no en disco local), para funcionar en Render.
"""

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel
import os
import uuid
from ai import get_provider
from ai.groq_provider import obtener_estado_groq
from database import (
    init_db,
    guardar_prenda,
    listar_prendas,
    obtener_prenda,
    eliminar_prenda,
    actualizar_prenda,
    guardar_outfit,
    listar_outfits,
    marcar_favorito,
    guardar_foto_corporal,
    obtener_foto_corporal,
    eliminar_foto_corporal,
    obtener_tryon_cache,
    guardar_tryon_cache,
    crear_usuario,
    obtener_usuario_por_email,
    obtener_usuario_por_id,
    actualizar_avatar,
    eliminar_outfit,
    listar_ids_prendas_probadas,
    obtener_combo_cache,
    guardar_combo_cache,
)
from fashn import crear_tryon, FashnError, obtener_creditos
from auth import hash_password, verificar_password, crear_token, obtener_usuario_actual
import storage
from bg_removal import quitar_fondo, RemoveBgError


class PrendaUpdate(BaseModel):
    tipo: str
    colores: str
    estilo: str
    descripcion: str


class ComboIniciarRequest(BaseModel):
    prenda_ids: list[int]


class ComboPasoRequest(BaseModel):
    model_photo: str
    prenda_id: int
    body_photo_original: str | None = None


class ComboFinalizarRequest(BaseModel):
    body_photo_original: str
    prenda_ids: list[int]
    resultado_archivo: str


class OutfitTryonSave(BaseModel):
    nombre: str
    ocasion: str
    descripcion: str
    prenda_id: int | None = None
    prenda_ids: list[int] | None = None
    resultado_archivo: str


class UsuarioRegistro(BaseModel):
    email: str
    password: str
    name: str


class UsuarioLogin(BaseModel):
    email: str
    password: str


load_dotenv()

app = FastAPI(title="AI Stylist Backend")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def read_root():
    return {"status": "ok", "message": "AI Stylist backend funcionando"}


# =====================================================
# AUTENTICACIÓN (REGISTRO, LOGIN, SESIÓN)
# =====================================================

@app.post("/auth/registro")
def registro(datos: UsuarioRegistro):
    email = datos.email.strip().lower()

    if "@" not in email:
        return {"status": "error", "message": "Ingresá un email válido."}
    if len(datos.password) < 6:
        return {"status": "error", "message": "La contraseña debe tener al menos 6 caracteres."}
    if obtener_usuario_por_email(email):
        return {"status": "error", "message": "Ya existe una cuenta con ese email."}

    password_hash = hash_password(datos.password)
    nuevo_id = crear_usuario(email, password_hash, datos.name.strip())
    token = crear_token(nuevo_id)

    return {
        "status": "success",
        "token": token,
        "user": {"id": nuevo_id, "email": email, "name": datos.name},
    }


@app.post("/auth/login")
def login(datos: UsuarioLogin):
    email = datos.email.strip().lower()
    usuario = obtener_usuario_por_email(email)

    if not usuario or not verificar_password(datos.password, usuario["password_hash"]):
        return {"status": "error", "message": "Email o contraseña incorrectos."}

    token = crear_token(usuario["id"])
    return {
        "status": "success",
        "token": token,
        "user": {"id": usuario["id"], "email": usuario["email"], "name": usuario["name"]},
    }


@app.get("/auth/yo")
def quien_soy(user_id: int = Depends(obtener_usuario_actual)):
    usuario = obtener_usuario_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {
        "status": "success",
        "user": {
            "id": usuario["id"],
            "email": usuario["email"],
            "name": usuario["name"],
            "avatar": usuario.get("avatar"),
        },
    }


# =====================================================
# PERFIL CORPORAL ("MI MODELO")
# =====================================================

@app.post("/perfil/modelo")
async def subir_foto_corporal(file: UploadFile = File(...), user_id: int = Depends(obtener_usuario_actual)):
    extension = os.path.splitext(file.filename or "")[1] or ".jpg"
    contenido = await file.read()

    foto_vieja = obtener_foto_corporal(user_id)

    url = storage.subir_bytes(contenido, carpeta="modelo", extension=extension, content_type=file.content_type or "image/jpeg")

    if foto_vieja:
        storage.eliminar_archivo(foto_vieja)

    guardar_foto_corporal(user_id, url)

    return {"status": "success", "message": "Foto corporal guardada con éxito.", "body_photo": url, "url": url}


@app.get("/perfil/modelo")
def ver_foto_corporal(user_id: int = Depends(obtener_usuario_actual)):
    foto = obtener_foto_corporal(user_id)
    if not foto:
        return {"status": "empty", "message": "No tenés una foto corporal configurada todavía."}
    return {"status": "success", "body_photo": foto, "url": foto}


@app.delete("/perfil/modelo")
def borrar_foto_corporal(user_id: int = Depends(obtener_usuario_actual)):
    foto_borrada = eliminar_foto_corporal(user_id)
    if foto_borrada:
        storage.eliminar_archivo(foto_borrada)
    return {"status": "success", "message": "Foto corporal eliminada."}


# =====================================================
# ANÁLISIS DE FOTO GENERAL (no se persiste, solo se analiza)
# =====================================================

@app.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    try:
        provider = get_provider()
        analysis = provider.analyze_image(image_bytes, mime_type)
    except Exception as e:
        return {"status": "error", "message": f"No se pudo analizar la imagen: {str(e)}"}

    return {
        "status": "success",
        "message": "Foto recibida correctamente",
        "original_filename": file.filename,
        "analysis": analysis.model_dump(),
    }


# =====================================================
# ARMARIO DIGITAL
# =====================================================




@app.post("/armario/subir")
async def subir_prenda(file: UploadFile = File(...), user_id: int = Depends(obtener_usuario_actual)):
    """
    Sube y analiza una prenda nueva para el armario. El fondo se remueve
    con la API de remove.bg (fuera del servidor, no consume memoria de
    Render). Si remove.bg falla por el motivo que sea (sin créditos ese
    mes, error puntual), seguimos con la foto original en vez de cortar
    el flujo del usuario.
    """
    image_bytes = await file.read()
    extension = os.path.splitext(file.filename or "")[1] or ".jpg"
    mime_type = file.content_type or ("image/png" if extension.lower() == ".png" else "image/jpeg")

    try:
        provider = get_provider()
        analysis = provider.analyze_garment(image_bytes, mime_type)
    except Exception as e:
        return {"status": "error", "message": f"No se pudo analizar la imagen: {str(e)}"}

    try:
        processed_bytes = quitar_fondo(image_bytes)
        extension = ".png"
        mime_type = "image/png"
    except RemoveBgError as e:
        print(f"[REMOVE.BG WARN] No se pudo quitar el fondo, se sube la imagen original: {e}")
        processed_bytes = image_bytes

    url = storage.subir_bytes(processed_bytes, carpeta="prendas", extension=extension, content_type=mime_type)

    tipo = analysis.tipo or "prenda sin identificar"
    colores = ", ".join(analysis.colores) if analysis.colores else ""
    categoria = analysis.categoria if analysis.categoria in ("tops", "pantalones", "vestidos", "calzado", "abrigos", "accesorios", "otros") else "otros"

    nuevo_id = guardar_prenda(
        archivo=url,
        tipo=tipo,
        colores=colores,
        estilo=analysis.estilo,
        descripcion=tipo,
        categoria=categoria,
        user_id=user_id,
    )

    return {
        "status": "success",
        "message": "Prenda agregada al armario",
        "id": nuevo_id,
        "archivo": url,
        "tipo": tipo,
        "colores": colores,
        "estilo": analysis.estilo,
        "categoria": categoria,
    }

@app.get("/armario")
def obtener_armario(user_id: int = Depends(obtener_usuario_actual)):
    prendas = listar_prendas(user_id=user_id)
    body_photo = obtener_foto_corporal(user_id)
    ids_probadas = set(listar_ids_prendas_probadas(user_id, body_photo)) if body_photo else set()

    for p in prendas:
        p["probada"] = p["id"] in ids_probadas

    return {"status": "success", "prendas": prendas}


@app.delete("/armario/{prenda_id}")
def borrar_prenda(prenda_id: int, user_id: int = Depends(obtener_usuario_actual)):
    prenda = obtener_prenda(prenda_id, user_id=user_id)
    if not prenda:
        return {"status": "error", "message": "No se encontró esa prenda"}

    eliminado = eliminar_prenda(prenda_id, user_id=user_id)
    if not eliminado:
        return {"status": "error", "message": "No se pudo eliminar la prenda"}

    storage.eliminar_archivo(prenda["archivo"])
    return {"status": "success", "id": prenda_id}


@app.put("/armario/{prenda_id}")
def editar_prenda(prenda_id: int, datos: PrendaUpdate, user_id: int = Depends(obtener_usuario_actual)):
    actualizado = actualizar_prenda(
        prenda_id,
        tipo=datos.tipo,
        colores=datos.colores,
        estilo=datos.estilo,
        descripcion=datos.descripcion,
        user_id=user_id,
    )
    if not actualizado:
        return {"status": "error", "message": "No se encontró esa prenda"}
    return {"status": "success", "id": prenda_id}


# =====================================================
# VIRTUAL TRY-ON CON FASHN AI & CACHÉ DE CRÉDITOS
# =====================================================

@app.post("/try-on")
async def virtual_try_on(
    prenda_id: int = Form(...),
    persona: UploadFile = File(None),
    user_id: int = Depends(obtener_usuario_actual),
):
    body_photo_url = None

    if persona and persona.filename:
        contenido = await persona.read()
        extension = os.path.splitext(persona.filename)[1] or ".jpg"
        body_photo_url = storage.subir_bytes(contenido, carpeta="modelo", extension=extension, content_type=persona.content_type or "image/jpeg")
    else:
        body_photo_url = obtener_foto_corporal(user_id)

    if not body_photo_url:
        return {
            "status": "error",
            "code": "NO_BODY_PHOTO",
            "message": "Primero necesitás subir una foto de cuerpo completo en 'Mi modelo' para utilizar el probador virtual.",
        }

    prenda = obtener_prenda(prenda_id, user_id=user_id)
    if not prenda:
        return {"status": "error", "message": "No se encontró esa prenda en tu armario."}

    cached = obtener_tryon_cache(user_id, body_photo_url, prenda_id)
    if cached:
        return {
            "status": "success",
            "message": "Virtual Try-On (recuperado de caché sin gastar créditos)",
            "resultado": cached["result_image"],
            "resultado_archivo": cached["result_image"],
            "cached": True,
            "prenda": prenda,
        }

    try:
        creditos_info = obtener_creditos()
        creditos_actuales = creditos_info.get("total")
    except FashnError:
        creditos_actuales = None

    if creditos_actuales is not None and creditos_actuales <= 0:
        return {
            "status": "error",
            "code": "NO_CREDITS",
            "message": "Te quedaste sin créditos de Fashn AI. Recargá saldo en fashn.ai para seguir generando pruebas nuevas (las que ya probaste antes siguen disponibles gratis desde el caché).",
        }

    try:
        resultado_fashn = crear_tryon(
            model_image_url=body_photo_url,
            garment_image_url=prenda["archivo"],
            mode="balanced",
            categoria=prenda.get("categoria"),
        )

        contenido_resultado = storage.descargar_bytes(resultado_fashn["output"][0])
        result_url = storage.subir_bytes(contenido_resultado, carpeta="tryon", extension=".jpg", content_type="image/jpeg")

        guardar_tryon_cache(user_id, body_photo_url, prenda_id, result_url)

        aviso_creditos = None
        try:
            creditos_post = obtener_creditos().get("total")
            if creditos_post is not None and creditos_post <= 5:
                aviso_creditos = f"Te quedan {creditos_post} créditos de Fashn AI."
        except FashnError:
            pass

        return {
            "status": "success",
            "message": "Virtual Try-On completado con Fashn AI.",
            "resultado": result_url,
            "resultado_archivo": result_url,
            "cached": False,
            "prenda": prenda,
            "aviso_creditos": aviso_creditos,
        }

    except FashnError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Error inesperado: {str(e)}"}


# =====================================================
# TRY-ON COMBINADO (VARIAS PRENDAS ENCADENADAS)
# =====================================================

@app.post("/try-on/combo/iniciar")
def iniciar_combo(datos: ComboIniciarRequest, user_id: int = Depends(obtener_usuario_actual)):
    if not datos.prenda_ids:
        return {"status": "error", "message": "No se seleccionó ninguna prenda."}

    body_photo = obtener_foto_corporal(user_id)
    if not body_photo:
        return {
            "status": "error",
            "code": "NO_BODY_PHOTO",
            "message": "Primero necesitás subir una foto de cuerpo completo en 'Mi modelo'.",
        }

    combo_cache = obtener_combo_cache(user_id, body_photo, datos.prenda_ids)
    if combo_cache:
        prendas_combo = [obtener_prenda(pid, user_id=user_id) for pid in datos.prenda_ids]
        prendas_combo = [p for p in prendas_combo if p]
        return {
            "status": "success",
            "cached_combo": True,
            "resultado_final": combo_cache["result_image"],
            "resultado_archivo": combo_cache["result_image"],
            "prendas": prendas_combo,
        }

    return {"status": "success", "cached_combo": False, "body_photo": body_photo}


@app.post("/try-on/combo/paso")
def paso_combo(datos: ComboPasoRequest, user_id: int = Depends(obtener_usuario_actual)):
    prenda = obtener_prenda(datos.prenda_id, user_id=user_id)
    if not prenda:
        return {"status": "error", "message": "Prenda no encontrada."}

    cached = obtener_tryon_cache(user_id, datos.model_photo, datos.prenda_id)
    if cached:
        return {
            "status": "success",
            "resultado": cached["result_image"],
            "resultado_archivo": cached["result_image"],
            "cached": True,
            "prenda": prenda,
        }

    try:
        creditos_info = obtener_creditos()
        creditos_actuales = creditos_info.get("total")
    except FashnError:
        creditos_actuales = None

    if creditos_actuales is not None and creditos_actuales <= 0:
        return {
            "status": "error",
            "code": "NO_CREDITS",
            "message": "Sin créditos de Fashn AI para continuar con esta prenda.",
        }

    try:
        resultado_fashn = crear_tryon(
            model_image_url=datos.model_photo,
            garment_image_url=prenda["archivo"],
            mode="balanced",
            categoria=prenda.get("categoria"),
        )

        contenido_resultado = storage.descargar_bytes(resultado_fashn["output"][0])
        result_url = storage.subir_bytes(contenido_resultado, carpeta="tryon", extension=".jpg", content_type="image/jpeg")

        guardar_tryon_cache(user_id, datos.model_photo, datos.prenda_id, result_url)

        if datos.body_photo_original and datos.body_photo_original != datos.model_photo:
            guardar_tryon_cache(user_id, datos.body_photo_original, datos.prenda_id, result_url)

        return {
            "status": "success",
            "resultado": result_url,
            "resultado_archivo": result_url,
            "cached": False,
            "prenda": prenda,
        }

    except FashnError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Error inesperado: {str(e)}"}


@app.post("/try-on/combo/finalizar")
def finalizar_combo(datos: ComboFinalizarRequest, user_id: int = Depends(obtener_usuario_actual)):
    guardar_combo_cache(user_id, datos.body_photo_original, datos.prenda_ids, datos.resultado_archivo)

    aviso_creditos = None
    try:
        creditos_post = obtener_creditos().get("total")
        if creditos_post is not None and creditos_post <= 5:
            aviso_creditos = f"Te quedan {creditos_post} créditos de Fashn AI."
    except FashnError:
        pass

    return {"status": "success", "aviso_creditos": aviso_creditos}


# =====================================================
# GUARDAR OUTFIT DE TRY-ON EN HISTORIAL
# =====================================================

@app.post("/armario/outfits/guardar_tryon")
def guardar_tryon_como_outfit(datos: OutfitTryonSave, user_id: int = Depends(obtener_usuario_actual)):
    ids_crudos = datos.prenda_ids if datos.prenda_ids else ([datos.prenda_id] if datos.prenda_id else [])
    prenda_ids = [pid for pid in ids_crudos if obtener_prenda(pid, user_id=user_id)]

    nuevo_id = guardar_outfit(
        nombre=datos.nombre or "Look Digital Atelier",
        ocasion=datos.ocasion or "Estilo Personal",
        descripcion=datos.descripcion or "Outfit generado con el Probador Virtual Digital Atelier.",
        prendas_ids=prenda_ids,
        user_id=user_id,
        imagen=datos.resultado_archivo,
    )

    return {"status": "success", "message": "Outfit guardado en tu diario de estilo", "id": nuevo_id}


# =====================================================
# GENERAR Y CONSULTAR OUTFITS / HISTORIAL
# =====================================================

@app.get("/armario/outfits")
def generar_outfits(ocasion: str = "todas", clima: str = "cualquiera", user_id: int = Depends(obtener_usuario_actual)):
    prendas = listar_prendas(user_id=user_id)

    if len(prendas) < 2:
        return {"status": "error", "message": "Necesitás al menos 2 prendas en tu armario para generar outfits."}

    try:
        provider = get_provider()
        sugerencias = provider.generate_outfits(prendas, ocasion=ocasion, clima=clima)
    except Exception as e:
        return {"status": "error", "message": f"No se pudieron generar los outfits: {str(e)}"}

    prendas_por_id = {p["id"]: p for p in prendas}
    outfits_completos = []

    for outfit in sugerencias.outfits:
        items = [prendas_por_id[pid] for pid in outfit.prendas_ids if pid in prendas_por_id]

        nuevo_id = guardar_outfit(
            nombre=outfit.nombre,
            ocasion=outfit.ocasion,
            descripcion=outfit.descripcion,
            prendas_ids=outfit.prendas_ids,
            user_id=user_id,
        )

        outfits_completos.append({
            "id": nuevo_id,
            "nombre": outfit.nombre,
            "ocasion": outfit.ocasion,
            "descripcion": outfit.descripcion,
            "favorito": False,
            "prendas": items,
            "imagen": None,
        })

    return {"status": "success", "outfits": outfits_completos}


@app.get("/armario/historial")
def obtener_historial(favoritos: bool = False, user_id: int = Depends(obtener_usuario_actual)):
    outfits = listar_outfits(solo_favoritos=favoritos, user_id=user_id)
    prendas = listar_prendas(user_id=user_id)
    prendas_por_id = {p["id"]: p for p in prendas}

    resultado = []
    for o in outfits:
        ids = [int(i) for i in o["prendas_ids"].split(",") if i]
        items = [prendas_por_id[i] for i in ids if i in prendas_por_id]
        resultado.append({
            "id": o["id"],
            "nombre": o["nombre"],
            "ocasion": o["ocasion"],
            "descripcion": o["descripcion"],
            "favorito": bool(o["favorito"]),
            "fecha": o["fecha"],
            "prendas": items,
            "imagen": o.get("imagen"),
        })

    return {"status": "success", "outfits": resultado}


@app.post("/armario/outfits/{outfit_id}/favorito")
def cambiar_favorito(outfit_id: int, valor: bool, user_id: int = Depends(obtener_usuario_actual)):
    actualizado = marcar_favorito(outfit_id, valor, user_id=user_id)
    if not actualizado:
        return {"status": "error", "message": "No se encontró ese outfit"}
    return {"status": "success", "id": outfit_id, "favorito": valor}


@app.delete("/armario/outfits/{outfit_id}")
def borrar_outfit(outfit_id: int, user_id: int = Depends(obtener_usuario_actual)):
    eliminado = eliminar_outfit(outfit_id, user_id=user_id)
    if not eliminado:
        return {"status": "error", "message": "No se encontró ese outfit"}
    return {"status": "success", "id": outfit_id}


@app.get("/estado/creditos")
def estado_creditos():
    fashn_data = None
    fashn_error = None

    try:
        fashn_data = obtener_creditos()
    except FashnError as e:
        fashn_error = str(e)

    return {"status": "success", "fashn": fashn_data, "fashn_error": fashn_error, "groq": obtener_estado_groq()}


@app.post("/perfil/avatar")
async def subir_avatar(file: UploadFile = File(...), user_id: int = Depends(obtener_usuario_actual)):
    extension = os.path.splitext(file.filename or "")[1] or ".jpg"
    contenido = await file.read()

    url = storage.subir_bytes(contenido, carpeta="avatars", extension=extension, content_type=file.content_type or "image/jpeg")
    actualizar_avatar(user_id, url)

    return {"status": "success", "url": url}


# =====================================================
# SERVIDOR ESTÁTICO DEL FRONTEND (ACCESO MÓVIL DIRECTO)
# =====================================================

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
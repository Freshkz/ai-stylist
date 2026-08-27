import os
import time
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
BACKEND_DIR = PROJECT_DIR / "backend"

INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"

PERSON_IMAGE = INPUTS_DIR / "person.jpg"
GARMENT_IMAGE = INPUTS_DIR / "garment.jpg"

ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

API_KEY = os.getenv("FASHN_API_KEY")

API_URL = "https://api.fashn.ai/v1/run"
STATUS_URL = "https://api.fashn.ai/v1/status"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# FUNCIONES
# ============================================================

def image_to_base64(path: Path) -> str:
    """
    Convierte una imagen local a Base64 con el prefijo
    necesario para que FASHN pueda procesarla.
    """

    with open(path, "rb") as file:
        encoded = base64.b64encode(file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


# ============================================================
# INICIO
# ============================================================

print("=" * 60)
print("       AI STYLIST — PRUEBA VIRTUAL TRY-ON")
print("=" * 60)


# ============================================================
# VALIDACIONES
# ============================================================

if not API_KEY:
    print("\n❌ No se encontró FASHN_API_KEY.")
    print(f"Busqué en: {ENV_FILE}")
    raise SystemExit(1)

print("\n✅ API key encontrada.")

if not PERSON_IMAGE.exists():
    print(f"\n❌ No existe:")
    print(PERSON_IMAGE)
    raise SystemExit(1)

if not GARMENT_IMAGE.exists():
    print(f"\n❌ No existe:")
    print(GARMENT_IMAGE)
    raise SystemExit(1)

OUTPUTS_DIR.mkdir(exist_ok=True)

print(f"📸 Persona: {PERSON_IMAGE.name}")
print(f"👕 Prenda:  {GARMENT_IMAGE.name}")


# ============================================================
# CONVERTIR IMÁGENES
# ============================================================

print("\n🔄 Preparando imágenes...")

try:
    person_base64 = image_to_base64(PERSON_IMAGE)
    garment_base64 = image_to_base64(GARMENT_IMAGE)
except Exception as e:
    print("\n❌ Error preparando las imágenes:")
    print(e)
    raise SystemExit(1)

print("✅ Imágenes preparadas.")


# ============================================================
# CREAR TRY-ON
# ============================================================

print("\n🤖 Iniciando Virtual Try-On...")
print("   Modelo: tryon-v1.6")
print("   Modo: performance")
print("   Samples: 1")
print()
print("⚠️ Si la solicitud es aceptada, consumirá 1 crédito.")


payload = {
    "model_name": "tryon-v1.6",
    "inputs": {
        "model_image": person_base64,
        "garment_image": garment_base64,
        "category": "auto",
        "garment_photo_type": "auto",
        "mode": "performance",
        "num_samples": 1,
        "output_format": "jpeg",
        "return_base64": False,
    },
}


try:
    response = requests.post(
        API_URL,
        headers=HEADERS,
        json=payload,
        timeout=120,
    )
except requests.RequestException as e:
    print("\n❌ Error de conexión:")
    print(e)
    raise SystemExit(1)


# ============================================================
# COMPROBAR RESPUESTA
# ============================================================

if not response.ok:

    print("\n❌ FASHN rechazó la solicitud.")
    print(f"HTTP: {response.status_code}")

    try:
        print(response.json())
    except Exception:
        print(response.text)

    raise SystemExit(1)


data = response.json()

print("\n📦 Respuesta de FASHN:")
print(data)


prediction_id = data.get("id")

if not prediction_id:

    print("\n❌ FASHN no devolvió un prediction ID.")

    if data.get("error"):
        print("Error:", data["error"])

    raise SystemExit(1)


print(f"\n🆔 Prediction ID:")
print(prediction_id)


# ============================================================
# ESPERAR RESULTADO
# ============================================================

print("\n⏳ Esperando resultado...")


result = None

for attempt in range(40):

    time.sleep(2)

    try:
        status_response = requests.get(
            f"{STATUS_URL}/{prediction_id}",
            headers={
                "Authorization": f"Bearer {API_KEY}",
            },
            timeout=60,
        )
    except requests.RequestException as e:

        print("\n❌ Error consultando el estado:")
        print(e)
        raise SystemExit(1)


    if not status_response.ok:

        print("\n❌ Error consultando el estado.")
        print(f"HTTP: {status_response.status_code}")
        print(status_response.text)

        raise SystemExit(1)


    result = status_response.json()

    status = result.get("status")

    print(
        f"   Intento {attempt + 1}/40 → {status}"
    )


    if status == "completed":
        break


    if status in ("failed", "canceled"):

        print("\n❌ El Try-On terminó con error.")

        print(result)

        raise SystemExit(1)

else:

    print("\n❌ Se agotó el tiempo de espera.")

    raise SystemExit(1)


# ============================================================
# RESULTADO
# ============================================================

print("\n🎉 ¡TRY-ON COMPLETADO!")


output = result.get("output")


if not output:

    print("\n❌ FASHN no devolvió ninguna imagen.")
    print(result)

    raise SystemExit(1)


if isinstance(output, list):

    output_url = output[0]

else:

    output_url = output


print("\n🔗 Resultado:")
print(output_url)


# ============================================================
# DESCARGAR IMAGEN
# ============================================================

print("\n📥 Descargando resultado...")


try:

    image_response = requests.get(
        output_url,
        timeout=120,
    )

except requests.RequestException as e:

    print("\n❌ Error descargando resultado:")
    print(e)

    raise SystemExit(1)


if not image_response.ok:

    print("\n❌ No se pudo descargar la imagen.")

    print(
        f"HTTP: {image_response.status_code}"
    )

    raise SystemExit(1)


output_file = OUTPUTS_DIR / "fashn_result.jpg"


with open(output_file, "wb") as file:

    file.write(image_response.content)


# ============================================================
# FIN
# ============================================================

print()
print("=" * 60)
print("              ✅ TERMINADO")
print("=" * 60)

print()
print("🖼️ Resultado guardado en:")

print(output_file)

print()
print("Abrí esa imagen para comprobar el resultado.")
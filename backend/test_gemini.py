import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ No se encontró GOOGLE_API_KEY en el archivo .env")
    exit()

print("🔑 API key encontrada.")
print("🤖 Probando Gemini 2.5 Flash...")

try:
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Respondé solamente: Hola, AI Stylist funciona."
    )

    print("\n✅ ¡CONEXIÓN EXITOSA!")
    print("Respuesta de Gemini:")
    print(response.text)

except Exception as e:
    print("\n❌ ERROR:")
    print(type(e).__name__)
    print(str(e))
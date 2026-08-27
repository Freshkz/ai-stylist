# AI Stylist — Fase 1

Aplicación web básica: subir una foto, verla en pantalla, enviarla a un backend FastAPI.

## Estructura

```
AI-Stylist/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── uploads/        (se crea sola al recibir la primera foto)
└── README.md
```

## Cómo ejecutarlo

### 1. Backend

```bash
cd AI-Stylist/backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

Debería quedar corriendo en: http://127.0.0.1:8000

Probalo abriendo esa URL en el navegador: tiene que responder
`{"status":"ok","message":"AI Stylist backend funcionando"}`

### 2. Frontend

No hace falta ningún servidor especial. Simplemente abrí
`AI-Stylist/frontend/index.html` con doble click en tu navegador
(o con la extensión "Live Server" de VS Code, si la tenés).

## Cómo comprobar que funciona

1. Con el backend corriendo, abrí `index.html`.
2. Hacé click en el input y elegí una foto.
3. Deberías ver la vista previa de la imagen.
4. Hacé click en "Enviar foto al servidor".
5. Debería aparecer un mensaje verde: "✅ Foto recibida correctamente".
6. Fijate en la carpeta `AI-Stylist/uploads/`: debería haber aparecido
   un archivo nuevo con un nombre tipo `a1b2c3d4....jpg`.

## Errores comunes

- **"Failed to fetch" / error de red**: el backend no está corriendo,
  o está corriendo en otro puerto. Verificá que `uvicorn` esté activo.
- **Error de CORS en la consola del navegador**: revisá que
  `CORSMiddleware` esté en `main.py` (ya está incluido en este código).
- **No aparece el botón habilitado**: solo se habilita después de elegir
  una foto válida.

const BACKEND_URL = window.location.origin && !window.location.origin.includes("file:")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// El backend ahora devuelve URLs completas de Supabase Storage para las
// fotos (https://...supabase.co/storage/...). imgUrl() las deja tal cual;
// solo antepone BACKEND_URL si en algún caso llegara una ruta relativa
// vieja (ej. datos ya guardados antes de la migración).
function imgUrl(pathOrUrl) {
  if (!pathOrUrl) return "";
  return pathOrUrl.startsWith("http") ? pathOrUrl : `${BACKEND_URL}${pathOrUrl.startsWith("/") ? "" : "/uploads/"}${pathOrUrl}`;
}

// ============================
// Sesión (login persistente por navegador, tipo Facebook)
// ============================

const TOKEN_KEY = "ai_stylist_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function guardarSesion(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function cerrarSesion() {
  localStorage.removeItem(TOKEN_KEY);
  mostrarPantallaLogin();
}

// Wrapper de fetch que agrega el token automáticamente a cada pedido
// protegido, y desloguea sola si el token venció o es inválido.
async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    cerrarSesion();
    throw new Error("Tu sesión expiró. Volvé a iniciar sesión.");
  }

  return res;
}

function mostrarPantallaLogin() {
  const authScreen = document.getElementById("authScreen");
  const appShell = document.getElementById("appShell");
  if (authScreen) authScreen.hidden = false;
  if (appShell) appShell.style.display = "none";
}

function mostrarApp() {
  const authScreen = document.getElementById("authScreen");
  const appShell = document.getElementById("appShell");
  if (authScreen) authScreen.hidden = true;
  if (appShell) appShell.style.display = "";
}

// --- Tabs login / registro ---
document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const modo = tab.dataset.authTab;
    document.getElementById("loginForm").hidden = modo !== "login";
    document.getElementById("registroForm").hidden = modo !== "registro";
  });
});

// --- Login ---
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById("loginError");
    errorEl.hidden = true;

    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
      const res = await authFetch(`${BACKEND_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();

      if (data.status === "error") {
        errorEl.textContent = data.message;
        errorEl.hidden = false;
        return;
      }

      guardarSesion(data.token);
      mostrarApp();
      location.reload(); // recarga limpia para que todo el armario cargue con la sesión activa
    } catch (error) {
      errorEl.textContent = "No se pudo conectar con el servidor.";
      errorEl.hidden = false;
    }
  });
}

// --- Registro ---
const registroForm = document.getElementById("registroForm");
if (registroForm) {
  registroForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById("registroError");
    errorEl.hidden = true;

    const name = document.getElementById("registroName").value.trim();
    const email = document.getElementById("registroEmail").value.trim();
    const password = document.getElementById("registroPassword").value;

    try {
      const res = await authFetch(`${BACKEND_URL}/auth/registro`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();

      if (data.status === "error") {
        errorEl.textContent = data.message;
        errorEl.hidden = false;
        return;
      }

      guardarSesion(data.token);
      mostrarApp();
      location.reload();
    } catch (error) {
      errorEl.textContent = "No se pudo conectar con el servidor.";
      errorEl.hidden = false;
    }
  });
}

// --- Al cargar la página: ¿hay sesión guardada? ---
if (getToken()) {
  mostrarApp();
} else {
  mostrarPantallaLogin();
}

// =====================================================
// ANALIZAR OUTFIT — FASE 1 Y 2
// =====================================================

const photoInput = document.getElementById("photoInput");
const previewBox = document.getElementById("previewBox");
const previewImage = document.getElementById("previewImage");
const sendButton = document.getElementById("sendButton");
const responseBox = document.getElementById("responseBox");

let selectedFile = null;




const photoDropzone = document.getElementById("photoDropzone");

if (photoInput) {

  photoInput.addEventListener("change", (event) => {

    const file = event.target.files[0];

    responseBox.textContent = "";
    responseBox.className = "response-box";

    if (!file) {

      selectedFile = null;

      if (previewBox) {
        previewBox.style.display = "none";
      }

      if (photoDropzone) {
        photoDropzone.style.display = "flex";
      }

      sendButton.disabled = true;

      return;
    }

    selectedFile = file;

    previewImage.src =
      URL.createObjectURL(file);

    previewBox.style.display = "block";

    if (photoDropzone) {
      photoDropzone.style.display = "none";
    }

    sendButton.disabled = false;

  });

}


// Click en el preview para volver a elegir otra foto
if (previewBox) {

  previewBox.style.cursor = "pointer";

  previewBox.addEventListener("click", () => {
    photoInput.click();
  });

}


if (sendButton) {

  sendButton.addEventListener(
    "click",
    async () => {

      if (!selectedFile) return;

      sendButton.disabled = true;
      sendButton.textContent = "Analizando...";

      responseBox.textContent = "";
      responseBox.className =
        "response-box";


      const formData =
        new FormData();

      formData.append(
        "file",
        selectedFile
      );


      try {

        const res = await authFetch(
          `${BACKEND_URL}/upload`,
          {
            method: "POST",
            body: formData
          }
        );


        const data =
          await res.json();


        if (data.status === "error") {
          throw new Error(
            data.message
          );
        }


        const a =
          data.analysis;


        const recomendacionesTexto =
          a.recomendaciones &&
          a.recomendaciones.length

            ? a.recomendaciones
                .map(
                  (r, i) =>
                    `${i + 1}. ${r}`
                )
                .join("\n")

            : "(sin recomendaciones esta vez)";


        responseBox.classList.add(
          "success"
        );


        responseBox.textContent =
          `✓ ${data.message}\n\n` +

          `👕 Prendas: ${
            a.prendas.join(", ")
          }\n` +

          `🎨 Colores: ${
            a.colores.join(", ")
          }\n` +

          `✨ Estilo: ${
            a.estilo
          }\n\n` +

          `${a.descripcion}\n\n` +

          `💡 Recomendaciones:\n${
            recomendacionesTexto
          }`;


      } catch (error) {

        responseBox.classList.add(
          "error"
        );


        responseBox.textContent =
          `❌ Error: ${error.message}`;


      } finally {

        sendButton.disabled = false;

        sendButton.textContent =
          "Analizar mi estilo";

      }

    }
  );

}


// =====================================================
// MI ARMARIO — FASE 3
// =====================================================

const garmentInput =
  document.getElementById(
    "garmentInput"
  );


const uploadGarmentButton =
  document.getElementById(
    "uploadGarmentButton"
  );


const garmentResponseBox =
  document.getElementById(
    "garmentResponseBox"
  );


const loadWardrobeButton =
  document.getElementById(
    "loadWardrobeButton"
  );


const wardrobeGrid =
  document.getElementById(
    "wardrobeGrid"
  );


let selectedGarmentFiles = [];

const garmentPreview = document.getElementById("garmentPreview");
const garmentPreviewGrid = document.getElementById("garmentPreviewGrid");
const garmentPreviewCount = document.getElementById("garmentPreviewCount");
const cancelGarmentPreview = document.getElementById("cancelGarmentPreview");


// =====================================================
// SELECCIONAR PRENDA
// =====================================================

if (garmentInput) {

  garmentInput.addEventListener("change", (event) => {

    selectedGarmentFiles = Array.from(event.target.files || []);

    if (uploadGarmentButton) {
      uploadGarmentButton.disabled = selectedGarmentFiles.length === 0;
    }

    if (garmentResponseBox) {
      garmentResponseBox.textContent = "";
      garmentResponseBox.className = "response-box";
    }

    renderGarmentPreview();

  });

}

function renderGarmentPreview() {

  if (!garmentPreview || !garmentPreviewGrid) return;

  if (!selectedGarmentFiles.length) {
    garmentPreview.hidden = true;
    garmentPreviewGrid.innerHTML = "";
    return;
  }

  garmentPreviewGrid.innerHTML = "";

  selectedGarmentFiles.forEach((file, index) => {

    const wrap = document.createElement("div");
    wrap.className = "preview-thumb-wrap";

    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    wrap.appendChild(img);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "preview-thumb-remove";
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", () => {
      selectedGarmentFiles.splice(index, 1);
      renderGarmentPreview();
      if (uploadGarmentButton) {
        uploadGarmentButton.disabled = selectedGarmentFiles.length === 0;
      }
    });
    wrap.appendChild(removeBtn);

    garmentPreviewGrid.appendChild(wrap);

  });

  if (garmentPreviewCount) {
    garmentPreviewCount.textContent =
      selectedGarmentFiles.length === 1
        ? "1 prenda seleccionada"
        : `${selectedGarmentFiles.length} prendas seleccionadas`;
  }

  garmentPreview.hidden = false;

}

if (cancelGarmentPreview) {

  cancelGarmentPreview.addEventListener("click", () => {

    selectedGarmentFiles = [];
    garmentInput.value = "";

    if (uploadGarmentButton) {
      uploadGarmentButton.disabled = true;
    }

    renderGarmentPreview();

  });

}

// =====================================================
// DRAG & DROP DE PRENDA
// =====================================================

// Bloquea el comportamiento por defecto del navegador
// (abrir la imagen en una pestaña nueva) en TODA la
// página, no solo dentro del recuadro de "soltar".
window.addEventListener("dragover", (event) => {
  event.preventDefault();
});

window.addEventListener("drop", (event) => {
  event.preventDefault();
});

const wardrobeDropzone =
  document.getElementById(
    "wardrobeDropzone"
  );

if (wardrobeDropzone && garmentInput) {

  ["dragenter", "dragover"].forEach(
    (eventName) => {

      wardrobeDropzone.addEventListener(
        eventName,
        (event) => {

          event.preventDefault();

          wardrobeDropzone.classList.add(
            "dragging"
          );

        }
      );

    }
  );

  ["dragleave", "drop"].forEach(
    (eventName) => {

      wardrobeDropzone.addEventListener(
        eventName,
        (event) => {

          event.preventDefault();

          wardrobeDropzone.classList.remove(
            "dragging"
          );

        }
      );

    }
  );

  wardrobeDropzone.addEventListener(
    "drop",
    (event) => {

      const archivos = event.dataTransfer.files;

      if (!archivos || !archivos.length) return;

      const transferencia = new DataTransfer();

      Array.from(archivos).forEach((archivo) => {
        transferencia.items.add(archivo);
      });

      garmentInput.files = transferencia.files;

      garmentInput.dispatchEvent(
        new Event("change")
      );

    }
  );

}

// =====================================================
// SUBIR PRENDA
// =====================================================

if (uploadGarmentButton) {

  uploadGarmentButton.addEventListener("click", async () => {

    if (!selectedGarmentFiles.length) return;

    uploadGarmentButton.disabled = true;

    if (garmentResponseBox) {
      garmentResponseBox.textContent = "";
      garmentResponseBox.className = "response-box";
    }

    const total = selectedGarmentFiles.length;
    let exitosas = 0;
    const errores = [];

    // Subimos de a una, en secuencia, para no saturar
    // de golpe el límite de peticiones por minuto de Groq.
    for (let i = 0; i < total; i++) {

      const file = selectedGarmentFiles[i];
      uploadGarmentButton.textContent = `✂️ Removiendo fondo y analizando ${i + 1}/${total}...`;

      if (garmentResponseBox) {
        garmentResponseBox.className = "response-box";
        garmentResponseBox.textContent = `✂️ Removiendo fondo con IA local y guardando PNG transparente (${i + 1}/${total})...`;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {

        const res = await authFetch(`${BACKEND_URL}/armario/subir`, {
          method: "POST",
          body: formData,
        });

        const data = await res.json();

        if (data.status === "error") {
          errores.push(`${file.name}: ${data.message}`);
          continue;
        }

        exitosas++;

        showGarmentToast({
          tipo: data.tipo || "Prenda",
          colores: data.colores || "Sin color",
          estilo: data.estilo || "Sin estilo",
        });

        cargarEstadoCreditos();

      } catch (error) {
        errores.push(`${file.name}: ${error.message}`);
      }

    }

    await loadWardrobe(false);

    if (garmentResponseBox) {
      if (errores.length) {
        garmentResponseBox.classList.add(errores.length === total ? "error" : "success");
        garmentResponseBox.textContent =
          `✓ ${exitosas} de ${total} prendas agregadas.\n` +
          `❌ Con problemas:\n${errores.join("\n")}`;
      } else {
        garmentResponseBox.className = "response-box";
        garmentResponseBox.textContent = "";
      }
    }

    garmentInput.value = "";
    selectedGarmentFiles = [];
    renderGarmentPreview();

    uploadGarmentButton.disabled = true;
    uploadGarmentButton.textContent = "Agregar al armario";

    setTimeout(() => {
      if (!wardrobeGrid) return;
      const items = wardrobeGrid.querySelectorAll(".wardrobe-item");
      const newestItem = items[items.length - 1];
      if (newestItem) {
        newestItem.classList.add("new-garment");
        setTimeout(() => newestItem.classList.remove("new-garment"), 1000);
      }
    }, 100);

  });

}


// =====================================================
// TOAST — NUEVA PRENDA
// =====================================================

function showGarmentToast({
  tipo,
  colores,
  estilo
}) {

  // Eliminar toast anterior

  const oldToast =
    document.querySelector(
      ".garment-toast"
    );


  if (oldToast) {
    oldToast.remove();
  }


  const toast =
    document.createElement(
      "div"
    );


  toast.className =
    "garment-toast";


  toast.innerHTML = `

    <div class="garment-toast-icon">
      ✦
    </div>

    <div class="garment-toast-content">

      <span class="garment-toast-label">
        PRENDA NUEVA
      </span>

      <strong>
        ${tipo}
      </strong>

      <div class="garment-toast-meta">
        ${colores} · ${estilo}
      </div>

    </div>

    <div class="garment-toast-check">
      ✓
    </div>

  `;


  document.body.appendChild(
    toast
  );


  // Entrada suave

  requestAnimationFrame(
    () => {

      toast.classList.add(
        "garment-toast-visible"
      );

    }
  );


  // Desaparecer después de 3.5 segundos

  setTimeout(
    () => {

      toast.classList.remove(
        "garment-toast-visible"
      );


      toast.classList.add(
        "garment-toast-hide"
      );


      setTimeout(
        () => {

          toast.remove();

        },
        450
      );

    },
    3500
  );

}

// =====================================================
// FILTROS POR CATEGORÍA
// =====================================================

let currentPrendas = [];
let currentWardrobeFilter = "todo";

function categorizarPrenda(prenda) {
  if (prenda && prenda.categoria) return prenda.categoria;

  const texto = (typeof prenda === "string" ? prenda : prenda?.tipo || "").toLowerCase();

  const tops = ["remera", "camiseta", "camisa", "musculosa", "buzo", "sweater", "top", "blusa", "polera", "chomba", "polo", "sudadera", "hoodie"];
  const pantalones = ["pantalon", "pantalón", "jean", "short", "bermuda", "falda", "pollera", "calza"];
  const vestidos = ["vestido", "mono", "enterizo", "jumpsuit"];
  const calzado = ["zapatilla", "zapato", "bota", "sandalia", "ojota", "mocasin", "mocasín"];
  const abrigos = ["campera", "abrigo", "saco", "tapado", "chaqueta", "piloto", "parka"];
  const accesorios = ["cartera", "gorra", "collar", "anteojo", "cinturon", "cinturón", "bufanda", "reloj", "gorro", "sombrero", "guante"];

  if (accesorios.some((p) => texto.includes(p))) return "accesorios";
  if (abrigos.some((p) => texto.includes(p))) return "abrigos";
  if (calzado.some((p) => texto.includes(p))) return "calzado";
  if (vestidos.some((p) => texto.includes(p))) return "vestidos";
  if (pantalones.some((p) => texto.includes(p))) return "pantalones";
  if (tops.some((p) => texto.includes(p))) return "tops";

  return "otros";
}

function filtrarPrendas(prendas) {
  if (currentWardrobeFilter === "todo") return prendas;
  return prendas.filter((prenda) => categorizarPrenda(prenda) === currentWardrobeFilter);
}

// =====================================================
// CARGAR ARMARIO
// =====================================================

async function loadWardrobe(
  showLoading = true
) {

  if (!wardrobeGrid) return;


  if (showLoading) {

    wardrobeGrid.innerHTML = `

      <div class="wardrobe-loading">

        <div class="wardrobe-loading-symbol">
          ✦
        </div>

        <span>
          Ordenando tu armario...
        </span>

      </div>

    `;

  }


  try {

    const res = await authFetch(
      `${BACKEND_URL}/armario`
    );


    const data =
      await res.json();


    if (data.status === "error") {

      throw new Error(
        data.message
      );

    }


    currentPrendas = data.prendas || [];

    renderWardrobeGrid(
      wardrobeGrid,
      filtrarPrendas(currentPrendas)
    );

  } catch (error) {

    wardrobeGrid.innerHTML = `

      <div class="wardrobe-empty">

        <div class="wardrobe-empty-icon">
          !
        </div>

        <h3>
          No pudimos abrir tu armario
        </h3>

        <p>
          ${error.message}
        </p>

      </div>

    `;

  }

}


// =====================================================
// BOTÓN ACTUALIZAR ARMARIO
// =====================================================

if (loadWardrobeButton) {

  loadWardrobeButton.addEventListener(
    "click",
    () => {

      loadWardrobe(true);

    }
  );

}



// =====================================================
// BOTONES DE FILTRO POR CATEGORÍA
// =====================================================

const wardrobeFilters =
  document.getElementById(
    "wardrobeFilters"
  );

if (wardrobeFilters && wardrobeGrid) {

  wardrobeFilters.addEventListener(
    "click",
    (event) => {

      const boton =
        event.target.closest(
          ".filter-pill"
        );

      if (!boton) return;

      currentWardrobeFilter =
        boton.dataset.filter || "todo";

      wardrobeFilters
        .querySelectorAll(".filter-pill")
        .forEach((pill) => {
          pill.classList.toggle(
            "active",
            pill === boton
          );
        });

      renderWardrobeGrid(
        wardrobeGrid,
        filtrarPrendas(currentPrendas)
      );

    }
  );

}

// =====================================================
// RENDERIZAR ARMARIO
// =====================================================

function renderWardrobeGrid(
  container,
  prendas
) {

  if (!prendas.length) {

    container.innerHTML = `

      <div class="wardrobe-empty">

        <div class="wardrobe-empty-icon">
          ✦
        </div>

        <h3>
          Tu armario está esperando
        </h3>

        <p>
          Subí tu primera prenda para comenzar
          a construir tu colección.
        </p>

      </div>

    `;

    return;

  }


  container.innerHTML = "";


  prendas.forEach(
    (prenda, index) => {

      const item =
        document.createElement(
          "article"
        );


      item.className =
        "wardrobe-item";

      item.dataset.prendaId = prenda.id;


      item.style.setProperty(
        "--item-index",
        index
      );


      item.innerHTML = `

        <div class="garment-card">

          <div class="garment-image-wrap">

            <div class="garment-shine"></div>

            <img
              class="garment-image"
              src="${imgUrl(prenda.archivo)}"
              alt="${prenda.tipo || "Prenda"}"
              loading="lazy"
            >

            <button
              class="garment-favorite"
              type="button"
              aria-label="Agregar a favoritos"
            >
              ♡
            </button>
          ${prenda.probada ? '<span class="garment-tried-badge" title="Ya probada con tu modelo actual — no gasta crédito de nuevo">⚡ Probada</span>' : ""}
            <button
              class="garment-tryon-btn"
              type="button"
              title="Probar en mi modelo"
            >
              <span>✦ Probar en mí</span>
            </button>

          </div>


          <div class="garment-info">

            <div>

              <span class="garment-category">
                ${prenda.tipo || "Prenda"}
              </span>

              <h3>
                ${prenda.colores || "Sin color definido"}
              </h3>

            </div>


            <button
              class="garment-more"
              type="button"
              aria-label="Más opciones"
            >
              ···
            </button>

          </div>

        </div>

      `;


      container.appendChild(
        item
      );


      // =================================================
      // TILT 3D
      // =================================================

      const card =
        item.querySelector(
          ".garment-card"
        );


      const imageWrap =
        item.querySelector(
          ".garment-image-wrap"
        );


      imageWrap.addEventListener(
        "mousemove",
        (event) => {

          const rect =
            imageWrap.getBoundingClientRect();


          const x =
            event.clientX -
            rect.left;


          const y =
            event.clientY -
            rect.top;


          const centerX =
            rect.width / 2;


          const centerY =
            rect.height / 2;


          const rotateY =
            ((x - centerX) /
              centerX) * 7;


          const rotateX =
            ((centerY - y) /
              centerY) * 7;


          card.style.transform = `

            perspective(900px)

            rotateX(${rotateX}deg)

            rotateY(${rotateY}deg)

            translateY(-6px)

          `;


          const shine =
            card.querySelector(
              ".garment-shine"
            );


          if (shine) {

            shine.style.opacity =
              "1";


            shine.style.left =
              `${x}px`;


            shine.style.top =
              `${y}px`;

          }

        }
      );


      imageWrap.addEventListener(
        "mouseleave",
        () => {

          card.style.transform = `

            perspective(900px)

            rotateX(0deg)

            rotateY(0deg)

            translateY(0)

          `;


          const shine =
            card.querySelector(
              ".garment-shine"
            );


          if (shine) {

            shine.style.opacity =
              "0";

          }

        }
      );


      // =================================================
      // PROBAR EN MÍ (FASHN AI)
      // =================================================

      const tryonBtn = item.querySelector(".garment-tryon-btn");
      if (tryonBtn) {
        tryonBtn.addEventListener("click", (event) => {
          event.stopPropagation();
          tryOnGarment(prenda);
        });
      }


      // =================================================
      // FAVORITO
      // =================================================

      const favoriteButton =
        item.querySelector(
          ".garment-favorite"
        );


      favoriteButton.addEventListener(
        "click",
        (event) => {

          event.stopPropagation();


          favoriteButton.classList.toggle(
            "active"
          );


          favoriteButton.textContent =

            favoriteButton.classList.contains(
              "active"
            )

              ? "♥"

              : "♡";

        }
      );


      // =================================================
      // CLICK EN PRENDA
      // =================================================

      card.addEventListener("click", () => {

        if (comboSelectionMode) {
          const id = prenda.id;
          const yaSeleccionada = comboSelectedIds.includes(id);

          if (yaSeleccionada) {
            comboSelectedIds = comboSelectedIds.filter((pid) => pid !== id);
            card.classList.remove("combo-selected");
            actualizarComboBar();
            return;
          }

          const categoria = categorizarPrenda(prenda);
          const seleccionadasActuales = currentPrendas.filter((p) => comboSelectedIds.includes(p.id));

          // Un vestido ya cubre torso y piernas: no se combina con tops, pantalones u otro vestido.
          if (categoria === "vestidos") {
            const conflicto = seleccionadasActuales.some((p) => ["tops", "pantalones", "vestidos"].includes(categorizarPrenda(p)));
            if (conflicto) {
              alert("Un vestido ya cubre torso y piernas — sacá primero el top, pantalón u otro vestido seleccionado.");
              return;
            }
          }

          // Si ya hay un vestido elegido, no se puede sumar top/pantalón/otro vestido.
          const hayVestido = seleccionadasActuales.some((p) => categorizarPrenda(p) === "vestidos");
          if (hayVestido && ["tops", "pantalones", "vestidos"].includes(categoria)) {
            alert("Ya tenés un vestido seleccionado — no combina con tops, pantalones u otro vestido.");
            return;
          }

          // Categorías de una sola prenda por vez: si elegís otra del mismo tipo, reemplaza a la anterior.
          const categoriasUnicas = ["tops", "pantalones", "vestidos", "calzado", "abrigos"];
          if (categoriasUnicas.includes(categoria)) {
            const anterior = seleccionadasActuales.find((p) => categorizarPrenda(p) === categoria);
            if (anterior) {
              comboSelectedIds = comboSelectedIds.filter((pid) => pid !== anterior.id);
              const itemAnterior = wardrobeGrid.querySelector(`[data-prenda-id="${anterior.id}"]`);
              const cardAnterior = itemAnterior ? itemAnterior.querySelector(".garment-card") : null;
              if (cardAnterior) cardAnterior.classList.remove("combo-selected");
            }
          }

          comboSelectedIds.push(id);
          card.classList.add("combo-selected");
          actualizarComboBar();
          return;
        }

        card.classList.add("garment-selected");
        setTimeout(() => card.classList.remove("garment-selected"), 500);

      });


      // =================================================
      // MENÚ "···" — EDITAR / ELIMINAR
      // =================================================

      const moreButton =
        item.querySelector(
          ".garment-more"
        );

      if (moreButton) {

        moreButton.addEventListener(
          "click",
          (event) => {

            event.stopPropagation();

            showGarmentMenu(
              moreButton,
              prenda
            );

          }
        );

      }

    }
  );

}


// =====================================================
// MENÚ CONTEXTUAL DE PRENDA (EDITAR / ELIMINAR)
// =====================================================

function closeGarmentMenu() {

  const menuAbierto =
    document.querySelector(
      ".garment-menu"
    );

  if (menuAbierto) {
    menuAbierto.remove();
  }

  document.removeEventListener(
    "click",
    closeGarmentMenu
  );

}

function showGarmentMenu(anchorButton, prenda) {

  closeGarmentMenu();

  const menu =
    document.createElement(
      "div"
    );

  menu.className = "garment-menu";

  menu.innerHTML = `
    <button type="button" class="garment-menu-item" data-action="tryon">
      Probar en mí ✦
    </button>
    <button type="button" class="garment-menu-item" data-action="edit">
      Editar
    </button>
    <button type="button" class="garment-menu-item garment-menu-item-danger" data-action="delete">
      Eliminar
    </button>
  `;

  document.body.appendChild(menu);

  const rect =
    anchorButton.getBoundingClientRect();

  menu.style.top =
    `${rect.bottom + window.scrollY + 6}px`;

  menu.style.left =
    `${rect.right + window.scrollX - menu.offsetWidth}px`;

  menu.addEventListener(
    "click",
    (event) => {
      event.stopPropagation();
    }
  );

  const tryonMenuItem = menu.querySelector('[data-action="tryon"]');
  const editButton = menu.querySelector('[data-action="edit"]');
  const deleteButton = menu.querySelector('[data-action="delete"]');

  if (tryonMenuItem) {
    tryonMenuItem.addEventListener("click", () => {
      closeGarmentMenu();
      tryOnGarment(prenda);
    });
  }

  editButton.addEventListener(
    "click",
    () => {
      closeGarmentMenu();
      openEditGarmentModal(prenda);
    }
  );

  deleteButton.addEventListener(
    "click",
    () => {
      closeGarmentMenu();
      deleteGarment(prenda);
    }
  );

  // Cerrar el menú al hacer click afuera.
  // Se agrega en el próximo "tick" para no
  // capturar el mismo click que lo abrió.
  setTimeout(
    () => {
      document.addEventListener(
        "click",
        closeGarmentMenu
      );
    },
    0
  );

}


// =====================================================
// ELIMINAR PRENDA
// =====================================================

async function deleteGarment(prenda) {

  const confirmado = window.confirm(
    `¿Eliminar "${prenda.tipo || "esta prenda"}" del armario? Esta acción no se puede deshacer.`
  );

  if (!confirmado) return;

  try {

    const res = await authFetch(
      `${BACKEND_URL}/armario/${prenda.id}`,
      { method: "DELETE" }
    );

    const data = await res.json();

    if (data.status === "error") {
      throw new Error(data.message);
    }

    await loadWardrobe(false);

  } catch (error) {

    alert(
      `No se pudo eliminar la prenda: ${error.message}`
    );

  }

}


// =====================================================
// EDITAR PRENDA
// =====================================================

const editGarmentModal =
  document.getElementById(
    "editGarmentModal"
  );

const editTipoInput =
  document.getElementById(
    "editTipo"
  );

const editColoresInput =
  document.getElementById(
    "editColores"
  );

const editEstiloInput =
  document.getElementById(
    "editEstilo"
  );

const editDescripcionInput =
  document.getElementById(
    "editDescripcion"
  );

const cancelEditGarmentButton =
  document.getElementById(
    "cancelEditGarment"
  );

const saveEditGarmentButton =
  document.getElementById(
    "saveEditGarment"
  );

let editingPrendaId = null;

function openEditGarmentModal(prenda) {

  if (!editGarmentModal) return;

  editingPrendaId = prenda.id;

  editTipoInput.value = prenda.tipo || "";
  editColoresInput.value = prenda.colores || "";
  editEstiloInput.value = prenda.estilo || "";
  editDescripcionInput.value = prenda.descripcion || "";

  editGarmentModal.hidden = false;

}

function closeEditGarmentModal() {

  if (!editGarmentModal) return;

  editGarmentModal.hidden = true;
  editingPrendaId = null;

}

if (cancelEditGarmentButton) {

  cancelEditGarmentButton.addEventListener(
    "click",
    closeEditGarmentModal
  );

}

if (editGarmentModal) {

  // Cerrar al hacer click en el fondo oscuro,
  // pero no al hacer click adentro de la tarjeta.
  editGarmentModal.addEventListener(
    "click",
    (event) => {

      if (event.target === editGarmentModal) {
        closeEditGarmentModal();
      }

    }
  );

}

if (saveEditGarmentButton) {

  saveEditGarmentButton.addEventListener(
    "click",
    async () => {

      if (!editingPrendaId) return;

      const payload = {
        tipo: editTipoInput.value.trim(),
        colores: editColoresInput.value.trim(),
        estilo: editEstiloInput.value.trim(),
        descripcion: editDescripcionInput.value.trim(),
      };

      saveEditGarmentButton.disabled = true;
      saveEditGarmentButton.textContent = "Guardando...";

      try {

        const res = await authFetch(
          `${BACKEND_URL}/armario/${editingPrendaId}`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
          }
        );

        const data = await res.json();

        if (data.status === "error") {
          throw new Error(data.message);
        }

        closeEditGarmentModal();
        await loadWardrobe(false);

      } catch (error) {

        alert(
          `No se pudieron guardar los cambios: ${error.message}`
        );

      } finally {

        saveEditGarmentButton.disabled = false;
        saveEditGarmentButton.textContent = "Guardar cambios";

      }

    }
  );

}


// =====================================================
// GENERAR OUTFITS — FASE 4
// =====================================================

const generateOutfitsButton =
  document.getElementById(
    "generateOutfitsButton"
  );


const outfitsContainer =
  document.getElementById(
    "outfitsContainer"
  );


function buildOutfitCard(outfit, onToggleFavorite, onDelete) {
  const card = document.createElement("div");
  card.className = "outfit-card";

  const thumbs = outfit.prendas
    .map((p) => `<img src="${imgUrl(p.archivo)}" alt="${p.tipo}">`)
    .join("");

  const previewHtml = outfit.imagen
    ? `<div class="outfit-model-preview">
         <img src="${imgUrl(outfit.imagen)}" alt="Vista previa en tu modelo">
       </div>`
    : "";

  card.innerHTML = `
    <div class="outfit-card-header">
      <div>
        <div class="outfit-card-title">${outfit.nombre}</div>
        <div class="outfit-card-occasion">${outfit.ocasion}</div>
      </div>
      <div style="display:flex; gap:6px; align-items:center;">
        <button class="favorite-btn ${outfit.favorito ? "active" : ""}" title="Marcar como favorito">
          ${outfit.favorito ? "★" : "☆"}
        </button>
        ${onDelete ? `<button class="outfit-delete-btn" title="Eliminar del historial">✕</button>` : ""}
      </div>
    </div>
    ${previewHtml}
    <p class="outfit-card-desc">${outfit.descripcion}</p>
    <div class="outfit-thumbs">${thumbs}</div>
    ${outfit.prendas.length ? `<button type="button" class="outfit-tryon-btn secondary-action compact">✦ Probar outfit</button>` : ""}
  `;

  const favBtn = card.querySelector(".favorite-btn");
  favBtn.addEventListener("click", () => onToggleFavorite(outfit, favBtn));

  const deleteBtn = card.querySelector(".outfit-delete-btn");
  if (deleteBtn && onDelete) {
    deleteBtn.addEventListener("click", () => onDelete(outfit, card));
  }

  const tryonOutfitBtn = card.querySelector(".outfit-tryon-btn");
  if (tryonOutfitBtn) {
    tryonOutfitBtn.addEventListener("click", () => {
      const ids = outfit.prendas.map((p) => p.id);
      const confirmado = confirm(
        `Vas a probar este outfit completo (${ids.length} prenda${ids.length === 1 ? "" : "s"}). ` +
        `Puede gastar hasta ${ids.length} crédito${ids.length === 1 ? "" : "s"} de Fashn AI ` +
        `(menos si ya está en caché). ¿Confirmás?`
      );
      if (!confirmado) return;
      runComboTryOn(ids);
    });
  }

  return card;
}

async function deleteOutfit(outfit, card) {
  const confirmado = window.confirm(`¿Eliminar "${outfit.nombre}" del historial? No se puede deshacer.`);
  if (!confirmado) return;

  try {
    const res = await authFetch(`${BACKEND_URL}/armario/outfits/${outfit.id}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (data.status === "error") throw new Error(data.message);

    card.remove();
  } catch (error) {
    alert(`No se pudo eliminar: ${error.message}`);
  }
}
// =====================================================
// FAVORITOS DE OUTFITS
// =====================================================

async function toggleFavorite(
  outfit,
  favBtn
) {

  const nuevoValor =
    !outfit.favorito;


  try {

    const res = await authFetch(

      `${BACKEND_URL}/armario/outfits/${outfit.id}/favorito?valor=${nuevoValor}`,

      {
        method: "POST"
      }

    );


    const data =
      await res.json();


    if (data.status === "error") {

      throw new Error(
        data.message
      );

    }


    outfit.favorito =
      nuevoValor;


    favBtn.classList.toggle(
      "active",
      nuevoValor
    );


    favBtn.textContent =
      nuevoValor
        ? "★"
        : "☆";


  } catch (error) {

    alert(
      `No se pudo actualizar el favorito: ${error.message}`
    );

  }

}


// =====================================================
// FILTROS DE OCASIÓN Y CLIMA (OUTFITS)
// =====================================================

let currentOutfitOcasion = "todas";
let currentOutfitClima = "cualquiera";
let currentAllOutfits = [];

function renderFilteredOutfits() {
  if (!outfitsContainer) return;
  if (!currentAllOutfits.length) {
    outfitsContainer.innerHTML = `
      <div class="empty-outfits">
        <div class="empty-outfits-symbol">✦</div>
        <h2>Tu próximo look te espera.</h2>
        <p>Agregá prendas a tu armario y generá tus primeros outfits.</p>
      </div>
    `;
    return;
  }

  const filtrados = currentAllOutfits.filter((outfit) => {
    const todo = `${outfit.ocasion || ""} ${outfit.nombre || ""} ${outfit.descripcion || ""}`.toLowerCase();

    if (currentOutfitOcasion !== "todas") {
      const mapaOcasiones = {
        casual: ["casual", "diario", "urbano", "relajado"],
        elegante: ["elegante", "cena", "formal", "noche", "gala"],
        noche: ["fiesta", "noche", "evento", "cocktail", "bar"],
        trabajo: ["trabajo", "oficina", "profesional", "reunion", "reunión"]
      };
      const palabras = mapaOcasiones[currentOutfitOcasion] || [currentOutfitOcasion];
      if (!palabras.some((p) => todo.includes(p))) return false;
    }

    if (currentOutfitClima !== "cualquiera") {
      const mapaClima = {
        calido: ["cálido", "calido", "verano", "fresco", "sol", "short", "remera", "musculosa"],
        frio: ["frío", "frio", "invierno", "campera", "abrigo", "buzo", "sweater", "saco"],
        templado: ["templado", "otoño", "primavera", "media estación", "casual"]
      };
      const palabrasClima = mapaClima[currentOutfitClima] || [currentOutfitClima];
      if (!palabrasClima.some((p) => todo.includes(p))) return false;
    }

    return true;
  });

  if (!filtrados.length) {
    outfitsContainer.innerHTML = `
      <div class="empty-outfits">
        <div class="empty-outfits-symbol">◇</div>
        <h2>Sin outfits guardados para este filtro</h2>
        <p>Tocá <strong>Generar outfits ↗</strong> para que la IA cree combinaciones exclusivas de esta ocasión y clima.</p>
      </div>
    `;
    return;
  }

  outfitsContainer.innerHTML = "";
  filtrados.forEach((outfit) => {
    outfitsContainer.appendChild(buildOutfitCard(outfit, toggleFavorite));
  });
}

const outfitsOccasionFilters = document.getElementById("outfitsOccasionFilters");
if (outfitsOccasionFilters) {
  outfitsOccasionFilters.addEventListener("click", (event) => {
    const btn = event.target.closest(".filter-pill");
    if (!btn) return;
    currentOutfitOcasion = btn.dataset.ocasion || "todas";
    outfitsOccasionFilters.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.classList.toggle("active", pill === btn);
    });
    renderFilteredOutfits();
  });
}

const outfitsWeatherFilters = document.getElementById("outfitsWeatherFilters");
if (outfitsWeatherFilters) {
  outfitsWeatherFilters.addEventListener("click", (event) => {
    const btn = event.target.closest(".filter-pill");
    if (!btn) return;
    currentOutfitClima = btn.dataset.clima || "cualquiera";
    outfitsWeatherFilters.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.classList.toggle("active", pill === btn);
    });
    renderFilteredOutfits();
  });
}

// =====================================================
// GENERAR OUTFITS
// =====================================================

if (generateOutfitsButton) {

  generateOutfitsButton.addEventListener(
    "click",
    async () => {

      outfitsContainer.innerHTML =
        '<p class="empty-state">Creando outfits inspirados en tu estilo...</p>';

      try {
        const res = await authFetch(
          `${BACKEND_URL}/armario/outfits?ocasion=${encodeURIComponent(currentOutfitOcasion)}&clima=${encodeURIComponent(currentOutfitClima)}`
        );

        const data = await res.json();

        if (data.status === "error") {
          outfitsContainer.innerHTML = `<p class="empty-state">❌ ${data.message}</p>`;
          return;
        }

        currentAllOutfits = data.outfits || [];
        renderFilteredOutfits();
        cargarEstadoCreditos();
      } catch (error) {
        outfitsContainer.innerHTML = `<p class="empty-state">❌ Error: ${error.message}</p>`;
      }
    }
  );

}


// =====================================================
// HISTORIAL Y FAVORITOS
// =====================================================

const historyContainer =
  document.getElementById(
    "historyContainer"
  );


const tabAllButton =
  document.getElementById(
    "tabAllButton"
  );


const tabFavButton =
  document.getElementById(
    "tabFavButton"
  );


async function loadHistory(
  soloFavoritos
) {

  if (!historyContainer) return;


  historyContainer.innerHTML =
    '<p class="empty-state">Cargando historial...</p>';


  if (tabAllButton) {

    tabAllButton.classList.toggle(
      "inactive",
      soloFavoritos
    );

  }


  if (tabFavButton) {

    tabFavButton.classList.toggle(
      "inactive",
      !soloFavoritos
    );

  }


  try {

    const res = await authFetch(

      `${BACKEND_URL}/armario/historial?favoritos=${soloFavoritos}`

    );


    const data =
      await res.json();


    if (!data.outfits.length) {

      historyContainer.innerHTML =

        soloFavoritos

          ? '<p class="empty-state">Todavía no marcaste ningún outfit como favorito.</p>'

          : '<p class="empty-state">Todavía no generaste ningún outfit.</p>';

      return;

    }


    historyContainer.innerHTML =
      "";


    data.outfits.forEach(
      (outfit) => {

        historyContainer.appendChild(

          buildOutfitCard(
            outfit,
            toggleFavorite,
            deleteOutfit
          )

        );

      }
    );


  } catch (error) {

    historyContainer.innerHTML =
      `<p class="empty-state">Error: ${error.message}</p>`;

  }

}


if (tabAllButton) {

  tabAllButton.addEventListener(
    "click",
    () => loadHistory(false)
  );

}


if (tabFavButton) {

  tabFavButton.addEventListener(
    "click",
    () => loadHistory(true)
  );

}


// =====================================================
// NAVEGACIÓN DEL ATELIER
// =====================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    const navItems =
      document.querySelectorAll(
        ".nav-item, .mobile-nav-item"
      );


    const sections = {

      analyze:
        document.getElementById(
          "analyzeSection"
        ),

      wardrobe:
        document.getElementById(
          "wardrobeSection"
        ),

      outfits:
        document.getElementById(
          "outfitsSection"
        ),

      tryon:
        document.getElementById(
          "tryonSection"
        ),

      history:
        document.getElementById(
          "historySection"
        )

    };


    navItems.forEach(
      (item) => {

        item.addEventListener(
          "click",
          () => {

            const target =
              item.dataset.section;


            if (!sections[target]) {

              console.warn(
                `Sección no encontrada: ${target}`
              );

              return;

            }


            navItems.forEach(
              (nav) => {

                if (nav.dataset.section === target) {
                  nav.classList.add("active");
                } else {
                  nav.classList.remove("active");
                }

              }
            );


            Object.values(
              sections
            ).forEach(
              (section) => {

                if (section) {

                  section.classList.remove(
                    "active-section"
                  );

                }

              }
            );


            sections[target].classList.add(
              "active-section"
            );


            // -----------------------------------------
            // Mi Armario
            // -----------------------------------------

            if (
              target === "wardrobe"
            ) {

              loadWardrobe(false);

            }


            // -----------------------------------------
            // Historial
            // -----------------------------------------

            if (
              target === "history"
            ) {

              if (getToken()) loadHistory(false);
              

            }

            window.scrollTo({

              top: 0,

              behavior: "smooth"

            });

          }
        );

      }
    );

  }
);


// =====================================================
// CARGA INICIAL DEL HISTORIAL
// =====================================================

loadHistory(false);

async function cargarUltimosOutfits() {
  if (!outfitsContainer) return;
  try {
    const res = await authFetch(`${BACKEND_URL}/armario/historial?favoritos=false`);
    const data = await res.json();
    if (!data.outfits || !data.outfits.length) return;

    outfitsContainer.innerHTML = "";
    data.outfits.slice(0, 6).forEach((outfit) => {
      outfitsContainer.appendChild(buildOutfitCard(outfit, toggleFavorite));
    });
  } catch (error) {
    // silencioso
  }
}

if (getToken()) cargarUltimosOutfits();


// =====================================================
// PERFIL CORPORAL ("MI MODELO") & PROBADOR VIRTUAL
// =====================================================

let hasBodyPhoto = false;
let currentBodyPhotoUrl = "";
let currentTryonResult = null; // { prenda_id, resultado_url, cached }

const bodyPhotoInput = document.getElementById("bodyPhotoInput");
const bodyPhotoEmpty = document.getElementById("bodyPhotoEmpty");
const bodyPhotoPreviewWrap = document.getElementById("bodyPhotoPreviewWrap");
const bodyPhotoPreview = document.getElementById("bodyPhotoPreview");
const deleteBodyPhotoBtn = document.getElementById("deleteBodyPhotoBtn");
const modelStatusBadge = document.getElementById("modelStatusBadge");
const modelStatusText = document.getElementById("modelStatusText");
const uploadBodyPhotoBtnText = document.getElementById("uploadBodyPhotoBtnText");
const bodyPhotoStatus = document.getElementById("bodyPhotoStatus");

const missingBodyPhotoModal = document.getElementById("missingBodyPhotoModal");
const closeMissingPhotoModal = document.getElementById("closeMissingPhotoModal");
const goToModelSectionBtn = document.getElementById("goToModelSectionBtn");

const tryonResultModal = document.getElementById("tryonResultModal");
const tryonModalResultImage = document.getElementById("tryonModalResultImage");
const tryonCacheBadge = document.getElementById("tryonCacheBadge");
const saveTryonOutfitBtn = document.getElementById("saveTryonOutfitBtn");
const tryonAnotherBtn = document.getElementById("tryonAnotherBtn");
const closeTryonModalBtn = document.getElementById("closeTryonModalBtn");

async function checkBodyPhotoStatus() {
  try {
    const res = await authFetch(`${BACKEND_URL}/perfil/modelo`);
    const data = await res.json();

    if (data.status === "success" && data.url) {
      hasBodyPhoto = true;
      currentBodyPhotoUrl = imgUrl(data.url);

      if (bodyPhotoPreview) bodyPhotoPreview.src = currentBodyPhotoUrl;
      if (bodyPhotoEmpty) bodyPhotoEmpty.hidden = true;
      if (bodyPhotoPreviewWrap) bodyPhotoPreviewWrap.hidden = false;
      if (deleteBodyPhotoBtn) deleteBodyPhotoBtn.hidden = false;
      if (uploadBodyPhotoBtnText) uploadBodyPhotoBtnText.textContent = "Cambiar foto corporal";

      if (modelStatusBadge) {
        modelStatusBadge.className = "model-status-badge active";
      }
      if (modelStatusText) modelStatusText.textContent = "✓ Foto corporal configurada y lista";
    } else {
      hasBodyPhoto = false;
      currentBodyPhotoUrl = "";

      if (bodyPhotoEmpty) bodyPhotoEmpty.hidden = false;
      if (bodyPhotoPreviewWrap) bodyPhotoPreviewWrap.hidden = true;
      if (deleteBodyPhotoBtn) deleteBodyPhotoBtn.hidden = true;
      if (uploadBodyPhotoBtnText) uploadBodyPhotoBtnText.textContent = "Subir foto corporal";

      if (modelStatusBadge) {
        modelStatusBadge.className = "model-status-badge warning";
      }
      if (modelStatusText) modelStatusText.textContent = "⚠️ Sin foto corporal configurada";
    }
  } catch (error) {
    console.error("Error al comprobar foto corporal:", error);
  }
}

if (bodyPhotoInput) {
  bodyPhotoInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (bodyPhotoStatus) {
      bodyPhotoStatus.className = "response-box";
      bodyPhotoStatus.textContent = "Guardando foto corporal...";
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await authFetch(`${BACKEND_URL}/perfil/modelo`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (data.status === "error") throw new Error(data.message);

      if (bodyPhotoStatus) {
        bodyPhotoStatus.className = "response-box success";
        bodyPhotoStatus.textContent = "✓ Foto corporal guardada correctamente.";
      }

      if (getToken()) checkBodyPhotoStatus();

      showGarmentToast({
        tipo: "Mi Modelo",
        colores: "Cuerpo Completo",
        estilo: "Foto Activa Configurada",
      });
    } catch (error) {
      if (bodyPhotoStatus) {
        bodyPhotoStatus.className = "response-box error";
        bodyPhotoStatus.textContent = `❌ Error: ${error.message}`;
      }
    }
  });
}

if (deleteBodyPhotoBtn) {
  deleteBodyPhotoBtn.addEventListener("click", async () => {
    if (!confirm("¿Eliminar la foto corporal configurada?")) return;

    try {
      await authFetch(`${BACKEND_URL}/perfil/modelo`, { method: "DELETE" });
      await checkBodyPhotoStatus();
      if (bodyPhotoStatus) {
        bodyPhotoStatus.className = "response-box";
        bodyPhotoStatus.textContent = "Foto corporal eliminada.";
      }
    } catch (error) {
      alert(`No se pudo eliminar: ${error.message}`);
    }
  });
}

// Advertencia foto faltante
if (closeMissingPhotoModal) {
  closeMissingPhotoModal.addEventListener("click", () => {
    if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = true;
  });
}

if (goToModelSectionBtn) {
  goToModelSectionBtn.addEventListener("click", () => {
    if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = true;
    const tryonNav = document.querySelector('.nav-item[data-section="tryon"]');
    if (tryonNav) tryonNav.click();
  });
}


function showAtelierToast({ label = "AVISO", titulo, meta = "", icono = "⚠" }) {
  const oldToast = document.querySelector(".garment-toast");
  if (oldToast) oldToast.remove();

  const toast = document.createElement("div");
  toast.className = "garment-toast";
  toast.innerHTML = `
    <div class="garment-toast-icon">${icono}</div>
    <div class="garment-toast-content">
      <span class="garment-toast-label">${label}</span>
      <strong>${titulo}</strong>
      <div class="garment-toast-meta">${meta}</div>
    </div>
    <div class="garment-toast-check">✓</div>
  `;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("garment-toast-visible"));
  setTimeout(() => {
    toast.classList.remove("garment-toast-visible");
    toast.classList.add("garment-toast-hide");
    setTimeout(() => toast.remove(), 450);
  }, 3500);
}

// Ejecutar Try-On
async function tryOnGarment(prenda) {
  if (!hasBodyPhoto) {
    if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = false;
    return;
  }

  if (tryonResultModal) {
    tryonResultModal.hidden = false;
  }
  const tryonLoading = document.getElementById("tryonLoading");
  if (tryonLoading) tryonLoading.hidden = false;
  if (tryonModalResultImage) {
    tryonModalResultImage.src = "";
    tryonModalResultImage.style.opacity = "0";
  }
  if (tryonCacheBadge) {
    tryonCacheBadge.className = "tryon-badge fresh";
    tryonCacheBadge.textContent = "✦ Generando con Fashn AI, puede tardar hasta un minuto...";
  }
  if (saveTryonOutfitBtn) saveTryonOutfitBtn.hidden = true;

  const formData = new FormData();
  formData.append("prenda_id", prenda.id);

  try {
    const res = await authFetch(`${BACKEND_URL}/try-on`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (data.status === "error") {
      if (tryonResultModal) tryonResultModal.hidden = true;

      if (data.code === "NO_BODY_PHOTO") {
        if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = false;
        return;
      }
      if (data.code === "NO_CREDITS") {
        showAtelierToast({
          label: "SIN CRÉDITOS",
          titulo: "Fashn AI sin saldo",
          meta: "Recargá en fashn.ai para seguir probando prendas nuevas",
          icono: "⚠",
        });
        return;
      }
      throw new Error(data.message);
    }

    if (data.aviso_creditos) {
      showAtelierToast({
        label: "CRÉDITOS BAJOS",
        titulo: "Fashn AI",
        meta: data.aviso_creditos,
        icono: "⚠",
      });
    }

    currentTryonResult = {
      prenda_id: prenda.id,
      resultado_url: imgUrl(data.resultado),
      resultado_archivo: data.resultado_archivo,
      prenda: prenda,
      cached: data.cached,
    };

  const nombreInput = document.getElementById("tryonOutfitNameInput");
    if (nombreInput) {
      nombreInput.value = `Look con ${prenda.tipo || "Prenda"}`;
    }
    if (tryonModalResultImage) {
      tryonModalResultImage.src = currentTryonResult.resultado_url;
      tryonModalResultImage.onload = () => {
        tryonModalResultImage.style.opacity = "1";
        if (tryonLoading) tryonLoading.hidden = true;
      };
    }

    if (tryonCacheBadge) {
      if (data.cached) {
        tryonCacheBadge.className = "tryon-badge cache";
        tryonCacheBadge.textContent = "⚡ Recuperado de Caché (0 créditos gastados)";
      } else {
        tryonCacheBadge.className = "tryon-badge fresh";
        tryonCacheBadge.textContent = "✦ Generado en tiempo real con Fashn AI";
      }
    }

    if (tryonResultModal) tryonResultModal.hidden = false;
    if (saveTryonOutfitBtn) saveTryonOutfitBtn.hidden = false;
    cargarEstadoCreditos();
    loadWardrobe(false);
  } catch (error) {
    if (tryonResultModal) tryonResultModal.hidden = true;
    alert(`No se pudo realizar el probado virtual: ${error.message}`);
  }
}

// Acciones del Modal Resultado Try-On
if (closeTryonModalBtn) {
  closeTryonModalBtn.addEventListener("click", () => {
    if (tryonResultModal) tryonResultModal.hidden = true;
  });
}

if (tryonAnotherBtn) {
  tryonAnotherBtn.addEventListener("click", () => {
    if (tryonResultModal) tryonResultModal.hidden = true;
    const wardrobeNav = document.querySelector('.nav-item[data-section="wardrobe"]');
    if (wardrobeNav) wardrobeNav.click();
  });
}

if (saveTryonOutfitBtn) {
  saveTryonOutfitBtn.addEventListener("click", async () => {
    if (!currentTryonResult) return;

    saveTryonOutfitBtn.disabled = true;
    saveTryonOutfitBtn.textContent = "Guardando...";

    try {
      const nombreInput = document.getElementById("tryonOutfitNameInput");
      const nombreFinal = (nombreInput && nombreInput.value.trim()) || `Look con ${currentTryonResult.prenda.tipo || "Prenda"}`;

      const esCombo = Array.isArray(currentTryonResult.prenda_ids);
      const descripcionAuto = esCombo
        ? `Combinación probada con Virtual Try-On: ${currentTryonResult.prendas.map((p) => p.tipo).join(", ")}.`
        : `Probado virtual generado para ${currentTryonResult.prenda.tipo} (${currentTryonResult.prenda.colores}).`;

      const payload = {
        nombre: nombreFinal,
        ocasion: "Probador Virtual Digital Atelier",
        descripcion: descripcionAuto,
        resultado_archivo: currentTryonResult.resultado_archivo,
      };

      if (esCombo) {
        payload.prenda_ids = currentTryonResult.prenda_ids;
      } else {
        payload.prenda_id = currentTryonResult.prenda_id;
      }

      const res = await authFetch(`${BACKEND_URL}/armario/outfits/guardar_tryon`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.status === "error") throw new Error(data.message);

      showGarmentToast({
        tipo: "Outfit Guardado",
        colores: "Diario de Estilo",
        estilo: "Disponible en Outfits e Historial ✓",
      });

      if (tryonResultModal) tryonResultModal.hidden = true;
      await loadHistory(false);
    } catch (error) {
      alert(`No se pudo guardar el outfit: ${error.message}`);
    } finally {
      saveTryonOutfitBtn.disabled = false;
      saveTryonOutfitBtn.innerHTML = "<span>✦</span> Guardar en mis outfits";
    }
  });
}

// Carga inicial estado foto corporal
checkBodyPhotoStatus();


// ============================
// Estado de créditos (Fashn AI + Groq)
// ============================

async function cargarEstadoCreditos() {
  const fashnEl = document.getElementById("fashnCreditsValue");
  const groqEl = document.getElementById("groqCreditsValue");
  if (!fashnEl || !groqEl) return;

  try {
    const res = await fetch(`${BACKEND_URL}/estado/creditos`);
    const data = await res.json();

    if (data.fashn && typeof data.fashn.total === "number") {
      fashnEl.textContent = `${data.fashn.total} créditos`;
      fashnEl.classList.toggle("credits-low", data.fashn.total <= 5);
    } else {
      fashnEl.textContent = "sin datos";
    }

    const groq = data.groq;
    if (groq && groq.restantes_requests_dia !== null && groq.restantes_requests_dia !== undefined) {
      groqEl.textContent = `${groq.restantes_requests_dia}/${groq.limite_requests_dia} req`;
    } else {
      groqEl.textContent = "aún sin usar";
    }
  } catch (error) {
    fashnEl.textContent = "error";
    groqEl.textContent = "error";
  }
}

cargarEstadoCreditos();

const profileMoreBtn = document.querySelector(".profile-more");
if (profileMoreBtn) {
  profileMoreBtn.addEventListener("click", () => {
    if (confirm("¿Cerrar sesión?")) cerrarSesion();
  });
}

// ============================
// Avatar de perfil
// ============================

const profileAvatar = document.getElementById("profileAvatar");
const profileAvatarImg = document.getElementById("profileAvatarImg");
const profileAvatarLetter = document.getElementById("profileAvatarLetter");
const avatarInput = document.getElementById("avatarInput");
const topbarAvatar = document.getElementById("topbarAvatar");

function aplicarAvatar(url) {
  if (!url) return;
  const fullUrl = imgUrl(url);

  if (profileAvatarImg) {
    profileAvatarImg.src = fullUrl;
    profileAvatarImg.hidden = false;
  }
  if (profileAvatarLetter) profileAvatarLetter.hidden = true;

  if (topbarAvatar) {
    topbarAvatar.innerHTML = `<img src="${fullUrl}" alt="" />`;
  }
}

async function cargarPerfil() {
  if (!getToken()) return;
  try {
    const res = await authFetch(`${BACKEND_URL}/auth/yo`);
    const data = await res.json();
    if (data.status === "success" && data.user.avatar) {
      aplicarAvatar(data.user.avatar);
    }
    if (data.status === "success" && profileAvatarLetter) {
      profileAvatarLetter.textContent = (data.user.name || "?").charAt(0).toUpperCase();
    }
  } catch (error) {
    // silencioso
  }
}

function closeAvatarMenu() {
  const menuAbierto = document.querySelector(".avatar-menu");
  if (menuAbierto) menuAbierto.remove();
  document.removeEventListener("click", closeAvatarMenu);
}

function showAvatarMenu(anchorEl) {
  closeAvatarMenu();

  const menu = document.createElement("div");
  menu.className = "avatar-menu garment-menu";
  menu.innerHTML = `
    <button type="button" class="garment-menu-item" data-action="change">Cambiar foto</button>
    <button type="button" class="garment-menu-item garment-menu-item-danger" data-action="logout">Cerrar sesión</button>
  `;

  document.body.appendChild(menu);

  const rect = anchorEl.getBoundingClientRect();
  const espacioArriba = rect.top;
  const espacioAbajo = window.innerHeight - rect.bottom;

  if (espacioAbajo > espacioArriba) {
    menu.style.top = `${rect.bottom + window.scrollY + 6}px`;
  } else {
    menu.style.top = `${rect.top + window.scrollY - menu.offsetHeight - 6}px`;
  }

  let left = rect.left + window.scrollX;
  const maxLeft = window.scrollX + window.innerWidth - menu.offsetWidth - 8;
  if (left > maxLeft) left = maxLeft;
  if (left < 8) left = 8;
  menu.style.left = `${left}px`;

  menu.addEventListener("click", (event) => event.stopPropagation());

  menu.querySelector('[data-action="change"]').addEventListener("click", () => {
    closeAvatarMenu();
    avatarInput.click();
  });

  menu.querySelector('[data-action="logout"]').addEventListener("click", () => {
    closeAvatarMenu();
    if (confirm("¿Cerrar sesión?")) cerrarSesion();
  });

  setTimeout(() => document.addEventListener("click", closeAvatarMenu), 0);
}

if (profileAvatar) {
  profileAvatar.addEventListener("click", (event) => {
    event.stopPropagation();
    showAvatarMenu(profileAvatar);
  });
}

if (topbarAvatar) {
  topbarAvatar.addEventListener("click", (event) => {
    event.stopPropagation();
    showAvatarMenu(topbarAvatar);
  });
}

if (avatarInput) {
  avatarInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await authFetch(`${BACKEND_URL}/perfil/avatar`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.status === "error") throw new Error(data.message);

      aplicarAvatar(data.url);
    } catch (error) {
      alert(`No se pudo subir la foto de perfil: ${error.message}`);
    } finally {
      avatarInput.value = "";
    }
  });
}

if (getToken()) cargarPerfil();


// ============================
// Combinar prendas en un Try-On
// ============================

let comboSelectionMode = false;
let comboSelectedIds = [];

const toggleComboSelectionBtn = document.getElementById("toggleComboSelectionBtn");
const comboActionBar = document.getElementById("comboActionBar");
const comboCountLabel = document.getElementById("comboCountLabel");
const comboRunBtn = document.getElementById("comboRunBtn");
const comboCancelBtn = document.getElementById("comboCancelBtn");

function actualizarComboBar() {
  if (!comboActionBar) return;
  comboActionBar.hidden = !comboSelectionMode || comboSelectedIds.length === 0;
  if (comboCountLabel) {
    const n = comboSelectedIds.length;
    comboCountLabel.textContent = `${n} prenda${n === 1 ? "" : "s"} · hasta ${n} crédito${n === 1 ? "" : "s"}`;
  }
}

if (toggleComboSelectionBtn) {
  toggleComboSelectionBtn.addEventListener("click", () => {
    comboSelectionMode = !comboSelectionMode;
    comboSelectedIds = [];
    toggleComboSelectionBtn.classList.toggle("active", comboSelectionMode);
    toggleComboSelectionBtn.textContent = comboSelectionMode ? "Cancelar selección" : "Combinar prendas ✦";
    if (wardrobeGrid) wardrobeGrid.classList.toggle("combo-mode", comboSelectionMode);
    renderWardrobeGrid(wardrobeGrid, filtrarPrendas(currentPrendas));
    actualizarComboBar();
  });
}

if (comboCancelBtn) {
  comboCancelBtn.addEventListener("click", () => {
    comboSelectedIds = [];
    renderWardrobeGrid(wardrobeGrid, filtrarPrendas(currentPrendas));
    actualizarComboBar();
  });
}

if (comboRunBtn) {
  comboRunBtn.addEventListener("click", () => {
    if (!comboSelectedIds.length) return;
    const n = comboSelectedIds.length;
    const confirmado = confirm(
      `Vas a probar ${n} prenda${n === 1 ? "" : "s"} juntas. Esto puede gastar hasta ${n} ` +
      `crédito${n === 1 ? "" : "s"} de Fashn AI (menos si alguna combinación ya está en caché). ¿Confirmás?`
    );
    if (!confirmado) return;
    runComboTryOn([...comboSelectedIds]);
  });
}

async function runComboTryOn(prendaIds) {
  if (!hasBodyPhoto) {
    if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = false;
    return;
  }

  if (tryonResultModal) tryonResultModal.hidden = false;

  const tryonLoading = document.getElementById("tryonLoading");
  const comboProgress = document.getElementById("tryonComboProgress");

  if (tryonLoading) tryonLoading.hidden = false;
  if (tryonModalResultImage) {
    tryonModalResultImage.src = "";
    tryonModalResultImage.style.opacity = "0";
  }
  if (saveTryonOutfitBtn) saveTryonOutfitBtn.hidden = true;

  // Info de cada prenda (para el cartelito con su foto), ya la tenemos
  // cargada en el armario, no hace falta pedirla de nuevo.
  const prendasInfo = prendaIds.map(
    (id) => currentPrendas.find((p) => p.id === id) || { id, tipo: "Prenda", archivo: "" }
  );

  const estadoPorId = {};
  prendasInfo.forEach((p) => { estadoPorId[p.id] = "pendiente"; });

  function renderSteps() {
    if (!comboProgress) return;
    const iconos = { pendiente: "○", activo: "◐", listo: "✓", error: "✕" };
    comboProgress.innerHTML = prendasInfo
      .map((p) => {
        const estado = estadoPorId[p.id];
        const clase =
          estado === "activo" ? "active" :
          estado === "listo" ? "done" :
          estado === "error" ? "error" : "";
        return `
          <div class="tryon-combo-step ${clase}">
            <img class="tryon-combo-step-thumb" src="${imgUrl(p.archivo)}" alt="${p.tipo}">
            <span class="tryon-combo-step-text">${p.tipo}${estado === "listo" ? " — lista" : estado === "activo" ? " — probando..." : ""}</span>
            <span class="tryon-combo-step-icon">${iconos[estado]}</span>
          </div>
        `;
      })
      .join("");
  }

  if (comboProgress) {
    comboProgress.hidden = false;
    renderSteps();
  }

  try {
    // Paso 1: ¿este combo ya está en caché?
    const resIniciar = await authFetch(`${BACKEND_URL}/try-on/combo/iniciar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prenda_ids: prendaIds }),
    });
    const dataIniciar = await resIniciar.json();

    if (dataIniciar.status === "error") {
      if (tryonResultModal) tryonResultModal.hidden = true;
      if (dataIniciar.code === "NO_BODY_PHOTO") {
        if (missingBodyPhotoModal) missingBodyPhotoModal.hidden = false;
        return;
      }
      alert(`No se pudo generar la combinación: ${dataIniciar.message}`);
      return;
    }

    let resultadoFinalArchivo;
    let resultadoFinalUrl;
    let prendasExitosas;
    let cachedCombo = false;
    let nuevosCreditos = 0;

    if (dataIniciar.cached_combo) {

      cachedCombo = true;
      resultadoFinalArchivo = dataIniciar.resultado_archivo;
      resultadoFinalUrl = dataIniciar.resultado_final;
      prendasExitosas = dataIniciar.prendas;

      prendasInfo.forEach((p) => { estadoPorId[p.id] = "listo"; });
      renderSteps();

    } else {

      let fotoActual = dataIniciar.body_photo;
      prendasExitosas = [];
      let huboError = null;

      for (const prenda of prendasInfo) {

        estadoPorId[prenda.id] = "activo";
        renderSteps();

        const resPaso = await authFetch(`${BACKEND_URL}/try-on/combo/paso`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model_photo: fotoActual,
            prenda_id: prenda.id,
            body_photo_original: dataIniciar.body_photo,
          }),
        });
        const dataPaso = await resPaso.json();

        if (dataPaso.status === "error") {
          estadoPorId[prenda.id] = "error";
          renderSteps();
          huboError = dataPaso;
          break;
        }

        estadoPorId[prenda.id] = "listo";
        renderSteps();

        if (!dataPaso.cached) nuevosCreditos += 1;

        fotoActual = dataPaso.resultado_archivo;
        resultadoFinalUrl = dataPaso.resultado;
        prendasExitosas.push(dataPaso.prenda);
      }

      if (!prendasExitosas.length) {
        if (tryonResultModal) tryonResultModal.hidden = true;
        alert(`No se pudo generar la combinación: ${huboError ? huboError.message : "Error desconocido"}`);
        return;
      }

      resultadoFinalArchivo = fotoActual;

      const resFinalizar = await authFetch(`${BACKEND_URL}/try-on/combo/finalizar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          body_photo_original: dataIniciar.body_photo,
          prenda_ids: prendasExitosas.map((p) => p.id),
          resultado_archivo: resultadoFinalArchivo,
        }),
      });
      const dataFinalizar = await resFinalizar.json();

      if (dataFinalizar.aviso_creditos) {
        showAtelierToast({
          label: "CRÉDITOS BAJOS",
          titulo: "Fashn AI",
          meta: dataFinalizar.aviso_creditos,
          icono: "⚠",
        });
      }
    }

    currentTryonResult = {
      prenda_ids: prendaIds,
      resultado_url: imgUrl(resultadoFinalUrl),
      resultado_archivo: resultadoFinalArchivo,
      prendas: prendasExitosas,
      cached: cachedCombo,
    };

    const nombreInput = document.getElementById("tryonOutfitNameInput");
    if (nombreInput) {
      const nombres = currentTryonResult.prendas.map((p) => p.tipo).join(" + ");
      nombreInput.value = `Look con ${nombres || "varias prendas"}`;
    }

    if (tryonLoading) tryonLoading.hidden = true;

    if (tryonModalResultImage) {
      tryonModalResultImage.src = currentTryonResult.resultado_url;
      tryonModalResultImage.onload = () => {
        tryonModalResultImage.style.opacity = "1";
      };
    }

    if (tryonCacheBadge) {
      const totalExitosas = currentTryonResult.prendas.length;
      if (totalExitosas < prendaIds.length) {
        tryonCacheBadge.className = "tryon-badge fresh";
        tryonCacheBadge.textContent = `⚠ Se probaron ${totalExitosas} de ${prendaIds.length} prendas.`;
      } else if (cachedCombo) {
        tryonCacheBadge.className = "tryon-badge cache";
        tryonCacheBadge.textContent = "⚡ Recuperado de caché (0 créditos gastados)";
      } else {
        tryonCacheBadge.className = "tryon-badge fresh";
        tryonCacheBadge.textContent = `✦ Generado con Fashn AI (${nuevosCreditos} crédito${nuevosCreditos === 1 ? "" : "s"} usados)`;
      }
    }

    if (saveTryonOutfitBtn) saveTryonOutfitBtn.hidden = false;
    cargarEstadoCreditos();
    loadWardrobe(false);

    comboSelectedIds = [];
    if (comboSelectionMode && toggleComboSelectionBtn) toggleComboSelectionBtn.click();

  } catch (error) {
    if (tryonResultModal) tryonResultModal.hidden = true;
    alert(`No se pudo generar la combinación: ${error.message}`);
  }
}

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("service-worker.js")
      .catch((error) => console.log("Service Worker no registrado en HTTP:", error));
  });
}
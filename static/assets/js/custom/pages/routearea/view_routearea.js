const { CONFIG } = window;

// Gerenciamento de estado da aplicação
const state = {
  map: null,
  drawnItems: null,
  routeGeoJSON: null,
  otherRoutes: [],
  undoStack: [],
  routeColor: null
};

/**
 * Inicializa o estado e componentes quando o DOM estiver pronto
 */
document.addEventListener("DOMContentLoaded", () => {
  initializeState();
  initializeMap();
  initializeControls();
  initializeEventListeners();
  loadInitialGeoJSON();
});

/**
 * Inicializa variáveis de estado a partir do DOM
 */
function initializeState() {
  const geojsonInput = document.getElementById("geojsonInput");

  if (!geojsonInput) {
    console.error("Elemento geojsonInput não encontrado");
    return;
  }

  // Define a cor da rota atual
  state.routeColor = document.querySelector("#hex_color").value;


  // Carrega outras rotas do atributo data
  try {
    state.otherRoutes = JSON.parse(geojsonInput.getAttribute("data-other-routes") || "[]");
  } catch (err) {
    console.error("Erro ao parsear outras rotas:", err);
    state.otherRoutes = [];
  }
}

/**
 * Cria o mapa Leaflet e camada de base
 */
function initializeMap() {
  // Cria o mapa com vista inicial definida em CONFIG
  state.map = L.map("map").setView(CONFIG.MAP.INITIAL_VIEW, CONFIG.MAP.INITIAL_ZOOM);

  // Adiciona camada de tiles
  L.tileLayer(CONFIG.MAP.TILE_URL, {
    attribution: CONFIG.MAP.TILE_ATTRIBUTION
  }).addTo(state.map);

  // Inicia grupo de camadas para desenhos do usuário
  state.drawnItems = new L.FeatureGroup();
  state.map.addLayer(state.drawnItems);
}

/**
 * Configura controles do mapa e componentes de interface
 */
function initializeControls() {
  // Adiciona controles do Geoman para desenho e edição
  state.map.pm.addControls({
    position: 'topright',
    drawPolygon: true,
    drawPolyline: false,
    drawMarker: false,
    drawCircleMarker: false,
    circleMarker: false,
    drawCircle: false,
    editMode: true,
    dragMode: false,
    removalMode: true,
    cutPolygon: true,
    snappable: true,
    snapMiddle: true,
    drawText: false,
  });

  // Adiciona botão de reset personalizado
  const ResetControl = createResetControl();
  state.map.addControl(new ResetControl());

  // Inicializa Select2 se existir o select de bairro
  if ($('#bairro_select').length) {
    $('#bairro_select').select2({
      tags: true,
      tokenSeparators: [',', ' ']
    });
  }
}

function debounce(fn, wait) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn.apply(this, args), wait);
  };
}
/**
 * Registra listeners para eventos do mapa e UI
 */
function initializeEventListeners() {
  // Eventos do mapa para criação, corte, remoção e edição
  state.map.on('pm:create', handleLayerCreated);
  state.map.on('pm:cut', handleLayerCut);
  state.map.on('pm:remove', showSaveButton);
  state.map.on('pm:edit', showSaveButton);
  state.map.on('pm:dragend', showSaveButton);

  const bairroInput = document.getElementById("bairroInput");
  const dropdownMenu = document.getElementById("dropdownMenu");
  const loader = document.getElementById("loader");
  const bairroDropdown = document.getElementById("bairroDropdown");

  // Debounce para busca enquanto digita
  if (bairroInput) {
    bairroInput.addEventListener("input", debounce((e) => {
      const termo = e.target.value.trim();
      if (termo.length >= CONFIG.SEARCH.MIN_QUERY_LENGTH) {
        searchNeighborhood(termo);
      }
    }, 500));

    // abrir/fechar dropdown ao clicar no input
    bairroInput.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDropdown();
    });
  }

  // fecha dropdown ao clicar fora
  document.addEventListener("click", (e) => {
    if (!bairroDropdown.contains(e.target)) {
      closeDropdown();
    }
  });

  // Clique em qualquer lugar para fechar dropdown
  document.addEventListener("click", handleDocumentClick);
  // Atalho de teclado Ctrl+Z para desfazer
  document.addEventListener("keydown", handleKeyDown);

  // Botão de salvar mapa
  const saveButton = document.getElementById("saveMap");
  if (saveButton) {
    saveButton.addEventListener("click", saveGeoJSON);
  }
}

/**
 * Carrega GeoJSON inicial se existir
 */
function loadInitialGeoJSON() {
  const geojsonInput = document.getElementById("geojsonInput");

  // Adiciona rotas preexistentes primeiro
  addOtherRoutes();

  // Carrega rota atual caso exista valor no input
  if (geojsonInput && geojsonInput.value && geojsonInput.value !== "None") {
    try {
      const parsed = JSON.parse(geojsonInput.value);

      // Verifica se é GeoJSON válido
      if (parsed.type && (parsed.type === "Feature" || parsed.type === "FeatureCollection")) {
        state.routeGeoJSON = parsed;

        const routeLayer = L.geoJSON(state.routeGeoJSON, {
          style: {
            ...CONFIG.STYLES.CURRENT_ROUTE,
            color: state.routeColor
          }
        });

        // Adiciona camadas e registra eventos
        routeLayer.eachLayer(layer => {
          state.map.addLayer(layer);
          registerLayerEvents(layer);
        });

        // Ajusta zoom para mostrar toda a rota
        const bounds = routeLayer.getBounds();
        if (bounds.isValid()) {
          state.map.fitBounds(bounds);
        }

        // Atualiza métricas de área e distância
        updateGeoJSONMetrics(state.routeGeoJSON);
      } else {
        console.error("GeoJSON inválido: estrutura ausente ou incorreta");
      }
    } catch (err) {
      console.error("Erro ao carregar GeoJSON inicial:", err);
    }
  }
}

/**
 * Cria controle personalizado para resetar o mapa
 */
function createResetControl() {
  return L.Control.extend({
    options: { position: 'topright' },
    onAdd: function () {
      const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
      const button = L.DomUtil.create('a', 'd-flex justify-content-center align-items-center', container);
      button.innerHTML = '<i class="ki-solid fs-2 ki-cross-circle"></i>';
      button.href = '#';
      button.title = 'Resetar Mapa';

      // Impede propagação e chama clearMap
      L.DomEvent.on(button, 'click', L.DomEvent.stopPropagation)
        .on(button, 'click', L.DomEvent.preventDefault)
        .on(button, 'click', clearMap);

      return container;
    }
  });
}

/**
 * Ao criar camada, mostra salvar e registra eventos
 */
function handleLayerCreated(e) {
  showSaveButton();
  registerLayerEvents(e.layer);
}

/**
 * Ao cortar camada, remove original e adiciona resultado ajustado
 */
function handleLayerCut(e) {
  showSaveButton();

  const original = e.originalLayer || e.layer;
  const result = e.resultLayer || e.result;

  if (original && state.map.hasLayer(original)) {
    state.map.removeLayer(original);
  }

  if (result?.eachLayer) {
    result.eachLayer(layer => {
      state.map.addLayer(layer);
      registerLayerEvents(layer);
    });
  }
}

/**
 * Registra eventos de edição e remoção em um layer
 */
function registerLayerEvents(layer) {
  if (!layer || !layer.on) return;
  layer.on('pm:edit', showSaveButton);
  layer.on('pm:remove', showSaveButton);
  layer.on('pm:dragend', showSaveButton);
}

/**
 * Exibe o botão de salvar
 */
function showSaveButton() {
  const btn = document.getElementById("saveMap");
  if (btn) btn.classList.remove("hidden");
}

/**
 * Trata submissão do formulário de busca de bairro
 */
function handleBairroSearch(e) {
  e.preventDefault();
  const input = document.getElementById("bairroInput");
  if (input) {
    const termo = input.value;
    if (termo.length >= CONFIG.SEARCH.MIN_QUERY_LENGTH) {
      searchNeighborhood(termo);
    }
  }
}

/**
 * Fecha dropdown ao clicar fora
 */
function handleDocumentClick(e) {
  if (!e.target.closest("[data-kt-dropdown=true]")) {
    const dd = document.getElementById("dropdown");
    if (dd) dd.classList.add("hidden");
  }
}

/**
 * Atalho Ctrl+Z para desfazer
 */
function handleKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "z") {
    undoLastChange();
    e.preventDefault();
  }
}

/**
 * Abre ou fecha o dropdown de resultados
 */
function toggleDropdown() {
  const menu = document.getElementById('dropdownMenu');
  const toggle = document.getElementById('bairroInput');
  const isOpen = menu.classList.contains('show');

  if (isOpen) {
    menu.classList.remove('show');
    toggle.setAttribute('aria-expanded', 'false');
  } else {
    menu.classList.add('show');
    toggle.setAttribute('aria-expanded', 'true');
  }
}

/** Fecha sempre */
function closeDropdown() {
  const menu = document.getElementById('dropdownMenu');
  const toggle = document.getElementById('bairroInput');
  menu.classList.remove('show');
  toggle.setAttribute('aria-expanded', 'false');
}

/**
 * Pesquisa bairro via Nominatim
 */
async function searchNeighborhood(query) {
  const dropdownMenu = document.getElementById("dropdownMenu");
  const loader = document.getElementById("loader");
  if (!dropdownMenu || !loader) return;

  // prepara UI
  dropdownMenu.innerHTML = "";
  loader.classList.remove("hidden");
  closeDropdown();

  try {
    const params = new URLSearchParams({
      format: 'geojson',
      polygon_geojson: 1,
      q: query,
      limit: CONFIG.SEARCH.RESULTS_LIMIT
    });
    const res = await fetch(`${CONFIG.SEARCH.NOMINATIM_URL}?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const features = (data.features || [])
      .filter(f => f.geometry && ["Polygon", "MultiPolygon"].includes(f.geometry.type));

    if (!features.length) {
      dropdownMenu.innerHTML = `
        <li><span class="dropdown-item-text text-muted">Nenhum bairro encontrado</span></li>
      `;
    } else {
      dropdownMenu.innerHTML = features.map((f, i) => `
        <li>
          <button
            class="dropdown-item text-muted border-bottom border-gray-200 text-wrap text-break"
            type="button"
            data-index="${i}"
          >
            ${f.properties.display_name}
          </button>
        </li>
      `).join("");

      // adiciona o listener em cada botão
      dropdownMenu.querySelectorAll(".dropdown-item").forEach(btn => {
        btn.addEventListener("click", () => {
          const idx = +btn.dataset.index;
          displaySelectedNeighborhood(features[idx]);
          closeDropdown();
        });
      });
    }

    // exibe menu e oculta loader
    loader.classList.add("hidden");
    toggleDropdown();

  } catch (err) {
    console.error("Erro ao buscar bairro:", err);
    loader.classList.add("hidden");
    dropdownMenu.innerHTML = `
      <li><span class="dropdown-item-text text-danger">Erro na busca</span></li>
    `;
    toggleDropdown();
  }
}


/**
 * Exibe bairro selecionado no mapa
 */
function displaySelectedNeighborhood(feature) {
  if (!feature.geometry?.type.includes("Polygon")) return;

  const layer = L.geoJSON(feature, {
    style: { color: state.routeColor, weight: 2, fillOpacity: 0.3 }
  });

  layer.eachLayer(sub => {
    state.map.addLayer(sub);
    registerLayerEvents(sub);
  });

  state.map.fitBounds(layer.getBounds());
  showSaveButton();
  document.getElementById("dropdown")?.classList.add("hidden");
}

function closeRing(feature) {
  const coords = feature.geometry.coordinates[0];
  const [x0, y0] = coords[0];
  const [xn, yn] = coords[coords.length - 1];
  if (x0 !== xn || y0 !== yn) {
    coords.push([x0, y0]);
    feature.geometry.coordinates[0] = coords;
  }
  return feature;
}

/**
 * Salva o GeoJSON atual (inclui união e subtração de polígonos)
 */
function saveGeoJSON() {
  // 1) salva estado para undo e esconde o botão
  saveCurrentState();
  document.getElementById("saveMap")?.classList.add("hidden");

   // Garante Feature<Polygon|MultiPolygon> e retira anéis com <4 vértices
  function sanitizeFeature(feat) {
    if (!feat || feat.type !== "Feature") return null;
    const g = feat.geometry;
    if (g.type === "Polygon") {
      g.coordinates = g.coordinates.filter(r => r.length >= 4);
      return g.coordinates.length ? feat : null;
    }
    if (g.type === "MultiPolygon") {
      g.coordinates = g.coordinates
        .map(poly => poly.filter(r => r.length >= 4))
        .filter(poly => poly.length > 0);
      return g.coordinates.length ? feat : null;
    }
    return null;
  }

  // Tenta várias estratégias de difference antes de desistir
  function safeDifference(a, b) {
    try {
      return turf.difference(a, b) || a;
    } catch (err1) {
      console.warn("difference falhou, tentando buffer em ambos:", err1);
      try {
        const ab = turf.buffer(a, 0);
        const bb = turf.buffer(b, 0);
        const d  = turf.difference(ab, bb);
        return d ? turf.buffer(d, 0) : a;
      } catch (err2) {
        console.warn("difference com buffer também falhou, pulando:", err2);
        return a;
      }
    }
  }


  // 2) coleta apenas os polígonos desenhados (não as rotas fixas)
  const drawn = [];
  state.map.eachLayer(layer => {
    if (
      layer instanceof L.Polygon &&
      !layer.options.isOtherRoute &&
      typeof layer.toGeoJSON === "function"
    ) {
      const f = sanitizeFeature(layer.toGeoJSON());
      if (f) drawn.push(f);
    }
  });

  // 3) se não há desenho, limpa tudo e recarrega só as rotas fixas
  if (drawn.length === 0) {
    state.routeGeoJSON = "";
    updateInputField("");
    updateGeoJSONMetrics("");
    state.map.eachLayer(l => {
      if (!(l instanceof L.TileLayer)) state.map.removeLayer(l);
    });
    addOtherRoutes();
    return;
  }


  // 4) para cada polígono desenhado, subtrai apenas as rotas que se interceptam
  const processed = drawn.map(feat => {
    let current = feat;
    state.map.eachLayer(other => {
      if (
        other instanceof L.Polygon &&
        other.options.isOtherRoute &&
        typeof other.toGeoJSON === "function"
      ) {
        const otherFeat = sanitizeFeature(other.toGeoJSON());
        if (!otherFeat) return;               // geometria fixa inválida
        // só tenta se intersectam
        if (!turf.booleanDisjoint(current, otherFeat)) {
          // primeiro buffer na rota fixa para “colar”
          let bf;
          try {
            bf = turf.buffer(otherFeat, 0);
          } catch (e) {
            console.warn(`buffer otherRoute id=${other.options.otherRouteId} falhou:`, e);
            return;
          }
          // diferença segura
          current = safeDifference(current, bf);
        }
      }
    });
    return current;
  });

  // 5) junta tudo num único Feature (Polygon ou MultiPolygon)
  let combined;
  if (processed.length === 1) {
    combined = processed[0];
  } else {
    const allCoords = [];
    processed.forEach(f => {
      const g = f.geometry;
      if (g.type === "Polygon") {
        allCoords.push(g.coordinates);
      } else {
        allCoords.push(...g.coordinates);
      }
    });
    combined = {
      type: "Feature",
      geometry: { type: "MultiPolygon", coordinates: allCoords }
    };
  }

  // 6) buffer final para “colar” fissuras
  try {
    combined = turf.buffer(combined, 0);
  } catch (e) {
    console.warn("Falha no buffer final:", e);
  }

  // 7) grava no estado e atualiza input/métricas
  state.routeGeoJSON = combined;
  updateInputField(combined);
  updateGeoJSONMetrics(combined);

  // 8) limpa todo o mapa (mantém apenas o tile layer)
  state.map.eachLayer(l => {
    if (!(l instanceof L.TileLayer)) state.map.removeLayer(l);
  });

  // 9) redesenha rotas fixas + resultado final
  addOtherRoutes();
  const finalFeat = sanitizeFeature(combined);
  if (finalFeat) {
    const layer = L.geoJSON(finalFeat, {
      style: { color: state.routeColor, weight: 2, fillOpacity: 0.15 }
    });
    layer.eachLayer(l => {
      state.map.addLayer(l);
      registerLayerEvents(l);
    });
  }

  // 10) redesenho apenas o resultado final
  const resultLayer = L.geoJSON(combined, {
    style: { color: state.routeColor, weight: 2, fillOpacity: 0.15 }
  });
  resultLayer.eachLayer(l => {
    state.map.addLayer(l);
    registerLayerEvents(l);
  });
}



/**
 * Armazena estado atual para desfazer depois
 */
function saveCurrentState() {
  if (state.routeGeoJSON) {
    state.undoStack.push(JSON.parse(JSON.stringify(state.routeGeoJSON)));
    if (state.undoStack.length > CONFIG.UNDO.MAX_HISTORY) state.undoStack.shift();
  }
}

/**
 * Desfaz última alteração
 */
function undoLastChange() {
  if (!state.undoStack.length) return;
  state.routeGeoJSON = state.undoStack.pop();

  // Remove polygons atuais
  Object.values(state.map._layers).forEach(l => { if (l instanceof L.Polygon) state.map.removeLayer(l); });

  // Redesenha estado anterior
  L.geoJSON(state.routeGeoJSON, { style: { color: state.routeColor, weight: 2, fillOpacity: 0.3 } })
    .eachLayer(l => { state.map.addLayer(l); registerLayerEvents(l); });

  showSaveButton();
  updateInputField(state.routeGeoJSON);
  updateGeoJSONMetrics(state.routeGeoJSON);
}

/**
 * Atualiza métricas de área e perímetro exibidas
 */
function updateGeoJSONMetrics(geojson) {
  const ids = ["areaTotal", "distanciaTotal", "areaTotalInput", "distanciaTotalInput"];
  if (!geojson) {
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        if (el.tagName === 'INPUT') el.value = "0.00";
        else el.textContent = id.includes("area") ? "0.00 m²" : "0.00 km";
      }
    });
    return;
  }
  try {
    const area = turf.area(geojson);
    const dist = turf.length(geojson, { units: 'kilometers' });
    document.getElementById("areaTotal").textContent = `${area.toFixed(2)} m²`;
    document.getElementById("distanciaTotal").textContent = `${dist.toFixed(2)} km`;
    document.getElementById("areaTotalInput").value = area.toFixed(2);
    document.getElementById("distanciaTotalInput").value = dist.toFixed(2);
  } catch (err) {
    console.error("Erro ao calcular métricas:", err);
  }
}

/**
 * Atualiza input hidden com o GeoJSON
 */
function updateInputField(geojson) {
  const input = document.getElementById("geojsonInput");
  if (input) input.value = geojson ? JSON.stringify(geojson) : "";
}

/**
 * Adiciona as outras rotas estáticas ao mapa
 */
function addOtherRoutes() {
  if (!state.otherRoutes.length) return;

  state.otherRoutes.forEach(r => {
    if (!r.geojson) {
      console.warn(`Rota ${r.id} sem geojson, pulando…`);
      return;
    }

    let gj = r.geojson;
    if (typeof gj === "string") {
      try {
        gj = JSON.parse(gj);
      } catch (err) {
        console.error(`Rota ${r.id} com geojson inválido, pulando…`, err);
        return;
      }
    }

    // normaliza qualquer geometria pura em Feature
    if (gj.type !== "Feature") {
      gj = { type: "Feature", geometry: gj };
    }

    // só Polygon ou MultiPolygon
    const gt = gj.geometry?.type;
    if (!["Polygon", "MultiPolygon"].includes(gt)) {
      console.warn(`Rota ${r.id} tipo não suportado (${gt}), pulando…`);
      return;
    }

    // adiciona a camada, marcando-a com isOtherRoute
    L.geoJSON(gj, {
      style: CONFIG.STYLES.OTHER_ROUTES,
      pmIgnore: true,
      onEachFeature: (feature, layer) => {
        layer.options.isOtherRoute   = true;
        layer.options.otherRouteId   = r.id;
        layer.on("click", e => {
          const url = `${CONFIG.REDIRECT.OTHER_ROUTES}/${r.id}/`;
          layer
            .bindPopup(
              `<a href="${url}" class="text-gray-900 hover:text-blue-600 text-sm">${
                r.name || "Rota"
              }</a>`
            )
            .openPopup(e.latlng);
        });
      }
    }).addTo(state.map);
  });
}

/**
 * Limpa o mapa, removendo todas as camadas de polígonos e restaurando o estado inicial
 */
function clearMap() {
  state.map.eachLayer(l => {
    if (!(l instanceof L.TileLayer)) state.map.removeLayer(l);
  });
  state.routeGeoJSON = null;
  state.map.addLayer(state.drawnItems);
  addOtherRoutes();
  showSaveButton();
  updateInputField(null);
  updateGeoJSONMetrics(null);
}

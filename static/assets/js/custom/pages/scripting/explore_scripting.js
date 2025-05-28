
document.addEventListener("DOMContentLoaded", function () {
    const LIcon = L.Icon.Default;
    LIcon.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-shadow.png',
    });

    const mapdata = document.getElementById("allRoutesMap");
    const rotas = JSON.parse(mapdata.dataset.routes); // válido!
    const mapa = L.map('allRoutesMap').setView([-22.85, -43.0], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap',
        detectRetina: true
    }).addTo(mapa);

    const colors = [
        { name: "orange", hex: "#e37b0e" },
        { name: "green", hex: "#0aa344" },
        { name: "blue", hex: "#0074D9" },
        { name: "purple", hex: "#4f2c56" },
        { name: "darkred", hex: "#8f1c1c" },
        { name: "darkgreen", hex: "#228B22" },
        { name: "darkblue", hex: "#1f5775" },
        { name: "cadetblue", hex: "#395b64" },
        { name: "lightred", hex: "#ff7f50" },
        { name: "beige", hex: "#ffb88c" },
        { name: "lightgreen", hex: "#caff70" },
        { name: "lightblue", hex: "#87cefa" },
        { name: "darkpurple", hex: "#5d2d5d" },
        { name: "pink", hex: "#f78fb3" },
        { name: "gray", hex: "#808080" },
    ]; // cores omitidas para brevidade

    const routeSelect = document.getElementById("routeSelect");
    const allRouteLayers = [];

    let ws = null;

    function connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${wsProtocol}://${window.location.host}/ws/marker-toggle/`;

        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
            console.log('✅ WebSocket conectado.');
        };

        ws.onmessage = function (event) {
            console.log("📩 Resposta do WebSocket:", event.data);
        };

        ws.onerror = function (e) {
            console.error("❌ Erro no WebSocket:", e);
        };

        ws.onclose = function (e) {
            console.warn("⚠️ WebSocket desconectado. Tentando reconectar em 3s...");
            setTimeout(connectWebSocket, 3000); // reconecta após 3s
        };
    }

    connectWebSocket();


    function limparMapa() {
        allRouteLayers.forEach(layer => mapa.removeLayer(layer));
        allRouteLayers.length = 0;
    }


    function carregarRotas(nomeSelecionado) {
        limparMapa();
        rotas.forEach((rt, idx) => {
            if (nomeSelecionado !== "all" && rt.name !== nomeSelecionado) return;

            // Decodifica GeoJSON
            const rotaGeo = typeof rt.geojson === "string"
                ? JSON.parse(rt.geojson)
                : rt.geojson;

            // Estilo da linha principal
            const corLinha = colors[idx % colors.length];
            const coordsLine = rotaGeo.features[0].geometry.coordinates.map(
                p => [p[1], p[0]]
            );
            const poly = L.polyline(coordsLine, {
                color: corLinha.hex,
                weight: 5,
                opacity: 0.7,
                dashArray: '10,5'
            }).addTo(mapa);
            allRouteLayers.push(poly);

            // Dados totais da rota (vindos do backend)
            const totalDist = parseFloat(rt.distance_km); // em km
            const totalTime = parseFloat(rt.time_min);    // em min
            const rawCoords = rotaGeo.features[0].geometry.coordinates;

            // Adiciona marcadores como antes
            rt.stops.forEach(p => {
                const icon = p.order_number === "SAIDA"
                    ? L.AwesomeMarkers.icon({ icon: 'home', markerColor: 'red', prefix: 'fa' })
                    : L.AwesomeMarkers.icon({
                        icon: p.is_check ? 'check' : ' ',
                        markerColor: corLinha.name,
                        prefix: 'fa',
                        html: p.is_check ? '' : `<span class='text-white text-sm'>${p.position}</span>`
                    });

                if (p.lat && p.long) {
                    const marker = L.marker([p.lat, p.long], { icon }).addTo(mapa);
                    marker._customData = { id: p.id, latlng: [p.lat, p.long], is_check: p.is_check };

                    // Gera popup com botão de copiar e marcar
                    function gerarPopupHTML() {
                        const checked = marker._customData.is_check;
                        const btnColor = checked ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700';
                        const btnIcon = checked ? 'times' : 'check';
                        const btnText = checked ? 'Desmarcar' : 'Marcar';

                        return `
            <div class="text-sm text-gray-800 rounded-lg p-1 space-y-2">
              <p class="flex justify-between items-center">
                <strong class="text-xs">${rt.name}</strong>
                <strong class="text-primary">Ordem #${p.position}</strong>
              </p>
              <div>
                <span class="text-yellow-500 dark:text-red-400">
                  Pedido: ${p.order_number}
                  <button class="ml-2 text-xs text-gray-600 copy-btn" data-copy-text="${p.order_number}" title="Copiar">
                    <i class="fas fa-copy"></i>
                  </button>
                </span><br>
                <span class="text-blue-500 dark:text-blue-400 font-semibold">Cliente: ${p.client}</span>
              </div>
              <p>${p.address}</p>
              <div class="text-center">
                <button class="mark-check-btn ${btnColor} text-white px-4 py-1 rounded text-xs font-medium" data-marker-id="${p.id}">
                  <i class="fas fa-${btnIcon} mr-1"></i>${btnText}
                </button>
              </div>
            </div>
          `;
                    }

                    marker.bindPopup(gerarPopupHTML, { className: 'dark:bg-gray-800' });
                    allRouteLayers.push(marker);
                    if (p.is_check) marker.getElement().classList.add("marker-checked");

                    marker.on("popupopen", () => {
                        document.querySelector(`.mark-check-btn[data-marker-id="${p.id}"]`)
                            ?.addEventListener("click", () => {
                                const newState = !marker._customData.is_check;
                                if (ws.readyState === WebSocket.OPEN) {
                                    ws.send(JSON.stringify({ delivery_id: p.id, is_check: newState }));
                                    marker._customData.is_check = newState;
                                    const newIcon = L.AwesomeMarkers.icon({
                                        icon: newState ? 'check' : ' ',
                                        markerColor: corLinha.name,
                                        prefix: 'fa',
                                        html: newState ? '' : `<span class='text-white text-sm'>${p.position}</span>`
                                    });
                                    marker.setIcon(newIcon);
                                    marker.getElement()?.classList.toggle("marker-checked", newState);
                                    marker.closePopup();
                                } else {
                                    alert("Conexão WebSocket perdida.");
                                }
                            });
                    });
                }
            });

        }); // fim rotas.forEach
    }

    routeSelect.addEventListener("change", function () {
        carregarRotas(this.value);
        document.querySelectorAll(".pedido-card").forEach(card => {
            card.style.display = (this.value === "all" || card.dataset.route === this.value) ? "block" : "none";
        });
    });
    document.querySelectorAll(".pedido-card").forEach(card => {
        card.addEventListener("click", () => {
            const markerId = card.getAttribute("data-marker-id");
            const marker = allRouteLayers.find(m => m._customData?.id == markerId);
            if (marker) {
                mapa.setView(marker._customData.latlng, 15, { animate: true });
                marker.openPopup();
            }
        });
    });
    carregarRotas("all");

    document.addEventListener('click', function (e) {
        if (e.target.closest('.copy-btn')) {
            const btn = e.target.closest('.copy-btn');
            const text = btn.getAttribute('data-copy-text');
            navigator.clipboard.writeText(text).then(() => {
                btn.innerHTML = '<i class="fas fa-check text-green-500"></i>';
                setTimeout(() => {
                    btn.innerHTML = '<i class="fas fa-copy"></i>';
                }, 1000);
            });
        }
    });
});

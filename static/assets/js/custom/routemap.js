class RouteMap {
  /**
   * @param {Object} opts
   * @param {string} opts.mapId      — id do container do mapa
   * @param {string} opts.dataUrl    — URL para fazer fetch do JSON de rotas
   * @param {string} [opts.selectId] — id do <select> de filtro
   * @param {Array}  [opts.center]   — [lat, lng] iniciais
   * @param {number} [opts.zoom]     — zoom inicial
   */
  constructor({ mapId, dataUrl, selectId = null, center = [-22.85, -43.0], zoom = 11 }) {
    this.mapEl = document.getElementById(mapId);
    if (!this.mapEl) throw new Error(`#${mapId} não encontrado`);
    this.dataUrl = dataUrl;
    this.selectEl = selectId ? document.getElementById(selectId) : null;
    this.center = center;
    this.zoom = zoom;
    this.layers = [];      // Armazenará polylines e markers já adicionados
    this.rotas = [];      // Vai conter o JSON de rota carregado do servidor
    this.scriptingId = this.mapEl.getAttribute('data-scripting-id');
    this.currentFilter = 0;

    // Controles de visibilidade das rotas especiais
    this.hideDeliveryRoute = false;  // Controla rota -1 (delivery)
    this.hideCompanyRoute = false;   // Controla rota -2 (company)
  }

  /**
   * Inicializa o mapa, carrega dados iniciais, desenha todas as rotas e abre o WebSocket.
   */
  async init() {
    // 1) cria o mapa Leaflet apenas UMA VEZ
    this._initLeaflet();

    // 2) adiciona botões de controle
    this._addControlButtons();

    // 3) busca e desenha dados iniciais
    await this._loadData();
    this._bindFilter();
    this._renderAll(0);

    // 4) conecta no WebSocket
    this._connectWebSocket();

    // 5) força redraw (caso esteja dentro de modal, etc.)
    setTimeout(() => this.map.invalidateSize(), 300);
  }

  _initLeaflet() {
    // Aponta ícones padrão no Leaflet (para funcionar offline)
    const LIcon = L.Icon.Default;
    LIcon.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-shadow.png',
    });

    // CRIA E CONFIGURA O MAPA (somente aqui, em init)
    this.map = L.map(this.mapEl).setView(this.center, this.zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap',
      detectRetina: true
    }).addTo(this.map);
  }

  _addControlButtons() {
    // Cria container para os botões
    const buttonContainer = L.DomUtil.create('div', 'leaflet-control-buttons');

    // Botão para ocultar/mostrar rotas de delivery (-1)
    const deliveryButton = L.DomUtil.create('button', 'leaflet-control-button delivery-button', buttonContainer);
    deliveryButton.innerHTML = '<i class="fa-solid fa-truck"></i>';
    deliveryButton.title = 'Ocultar/Mostrar Rotas de Entrega';

    // Botão para ocultar/mostrar rotas da empresa (-2)
    const companyButton = L.DomUtil.create('button', 'leaflet-control-button company-button', buttonContainer);
    companyButton.innerHTML = '<i class="fa-solid fa-building"></i>';
    companyButton.title = 'Ocultar/Mostrar Rotas da Empresa';

    // Adiciona os botões ao container do mapa Leaflet
    this.map.getContainer().appendChild(buttonContainer);

    // Event listeners
    deliveryButton.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this._toggleDeliveryRoute(deliveryButton);
    });

    companyButton.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this._toggleCompanyRoute(companyButton);
    });

    // Impede que cliques nos botões afetem o mapa
    L.DomEvent.disableClickPropagation(buttonContainer);

  }

  _toggleDeliveryRoute(button) {
    this.hideDeliveryRoute = !this.hideDeliveryRoute;

    if (this.hideDeliveryRoute) {
      // Oculta a rota -1
      this.clear(-1);
      button.classList.add('hidden-state');
      button.title = 'Mostrar Rotas de Entrega';
    } else {
      // Mostra a rota -1
      button.classList.remove('hidden-state');
      button.title = 'Ocultar Rotas de Entrega';

      // Re-renderiza para mostrar a rota
      const currentFilter = this.selectEl ? parseInt(this.selectEl.value, 10) || 0 : 0;
      this._renderAll(currentFilter);
    }
  }

  _toggleCompanyRoute(button) {
    this.hideCompanyRoute = !this.hideCompanyRoute;

    if (this.hideCompanyRoute) {
      // Oculta a rota -2
      this.clear(-2);
      button.classList.add('hidden-state');
      button.title = 'Mostrar Rotas da Empresa';
    } else {
      // Mostra a rota -2
      button.classList.remove('hidden-state');
      button.title = 'Ocultar Rotas da Empresa';

      // Re-renderiza para mostrar a rota
      const currentFilter = this.selectEl ? parseInt(this.selectEl.value, 10) || 0 : 0;
      this._renderAll(currentFilter);
    }
  }

  async _loadData(loadplanId = null) {
    try {
      let url = this.dataUrl;
      if (loadplanId) {
        // Adiciona o loadplan_id como query parameter
        const separator = url.includes('?') ? '&' : '?';
        url += `${separator}loadplan_id=${loadplanId}`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      this._updateData(data);
    } catch (err) {
      console.error("Erro ao carregar rotas:", err);
      this.rotas = [];
    }
  }

  _updateData(data) {
    data.forEach(route => {
      const existingRoute = this.rotas.find(rt => rt.id === route.id);
      if (existingRoute) {
        this.clear(route.id);
        Object.assign(existingRoute, route);
        // Só desenha se não estiver oculta
        if (!this._shouldHideRoute(route.id)) {
          if (route.id == -1 && !this.hideDeliveryRoute) this._drawRoute(route);
          if (this.currentFilter !== 0 && this.currentFilter !== route.id) return;
          this._drawRoute(route);
        }
        if (window.CopyClipboard) window.CopyClipboard.init();
      } else {
        this.rotas.push(route);
      }
    })
  }

  _shouldHideRoute(routeId) {
    return (routeId === -1 && this.hideDeliveryRoute) ||
      (routeId === -2 && this.hideCompanyRoute);
  }

  clear(routeData_id = null) {
    if (routeData_id) {
      // Remove apenas os layers da rota específica (usando routeData_id)
      this.layers = this.layers.filter(layer => {
        if (layer.routeData && layer.routeData.id === routeData_id) {
          this.map.removeLayer(layer);
          return false; // Remove do array
        }

        return true;
      });
    } else {
      // Remove todos os layers, exceto os fixos (id < -1)
      this.layers = this.layers.filter(layer => {
        // Remove o layer do mapa e do array
        this.map.removeLayer(layer);
        return false;
      });
    }
  }

  /**
   * Desenha no mapa todas as rotas ou apenas uma rota, de acordo com filterId.
   * @param {number} filterId — 0 = todas, >0 = rota específica
   */
  _renderAll(filterId = 0) {
    this.clear();

    this.rotas.forEach(rt => {
      if (rt.id) {
        const routeIdNum = Number(rt.id);
        if (filterId > 0 && routeIdNum !== filterId) return;

        // Verifica se a rota deve ser ocultada
        if (this._shouldHideRoute(routeIdNum)) return;
      }
      this._drawRoute(rt);
    });

    // Rota só é mostrada quando há filtro específico e não está oculta
    if (filterId > 0) {
      const rotaCompany = this.rotas.find(rt => rt.id === -2);
      const deliveryUnassigned = this.rotas.find(rt => rt.id === -1);
      if (rotaCompany && !this.hideCompanyRoute) {
        this._drawRoute(rotaCompany);
      }
      if (deliveryUnassigned && !this.hideDeliveryRoute) {
        this._drawRoute(deliveryUnassigned);
      }
    }
    if (window.CopyClipboard) window.CopyClipboard.init();
  }

  _drawRoute(rt) {
    // 1) Polyline
    let geo, coords;
    try {

      if (rt.geojson) {

        geo = (typeof rt.geojson === 'string') ? JSON.parse(rt.geojson) : rt.geojson;
        coords = geo.features[0].geometry.coordinates.map(p => [p[1], p[0]]);

        const line = L.polyline(coords, {
          color: rt.color,
          weight: 5,
          opacity: 0.7,
          dashArray: '8,6'
        }).addTo(this.map);

        line.routeData = {
          id: Number(rt.id),
          name: rt.name,
          color: rt.color,
          geojson: rt.geojson,
          stops: rt.stops
        };

        this.layers.push(line);

      }

      // 2) Marcadores de parada
      rt.stops.forEach(stop => {
        if (!stop.lat || !stop.long) return;
        const isHome = (stop.order_number === 'SAIDA');
        const icon = this._bindIcon(rt, stop);
        const m = L.marker([stop.lat, stop.long], { icon }).addTo(this.map);
        m.routeData = {
          id: Number(rt.id),
          code: rt.code,
          name: rt.name,
          loadPlan: rt.loadPlan,
          color: rt.color,
          geojson: rt.geojson,
          stops: rt.stops
        };
        m.stopData = stop;
        this.layers.push(m);
        this._bindPopup(m);
      });

    } catch (err) {
      console.error("Erro ao iniciar rota:", err);
      return;
    }
  }

  _bindIcon(rt, stop) {
    const icontype = {
      delivery: stop.position,
      delivery_unassigned: `<i class="fa-solid fa-box text-white"></i>`,
      warehouse: `<i class="fa-solid fa-warehouse text-white"></i>`,
      store: `<i class="fa-solid fa-store text-white"></i>`,
      distribution_center: `<i class="fa-solid fa-distribution-center text-white"></i>`,
      hub: `<i class="fa-solid fa-hub text-white"></i>`,
      secondary_warehouse: `<i class="fa-solid fa-warehouse-alt text-white"></i>`,
      other: `<i class="fa-solid fa-question-circle text-white"></i>`,
    };
    const colors = {
      delivery: rt.color,
      delivery_unassigned: 'gray',
      warehouse: '#F44336',
      store: '#E91E63',
      distribution_center: '#9C27B0',
      hub: '#673AB7',
      secondary_warehouse: '#2196F3',
      other: '#009688',
    };

    const icon = L.divIcon({
      className: '',
      html: `
        <div style="background-color:${colors[stop.type]};" class="custom-circle-marker">
          ${icontype[stop.type]}
        </div>`,
      iconSize: [20, 28],
      iconAnchor: [18, 14],
    });
    return icon;
  }

  _bindPopup(marker) {
    marker.on('click', () => {
      const { routeData: rt, stopData: p } = marker;
      this.map.closePopup();
      const stt_obj = {
        pending: "<span class='badge badge-light-warning'><span class='bullet bullet-dot bg-warning me-2'></span>Pendente</span>",
        in_script: "<span class='badge badge-light-warning'><span class='bullet bullet-dot bg-warning me-2'></span>Em Roteiro</span>",
        in_load: "<span class='badge badge-light-primary'><span class='bullet bullet-dot bg-primary me-2'></span>Alocado</span>",
        picked: "<span class='badge badge-light-info'><span class='bullet bullet-dot bg-info me-2'></span>Separado</span>",
        loaded: "<span class='badge badge-light-info'><span class='bullet bullet-dot bg-info me-2'></span>Carregado</span>",
        in_transit: "<span class='badge badge-light-info'><span class='bullet bullet-dot bg-info me-2'></span>Em Trânsito</span>",
        delivered: "<span class='badge badge-light-success'><span class='bullet bullet-dot bg-success me-2'></span>Entregue</span>",
        failed: "<span class='badge badge-light-danger'><span class='bullet bullet-dot bg-danger me-2'></span>Falha na Entrega</span>",
        cancelled: "<span class='badge badge-light-danger'><span class='bullet bullet-dot bg-danger me-2'></span>Cancelado</span>",
      }
      const filial = p.filial ? `${p.filial} - ` : '';

      const main = document.createElement('div');
      main.classList.add('card', 'card-custom', 'card-shadow', 'gutter-b', 'mb-0');
      let load = {
        id: 0,
        code: '',
        name: 'Entrega sem rota e carga definida'
      }
      if (rt.loadPlan) {
        load = rt.loadPlan;
      }
      let HTML;
      if (p.type == 'delivery' || p.type == 'delivery_unassigned') {
        const customerUrl = `/crm/customer/${p.customer.id}/update/`;
        HTML = `
            <div class="border-0 px-2">
              <div class="d-flex justify-conten-between align-items-center card-title d-flex align-items-center m-0 w-100">
                <span class="fs-6 fw-bold me-2 d-flex align-items-center">
                  ${filial}${p.order_number}
                  <i class="fa-regular fa-copy ms-2 cursor-pointer text-muted text-hover-success" data-copy-text="${p.order_number}"></i>
                </span>
                ${stt_obj[p.status]}
              </div>
            </div>

            <div class="bg-gray-100 card-subtitle mt-2 p-2 rounded d-flex justify-content-between align-items-center">
              <div class="fs-7 text-gray-800">${p.customer.name}</div>
              <a href="${customerUrl}">
                <i class="fa fa-external-link ms-2 text-primary"></i>
              </a>
            </div>
            
            <div class="d-flex justify-content-between align-items-center border-bottom border-gray-100 card-body p-2">
              <div class="fs-7 text-start">${p.address}</div>
              <i class="fas fa-map-marker-alt text-primary fs-4 ms-2"></i>
            </div>

            <div class="mt-2">
            <form data-form class="form">
              <input type="hidden" name="delivery" value="${p.id}">
              ${this._createLoadDropdown(load, p)}
            </form>
            </div>
            <div class="mt-4">
              <div class="d-flex gap-2 align-items-center">
                <i class="fa-solid fa-cube text-muted"></i>
                <span class="text-info badge badge-light-info">${p.total_volume_m3 || 0}</span>
                <i class="fa-solid fa-weight-hanging text-muted"></i>
                <span class="text-info badge badge-light-info">${p.total_weight_kg || 0}</span>
                <i class="fa-solid fa-dollar-sign text-muted"></i>
                <span class="text-success badge badge-light-success">${p.price || 0}</span>
              </div>
            </div>
          `;

      } else {
        HTML = `
            <div class="border-0 py-0">
              <div class="card-title d-flex m-0 align-items-center w-100">
                ${p.name}
              </div>
            </div>
          `;
      }

      main.innerHTML += HTML;

      setTimeout(() => {
        if (marker.getPopup()) {
          marker.unbindPopup();
        }

        marker.bindPopup(main, {
          maxWidth: 260,
          className: 'leaflet-popup-metronic',
          closeOnClick: true,
          autoClose: true
        }).openPopup();

        this._bindDropdownEvents(main, p, load);

      }, 10);
    });
  }

  _createLoadDropdown(load, delivery) {
    if (delivery.status != 'in_script') return `${load.code} - ${load.name}`;
    const dropdownHTML = `
        <select data-select class="form-select form-select-sm" aria-label=".form-select-sm example" style="max-height: 250px; overflow-y: auto;">
          <option value="0">Entrega sem rota e carga definida</option>
          ${this.rotas.filter(rt => rt.id > 0).map(rt => `
            <option style="color: ${rt.color}" value="${rt.id}" ${load.id === rt.loadPlan.id ? 'selected' : ''}>
              ${rt.loadPlan.code} - ${rt.name}
            </option>
          `).join('')}
        </select>
    `;

    return dropdownHTML;
  }

  _bindDropdownEvents(popupElement, stopData, load) {
    // Event listener para mudança de seleção no dropdown select
    const selectElement = popupElement.querySelector('select[data-select]');

    if (selectElement) {
      selectElement.addEventListener('change', (e) => {
        const selectedLoadplanId = parseInt(e.target.value);

        // Dados simplificados para envio via WebSocket
        const payload = {
          delivery_id: stopData.id,
          scripting_id: this.scriptingId,
          old_loadplan_id: load.id,
          new_loadplan_id: selectedLoadplanId
        };

        // Envia via WebSocket
        this._sendWebSocketMessage({
          action: 'update_route',
          data: payload
        });

        // Fechar o popup após a mudança
        this.map.closePopup();
      });
    }
  }

  _bindFilter() {
    if (!this.selectEl) return;
    this.selectEl.addEventListener('change', () => {
      const valNum = parseInt(this.selectEl.value, 10) || 0;
      this.currentFilter = valNum;
      this._renderAll(valNum);
    });
  }

  _sendWebSocketMessage(message) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      console.error('WebSocket não está conectado');
    }
  }

  _connectWebSocket() {
    const proto = (window.location.protocol === 'https:') ? 'wss' : 'ws';
    const url = `${proto}://${window.location.host}/ws/routes/${this.scriptingId}/`;
    this.socket = new ReconnectingWebSocket(url);

    this.socket.addEventListener('message', async ({ data }) => {
      try {
        const payload = JSON.parse(data);
        if (payload.action === 'reload_map') {
          await this._reloadAllRoutes();
        } else if (payload.action === 'update_route') {
          this._updateData(payload.data);
          this._updateTableRow(payload.data);
        }
      } catch (err) {
        console.warn("Falha ao processar evento do WebSocket:", err);
      }
    });
    this.socket.addEventListener('error', (error) => {
      console.error('Erro no WebSocket:', error);
    });
  }

  _updateTableRow(plans) {
    plans.forEach(data => {
      const plan = data.loadPlan;
      if (!plan) {
        return;
      }

      const row = document.querySelector(`#load_plans_table tr[data-id="${plan.id}"]`);
      if (!row) {
        return;
      }

      const elNotScript = document.querySelector('[data-total-not-deliveries-scripting]');
      if (elNotScript) {
        elNotScript.textContent = data.scripting?.total_deliveries_unassigned ?? '';
      } else {
      }

      const elScript = document.querySelector('[data-total-deliveries-scripting]');
      if (elScript) {
        elScript.textContent = data.scripting?.total_deliveries ?? '';
      }

      const elTotalDel = row.querySelector('[data-total-deliveries]');
      if (elTotalDel) {
        elTotalDel.textContent = plan.totals?.deliveries ?? '';
      }

      const elWeight = row.querySelector('[data-total-weight]');
      if (elWeight) {
        elWeight.textContent = `${plan.totals?.weight_kg ?? ''}`;
        elWeight.classList.toggle('text-danger', plan.is_weight_overloaded);
        elWeight.classList.toggle('text-gray-800', !plan.is_weight_overloaded);
      }

      const elVolume = row.querySelector('[data-total-volume]');
      if (elVolume) {
        elVolume.textContent = `${plan.totals?.volume_m3 ?? ''}`;
        elVolume.classList.toggle('text-danger', plan.is_volume_overloaded);
        elVolume.classList.toggle('text-gray-800', !plan.is_volume_overloaded);
      }

      const elValue = row.querySelector('[data-total-value]');
      if (elValue) {
        if(plan.totals.value) elValue.textContent = `R$ ${plan.totals.value}`;
      }
    });
  }


  async _reloadAllRoutes() {
    await this._loadData();
    this._bindFilter();
    if (this.selectEl) {
      this.selectEl.value = '0';
    }
    this._renderAll(0);
  }
}
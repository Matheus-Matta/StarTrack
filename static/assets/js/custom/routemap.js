class RouteMap {
  /**
   * @param {Object} opts
   * @param {string} opts.mapId      — id do container do mapa
   * @param {string} opts.dataUrl    — URL pra fetch do JSON
   * @param {string} [opts.selectId] — id do <select> de filtro
   * @param {Array}  [opts.center]   — [lat, lng] iniciais
   * @param {number} [opts.zoom]     — zoom inicial
   */
  constructor({ mapId, dataUrl, selectId=null, center=[-22.85, -43.0], zoom=11 }) {
    this.mapEl    = document.getElementById(mapId);
    if (!this.mapEl) throw new Error(`#${mapId} não encontrado`);
    this.dataUrl  = dataUrl;
    this.selectEl = selectId ? document.getElementById(selectId) : null;
    this.center   = center;
    this.zoom     = zoom;
    this.layers   = [];
    this.rotas    = [];
  }

  async init() {
    this._initLeaflet();
    await this._loadData();
    this._bindFilter();     // <<–– registra o listener do select
    this._renderAll(0);     // 0 = todas as rotas
    // se for dentro de modal, force redraw depois de alguns ms
    setTimeout(()=> this.map.invalidateSize(), 300);
  }

  _initLeaflet() {
    const LIcon = L.Icon.Default;
    LIcon.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon-2x.png',
      iconUrl:       'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png',
      shadowUrl:     'https://unpkg.com/leaflet@1.9.3/dist/images/marker-shadow.png',
    });

    this.map = L.map(this.mapEl).setView(this.center, this.zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap', detectRetina: true
    }).addTo(this.map);
  }

  async _loadData() {
    try {
      const res = await fetch(this.dataUrl);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.rotas = await res.json();
    } catch (err) {
      console.error("Erro ao carregar rotas:", err);
      this.rotas = [];
    }
  }

  clear() {
    this.layers.forEach(l => this.map.removeLayer(l));
    this.layers = [];
  }

  /**
   * @param {number} filterId — 0 = todas, >0 = rota específica
   */
  _renderAll(filterId=0) {
    this.clear();
    this.rotas.forEach((rt, idx) => {
      if (filterId > 0 && rt.id !== filterId) return;
      this._drawRoute(rt);
    });
  }

  _drawRoute(rt) {
    // desenha a linha
    const geo    = typeof rt.geojson==='string'?JSON.parse(rt.geojson):rt.geojson;
    const coords = geo.features[0].geometry.coordinates.map(p=>[p[1],p[0]]);
    const line   = L.polyline(coords, {
      color: rt.color, weight:5, opacity:0.7, dashArray:'8,6'
    }).addTo(this.map);
    this.layers.push(line);

    // desenha marcadores
    rt.stops.forEach(stop => {
      if (!stop.lat||!stop.long) return;
      const isHome = stop.order_number==='SAIDA';
      const icon = L.ExtraMarkers.icon({
        icon:        isHome?'fa-home':'fa-number',
        markerColor: isHome?'red':rt.color,
        shape:       'circle', prefix:'fa',
        number:      (!isHome&&!stop.is_check)?stop.position:'',
        svg:true
      });
      const m = L.marker([stop.lat,stop.long],{icon}).addTo(this.map);
      m.routeData = rt;
      m.stopData  = stop;
      this.layers.push(m);
      this._bindPopup(m);
    });
  }

  _bindPopup(marker) {
    marker.on('click',()=>{
      const {routeData:rt,stopData:p} = marker;
      const html = `
        <div style="font-size:.9em">
          <strong>${rt.name}</strong><br>
          Ordem: ${p.position}<br>
          Pedido: ${p.order_number}<br>
          Cliente: ${p.client}<br>
          Endereço: ${p.address}<br>
          Filial: ${p.filial}<br>
          <button class="toggle-check">
            ${p.is_check?'Desmarcar':'Marcar'}
          </button>
        </div>`;
      marker.bindPopup(html).openPopup();
      const btn = marker.getPopup().getElement().querySelector('.toggle-check');
      btn.onclick = ()=>{
        p.is_check = !p.is_check;
        marker.closePopup();
      };
    });
  }

  _bindFilter() {
    if (!this.selectEl) return;
    this.selectEl.addEventListener('change', ()=>{
      const val = parseInt(this.selectEl.value,10)||0;
      this._renderAll(val);
    });
  }
}

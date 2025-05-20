/**
 * Código otimizado para visualização de mapas e gráficos
 * Utiliza práticas de clean code e configuração centralizada
 */

// Importa a configuração global
const { CONFIG } = window;

/**
 * Inicializa a aplicação quando o DOM estiver pronto
 */
document.addEventListener('DOMContentLoaded', () => {
  // Inicializa os componentes principais
  const mapManager = new MapManager();
  const chartManager = new ChartManager();
  
  // Carrega dados e configura os componentes
  const areaData = loadAreaData();
  mapManager.initialize(areaData);
  chartManager.createCharts(areaData);
  
  // Configura os eventos de UI
  setupUIEvents(mapManager);
});

/**
 * Carrega os dados das áreas do atributo data-areas
 * @returns {Array} Array de objetos com dados das áreas
 */
function loadAreaData() {
  const script = document.getElementById('areas-data');
  if (!script) return [];
  try {
    return JSON.parse(script.textContent);
  } catch (err) {
    console.error('Erro ao parsear areas-data JSON:', err);
    return [];
  }
}

/**
 * Configura os event listeners para interação do usuário
 * @param {MapManager} mapManager Instância do gerenciador de mapas
 */
function setupUIEvents(mapManager) {
  // Event listener para o filtro de áreas
  const filterElement = document.getElementById('filterArea');
  if (filterElement) {
    filterElement.addEventListener('change', (e) => mapManager.showArea(e.target.value));
  }
  
  // Event listeners para a lista de áreas
  document.querySelectorAll('#areaList li').forEach(li => {
    li.addEventListener('click', () => {
      const areaId = li.dataset.id;
      mapManager.showArea(areaId);
    });
  });
}

/**
 * Classe responsável pelo gerenciamento do mapa e seus layers
 */
class MapManager {
  constructor() {
    this.map = null;
    this.areaLayers = {};
  }
  
  /**
   * Inicializa o mapa e adiciona os layers
   * @param {Array} areas Dados das áreas a serem exibidas
   */
  initialize(areas) {
    // Inicializa o mapa com a configuração padrão
    this.map = L.map('map').setView(
      CONFIG.MAP.INITIAL_VIEW, 
      CONFIG.MAP.INITIAL_ZOOM
    );
    
    // Adiciona a camada base de tiles
    L.tileLayer(CONFIG.MAP.TILE_URL, {
      attribution: CONFIG.MAP.TILE_ATTRIBUTION
    }).addTo(this.map);
    
    // Cria os layers para cada área
    this._createAreaLayers(areas);
    
    // Mostra todas as áreas inicialmente
    this.showArea('all');
  }
  
  /**
   * Cria os layers para cada área e armazena referências
   * @param {Array} areas Dados das áreas
   * @private
   */
  _createAreaLayers(areas) {
    areas.forEach(area => {
      let geo;
     
      // 1) Se veio como string, tenta parsear
      if (typeof area.geojson === 'string') {
        try {
          geo = JSON.parse(area.geojson);
          
        } catch (err) {
          console.warn(`Área ${area.id} pulada: JSON inválido`, err);
          return;
        }
      } else {
        // 2) Se já veio como objeto
        geo = area.geojson;
      }
      // 3) Verifica se é GeoJSON válido
      if (!geo || !geo.type) {
        console.warn(`Área ${area.id} pulada: objeto GeoJSON sem "type"`, geo);
      } else {
      // Aplica estilo com base na configuração e cor específica da área
      const layerStyle = {
        ...CONFIG.STYLES.CURRENT_ROUTE,
        color: area.color,
        fillColor: area.color
      };
      
      // Cria o layer e adiciona ao mapa
      const layer = L.geoJSON(geo, { style: () => layerStyle }).addTo(this.map);
      
      // Configura o popup ao clicar
      layer.on("click", (e) => {
        const routeUrl = `${CONFIG.REDIRECT.OTHER_ROUTES}/${area.id}/`;
        const popupContent = `<a href="${routeUrl}" class="text-dark text-hover-primary fs-5">${area.name || 'Rota'}</a>`;
        
        layer.bindPopup(popupContent).openPopup(e.latlng);
      });
      
      // Armazena referência ao layer
      this.areaLayers[area.id] = layer;
      }
    });
  }
  
  /**
   * Exibe ou oculta áreas no mapa com base no ID
   * @param {string} id ID da área ou 'all' para todas
   */
  showArea(id) {
    Object.entries(this.areaLayers).forEach(([areaId, layer]) => {
      const shouldShow = id === 'all' || areaId === id;
      
      if (shouldShow) {
        this.map.addLayer(layer);
        // Ajusta a visualização para focalizar a área selecionada
        this.map.fitBounds(layer.getBounds(), { maxZoom: 13 });
      } else {
        this.map.removeLayer(layer);
      }
    });
  }
}

/**
 * Classe responsável pela criação e gerenciamento dos gráficos
 */
class ChartManager {
  /**
   * Cria os gráficos de área e distância
   * @param {Array} areas Dados das áreas
   */
  createCharts(areas) {
    this._createAreaChart(areas);
    this._createDistanceChart(areas);
  }
  
  /**
   * Cria o gráfico de top 5 áreas
   * @param {Array} areas Dados das áreas
   * @private
   */
  _createAreaChart(areas) {
    const chartElement = document.getElementById('chartArea');
    if (!chartElement) return;
    
    // Prepara os dados para o gráfico: top 5 áreas por tamanho
    const topAreas = areas
      .map(area => ({ 
        name: area.name, 
        value: area.area, 
        color: area.color 
      }))
      .sort((a, b) => b.value - a.value)
    
    // Cria o gráfico com as configurações adequadas
    new Chart(chartElement, {
      type: 'bar',
      data: {
        labels: topAreas.map(area => area.name),
        datasets: [{
          label: 'm²',
          data: topAreas.map(area => area.value),
          backgroundColor: topAreas.map(area => area.color)
        }]
      },
      options: this._getChartOptions()
    });
  }
  
  /**
   * Cria o gráfico de top 5 distâncias
   * @param {Array} areas Dados das áreas
   * @private
   */
  _createDistanceChart(areas) {
    const chartElement = document.getElementById('chartKm');
    if (!chartElement) return;
    
    // Prepara os dados para o gráfico: top 5 áreas por distância
    const topDistances = areas
      .map(area => ({ 
        name: area.name, 
        value: area.km, 
        color: area.color 
      }))
      .sort((a, b) => b.value - a.value)
    
    // Cria o gráfico com as configurações adequadas
    new Chart(chartElement, {
      type: 'bar',
      data: {
        labels: topDistances.map(area => area.name),
        datasets: [{
          label: 'km',
          data: topDistances.map(area => area.value),
          backgroundColor: topDistances.map(area => area.color)
        }]
      },
      options: this._getChartOptions()
    });
  }
  
  /**
   * Retorna configurações padrão para os gráficos
   * @returns {Object} Configurações do gráfico
   * @private
   */
  _getChartOptions() {
    return {
      indexAxis: 'y',                // Barras horizontais
      responsive: true,
      plugins: {
        legend: { display: false },  // Oculta a legenda
      },
      scales: {
        x: {
          display: false,            // Oculta o eixo X
          beginAtZero: true
        },
        y: {
          display: true,             // Mostra apenas o eixo Y
          grid: { display: false },  // Sem linhas de grade
          ticks: {
            padding: 8,              // Espaçamento dos labels
            font: { size: 12 }
          }
        }
      }
    };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const wrapper = document.getElementById('my-areas-table');
  const table = wrapper.querySelector('table');
  const ct = new DjangoDataTable({
    root: wrapper,
    pageSize: 10,
    cellClassName: 'px-2 py-1 w-100',
    rowRenderer: area => {
      const routeUrl = `${CONFIG.REDIRECT.OTHER_ROUTES}/${area.id}/`;
      const status    = area.status === 'active' ? 'Ativo' : 'Desabilitado';
      const statusCls = area.status === 'active' ? 'success' : 'danger';
      return `
        <tr onclick="location.href='${routeUrl}';" class="py-0 cursor-pointer bg-hover-light border-bottom border-gray-200">
          <td class="ps-5 fw-bold d-flex align-items-center">
            <span style="background-color: ${area.hex_color}"
                  class="bullet bullet-dot h-15px w-15px me-2"></span>
            ${area.name}
          </td>
          <td class="py-0 text-gray-700 text-center">${area.vehicle_count}</td>
          <td class="py-0">
            <span class="badge badge-${statusCls} badge-outline rounded-pill">
              ${status}
            </span>
          </td>
        </tr>`;
    }
  });
});
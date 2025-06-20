/**
 * LoadPlan Drawer Manager
 * Gerencia a exibição de detalhes de planos de carga em um drawer
 */
class LoadPlanDrawer {
  constructor() {
    this.config = {
      endpoint: null,
      listSelector: null,
      detailsId: null,
      scripting_id: null
    };

    this.elements = {
      listEls: null,
      details: null,
      card: null
    };

    this.isInitialized = false;
    this.currentPlanId = null;
  }

  init(options = {}) {
    this.validateConfig(options);
    this.config = { ...options };
    this.initializeElements();
    this.setupEventListeners();
    this.hideDetails();
    this.isInitialized = true;
  }

  validateConfig(options) {
    const required = ['endpoint', 'scripting_id', 'listSelector', 'detailsId'];
    const missing = required.filter(key => !options[key]);
    if (missing.length) {
      throw new Error(`Configurações obrigatórias ausentes: ${missing.join(', ')}`);
    }
  }

  initializeElements() {
    this.elements.listEls = document.querySelectorAll(this.config.listSelector);
    this.elements.details = document.getElementById(this.config.detailsId);
    if (!this.elements.details) throw new Error(`Elemento '${this.config.detailsId}' não encontrado`);
    this.elements.card = this.elements.details.querySelector('#plan-details-card');
    if (!this.elements.card) {
      this.elements.card = document.createElement('div');
      this.elements.card.id = 'plan-details-card';
      this.elements.details.appendChild(this.elements.card);
    }
  }

  setupEventListeners() {
    // abre drawer
    document.addEventListener('click', event => {
      const row = event.target.closest('tr[data-id]');
      if (row) {
        event.preventDefault();
        this.showDetails(row.dataset.id);
      }
    });
    // fecha drawer
    document.addEventListener('click', event => {
      if (event.target.closest('[data-action="close-details"]')) {
        event.preventDefault();
        this.hideDetails();
      }
    });
    // ESC fecha
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.isDetailsVisible()) {
        this.hideDetails();
      }
    });
  }

  async showDetails(planId) {
    if (!this.isInitialized) return;
    this.showLoading();
    const resp = await this.fetchPlanDetails(planId);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.message);
    this.elements.card.innerHTML = data.html;
    this.initializeLoadedContent();
    this.showDetailsPanel();
    confirmForm = window.confirmSubmitForm;
    confirmForm();
    this.currentPlanId = planId;
  }

  initializeLoadedContent() {
    // agora com a lógica de habilitar/desabilitar
    this.setupDynamicEventListeners();
    // batch checkboxes
    this.setupBatchEventListeners();
    // copy to clipboard
    if (window.CopyClipboard) window.CopyClipboard.init();
  }

  setupDynamicEventListeners() {
    // Localiza os botões dentro do card
    const removeBtn = this.elements.card.querySelector('#rmvLoad');
    const addBtn = this.elements.card.querySelector('#addLoad');

    // Lista de checkboxes de cada tipo
    const inChecks = Array.from(this.elements.card.querySelectorAll('input[name="in_load"]'));
    const outChecks = Array.from(this.elements.card.querySelectorAll('input[name="out_load"]'));

    // Função que atualiza o disabled dos botões
    const updateButtons = () => {
      if (removeBtn) {
        // habilita se houver ao menos um in_load checado
        removeBtn.disabled = !inChecks.some(chk => chk.checked);
      }
      if (addBtn) {
        // habilita se houver ao menos um out_load checado
        addBtn.disabled = !outChecks.some(chk => chk.checked);
      }
    };

    // Anexa listener de change em todos os checkboxes
    inChecks.forEach(chk => chk.addEventListener('change', updateButtons));
    outChecks.forEach(chk => chk.addEventListener('change', updateButtons));

    // Atualiza o estado inicial dos botões
    updateButtons();
  }

  setupBatchEventListeners() {
    // botões batch (certifique-se de que no HTML tenham esses IDs)
    const removeBtn = this.elements.card.querySelector('#rmvLoad');
    const addBtn = this.elements.card.querySelector('#addLoad');

    if (removeBtn) removeBtn.addEventListener('click', () => this.handleBatchRemove());
    if (addBtn) addBtn.addEventListener('click', () => this.handleBatchAdd());
  }

  async handleBatchRemove() {
    const ids = Array.from(
      this.elements.card.querySelectorAll('input[name="in_load"]:checked')
    ).map(chk => chk.value);

    if (!ids.length) return;
    const resp = await this.deliveryBatchRequest('DELETE', ids);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    await this.showDetails(this.currentPlanId);
  }

  async handleBatchAdd() {
    const ids = Array.from(
      this.elements.card.querySelectorAll('input[name="out_load"]:checked')
    ).map(chk => chk.value);

    if (!ids.length) return;
    const resp = await this.deliveryBatchRequest('POST', ids);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    await this.showDetails(this.currentPlanId);
  }

  async deliveryBatchRequest(method, deliveryIds) {
    const payload = {
      delivery_ids: deliveryIds,       // <- note o plural
      loadplan_id: this.currentPlanId,
      scripting_id: this.config.scripting_id,
      method: method
    };
    const csrf = this.getCSRFToken();
    return fetch(this.config.endpoint_add, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });
  }

  getCSRFToken() {
    // sua implementação de CSRF aqui (cookie/meta/input)
    return this.getCSRFFromCookie() || '';
  }
  getCSRFFromCookie() {
    const name = 'csrftoken', c = document.cookie.split(';').find(x => x.trim().startsWith(name + '='));
    return c ? decodeURIComponent(c.split('=')[1]) : null;
  }

  async fetchPlanDetails(planId) {
    const url = `${this.config.endpoint}${this.config.scripting_id}/${planId}/`;
    return fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    });
  }

  showDetailsPanel() {
    this.elements.listEls.forEach(el => el.classList.add('d-none'));
    this.elements.details.classList.remove('d-none');
  }
  hideDetails() {
    // remove event listeners dinâmicos se houver
    this.elements.details.classList.add('d-none');
    this.elements.listEls.forEach(el => el.classList.remove('d-none'));
    this.elements.card.innerHTML = '';
    this.currentPlanId = null;
  }
  showLoading() {
    this.elements.card.innerHTML = `
      <div class="d-flex justify-content-center align-items-center p-4">
        <div class="spinner-border text-primary" role="status"></div>
        <span class="ms-2">Carregando...</span>
      </div>`;
    this.showDetailsPanel();
  }
  isDetailsVisible() {
    return !this.elements.details.classList.contains('d-none');
  }
  destroy() {
    this.hideDetails();
    this.isInitialized = false;
    this.currentPlanId = null;
  }
}

class DjangoSelect {
  constructor({
    root,
    pageSize    = 10,
    filters     = {},
    orderBy     = null,
    orderDir    = 'asc',
    rowRenderer = null,
    valueField  = 'id'
  }) {
    this.root        = root;
    this.url         = root.dataset.url;
    this.fields      = (root.dataset.fields || '').split(',').map(f=>f.trim()).filter(Boolean);
    this.input       = root.querySelector('[data-djangoselect]');
    this.hidden      = root.querySelector('[data-target-djangoselect]');
    this.dropdown    = root.querySelector('[data-dropdown]');
    this.optionsEl   = this.root.querySelector('[data-options]');
    this.pageSize    = pageSize;
    this.filters     = filters;
    this.orderBy     = orderBy;
    this.orderDir    = orderDir;
    this.rowRenderer = rowRenderer;
    this.valueField  = valueField;
    this.currentPage   = 1;
    this.currentSearch = '';
    this.csrfToken     = this._getCsrfToken();

    // bind do click-fora
    this._onDocumentClick = this._onDocumentClick.bind(this);
    document.addEventListener('click', this._onDocumentClick);

    // cria um único handler debounced
    this._debouncedFetch = this._debounce(() => this._onInput(), 800);

    this._bindEvents();
    this._toggleOptions();
    // carrega valor inicial, se houver
    const initial = root.dataset.valueDjangoselect;
    if (initial) this._loadInitial(initial);
  }
 
  _bindEvents() {
    const cleanBtn  = this.root.querySelector('[data-clean]');

    // busca ao digitar, mas debounceado
    this.input.addEventListener('input', () => {
      this._debouncedFetch();;
      this._toggleOptions()
    });

    // mostra dropdown ao focar, se já tiver itens
    this.input.addEventListener('focus', () => {
        this._show();
        this._fetch();
    });
    cleanBtn.addEventListener('click', () => {
      this.input.value  = '';
      this.hidden.value = '';
      const dd = this.root.querySelector('[data-dropdown]');
      if (dd) dd.innerHTML = '';
      this._hide();
      this._toggleOptions()
    });
    }

  _toggleOptions() {
    // esconde ou mostra o <span data-options>
    if (this.input.value.length <= 0) {
      this.optionsEl.classList.add('d-none');
    } else {
      this.optionsEl.classList.remove('d-none');
    }
  }


  _onInput() {
    this.currentSearch = this.input.value.trim();
    this.currentPage   = 1;
    this._fetch();
  }

  _onDocumentClick(e) {
    if (!this.root.contains(e.target)) {
      this._hide();
    }
  }

  _getCsrfToken() {
    const name  = 'csrftoken';
    const match = document.cookie.match(`(^|;)\\s*${name}=([^;]+)`);
    return match ? decodeURIComponent(match[2]) : '';
  }

  _loadInitial(id) {
    // mesmo código seu para carregar texto inicial…
  }

  _showLoading() {
    // limpa e mostra spinner
    this.dropdown.innerHTML = `
      <div class="dropdown-item text-center py-2">
        <div class="spinner-border spinner-border-sm" role="status"></div>
      </div>`;
    this._show();
  }

  _fetch() {
    // mostra o loading antes de tudo
    this._showLoading();

    const params = new URLSearchParams({
      page:      this.currentPage,
      size:      this.pageSize,
      search:    this.currentSearch,
      order_by:  this.orderBy,
      order_dir: this.orderDir,
      fields:    this.fields.join(','),
    });

    if (Object.keys(this.filters).length) {
      params.set('filters', JSON.stringify(this.filters));
    }
    if (this.root.dataset.model) {
      params.set('model', this.root.dataset.model);
    }

    fetch(`${this.url}?${params}`, {
      headers: {
        'X-CSRFToken': this.csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin'
    })
    .then(r => r.ok ? r.json() : { results: [] })
    .then(data => {
      const rows = Array.isArray(data.results) ? data.results : [];
      this.totalPages = data.total_pages || 1;
      this._renderItems(rows);
      this._renderPagination(data.page || 1, this.totalPages);
      // mantém dropdown aberto
    })
    .catch(err => {
      console.error('DjangoSelect fetch error:', err);
      // opcional: mostrar erro no dropdown
      this.dropdown.innerHTML = `<div class="dropdown-item text-danger">Erro ao carregar</div>`;
    });
  }

  _renderItems(rows) {
    this.dropdown.innerHTML = '';
    if (!rows.length) {
      this.dropdown.innerHTML = `<div class="dropdown-item text-muted">Nenhum resultado</div>`;
      return;
    }
    rows.forEach(row => {
      const item = document.createElement('div');
      item.className = 'dropdown-item bg-hover-light rounded';
      item.innerHTML = this.rowRenderer
        ? this.rowRenderer(row)
        : (row[this.fields[1]] || '');
      item.addEventListener('click', () => {
        this.input.value  = row[this.fields[1]] || '';
        this.hidden.value = row[this.valueField]   || '';
        this._hide();
        this._toggleOptions()
      });
      this.dropdown.append(item);
    });
  }

  _renderPagination(page, total) {
    // implementar paginação se necessário
  }

  _show() {
    this.dropdown.style.display = 'block';
  }

  _hide() {
    this.dropdown.style.display = 'none';
  }

  _debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }
}

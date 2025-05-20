(function (global) {
  // Pega CSRF do cookie
  function getCsrfToken() {
    const name = 'csrftoken';
    const m = document.cookie.match(new RegExp('(^|;)\\s*' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }

  class DjangoDataTable {
    /**
     * @param {Object} options
     * @param {HTMLElement} options.root - elemento que contém a tabela
     * @param {string} options.url - endpoint para buscar dados
     * @param {number} [options.pageSize=10]
     * @param {string} [options.cellClassName=''] - classes CSS para cada <td>
     * @param {Object<string,function>} [options.renderers={}] - renderizadores por coluna
     * @param {Object} [options.pagination={}] - textos e classes de paginação
     * @param {function(Object):string} [options.rowRenderer] - função que recebe um objeto `row` e retorna um `<tr>…</tr>` completo
     * @param {Object}    [options.filters]      - { campo: valor, … }
     * @param {string}    [options.orderBy]    - campo inicial de ordenação
     * @param {string}    [options.orderDir]   - direção inicial ('asc'|'desc')
     */
    constructor({
      root,
      pageSize = 10,
      cellClassName = '',
      renderers = {},
      pagination = {},
      filters = {},
      rowRenderer = null,
      orderBy = null,
      orderDir = 'asc'
    }) {
      if (!root) {
        console.error('DjangoDataTable: elemento root não fornecido');
        return;
      }
      this.root = root;
      this.url = root.dataset.url;
      this.table = root.querySelector('table');
      if (!this.table) {
        console.error('DjangoDataTable: <table> não encontrado em root');
        return;
      }
      this.tbody = this.table.querySelector('tbody');
      this.ths = Array.from(this.table.querySelectorAll('th[data-field]'));
      this.pagWrap = root.querySelector('[data-pagination]') || null;

      // modelo vindo de data-model no root (opcional)
      this.model = root.dataset.model || null;

      // mapeamento de paginação
      this.p = Object.assign({
        wrapperClass: '',
        btnClass: 'btn',
        activeClass: 'active',
        disabledClass: 'disabled',
        ellipsisClass: 'text-gray-500',
        prevText: '«',
        nextText: '»',
      }, pagination);
 
      this.p.instanceName = `DT_${Date.now()}_${Math.random().toString(36).substr(2,5)}`;
      window[this.p.instanceName] = this;

      this.renderers = renderers;
      this.rowRenderer = typeof rowRenderer === 'function' ? rowRenderer : null;
      this.cellClassName = cellClassName;
      this.sizeEl = root.querySelector('select[data-page-size]') || null;

      this.filters       = filters;

      this.currentPage = 1;
      this.pageSize = pageSize;
      this.currentSearch = '';
      this.currentOrderBy  = orderBy  || this.ths[0]?.dataset.field || null;
      this.currentOrderDir = orderDir === 'desc' ? 'desc' : 'asc';
      this.csrfToken = getCsrfToken();

      this._bindEvents();
      this.fetchData();
    }

    _bindEvents() {
      // busca
      const search = this.root.querySelector('[data-search]');
      if (search) {
        search.addEventListener(
          'input',
          this.debounce(e => {
            this.currentSearch = e.target.value;
            this.currentPage = 1;
            this.fetchData();
          }, 300)
        );
      }

      // ordenação
      this.ths.forEach(th => {
        const fld = th.dataset.field;
        if (fld === this.currentOrderBy) {
          th.classList.add(
            this.currentOrderDir === 'asc'
              ? 'table-sort-asc'
              : 'table-sort-desc'
          );
        }
        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
          const fld = th.dataset.field;
          if (this.currentOrderBy === fld) {
            this.currentOrderDir = this.currentOrderDir === 'asc' ? 'desc' : 'asc';
          } else {
            this.currentOrderBy  = fld;
            this.currentOrderDir = 'asc';
          }
          this.ths.forEach(t => t.classList.remove('table-sort-asc','table-sort-desc'));
          th.classList.add(this.currentOrderDir === 'asc'
            ? 'table-sort-asc'
            : 'table-sort-desc');
          this.fetchData();
        });
      });

      // seleção de tamanho de página
      if (this.sizeEl) {
        this.sizeEl.addEventListener('change', e => {
          const v = parseInt(e.target.value, 10);
          if (v > 0) {
            this.pageSize = v;
            this.currentPage = 1;
            this.fetchData();
          }
        });
      }
    }

    fetchData() {
      // 1) monta os params iniciais
      const params = new URLSearchParams({
        page: this.currentPage,
        size: this.pageSize,
        search: this.currentSearch,
        order_by: this.currentOrderBy,
        order_dir: this.currentOrderDir,
      });
    
    
      // 2) injeta o modelo (data-model) se existir
      const model = this.root.dataset.model;
      if (model) {
        params.set('model', model);
      }


      // monta lista de campos a partir dos <th data-field>
      const allFields = this.ths
        .map(th => th.dataset.field)
        .filter(Boolean)
        .join(',');

      if (allFields) {
        params.set('search_fields', allFields);
        params.set('fields',        allFields);
      }

      if (Object.keys(this.filters).length) {
       
      }
      // filtros explícitos (campo ou {value,method})
      if (Object.keys(this.filters).length) {
        params.set('filters', JSON.stringify(this.filters));
      }

      // 3) placeholder de loading
      this._showLoadingRow();
    
      // 4) dispara o fetch já com ?…&model=driver
      fetch(`${this.url}?${params.toString()}`, {
        headers: {
          'X-CSRFToken': this.csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
      })
        .then(r => r.json())
        .then(json => {
          this.totalCount = json.total_count;
          this.totalPages = json.total_pages;
          this._renderRows(json.results);
          this._renderPagination(json.page, json.total_pages);
        })
        .catch(err => {
          console.error('DataTable fetch error', err);
          this._showErrorRow();
        });
    }

    _showLoadingRow() {
      const colspan = this.ths.length || 1;
      this.tbody.innerHTML =
        `<tr><td></td></tr><tr><td colspan="${colspan}" class="${this.cellClassName} text-center"><div class="spinner-border text-primary" role="status"></div></td></tr>`;
    }

    _showErrorRow() {
      const colspan = this.ths.length || 1;
      this.tbody.innerHTML =
        `<tr><td></td></tr><tr><td colspan="${colspan}" class="${this.cellClassName} text-center text-danger">Erro ao carregar dados.</td></tr>`;
    }

    _renderRows(data) {
      if (!Array.isArray(data) || data.length === 0) {
        const colspan = this.ths.length || 1;
        this.tbody.innerHTML =
          `<tr><td></td></tr><tr><td colspan="${colspan}" class="${this.cellClassName} text-center">Nenhum registro encontrado.</td></tr>`;
        return;
      }
      this.tbody.innerHTML = '<tr><td></td></tr>' + data.map(row => {
        if (this.rowRenderer) {
          try {
            return this.rowRenderer(row);
          } catch (e) {
            console.error('rowRenderer erro:', e);
          }
        }
        const cols = this.ths.map(th => {
          const field = th.dataset.field;
          let content;
          if (this.renderers[field]) {
            content = this.renderers[field](row);
          } else {
            let v = row[field];
            if (typeof v === 'boolean') v = v ? 'Sim' : 'Não';
            content = v == null ? '' : v;
          }
          return `<td class="${this.cellClassName}">${content}</td>`;
        }).join('');
        return `<tr>${cols}</tr>`;
      }).join('');
    }

    _renderPagination(page) {
      const wrap = this.pagWrap;
      if (!wrap) return;
    
      const total = this.totalPages;
      if (total <= 1) {
        wrap.style.display = 'none';
        return;
      }
      wrap.style.display = '';
    
      // calcula início e fim da exibição de resultados
      const start = (page - 1) * this.pageSize + 1;
      const end   = Math.min(page * this.pageSize, this.totalCount);
    
      // helper para criar <li> com botão ou span
      const makeItem = (num, label, enabled, active = false) => {
        const liCls = ['page-item', !enabled && 'disabled', active && 'bg-light text-gray-700 rounded']
          .filter(Boolean).join(' ');
        const inner = enabled
          ? `<button class="page-link" onclick="${this.p.instanceName}.loadPage(${num})">${label}</button>`
          : `<span class="page-link">${label}</span>`;
        return `<li class="${liCls}">${inner}</li>`;
      };
    
      const items = [];
    
      // < anterior
      items.push(makeItem(page - 1, '<i class="ki-solid ki-arrow-left fs-2"></i>', page > 1));
    
      // se page > 2, mostre "1" e possível elipse
      if (page > 2) {
        items.push(makeItem(1, '1', true, page === 1));
        if (page > 3) {
          items.push(`<li class="page-item disabled"><span class="page-link">…</span></li>`);
        }
      }
    
      // página anterior, se existir
      if (page > 1) {
        items.push(makeItem(page - 1, String(page - 1), true));
      }
    
      // página atual
      items.push(makeItem(page, String(page), false, true));
    
      // próxima página, se existir
      if (page < total) {
        items.push(makeItem(page + 1, String(page + 1), true));
      }
    
      // se faltam duas ou mais após, elipse + última
      if (page < total - 1) {
        if (page < total - 2) {
          items.push(`<li class="page-item disabled"><span class="page-link">…</span></li>`);
        }
        items.push(makeItem(total, String(total), true, page === total));
      }
    
      // > próximo
      items.push(makeItem(page + 1, '<i class="ki-solid ki-arrow-right fs-2"></i>', page < total));
    
      // renderiza
      wrap.innerHTML = `
        <div class="d-flex align-items-center gap-4">
          <span data-datatable-info class="fs-7 text-gray-600">
            ${start}–${end} de ${this.totalCount}
          </span>
          <ul class="pagination pagination-sm pagination-rounded mb-0">
            ${items.join('')}
          </ul>
        </div>
      `;
    }
    

    loadPage(n) {
      this.currentPage = n;
      this.fetchData();
    }

    debounce(fn, ms) {
      let t;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), ms);
      };
    }
  }

  global.DjangoDataTable = DjangoDataTable;
})(window);

// estado interno
let _LPD = {
  endpoint:    null,
  listSelector: null,
  $listEls:    null,
  $details:    null,
  $card:       null,
};

/**
 * Configura o drawer de LoadPlan
 * @param {Object} opts
 * @param {string} opts.endpoint     — URL base p/ o fetch (sem o ID no final)
 * @param {string} opts.listSelector — selector CSS p/ todos os containers de lista
 * @param {string} opts.detailsId    — id do container da área de detalhes
 */
function initLoadPlanDrawer({ endpoint, listSelector, detailsId }) {
  _LPD.endpoint     = endpoint;
  _LPD.listSelector = listSelector;
  _LPD.$listEls     = document.querySelectorAll(listSelector);
  _LPD.$details     = document.getElementById(detailsId);
  _LPD.$card        = _LPD.$details.querySelector('#plan-details-card');
  // Esconde detalhes inicialmente
  _LPD.$details.classList.add('d-none');
}

/**
 * Busca e mostra os dados do plano
 * @param {string|number} planId
 */
async function showLoadPlanDrawer(planId) {
  const resp = await fetch(`${_LPD.endpoint}${planId}/`);
  const { html } = await resp.json();
  _LPD.$card.innerHTML = html;

  // oculta todos os listEls e mostra o detalhes
  _LPD.$listEls.forEach(el => el.classList.add('d-none'));
  _LPD.$details.classList.remove('d-none');

  // binda o close
  const btn = _LPD.$card.querySelector('[data-action="close-details"]');
  if (btn) btn.addEventListener('click', hideLoadPlanDrawer);
}

/** Fecha o painel de detalhes e retorna à lista */
function hideLoadPlanDrawer() {
  _LPD.$details.classList.add('d-none');
  _LPD.$listEls.forEach(el => el.classList.remove('d-none'));
  _LPD.$card.innerHTML = '';
}

// auto-init e binding
document.addEventListener('DOMContentLoaded', () => {
  initLoadPlanDrawer({
    endpoint:     '/tms/fleet/loadplan/details/',  // sua URL base
    listSelector: '.plans-list',                  // <div class="plans-list"> que envolve cada tabela
    detailsId:    'plan-details'                  // id do <div id="plan-details">
  });

  // dispara showLoadPlanDrawer no clique de cada <tr data-id>
  document.querySelectorAll('tr[data-id]').forEach(tr => {
    tr.addEventListener('click', () => showLoadPlanDrawer(tr.dataset.id));
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host;

  // ─── TASKS SOCKET ───────────────────────────────
  const taskSocket = new ReconnectingWebSocket(`${wsScheme}://${host}/ws/tasks/`);
  taskSocket.onmessage = e => {
    if (Date.now() < window._wsIgnoreTasksUntil) {
      return;
    }
    const payload = JSON.parse(e.data);
    renderOrUpdateTask(payload);
    markUnreadNotifications();
  };

  // ─── ALERTS SOCKET ──────────────────────────────
  const alertsSocket = new ReconnectingWebSocket(`${wsScheme}://${host}/ws/alerts/`);
  alertsSocket.onmessage = e => {
    if (Date.now() < window._wsIgnoreTasksUntil) {
      return;
    }
    const payload = JSON.parse(e.data);
    prependAlert(payload);
    markUnreadNotifications();
    showToast({
      title: payload.title,
      message: payload.message,
      level: payload.level
    });
    playAlertSound();
  };



  // ─── FUNÇÕES DE RENDERIZAÇÃO ────────────────────

  function prependAlert(note) {
    // note = { title, message, level, level_icon, created_at, link? }
    const container = document.getElementById('alerts_container');

    const item = document.createElement('div');
    item.className = 'd-flex px-4 flex-column py-2 border-bottom cursor-pointer bg-hover-gray-100 bg-gray-100 unread';
    item.setAttribute('data-id', note.id);
    if (note.link) {
      item.style.cursor = 'pointer';
      item.addEventListener('click', () => window.location = note.link);
    }

    item.innerHTML = `
      <div class="d-flex align-items-center unread">
        <div class="symbol symbol-35px me-4">
          <span class="symbol-label bg-light-${note.level}">
            <i class="${note.level_icon} fs-2 text-${note.level}"></i>
          </span>
        </div>
        <div>
          <div class="min-w-375px d-flex justify-content-between">
            <div class="fs-6 text-gray-800 fw-bold">${note.title}</div>
            <small class="text-gray-500">${formatDate(note.created_at)}</small>
          </div>
          <div class="min-w-375px d-flex justify-content-between">
            <div data-message class="fs-7 text-gray-500">${note.message}</div>
            <span data-new class="mh-15px badge badge-light-warning fs-9">Novo</span>
          </div
        </div>
      </div>
    `;

    markRead(item)
    container.prepend(item);
  }

  function renderOrUpdateTask(task) {
    // task = { task_id, name, message, percent, status }
    const container = document.getElementById('tasks_container');
    let item = container.querySelector(`[data-id="${task.id}"]`);

    if (!item) {
      // cria novo
      item = document.createElement('div');
      item.className = 'd-flex border-bottom border-gray-200 flex-column justify-content-center py-2';
      item.setAttribute('data-task-id', task.task_id);
      item.setAttribute('data-id', task.id);
      item.innerHTML = `
        <div class="d-flex ps-5 w-425px align-items-center">
          <div class="symbol symbol-35px me-4" data-symbol></div>
          <div class="mb-0 me-2">
            <div class="w-375px d-flex align-items-center justify-content-between pe-2">
              <div class="d-flex flex-column justify-content-center">
                <a href="#" data-title class="fs-6 text-gray-800 text-hover-primary fw-bold">${task.name || task.task_id}</a>
                <div data-message class="text-gray-500 fs-7">${task.message || ''}</div>
              </div>
              <span data-badge class="badge fs-8"></span>
            </div>
          </div>
        </div>
        <div data-bar class="px-4 mt-2 min-w-425px">
          <div class="progress w-100 h-10px">
            <div class="progress-bar bg-primary" style="width:0%">${task.percent}</div>
          </div>
        </div>
      `;
      container.prepend(item);
    }

    // atualiza ícone, badge, texto e progresso
    const sym = item.querySelector('[data-symbol]');
    const badge = item.querySelector('[data-badge]');
    const msg = item.querySelector('[data-message]');
    const bxbar = item.querySelector('[data-bar]');
    const bar = bxbar.querySelector('.progress-bar');

    // atualiza mensagem
    msg.textContent = task.message;

    // switch de status
    if (task.status === 'success') {
      sym.innerHTML = `<span class="symbol-label bg-light-primary">
                          <i class="ki-solid ki-verify text-success fs-2"></i>
                        </span>`;
      badge.className = 'badge badge-light-success fs-8';
      badge.textContent = 'Concluída';
      bxbar.classList.add('d-none');
    }
    else if (task.status === 'failure') {
      sym.innerHTML = `<span class="symbol-label bg-light-danger">
                          <i class="ki-solid ki-cross text-danger fs-2"></i>
                        </span>`;
      badge.className = 'badge badge-light-danger fs-8';
      badge.textContent = 'Falha';
      bxbar.classList.add('d-none');
    }
    else {
      sym.innerHTML = `<span class="symbol-label bg-light-primary">
                          <i class="animation-spin ki-duotone ki-abstract-12 text-primary fs-2">
                            <span class="path1"></span><span class="path2"></span>
                          </i>
                        </span>`;
      badge.className = 'badge badge-light-primary fs-8';
      badge.textContent = 'Em andamento';
      bar.style.width = `${task.percent || 0}%`;
      bar.textContent = task.percent || 0;
    }
  }

  function formatDate(iso) {
    const d = new Date(iso);
    // dd/mm/yyyy hh:MM
    return d.toLocaleDateString('pt-BR') + ' ' +
      d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }

  const icon = document.querySelector('#header_notifications_toggle');
  const ph = icon?.querySelector('#unhead-notifications');
  const pulse = icon?.querySelector('.pulse-ring');
  const dp = document.querySelector('#header_notifications_dropdown');
  function markUnreadNotifications() {
    if (dp.classList.contains('show')) return;

    icon?.classList.add('pulse', 'pulse-light');
    ph?.classList.add('text-danger');
    pulse?.classList.remove('d-none');
  }
  icon?.addEventListener('click', () => {
    icon?.classList.remove('pulse', 'pulse-light');
    ph?.classList.remove('text-danger');
    pulse?.classList.add('d-none');
  });
  function playAlertSound() {
    const sound = document.getElementById('alert-sound');
    sound.volume = 0.5;
    if (sound) {
      sound.currentTime = 0;
      sound.play().catch(err => {
        // em alguns navegadores o autoplay pode falhar sem interação
        console.warn('Não foi possível tocar som de alerta:', err);
      });
    }
  }

  function markRead(element){
     if (element) {
        element.addEventListener('mouseenter', () => {
          alertsSocket.send(JSON.stringify({
            action: 'mark_read',
            notification_id: element.dataset.id
          }));
          element.classList.remove('bg-gray-100');
          bd = element.querySelector('[data-new]');
          if (bd) bd.remove();
        })
      }
  }

  document.querySelectorAll('.unread').forEach(item => {
    markRead(item);
  });
});
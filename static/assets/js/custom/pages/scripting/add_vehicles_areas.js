document.addEventListener('DOMContentLoaded', function () {
    // Armazena áreas selecionadas por veículo: { vehicleId: [areaId, ...], ... }
    const vehicles_areas = {};
    let currentVehicleId = null;

    function showStep(step) {
        const modal = document.getElementById('modalVehicles');
        modal.querySelector('[data-step="vehicles"]').classList.toggle('d-none', step !== 'vehicles');
        modal.querySelector('[data-step="areas"]').classList.toggle('d-none', step !== 'areas');
        const title = modal.querySelector('[data-title]');
        if (step === 'vehicles') {
            title.textContent = 'Selecione o Veículo';
        } else {
            title.textContent = title.dataset.vehicleName;
        }
    }

    function addValuesToInput() {
        const input = document.querySelector('#vehicles_areas_input');
        if (input) {
            input.value = JSON.stringify(vehicles_areas);
        }
    }

    function updateAddButtonState() {
        const input = document.querySelector('#vehicles_areas_input');
        const btn = document.querySelector('#addVehicleArea');
        if (!btn || !input) return;
        let hasData = false;
        try {
            const data = JSON.parse(input.value || '{}');
            hasData = Object.keys(data).some(key => Array.isArray(data[key]) && data[key].length > 0);
        } catch (e) {
            console.warn('Erro ao parsear vehicles_areas_input:', e);
        }
        const icon = btn.querySelector('i');
        // remove text nodes    
        Array.from(btn.childNodes).forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) btn.removeChild(node);
        });
        if (hasData) {
            if (icon) {
                icon.classList.remove('text-gray-700');
                icon.classList.add('text-success');
            }
            btn.classList.add('text-success');
            btn.classList.remove('text-gray-700');
            btn.insertAdjacentText('beforeend', ' Selecionado');
        } else {
            if (icon) {
                icon.classList.remove('text-success');
                icon.classList.add('text-gray-700');
            }
            btn.classList.remove('text-success');
            btn.classList.add('text-gray-700');
            btn.insertAdjacentText('beforeend', ' Adicionar');
        }
    }

    function confirmAreas() {
        // 1) lê checkboxes marcados no passo Áreas
        const checkedInputs = Array.from(
            document.querySelectorAll('[data-step="areas"] input[name="areas"]:checked')
        );
        // 2) localiza o elemento do veículo no passo Veículos
        const vehicleItem = document.querySelector(
            `#modalVehicles [data-step="vehicles"] [data-vehicle-id="${currentVehicleId}"]`
        );
        if (!vehicleItem) {
            console.error(`Vehicle item not found for ID ${currentVehicleId}`);
            return;
        }
        const areasContainer = vehicleItem.querySelector('[data-templete-areas]');
        if (!areasContainer) {
            console.error('Areas container not found for vehicle ID ' + currentVehicleId);
            return;
        }
        // limpa e mostra container
        areasContainer.innerHTML = '';
        areasContainer.classList.remove('d-none');
        // salva e injeta cada área selecionada
        vehicles_areas[currentVehicleId] = checkedInputs.map(chk => parseInt(chk.value, 10));
        checkedInputs.forEach(chk => {
            const label = document.querySelector(`label[for="${chk.id}"]`);
            const areaName = label ? label.textContent.trim() : chk.value;
            const iconEl = label ? label.querySelector('i') : null;
            const areaColor = iconEl ? iconEl.style.color : '';
            const div = document.createElement('div');
            div.setAttribute('data-item', '');
            div.className = 'fw-semibold';
            div.innerHTML = `<i class="bi bi-geo-alt-fill me-1" style="color: ${areaColor};"></i>${areaName}`;
            areasContainer.appendChild(div);
        });
        // se não houver itens, esconde o container
        if (areasContainer.children.length === 0) {
            areasContainer.classList.add('d-none');
        } else {
            areasContainer.classList.remove('d-none');
        }
        // atualiza input e botão
        addValuesToInput();
        updateAddButtonState();
        // volta para o passo de veículos
        showStep('vehicles');
    }

    // Botões para abrir step de áreas e definir currentVehicleId
    document.querySelectorAll('[data-select-area]').forEach(btn => {
        btn.addEventListener('click', () => {
            currentVehicleId = parseInt(btn.getAttribute('data-id'), 10);
            const place = btn.getAttribute('data-place');
            const title = document.querySelector('#modalVehicles [data-title]');
            title.dataset.vehicleName = `Selecione as Áreas do veículo ${place}`;
            // reseta checkboxes
            document.querySelectorAll('[data-step="areas"] input[name="areas"]').forEach(input => {
                input.checked = false;
                input.closest('li').classList.remove('d-none');
            });
            const prev = vehicles_areas[currentVehicleId] || [];
            document.querySelectorAll('[data-step="areas"] input[name="areas"]').forEach(input => {
                if (prev.includes(parseInt(input.value, 10))) input.checked = true;
            });
            showStep('areas');
        });
    });

    // Botões para retornar a um step específico
    document.querySelectorAll('[data-return-step]').forEach(btn => {
        btn.addEventListener('click', () => showStep(btn.getAttribute('data-return-step')));
    });

    // Botões de confirmação de seleção
    document.querySelectorAll('[data-confirm-select]').forEach(btn => {
        btn.addEventListener('click', confirmAreas);
    });

    // Inicializa estado do botão ao carregar
    updateAddButtonState();
});
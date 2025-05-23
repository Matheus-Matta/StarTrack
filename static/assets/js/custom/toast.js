(function () {
    // 1) referências ao container e ao template
    document.addEventListener('DOMContentLoaded', () => {
        const container = document.getElementById('docs_toast_stack_container');
        const tplInit = document.querySelector('.data-toast_template');
        function showToast({ title, message, level = 'info', duration = 5000 }) {
            // clona o node inteiro
            const toast = tplInit.cloneNode(true);
            toast.classList.remove('d-none');

            // trocar ícone de acordo com level
            const iconMap = {
                success: 'ki-solid ki-verify text-success',
                danger: 'ki-solid ki-cross-circle text-danger',
                warning: 'ki-solid ki-information text-warning',
                info: 'ki-solid ki-information-4 text-info'
            };
            const iconEl = toast.querySelector('[data-toast-icon]');
            // limpa todas as classes de ícone e aplica a nova
            iconEl.className = iconMap[level] + ' fs-2';

            // título, corpo e hora
            toast.querySelector('[data-toast-title]').textContent = title;
            toast.querySelector('[data-toast-body]').textContent = message;
            toast.querySelector('[data-toast-time]').textContent = new Date()
                .toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

            // 5) click no X para fechar
            toast.querySelector('[data-toast-close]')
                .addEventListener('click', () => toast.remove());

            // insere no container e agenda auto‐removal
            container.appendChild(toast);
            setTimeout(() => toast.remove(), duration);

        };
        window.showToast = showToast

        document.querySelectorAll("#message-django .message-itens").forEach((el) => {
            try {
                showToast({
                    title: 'Alerta do sistema',
                    message: el.getAttribute("data-message"),
                    level: el.getAttribute("data-level"),
                    duration: 5000
                })
            } catch(err) {
                console.error("Erro ao mostrar toast:", err);
            }
        })
    })
})();





// copy-clipboard.js
;(function(window, document) {

  class CopyClipboard {
    static _bound = false;

    static init() {
      if (!this._bound) {
        this._clickHandler = this._clickHandler.bind(this);
        document.addEventListener('click', this._clickHandler);
        this._bound = true;
      }
    }

    static destroy() {
      if (this._bound) {
        document.removeEventListener('click', this._clickHandler);
        this._bound = false;
      }
    }

    static async _clickHandler(event) {
      const el = event.target.closest('[data-copy-text]');
      if (!el) return;

      let text = el.getAttribute('data-copy-text') || '';
      const regexAttr = el.getAttribute('data-regex');
      if (regexAttr) {
        try {
          const [, pattern, flags = ""] = regexAttr.split('/');
          const re = new RegExp(pattern, flags);
          if (flags.includes('g')) {
            const matches = [...text.matchAll(re)].map(m => m[0]);
            text = matches.join('');
          } else {
            const m = text.match(re);
            text = m ? m[0] : '';
          }
        } catch (e) {
          console.warn('Regex inválido em data-regex:', regexAttr, e);
        }
      }

      try {
        await navigator.clipboard.writeText(text.trim());

        // === aqui vem a troca de ícone ===
        // supondo que o próprio el seja o <i class="fa-copy">
        const icon = el;
        // armazena as classes originais
        const originalClasses = icon.className;

        // aplica classes do check
        icon.className = 'fa-solid fa-check text-success ms-2';
        
        // após 1s, volta ao original
        setTimeout(() => {
          icon.className = originalClasses;
        }, 1000);
        // === fim da troca de ícone ===

      } catch (err) {
        console.error('Erro ao copiar para clipboard:', err);
      }
    }
  }

  window.CopyClipboard = CopyClipboard;

})(window, document);

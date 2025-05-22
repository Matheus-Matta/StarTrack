// static/js/custom/config.js
(function (global) {
  // Se já existir, não sobrescreve
  if (global.CONFIG) return;

  global.CONFIG = {
    MAP: {
      INITIAL_VIEW: [-22.8, -42.9],
      INITIAL_ZOOM: 12,
      TILE_URL: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      TILE_ATTRIBUTION: '&copy; OpenStreetMap contributors'
    },
    STYLES: {
      CURRENT_ROUTE: {
        weight: 2,
        fillOpacity: 0.3
      },
      OTHER_ROUTES: {
        color: "black",
        weight: 1,
        fillOpacity: 0.15
      }
    },
    REDIRECT: {
      OTHER_ROUTES: '/tms/script/route'
    },
    SEARCH: {
      NOMINATIM_URL: "https://nominatim.openstreetmap.org/search",
      MIN_QUERY_LENGTH: 2,
      RESULTS_LIMIT: 5
    },
    UNDO: {
      MAX_HISTORY: 20
    }
  };
})(window);

document.addEventListener('DOMContentLoaded', function () {
  // Seleciona todos os forms cujo action contenha "driver_delete"
  document.querySelectorAll('.form-confirm').forEach(form => {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const cl = this.dataset.color || 'danger';
      const btn = `btn btn-${cl}`;
      Swal.fire({
        text: this.dataset.message || "Tem certeza que deseja prosseguir?",
        icon: this.dataset.icon || 'warning',
        showCancelButton: true,
        buttonsStyling: false,
        confirmButtonText: "Sim",
        cancelButtonText: "Cancelar",
        customClass: {
          confirmButton:  btn,
          cancelButton: "btn btn-secondary ms-2"
        }
      }).then((result) => {
        if (result.isConfirmed) {
          this.submit();
        }
      });
    });
  });
});

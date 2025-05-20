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
  document.querySelectorAll('form[method="delete"]').forEach(form => {
    console.log(form);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      Swal.fire({
        text: this.dataset.message || "Tem certeza que deseja excluir?",
        icon: "warning",
        showCancelButton: true,
        buttonsStyling: false,
        confirmButtonText: "Sim, excluir",
        cancelButtonText: "Cancelar",
        customClass: {
          confirmButton: "btn btn-danger",
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

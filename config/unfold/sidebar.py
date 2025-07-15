from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

SIDEBAR = {
    "SITE_TITLE":     _("Administrador"),
    "SITE_HEADER":    _("Mx Route"),
    "SITE_SUBHEADER": _("Painel de Controle"),
    "SITE_URL":       reverse_lazy("index"),
    "SHOW_LANGUAGES": True,
    "SIDEBAR": {
        "show_search":           True,
        "show_all_applications": False,
        "navigation": [

            {
                "title":       _("Navegação"),
                "icon":        "menu",
                "separator":   False,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Início"),
                        "icon":  "home",
                        "link":  reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("Entregas"),
                        "icon":  "local_shipping",
                        "link":  reverse_lazy("admin:tmsapp_delivery_changelist"),
                    },
                    {
                        "title": _("Clientes"),
                        "icon":  "people",
                        "link":  reverse_lazy("admin:crmapp_customer_changelist"),
                    },
                    {
                        "title": _("Locais da Empresa"),
                        "icon":  "location_on",
                        "link":  reverse_lazy("admin:tmsapp_companylocation_changelist"),
                    },
                ],
            },
            {
                "title":       _("Frota"),
                "icon":        "directions_bus",
                "separator":   True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Motoristas"),
                        "icon":  "person",
                        "link":  reverse_lazy("admin:tmsapp_driver_changelist"),
                    },
                    {
                        "title": _("Veículos"),
                        "icon":  "directions_car",
                        "link":  reverse_lazy("admin:tmsapp_vehicle_changelist"),
                    },
                    {
                        "title": _("Transportadoras"),
                        "icon":  "local_shipping",
                        "link":  reverse_lazy("admin:tmsapp_carrier_changelist"),
                    },
                ],
            },
            {
                "title":       _("Roteirização"),
                "icon":        "map",
                "separator":   True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Planos de Carga"),
                        "icon":  "view_list",
                        "link":  reverse_lazy("admin:tmsapp_loadplan_changelist"),
                    },
                    {
                        "title": _("Rotas"),
                        "icon":  "alt_route",
                        "link":  reverse_lazy("admin:tmsapp_route_changelist"),
                    },
                    {
                        "title": _("Area de Rotas"),
                        "icon":  "map",
                        "link":  reverse_lazy("admin:tmsapp_routearea_changelist"),
                    },
                    {
                        "title": _("Composição de Rotas"),
                        "icon":  "merge_type",
                        "link":  reverse_lazy("admin:tmsapp_routecomposition_changelist"),
                    },
                    {
                        "title": _("Entregas da Composição"),
                        "icon":  "local_shipping",
                        "link":  reverse_lazy("admin:tmsapp_routecompositiondelivery_changelist"),
                    },
                ],
            },
            {
                "title":       _("Usuários & Grupos"),
                "icon":        "people",
                "separator":   True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Usuários"),
                        "icon":  "person",
                        "link":  reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": _("Grupos"),
                        "icon":  "group",
                        "link":  reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": _("Permissões"),
                        "icon":  "security",
                        "link":  reverse_lazy("admin:auth_permission_changelist"),
                    },
                ],
            },
            {
                "title":       _("Alertas & Tarefas"),
                "icon":        "notifications",
                "separator":   True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Alertas"),
                        "icon":  "notifications",
                        "link":  reverse_lazy("admin:djangonotify_notification_changelist"),
                    },
                    {
                        "title": _("Tarefas"),
                        "icon":  "assignment",
                        "link":  reverse_lazy("admin:djangonotify_taskrecord_changelist"),
                    },
                ],
            },
            {
                "title":       _("Auditoria"),
                "icon":        "history",        # ou outro ícone de sua preferência
                "separator":   True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Log de Auditoria"),
                        "icon":  "history_toggle_off",
                        "link":  reverse_lazy("admin:auditlog_logentry_changelist"),
                    },
                ],
            },
        ],
    },
    "LANGUAGES": {
        "navigation": [
            {
                'bidi': False,
                'code': 'pt-br',
                'name': 'Português',
                'name_local': 'Português',
                'name_translated': 'Português',
            },
            {
                'bidi': False,
                'code': 'en',
                'name': 'English',
                'name_local': 'Inglês',
                'name_translated': 'English',
            },
        ],
    },
}

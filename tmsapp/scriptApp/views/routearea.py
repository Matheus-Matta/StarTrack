from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib import messages
from django.db.models import Q
from tmsapp.models import RouteArea, Vehicle
import json

@login_required
def create_routearea(request):
    if request.method == 'POST':
        name = request.POST.get('nomeRota')
        status = request.POST.get('statusRota')  # você pode guardar em outro campo se necessário
        color = request.POST.get('hex_color')

        rota = RouteArea.objects.create(
            name=name,
            hex_color=color,
            created_by=request.user,
        )

        return redirect('tmsapp:scriptapp:route_view', route_id=rota.id)

    return redirect('tmsapp:scriptapp:route')


@login_required
def route_view(request, route_id):
    try:
        rota = RouteArea.objects.get(id=route_id)
    except RouteArea.DoesNotExist:
        messages.error(request, "Rota não encontrada ou pode ter sido removida.")
        return redirect(request.META.get('HTTP_REFERER', 'tmsapp:route'))  # fallback

    outras_rotas = RouteArea.objects.exclude(id=rota.id).exclude(geojson__isnull=True).exclude(geojson="")

    all_vehicles = Vehicle.objects.filter(
        Q(route_area__isnull=True) |  # veículos sem rota
        Q(route_area=rota)            # ou já nesta rota
    ).distinct()

    outras = []
    for r in outras_rotas:
        try:
            outras.append({
                "geojson": json.loads(r.geojson),
                "name": r.name,
                "id": r.id
            })
        except json.JSONDecodeError:
            pass

    return render(request, 'pages/routes/view_routearea.html', {
        "rota": rota,
        "outras": json.dumps(outras),
        "all_vehicles": all_vehicles,
    })



@login_required
def edit_routearea(request, route_id):
    rota = get_object_or_404(RouteArea, id=route_id)

    if request.method == 'POST':
        try:
            # --- campos básicos ---
            rota.name      = request.POST.get('nomeRota')   or None
            rota.status    = request.POST.get('statusRota') or None
            rota.hex_color = request.POST.get('hex_color')  or None
            rota.areatotal = (
                float(request.POST.get('areatotal').replace(',', '.'))
                if request.POST.get('areatotal') else None
            )
            rota.kmtotal   = (
                float(request.POST.get('kmtotal').replace(',', '.'))
                if request.POST.get('kmtotal') else None
            )

            # --- geojson ---
            geojson_raw = request.POST.get('geojson')
            if geojson_raw:
                geojson_obj = json.loads(geojson_raw)
                rota.geojson = json.dumps(geojson_obj)
            else:
                rota.geojson = None

            rota.save()

            # --- agora vincula veículos via FK em vez de M2M ---
            submitted_ids = [int(pk) for pk in request.POST.getlist('vehicles') if pk.isdigit()]
            blocked = []
            allowed = []

            # 1) vincula cada vehicle válido
            for vid in submitted_ids:
                try:
                    v = Vehicle.objects.get(pk=vid)
                except Vehicle.DoesNotExist:
                    continue

                # já pertence a outra rota?
                if v.route_area and v.route_area.pk != rota.pk:
                    blocked.append(str(v))
                else:
                    v.route_area = rota
                    v.save()
                    allowed.append(v.pk)

            # 2) remove o vínculo de quem saiu da lista
            Vehicle.objects.filter(route_area=rota).exclude(pk__in=allowed).update(route_area=None)

            # --- mensagens de feedback ---
            messages.success(request, "Rota atualizada com sucesso.")
            if blocked:
                messages.warning(
                    request,
                    "Os seguintes veículos não foram vinculados pois já estão em outra rota: "
                    + ", ".join(blocked)
                )

            return redirect('tmsapp:scriptapp:route_view', route_id=rota.id)

        except Exception as e:
            messages.error(request, f"Erro ao atualizar rota: {e}")
            return redirect('tmsapp:scriptapp:route_view', route_id=rota.id)

    # GET ou qualquer outro método volta pra listagem
    return redirect('tmsapp:scriptapp:route')

@login_required
def delete_routearea(request, route_id):
    try:
        rota = get_object_or_404(RouteArea, id=route_id)
        rota.delete()
        messages.success(request, "Rota deletada com sucesso.")
        return redirect('tmsapp:scriptapp:route')  # redirecione para sua lista de rotas
    except Exception as e:
        print(f"Erro ao deletar rota: {e}")
        messages.error(request, "Erro ao deletar rota.")
        return redirect('tmsapp:scriptapp:route_view', route_id=route_id)

def list_routearea(request):
    # traz apenas as áreas ativas
    areas_qs = RouteArea.objects.filter(status='active').order_by('-created_at')

    # prepara lista serializável
    areas = []
    for a in areas_qs:
        # tenta carregar geojson se existir
        geojson_data = None
        if a.geojson:
            try:
                geojson_data = json.loads(a.geojson)
            except (TypeError, json.JSONDecodeError):
                geojson_data = None

        areas.append({
            'id': a.id,
            'name': a.name,
            'geojson': json.dumps(geojson_data) if geojson_data is not None else None,
            'color': a.hex_color or '#0074D9',
            'area': round(a.areatotal or 0, 2),
            'km': round(a.kmtotal or 0, 2),
        })

    return render(request, 'pages/routes/list_routearea.html', {
        'areas': areas,
        'areas_json': json.dumps(areas)
    })

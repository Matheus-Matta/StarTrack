import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.apps import apps
from django.db import models
from django.core.exceptions import FieldDoesNotExist , FieldError

@login_required
def djangotables(request):
    # Qual modelo?
    model_name = request.GET.get('model', '').strip()
    if not model_name:
        return JsonResponse({'error': 'Parâmetro model não encontrado.'}, status=400)

    # Encontra classe
    model_class = next(
        (m for m in apps.get_models() if m.__name__.lower() == model_name.lower()),
        None
    )
    if model_class is None:
        return JsonResponse({'error': f'Modelo "{model_name}" não encontrado.'}, status=404)

    try:
        qs = model_class.objects.filter(is_active=True)
    except FieldError:
        qs = model_class.objects.all()


    # extrai e parseia o JSON de “filters”
    raw = request.GET.get('filters','').strip()
    filtro_dict = {}
    if raw:
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                filtro_dict = loaded
        except json.JSONDecodeError:
            filtro_dict = {}

    # itera sobre cada filtro
    for field, raw_val in filtro_dict.items():
        # descarta valores vazios
        if raw_val is None or (isinstance(raw_val,str) and not raw_val.strip()):
            continue

        # decide “valor” e “lookup” padrão
        if isinstance(raw_val, dict) and 'value' in raw_val:
            val    = raw_val['value']
            method = raw_val.get('method','icontains')
        else:
            val    = raw_val
            method = 'icontains'

        # verifica se o campo existe no modelo
        try:
            model_class._meta.get_field(field)
        except FieldDoesNotExist:
            continue

        lookup = f"{field}__{method}"
        qs = qs.filter(**{lookup: val})


    # Filtro search
    search = request.GET.get('search', '').strip()
    search_fields = [f.strip() for f in request.GET.get('search_fields','').split(',') if f.strip()]
    if search and search_fields:
        q = Q()
        for fld in search_fields:
            try:
                fobj = model_class._meta.get_field(fld)
            except FieldDoesNotExist:
                continue
            if fobj.is_relation:
                continue
            if isinstance(fobj, (models.CharField, models.TextField, models.EmailField)):
                q |= Q(**{f"{fld}__icontains": search})
        qs = qs.filter(q)

    # Ordenação com fallback para @property
    order_by  = request.GET.get('order_by', 'id').strip()
    direction = request.GET.get('order_dir', 'asc')
    meta_fields = {f.name for f in model_class._meta.get_fields()}
    reverse = (direction == 'desc')

    if order_by in meta_fields:
        # Campo de BD
        sort_expr = f"-{order_by}" if reverse else order_by
        try:
            qs = qs.order_by(sort_expr)
            object_list = qs
        except FieldError:
            object_list = list(qs)
    else:
        # Propriedade no Python, garantido None no final
        all_objs = list(qs)
        def sort_key(obj):
            val = getattr(obj, order_by, None)
            # (True, ...) se for None — assim None sempre fica por último
            return (val is None, val)
        all_objs.sort(key=sort_key, reverse=reverse)
        object_list = all_objs

    # Paginação
    page_num  = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('size', 10))
    paginator = Paginator(object_list, page_size)
    page = paginator.get_page(page_num)

    # Campos de saída
    raw_fields = request.GET.get('fields', '').strip()
    if raw_fields:
        fields = [f.strip() for f in raw_fields.split(',') if f.strip()]
    else:
        fields = [f.name for f in model_class._meta.fields]
        fields += [f.name for f in model_class._meta.many_to_many]
        fields += [n for n,a in vars(model_class).items() if isinstance(a, property)]

    # Monta o JSON
    results = []
    for obj in page.object_list:
        row = {}
        for f in fields:
            try:
                field_obj = model_class._meta.get_field(f)
            except FieldDoesNotExist:
                field_obj = None
            val = getattr(obj, f, None)

            # desserializa geojson salvo como string
            if f == 'geojson' and isinstance(val, str):
                try:
                    row[f] = json.loads(val)
                except json.JSONDecodeError:
                    row[f] = None
                continue

            if field_obj and getattr(field_obj, 'many_to_many', False):
                row[f] = [{'id': r.pk, 'label': str(r)} for r in val.all()]
            elif field_obj and getattr(field_obj, 'one_to_many', False):
                row[f] = [{'id': r.pk, 'label': str(r)} for r in val.all()]
            elif field_obj and field_obj.is_relation:
                row[f] = {'id': val.pk, 'label': str(val)} if val is not None else None
            else:
                row[f] = '...' if val in (None, '') else val

        results.append(row)

    return JsonResponse({
        'results':     results, # resultados
        'page':        page.number, # página atual
        'total_pages': paginator.num_pages, #
        'total_count': paginator.count, # 
        'page_size':   page_size, # 
    })
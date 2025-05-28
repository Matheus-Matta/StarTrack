import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, CharField, TextField, EmailField
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


    for field, raw_val in filtro_dict.items():
        # descarta vazio
        if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
            continue

        # extrai valor e método
        if isinstance(raw_val, dict) and 'value' in raw_val:
            val    = raw_val['value']
            method = raw_val.get('method','icontains')
        else:
            val    = raw_val
            method = 'icontains'

        # —— se for property em Python, filtra na lista —— 
        if hasattr(model_class, field) and isinstance(getattr(model_class, field), property):
            # converte qs em lista só na primeira iteração
            objs = list(qs) if not isinstance(qs, list) else qs
            if method == 'exact':
                qs = [o for o in objs if getattr(o, field) == val]
            else:
                qs = [o for o in objs if val.lower() in str(getattr(o, field, '')).lower()]
            continue

        # —— senão tenta filtrar no banco —— 
        try:
            model_class._meta.get_field(field)
        except FieldDoesNotExist:
            continue

        lookup = f"{field}__{method}"
        qs = qs.filter(**{lookup: val})


    search   = request.GET.get('search','').strip()
    search_fields   = [f.strip() for f in request.GET.get('search_fields','').split(',') if f.strip()]

    qs = apply_search_filter(qs, model_class, search, search_fields)

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


def apply_search_filter(qs, model_class, search, search_fields):
    """
    Busca em três etapas:
      1) campos diretos (__icontains)
      2) propriedades Python
      3) relações FK/M2M (prefere related.full_name, senão primeiro texto)
    """
    term = search.strip()
    if not term or not search_fields:
        return qs

    # ─── 1) campos diretos ─────────────────────────
    q1 = Q()
    for fld in search_fields:
        # ignora “dotted” e relações aqui
        if "__" in fld:
            continue
        try:
            fobj = model_class._meta.get_field(fld)
        except FieldDoesNotExist:
            continue
        if isinstance(fobj, (CharField, TextField, EmailField)):
            q1 |= Q(**{f"{fld}__icontains": term})
    qs1 = qs.filter(q1).distinct() if q1 else qs.none()
    if qs1.exists():
        return qs1

    # ─── 2) propriedades Python ─────────────────────
    prop_fields = [
        fld for fld in search_fields
        if isinstance(getattr(model_class, fld, None), property)
    ]
    if prop_fields:
        matches = []
        for obj in qs:
            for prop in prop_fields:
                val = getattr(obj, prop, "")
                if isinstance(val, str) and term.lower() in val.lower():
                    matches.append(obj.pk)
                    break
        if matches:
            return model_class.objects.filter(pk__in=matches)

    # ─── 3) relações FK/M2M ─────────────────────────
    q3 = Q()
    for fld in search_fields:
        # pula dotteds (já buscados na 1) e propriedades
        if "__" in fld or fld in prop_fields:
            continue
        try:
            fobj = model_class._meta.get_field(fld)
        except FieldDoesNotExist:
            continue

        if fobj.is_relation:
            rel = fobj.related_model
            # prefere full_name
            if 'full_name' in {f.name for f in rel._meta.fields}:
                q3 |= Q(**{f"{fld}__full_name__icontains": term})
            else:
                # fallback para primeiro campo de texto da relação
                rel_text = next(
                    (f.name for f in rel._meta.fields
                     if isinstance(f, (CharField, TextField, EmailField))),
                    None
                )
                if rel_text:
                    q3 |= Q(**{f"{fld}__{rel_text}__icontains": term})

    qs3 = qs.filter(q3).distinct() if q3 else qs.none()
    return qs3
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.apps import apps
from django.db import models
from django.core.exceptions import FieldDoesNotExist, FieldError

@login_required
def djangoselect(request):
    try:
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

        # filters
        raw = request.GET.get('filters', '').strip()
        if raw:
            try:
                filtro_dict = json.loads(raw)
            except json.JSONDecodeError:
                filtro_dict = {}
            for field, raw_val in filtro_dict.items():
                if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
                    continue
                if isinstance(raw_val, dict) and 'value' in raw_val:
                    val = raw_val['value']
                    method = raw_val.get('method', 'icontains')
                else:
                    val = raw_val
                    method = 'icontains'
                try:
                    model_class._meta.get_field(field)
                except FieldDoesNotExist:
                    continue
                qs = qs.filter(**{f"{field}__{method}": val})

        # search
        search = request.GET.get('search', '').strip()
        search_fields = [f.strip() for f in request.GET.get('fields','').split(',') if f.strip()]
        if search and search_fields:
            q = Q()
            for fld in search_fields:
                try:
                    fobj = model_class._meta.get_field(fld)
                except FieldDoesNotExist:
                    continue
                if not fobj.is_relation and isinstance(fobj, (models.CharField, models.TextField, models.EmailField)):
                    q |= Q(**{f"{fld}__icontains": search})
            qs = qs.filter(q)

        # ordering
        order_by  = request.GET.get('order_by', 'id').strip()
        direction = request.GET.get('order_dir', 'asc')
        meta_fields = {f.name for f in model_class._meta.get_fields()}
        reverse = (direction == 'desc')
        if order_by in meta_fields:
            sort_expr = f"-{order_by}" if reverse else order_by
            try:
                qs = qs.order_by(sort_expr)
                object_list = qs
            except FieldError:
                object_list = list(qs)
        else:
            all_objs = list(qs)
            all_objs.sort(key=lambda o: (getattr(o, order_by, None) is None, getattr(o, order_by, None)), reverse=reverse)
            object_list = all_objs

        # 5) paginação
        page_num  = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('size', 10))
        paginator = Paginator(object_list, page_size)
        page = paginator.get_page(page_num)

        # 6) campos retornados
        raw_fields = request.GET.get('fields', '').strip()
        if raw_fields:
            fields = [f.strip() for f in raw_fields.split(',') if f.strip()]
        else:
            fields = [f.name for f in model_class._meta.fields]

        # 7) monta JSON
        results = []
        for obj in page.object_list:
            row = {}
            for f in fields:
                val = getattr(obj, f, None)
                row[f] = '...' if val in (None, '') else val
            results.append(row)

        return JsonResponse({
            'results':     results,
            'page':        page.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'page_size':   page_size,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


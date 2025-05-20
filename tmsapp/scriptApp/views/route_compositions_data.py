# views.py
from django.core.paginator import Paginator, EmptyPage
from django.template.loader import render_to_string
from django.http import JsonResponse
from tmsapp.models import RouteComposition
from django.db.models import Q

def route_compositions_data(request):
    page_number = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('size', 5))
    search_value = request.GET.get('search', '').strip()
    order_by = request.GET.get('order_by', 'id')
    order_dir = request.GET.get('order_dir', 'desc')


    compositions = RouteComposition.objects.all()

    if search_value:
        compositions = compositions.filter(
            Q(name__icontains=search_value) |
            Q(type__icontains=search_value) |
            Q(created_by__username__icontains=search_value)
        )

    # Aqui sim faz a ordenação final
    if order_by == 'created_by':
        order_by = 'created_by__username'

    if order_dir == 'desc':
        order_by = f'-{order_by}'

    compositions = compositions.order_by(order_by)

    paginator = Paginator(compositions, page_size)

    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'compositions': page_obj,
    }

    table_html = render_to_string('components/tables/compositions_table_body.html', context, request=request)
    pagination_html = render_to_string('components/tables/compositions_pagination.html', context, request=request)

    return JsonResponse({
        'table_html': table_html,
        'pagination_html': pagination_html,
        'info_text': f"{page_obj.start_index()}-{page_obj.end_index()} de {paginator.count}"
    })
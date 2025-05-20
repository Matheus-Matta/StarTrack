from collections import defaultdict
from datetime import datetime
import os
import random
import time

import pandas as pd
from asgiref.sync import async_to_sync
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from channels.layers import get_channel_layer
from auditlog.context import set_actor

from tmsapp.models import Delivery, Route, RouteComposition, RouteDelivery
from tmsapp.action import (
    get_geojson_by_ors,
    read_file_to_dataframe,
    geocode_endereco,
)


User = get_user_model()


def generate_random_color() -> str:
    """Gera uma cor hexadecimal aleatória."""
    return '#' + ''.join(random.choices('0123456789ABCDEF', k=6))


def sanitize(value) -> str:
    """Converte valores NaN ou vazios para string vazia, caso contrário retorna string limpa."""
    if pd.isna(value) or str(value).strip().lower() == 'nan':
        return ''
    return str(value).strip()


def send_task_update(task_id: str, message: str, percent: int, composition_id=None):
    """Envia atualizarão de progresso via WebSocket."""
    channel_layer = get_channel_layer()
    event = {'type': 'task_progress_update', 'progress': message, 'percent': percent}
    if composition_id is not None:
        event['composition_id'] = composition_id

    async_to_sync(channel_layer.group_send)(
        f'task_progress_{task_id}',
        event
    )


def load_deliveries(df: pd.DataFrame, user, task_id: str) -> list[Delivery]:
    """
    Constrói objetos Delivery a partir do DataFrame.
    Retorna uma lista de instâncias não salvas.
    """
    galpao = [-42.9455242, -22.7920595]

    total = len(df)
    deliveries = []

    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        # Atualiza progresso: mensagem e percentual
        percent = 6 + int(idx / total * 34)  # de 6% a 40%
        send_task_update(task_id, f"Importando pedidos: {idx}", percent)

        order_number = sanitize(row.get("numerosaida"))
        if not order_number:
            continue

        address = sanitize(row.get('enderecoentrega'))
        number_row = sanitize(row.get('numeroentrega'))
        postal_row = sanitize(row.get('cepentrega'))
        neighborhood = sanitize(row.get('bairroentrega'))
        city = sanitize(row.get('cidadeentrega')).split('-')[0].strip()
        phone_row = sanitize(row.get('telefoneentrega'))
        state = 'RJ'

        number = str(int(float(number_row))) if number_row else ''
        postal = str(int(float(postal_row))) if postal_row else ''
        phone = str(int(float(phone_row)))  if phone_row  else ''

        latitude, longitude = geocode_endereco(
            address, number, postal, neighborhood, city, state
        )

        deliveries.append(Delivery(
            customer_name = sanitize(row.get('nomecliente')),
            order_number = str(int(float(order_number))),
            route_name = sanitize(row.get('nomerota')),
            street = sanitize(row.get('ruaentrega')),
            number = number,
            neighborhood = neighborhood,
            city = city,
            state = state,
            phone = phone,
            observation = sanitize(row.get('observacao')),
            address = address,
            cpf = sanitize(row.get('doctocliente')),
            reference = sanitize(row.get('pontoreferenciaentrega')),
            postal_code = postal,
            latitude = latitude,
            longitude = longitude,
            created_by = user
        ))

    return deliveries


def create_unique_route(deliveries, composition, task_id, galpao_coords):
    """Cria uma rota única otimizada e associa ao composition."""
    send_task_update(task_id, 'Otimizando rota única...', 50)
    coords = [{'long': galpao_coords[0], 'lat': galpao_coords[1], 'order_number': 'SAIDA'}] + [
        {'long': float(d.longitude), 'lat': float(d.latitude), 'order_number': d.order_number}
        for d in deliveries if d.latitude and d.longitude
    ]

    geojson, duration, ordered = get_geojson_by_ors(coords)

    route = Route.objects.create(
        name="Rota única",
        color=generate_random_color(),
        created_by=composition.created_by,
        stops=len(deliveries),
        distance_km=round(duration / 1000, 2),
        time_min=round(duration / 60, 1),
        geojson=geojson,
        points=coords
    )

    mapping = {d.order_number: d for d in deliveries}
    for pos, stop in enumerate(ordered):
        delivery = mapping.get(stop['order_number'])
        if delivery:
            RouteDelivery.objects.get_or_create(route=route, delivery=delivery, position=pos)

    composition.routes.add(route)
    send_task_update(task_id, 'Finalizando rota única...', 92)


def create_city_routes(deliveries, composition, task_id, galpao_coords):
    """Cria várias rotas, uma por cidade/grupo, e associa ao composition."""
    send_task_update(task_id, 'Agrupando entregas por cidade...', 50)

    # Agrupa por nome de rota, exceto marketplace
    groups = defaultdict(list)
    extras = []
    for d in deliveries:
        key = d.route_name.lower()
        if key == 'marketplace':
            extras.append(d)
        else:
            groups[d.route_name].append(d)

    # Adiciona extras a grupos por cidade
    for d in extras:
        matched = False
        for k in groups:
            if d.city.lower() in k.lower():
                groups[k].append(d)
                matched = True
                break
        if not matched:
            groups[d.city].append(d)

    total = len(groups)
    for idx, (route_name, group) in enumerate(sorted(groups.items())):
        percent = 50 + int(40 * ((idx + 1) / total))
        send_task_update(task_id, f'Otimização: {route_name}', percent)

        coords = [{'long': galpao_coords[0], 'lat': galpao_coords[1], 'order_number': 'SAIDA'}] + [
            {'long': float(d.longitude), 'lat': float(d.latitude), 'order_number': d.order_number}
            for d in group if d.latitude and d.longitude
        ]

        geojson, duration, ordered = get_geojson_by_ors(coords)
        route = Route.objects.create(
            name=route_name,
            color=generate_random_color(),
            created_by=composition.created_by,
            stops=len(group),
            distance_km=round(duration / 1000, 2),
            time_min=round(duration / 60, 1),
            geojson=geojson,
            points=coords
        )

        mapping = {d.order_number: d for d in group}
        for pos, stop in enumerate(ordered):
            delivery = mapping.get(stop['order_number'])
            if delivery:
                RouteDelivery.objects.get_or_create(route=route, delivery=delivery, position=pos)

        composition.routes.add(route)

    send_task_update(task_id, 'Finalizando rotas por cidade...', 92)


@shared_task(bind=True)
def create_routes_task(self, user_id, sp_router, temp_file_path):
    """
    Task principal que:
    1. Lê planilha e cria entregas
    2. Cria RouteComposition
    3. Otimiza e salva rotas (única ou por cidade)
    4. Envia updates via WebSocket
    """
    user = User.objects.get(id=user_id)
    set_actor(user)
    task_id = self.request.id
    galpao_coords = [-42.9455242, -22.7920595]

    try:
        send_task_update(task_id, 'Lendo planilha...', 5)
        df = read_file_to_dataframe(temp_file_path)

        send_task_update(task_id, 'Importando entregas...', 6)
        with transaction.atomic():
            deliveries = load_deliveries(df, user, task_id)
            Delivery.objects.bulk_create(deliveries, batch_size=1000)

            # Recupera instâncias recém-criadas
            recent = Delivery.objects.filter(created_by=user).order_by('-created_at')[:len(deliveries)]

            send_task_update(task_id, 'Criando composição...', 41)
            composition = RouteComposition.objects.create(
                name=f"Comp. {datetime.now():%d-%m-%Y %H:%M}",
                type=sp_router,
                created_by=user
            )

            # Gera rotas conforme tipo
            if sp_router == 'unique':
                create_unique_route(recent, composition, task_id, galpao_coords)
            else:
                create_city_routes(recent, composition, task_id, galpao_coords)

        send_task_update(task_id, 'Finalizado', 100, composition.id)
        return {'status': 'Concluído', 'composition_id': composition.id}

    except Exception as e:
        send_task_update(task_id, f"Erro: {e}", 0)
        raise
    finally:
        # Remove arquivo temporário
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

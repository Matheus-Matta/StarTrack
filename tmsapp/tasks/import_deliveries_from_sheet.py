# tmsapp/deliveryApp/tasks.py

import os
import pandas as pd
import time 
import re
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction

from crmapp.models import Customer
from tmsapp.deliveryApp.models import Delivery
from djangonotify.models import TaskRecord
from tmsapp.scriptApp.action import read_file_to_dataframe, geocode_endereco
from djangonotify.utils import send_progress, send_notification

User = get_user_model()


def sanitize(value) -> str:
    """
    Converte NaN ou vazios para string vazia,
    floats inteiros para inteiros, e sempre retorna str.
    """
    if pd.isna(value) or str(value).strip().lower() == 'nan':
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def parse_decimal(value_str: str, field_name: str = "") -> Decimal:
    """
    Recebe uma string tipo "1.234,56" ou "430,00" e devolve Decimal("1234.56") ou Decimal("430.00").
    Se não conseguir parsear, lança ValueError com mensagem clara.
    """
    s = value_str.strip()
    if not s:
        return Decimal('0')
    # remove separador de milhares e normaliza vírgula decimal
    s = re.sub(r'\.(?=\d{3}(?:[,\s]|$))', '', s)
    s = s.replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f'O valor “{value_str}” não é um decimal válido para o campo {field_name}.')

def geocode_deliveries_if_needed(deliveries: list, existing_map: dict) -> list:
    """
    Executa geocodificação somente se:
    - Latitude/longitude estiverem vazias
    - Algum campo de endereço tiver sido alterado (comparado com o existente)
    """
    for d in deliveries:
        should_geocode = False
        if not (d.latitude and d.longitude):
            should_geocode = True
        else:
            old = existing_map.get(d.order_number)
            if old:
                for field in ('street', 'number', 'postal_code', 'neighborhood', 'city', 'state'):
                    if getattr(old, field) != getattr(d, field):
                        should_geocode = True
                        break

        if should_geocode:
            lat, lon = geocode_endereco(
                d.street,
                d.number,
                d.postal_code,
                d.neighborhood,
                d.city,
                d.state
            )
            if lat and lon:
                d.latitude = lat
                d.longitude = lon
    return deliveries

@shared_task(bind=True)
def import_deliveries_from_sheet(self, user_id: int, tkrecord_id: int, temp_file_path: str):
    try:
        # 1) vincula o TaskRecord à nova task_id
        task_id = self.request.id
        tk = TaskRecord.objects.get(pk=tkrecord_id)
        tk.task_id = task_id
        tk.save(update_fields=['task_id'])

        time.sleep(5)
        send_progress(task_id, user_id, "Importação iniciada", 0, status='started')
        user = User.objects.get(pk=user_id)
        df = read_file_to_dataframe(temp_file_path)
        total = len(df)

        # 2) coleta e sanitiza todas as linhas
        rows, cpfs = [], set()
        for i, row in enumerate(df.itertuples(index=False), start=1):
            vol_str   = sanitize(getattr(row, 'cubagemm3', ''))
            wgt_str   = sanitize(getattr(row, 'peso', ''))
            price_str = sanitize(getattr(row, 'valtotnota', ''))
            data = {
                'cpf': sanitize(getattr(row, 'doctocliente', '')),
                'full_name': sanitize(getattr(row, 'nomecliente', '')),
                'email': sanitize(getattr(row, 'emailcliente', '')),
                'phone': sanitize(getattr(row, 'telefoneentrega', '')),
                'order_number': sanitize(getattr(row, 'numerosaida', '')),
                'filial': sanitize(getattr(row, 'idfilial', '')),
                'street': sanitize(getattr(row, 'enderecoentrega', '')),
                'number': sanitize(getattr(row, 'numeroentrega', '')),
                'neighborhood': sanitize(getattr(row, 'bairroentrega', '')),
                'city_full': sanitize(getattr(row, 'cidadeentrega', '')),
                'state': sanitize(getattr(row, 'estadoentrega', 'RJ')),
                'postal_code': sanitize(getattr(row, 'cepentrega', '')),
                'observation': sanitize(getattr(row, 'observacao', '')),
                'reference': sanitize(getattr(row, 'pontoreferenciaentrega', '')),
                'total_volume_m3':   parse_decimal(vol_str,   'total_volume_m3'),
                'total_weight_kg':   parse_decimal(wgt_str,   'total_weight_kg'),
                'price':             parse_decimal(price_str, 'price'),
            }
            if data['cpf']:
                cpfs.add(data['cpf'])
            rows.append(data)

            pct = int(i / total * 10)
            send_progress(task_id, user_id, f"Coletando dados: {i}/{total}", pct, status='progress')

        with transaction.atomic():
            # 3) CARREGA e BULK-CREATE de Customers
            existing_customers = Customer.objects.filter(cpf__in=cpfs)
            customer_map = {c.cpf: c for c in existing_customers}

            to_create_cust = [
                Customer(
                    cpf=cpf,
                    full_name=next(r for r in rows if r['cpf'] == cpf)['full_name'] or '',
                    email=next(r for r in rows if r['cpf'] == cpf)['email'] or None,
                    phone=next(r for r in rows if r['cpf'] == cpf)['phone'] or None,
                )
                for cpf in cpfs - customer_map.keys()
            ]
            Customer.objects.bulk_create(to_create_cust, batch_size=500)
            for c in Customer.objects.filter(cpf__in=[c.cpf for c in to_create_cust]):
                customer_map[c.cpf] = c

            send_progress(task_id, user_id, f"{len(to_create_cust)} clientes criados", 15, status='progress')

            # 4) BULK-UPDATE de Customers existentes
            to_update_cust = []
            for data in rows:
                cpf = data['cpf']
                cust = customer_map.get(cpf)
                if not cust:
                    continue
                changed = False
                if data['full_name'] and cust.full_name != data['full_name']:
                    cust.full_name = data['full_name']; changed = True
                if data['email'] and cust.email != data['email']:
                    cust.email = data['email']; changed = True
                if data['phone'] and cust.phone != data['phone']:
                    cust.phone = data['phone']; changed = True
                if changed:
                    to_update_cust.append(cust)

            if to_update_cust:
                Customer.objects.bulk_update(to_update_cust, ['full_name','email','phone'], batch_size=500)
            send_progress(task_id, user_id, f"{len(to_update_cust)} clientes atualizados", 25, status='progress')

            # 5) PREPARA bulk_create / bulk_update de Deliveries
            all_orders = {d['order_number'] for d in rows if d['order_number']}
            existing_delivs = Delivery.objects.filter(order_number__in=all_orders)
            delivery_map = {d.order_number: d for d in existing_delivs}

            to_create_del, to_update_del = [], []

            for idx, data in enumerate(rows, start=1):
                order = data['order_number']
                if not order:
                    continue

                city = data['city_full'].split('-')[0].strip() if data['city_full'] else ''

                if order in delivery_map:
                    # já existe → atualiza
                    d = delivery_map[order]
                    d.customer     = customer_map.get(data['cpf'])
                    d.filial       = data['filial']
                    d.street       = data['street']
                    d.number       = data['number']
                    d.neighborhood = data['neighborhood']
                    d.city         = city
                    d.state        = data['state']
                    d.postal_code  = data['postal_code']
                    d.observation  = data['observation']
                    d.reference    = data['reference']
                    d.total_volume_m3 = data['total_volume_m3']
                    d.total_weight_kg = data['total_weight_kg'] 
                    d.price = data['price']                   
                    to_update_del.append(d)
                else:
                    # novo delivery
                    to_create_del.append(Delivery(
                        customer     = customer_map.get(data['cpf']),
                        filial       = data['filial'],
                        order_number = order,
                        street       = data['street'],
                        number       = data['number'],
                        neighborhood = data['neighborhood'],
                        city         = city,
                        state        = data['state'],
                        postal_code  = data['postal_code'],
                        observation  = data['observation'],
                        reference    = data['reference'],
                        total_volume_m3 = data['total_volume_m3'],
                        total_weight_kg = data['total_weight_kg'],
                        price        = data['price'],
                        created_by   = user
                    ))

                pct_phase = int(idx / total * 70)
                pct = 25 + pct_phase
                if pct > 95: 
                    pct = 95
                if idx % 10 == 0:
                    send_progress(task_id, user_id, f"Preparando entregas: {idx}", pct, status='progress')

                # junta todas para verificar se precisa geocodificar
                to_geocode = to_create_del + to_update_del

                # passa para função condicional
                geocode_deliveries_if_needed(to_geocode, delivery_map)

                # salva os updates
            if to_update_del:
                Delivery.objects.bulk_update(
                    to_update_del,
                    [
                        'customer', 'street', 'number', 'neighborhood', 'city', 'state',
                        'postal_code', 'observation', 'reference', 'filial',
                        'latitude', 'longitude', 'total_volume_m3', 'total_weight_kg',
                        'price'
                    ],
                    batch_size=500
                )

                # salva os novos
            if to_create_del:
                Delivery.objects.bulk_create(to_create_del, batch_size=500)

            send_progress(
                task_id, user_id,
                f"{len(to_create_del)} criados, {len(to_update_del)} atualizados",
                100,
                status='success',
                extra={
                    'deliveries_created': len(to_create_del),
                    'deliveries_updated': len(to_update_del),
                }
            )

            # 6) envia notificação final
            send_notification(
                user_id,
                'Importação de entregas concluída',
                f"{len(to_create_del)} novas entregas criadas e {len(to_update_del)} atualizadas.",
                level='success'
            )

        # 7) limpa o arquivo
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        return {
            'status': 'success',
            'created_customers': len(to_create_cust),
            'updated_customers': len(to_update_cust),
            'deliveries_created': len(to_create_del),
            'deliveries_updated': len(to_update_del),
        }
    except Exception as e:
        send_notification(user_id, "Importação de entregas falhou", str(e), level='danger')
        send_progress(task_id, user_id, "Script personalizado falhou", 100, status='failure')
        return {
            "status": "error",
            "error": str(e)
        }
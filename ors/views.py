from django.shortcuts import render, redirect
import pandas as pd
import openrouteservice
import json
from openrouteservice.optimization import Vehicle
import requests
from django.contrib.auth.decorators import login_required
from .models import Rota as RotaModel
from .models import ComposicaoRota
from django.shortcuts import get_object_or_404
from django.contrib import messages
from collections import defaultdict
from datetime import datetime
import random
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date


ORS_KEY = '5b3ce3597851110001cf624857ca3dbdb76747aba863b8733dacd9ef'


def gerar_cor_hex():
    return '#' + ''.join([random.choice('0123456789ABCDEF'[:11]) for _ in range(6)])

@login_required
def rota_view(request):
    if request.method == 'POST':
        try:
            arquivo = request.FILES['planilha']
            df = pd.read_excel(arquivo) if arquivo.name.endswith('.xlsx') else pd.read_csv(arquivo)

            if 'Latitude' not in df.columns or 'Longitude' not in df.columns:
                messages.error(request, 'Planilha inválida')
                return redirect('index')

            if abs(df['Latitude'].max()) > 1000:
                df['Latitude'] = df['Latitude'] / 1_000_000
                df['Longitude'] = df['Longitude'] / 1_000_000

            galpao_coord = [-42.9455242, -22.7920595]
            headers = {
                'Authorization': ORS_KEY,
                'Content-Type': 'application/json'
            }

            rotas_por_cidade = defaultdict(list)
            for _, row in df.iterrows():
                cidade = row['Município']
                rotas_por_cidade[cidade].append(row)

            nome_composicao = f"Composição de Rota - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            composicao = ComposicaoRota.objects.create(nome=nome_composicao)
            rotas_salvas = []

            for cidade, pedidos in rotas_por_cidade.items():
                entregas = [{
                    'ordem': 1,
                    'numPedido': 'SAIDA',
                    'endereco': 'Galpão Maxxx Móveis',
                    'lat': galpao_coord[1],
                    'long': galpao_coord[0]
                }]
                coordenadas = [galpao_coord]
                jobs = []

                for i, row in enumerate(pedidos):
                    coord = [row['Longitude'], row['Latitude']]
                    jobs.append({"id": i + 1, "location": coord})
                    coordenadas.append(coord)

                payload = {
                    "jobs": jobs,
                    "vehicles": [{"id": 1, "profile": "driving-hgv", "start": galpao_coord}]
                }

                response = requests.post('https://api.openrouteservice.org/optimization', headers=headers, data=json.dumps(payload))
                data = response.json()

                coordenadas_ordenadas = [galpao_coord]
                for step in data['routes'][0]['steps']:
                    if step['type'] != 'job':
                        continue
                    job_id = step['id']
                    coord = step['location']
                    coordenadas_ordenadas.append(coord)
                    idx = job_id - 1
                    linha = pedidos[job_id - 1]
                    endereco = f"{linha['Nome do cliente']} - {linha['Rua']}, {linha.get('Número', '')}, {linha['Bairro']}, {linha['Município']} - {linha['Estado']}"
                    entregas.append({
                        'ordem': len(entregas) + 1,
                        'numPedido': int(linha.get('Número Pedido') or 0),
                        'endereco': endereco,
                        'lat': coord[1],
                        'long': coord[0]
                    })

                response_rota = requests.post(
                    "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
                    headers=headers,
                    json={"coordinates": coordenadas_ordenadas}
                )
                rota_geojson = response_rota.json()
                pontos = [[e['long'], e['lat']] for e in entregas]

                # --- Salvar rota por cidade no banco ---
                nova_rota = RotaModel.objects.create(
                    cor=gerar_cor_hex(),
                    paradas=len(entregas) - 1,
                    distancia_km=round(data['routes'][0]['duration'] / 1000, 2),
                    tempo_min=round(data['routes'][0]['duration'] / 60, 1),
                    geojson=rota_geojson,
                    pontos=pontos,
                    entregas=entregas
                )
                nova_rota.nome = f'Rota para {cidade}'
                nova_rota.save()
                rotas_salvas.append(nova_rota)
                
            # Adiciona as rotas criadas à composição
            composicao.rotas.set(rotas_salvas)
            composicao.save()
            messages.success(request, 'Rotas calculadas com sucesso!')
            return redirect('visualizar_rota', composicao_id=composicao.id)

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Erro ao calcular rotas: {e}")
            return redirect('index')

    return redirect('index')

@login_required
def visualizar_composicao_view(request, composicao_id):
    composicao = get_object_or_404(ComposicaoRota, id=composicao_id)
    rotas = composicao.rotas.all()

    rotas_data = []
    for rota in rotas:
        rotas_data.append({
            'cor': rota.cor,
            'rota': json.dumps(rota.geojson),  # Envia como JSON para o template
            'ordem': rota.entregas,         # Lista de dicionários com cliente, numPedido, endereço, lat, long
            'rota_nome': rota.nome,
            'data': rota.data_criacao.strftime('%Y-%m-%d %H:%M:%S'),
        })

    context = {
        'composicao_nome': composicao.nome,
        'data': composicao.data_criacao,
        'rotas': json.dumps(rotas_data),
        'rotas_data': rotas_data 
    }

    return render(request, 'map.html', context)
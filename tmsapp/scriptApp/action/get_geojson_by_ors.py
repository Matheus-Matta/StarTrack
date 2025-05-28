import json
import requests
from typing import List, Dict, Optional, Tuple, Any


def get_geojson_by_ors(
    coordinates: List[Dict[str, Any]], 
    departure_location: Optional[Any] = None
) -> Tuple[Dict, int, int, List[Dict]]:
    """
    Otimiza rota usando VROOM e gera GeoJSON com ORS
    
    Args:
        coordinates: Lista de coordenadas [{'lat': x, 'long': y, 'order_number': z}, ...]
        departure_location: CompanyLocation de partida com latitude/longitude (opcional)
    
    Returns:
        Tuple contendo: (geojson, duration, distance, delivery_ordered)
    
    Raises:
        Exception: Se houver erro nas chamadas VROOM ou ORS
        KeyError: Se a resposta VROOM não contiver 'routes'
    """
    
    # Validação de entrada
    if not coordinates:
        raise ValueError("Lista de coordenadas não pode estar vazia")
    
    # Define ponto de partida
    if (departure_location and 
        hasattr(departure_location, 'latitude') and 
        hasattr(departure_location, 'longitude') and
        departure_location.latitude and 
        departure_location.longitude):
        start_coord = [float(departure_location.longitude), float(departure_location.latitude)]
    else:
        # Usa primeira coordenada como padrão
        start_coord = [float(coordinates[0]['long']), float(coordinates[0]['lat'])]
    
    # Prepara jobs para VROOM
    jobs = []
    for idx, coord_info in enumerate(coordinates):
        coord = [float(coord_info['long']), float(coord_info['lat'])]
        jobs.append({
            "id": idx + 1,
            "location": coord,
            "description": str(coord_info['order_number'])
        })

    # Payload para VROOM
    payload = {
        "jobs": jobs,
        "vehicles": [
            {
                "id": 1,
                "start": start_coord,
                "profile": "driving-car"
            }
        ]
    }

    try:
        # Chamada ao VROOM
        vroom_response = requests.post(
            "https://vroom.starseguro.com.br/", 
            json=payload,
            timeout=30
        )
        vroom_response.raise_for_status()
        
    except requests.RequestException as e:
        raise Exception(f"Erro na requisição VROOM: {str(e)}")

    vroom_data = vroom_response.json()
    
    # Validação da resposta VROOM
    if "routes" not in vroom_data or not vroom_data["routes"]:
        raise KeyError(f"Resposta VROOM inválida: 'routes' ausente\n{json.dumps(vroom_data, indent=2)}")

    route = vroom_data["routes"][0]
    coordenadas_ordenadas = [start_coord]
    delivery_ordered = []

    # Reorganiza entregas conforme otimização VROOM
    for step in route["steps"]:
        if step["type"] != "job":
            continue
            
        job = next((j for j in jobs if j["id"] == step["id"]), None)
        if job:
            coord = job["location"]
            coordenadas_ordenadas.append(coord)
            delivery_ordered.append({
                "order_number": job["description"],
                "lat": coord[1],
                "long": coord[0]
            })

    # Payload para ORS
    geojson_payload = {"coordinates": coordenadas_ordenadas}
    
    try:
        # Chamada ao ORS para GeoJSON
        ors_response = requests.post(
            "https://ors.starseguro.com.br/ors/v2/directions/driving-car/geojson",
            headers={"Content-Type": "application/json"},
            json=geojson_payload,
            timeout=30
        )
        ors_response.raise_for_status()
        
    except requests.RequestException as e:
        raise Exception(f"Erro na requisição ORS: {str(e)}")

    geojson = ors_response.json()
    
    feat = geojson["features"][0]
    props = feat["properties"]["summary"]
    distance_m = props["distance"]
    duration_s = props["duration"]

    # 4) Retorna geojson, duration (s), distance (m) e ordered list
    return geojson, duration_s, distance_m, delivery_ordered

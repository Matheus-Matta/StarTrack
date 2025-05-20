import json
import requests


def get_geojson_by_ors(coordinates):
    # Coord do galpão
    start_coord = [coordinates[0]['long'], coordinates[0]['lat']]
    jobs = []

    for idx, coord_info in enumerate(coordinates[1:]):
        coord = [coord_info['long'], coord_info['lat']]
        jobs.append({
            "id": idx + 1,
            "location": coord,
            "description": str(coord_info['order_number'])  # Identificador
        })

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

    # Chamada ao VROOM local
    vroom_response = requests.post("https://vroom.starseguro.com.br/", json=payload)

    if vroom_response.status_code != 200:
        raise Exception(f"Erro VROOM: {vroom_response.status_code} - {vroom_response.text}")

    vroom_data = vroom_response.json()

    if "routes" not in vroom_data or not vroom_data["routes"]:
        raise KeyError(f"Resposta VROOM inválida: 'routes' ausente\n{json.dumps(vroom_data, indent=2)}")

    coordenadas_ordenadas = [start_coord]
    delivery_ordered = []

    # Reorganiza entregas conforme VROOM
    for step in vroom_data["routes"][0]["steps"]:
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

    # Chamada ao ORS local para obter o GeoJSON da rota
    geojson_payload = {
        "coordinates": coordenadas_ordenadas
    }

    ors_response = requests.post(
        "http://10.0.0.4:8080/ors/v2/directions/driving-car/geojson",
        headers={"Content-Type": "application/json"},
        json=geojson_payload
    )

    if ors_response.status_code != 200:
        raise Exception(f"Erro ORS (directions): {ors_response.status_code} - {ors_response.text}")

    geojson = ors_response.json()
    duration = vroom_data["routes"][0]["duration"]

    return geojson, duration, delivery_ordered

import logging
import os
import random
import requests
from typing import Optional, Tuple
import unicodedata

from decouple import config

GOOGLE_API_KEY = config('GOOGLE_API_KEY', default=None)


def generate_random_color() -> str:
    """Gera uma cor hexadecimal aleatória."""
    return '#' + ''.join(random.choices('0123456789ABCDEF', k=6))


def sanitize_str(value) -> str:
    """Remove espaços das pontas e converte NaN em string vazia."""
    text = '' if value is None else str(value).strip()
    return '' if text.lower() == 'nan' else text

def normalize_for_compare(text: str) -> str:
    """
    Transforma 'São Gonçalo' em 'sao goncalo':
    - NFKD separa base + acento
    - encode/decode joga fora acentos
    - lower() para comparação case-insensitive
    """
    no_accents = unicodedata.normalize('NFKD', sanitize_str(text)) \
                             .encode('ASCII', 'ignore') \
                             .decode('ASCII')
    return no_accents.lower()

def consultar_cep_viacep(
    cep: str,
    bairro_esperado: Optional[str] = None,
    cidade_esperada: Optional[str] = None
) -> Optional[dict]:
    """Consulta o CEP e confirma bairro/cidade após normalizar."""
    cep_num = ''.join(filter(str.isdigit, str(cep)))
    if len(cep_num) != 8:
        logging.warning(f"[ViaCEP] CEP inválido: {cep}")
        return None

    url = f"https://viacep.com.br/ws/{cep_num}/json/"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("erro"):
            logging.warning(f"[ViaCEP] CEP não encontrado: {cep_num}")
            return None

        # Normaliza e compara:
        bairro_ret = data.get("bairro", "")
        cidade_ret = data.get("localidade", "")
        if bairro_esperado and normalize_for_compare(bairro_ret) != normalize_for_compare(bairro_esperado):
            logging.warning(
                f"[ViaCEP] Bairro divergente: esperado '{bairro_esperado}', recebido '{bairro_ret}'"
            )
            return None
        if cidade_esperada and normalize_for_compare(cidade_ret) != normalize_for_compare(cidade_esperada):
            logging.warning(
                f"[ViaCEP] Cidade divergente: esperado '{cidade_esperada}', recebido '{cidade_ret}'"
            )
            return None

        return {
            "rua":      sanitize_str(data.get("logradouro")),
            "bairro":   sanitize_str(bairro_ret),
            "cidade":   sanitize_str(cidade_ret),
            "estado":   sanitize_str(data.get("uf")),
            "cep":      sanitize_str(data.get("cep")),
        }

    except Exception as e:
        logging.warning("[ViaCEP] Erro na consulta", exc_info=e)
        return None


def geocode_endereco(
    endereco: str,
    numero: Optional[str] = None,
    postal_code: Optional[str] = None,
    bairro: Optional[str] = None,
    cidade: Optional[str] = None,
    estado: Optional[str] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Tenta obter latitude/longitude do endereço via Google Geocoding API.
    1) Geocode com components
    2) Se falhar e tiver postal_code, consulta ViaCEP + geocode completo
    3) Geocode com string completa (autocomplete)
    """
    API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    key = GOOGLE_API_KEY
    if not key:
        logging.error("[Geocode] Chave da API do Google não configurada.")
        return None, None

    def attempt_geocode(params: dict) -> Optional[Tuple[float, float]]:
        try:
            resp = requests.get(API_URL, params=params, timeout=10)
            resp.raise_for_status()
            j = resp.json()
            if j.get('status') == 'OK' and j.get('results'):
                loc = j['results'][0]['geometry']['location']
                return loc['lat'], loc['lng']
        except Exception as e:
            logging.warning(f"[Geocode] Falha ao geocodificar com params={params}", exc_info=e)
        return None

    # 1) Tentativa com components
    components = []
    if estado:
        components.append(f"administrative_area:{estado}")
    if cidade:
        components.append(f"locality:{cidade}")
    if postal_code:
        components.append(f"postal_code:{postal_code}")
    components.append("country:BR")

    base_address = f"{endereco}, {numero or ''}".strip(', ')
    params1 = {
        "address": base_address,
        "key": key,
        "components": "|".join(components)
    }
    logging.debug(f"[Geocode] Tentativa 1 components: {params1}")
    result = attempt_geocode(params1)
    if result:
        return result

    # 2) Tentativa via ViaCEP
    if postal_code:
        via_cep = consultar_cep_viacep(postal_code, bairro, cidade)
        if via_cep:
            addr = ", ".join(filter(None, [
                via_cep["rua"],
                numero or '',
                via_cep["bairro"],
                via_cep["cidade"],
                via_cep["estado"],
                via_cep["cep"],
                "Brasil"
            ]))
            params2 = {"address": addr, "key": key}
            logging.warning(f"[Geocode] Tentativa 2 ViaCEP: {params2}")
            result = attempt_geocode(params2)
            if result:
                return result

    # 3) Tentativa geral (autocomplete)

    # Primeiro normaliza para string ou vazia
    number_str = numero or ''

    # Se for exatamente '0', substitui por '1'
    if number_str == '0':
        number_str = '1'

    full_addr = ", ".join(filter(None, [
        endereco,
        number_str,
        bairro or '',
        cidade or '',
        estado or '',
        "Brasil"
    ]))

    params3 = {"address": full_addr, "key": key}
    result = attempt_geocode(params3)
    logging.warning(f"[Geocode] Tentativa 3 autocomplete: {params3} LATITUDE: {result}")
    if result:
        return result

    return None, None


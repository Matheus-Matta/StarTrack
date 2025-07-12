# tmsapp/deliveryApp/tasks.py

import os
import pandas as pd
import time 
import re
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from crmapp.models import Customer
from tmsapp.deliveryApp.models import Delivery
from djangonotify.models import TaskRecord
from tmsapp.scriptApp.action import read_file_to_dataframe, geocode_endereco
from djangonotify.utils import send_progress, send_notification

User = get_user_model()


class DeliveryImporter:
    """
    Classe responsável por importar entregas de planilhas Excel/CSV.
    Organiza todo o processo de importação em métodos especializados.
    """
    
    def __init__(self, user_id: int, task_id: str):
        """
        Inicializa o importador com as informações da tarefa.
        
        Args:
            user_id: ID do usuário que iniciou a importação
            task_id: ID da tarefa Celery para controle de progresso
        """
        self.user_id = user_id
        self.task_id = task_id
        self.user = User.objects.get(pk=user_id)
        
    def sanitize_value(self, value) -> str:
        """
        Sanitiza valores vindos da planilha, convertendo NaN/vazios para string vazia.
        Remove espaços desnecessários e converte floats inteiros para inteiros.
        
        Args:
            value: Valor a ser sanitizado
            
        Returns:
            String sanitizada
        """
        if pd.isna(value) or str(value).strip().lower() == 'nan':
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def parse_decimal_value(self, value_str: str, field_name: str = "") -> Decimal:
        """
        Converte string no formato brasileiro (ex: "1.234,56") para Decimal.
        Remove separadores de milhares e normaliza vírgula decimal.
        """
        if not value_str or not value_str.strip():
            return Decimal('0')
        sanitized = re.sub(r'\.(?=\d{3}(?:[,\s]|$))', '', value_str).replace(',', '.')
        try:
            return Decimal(sanitized)
        except InvalidOperation:
            raise ValueError(f'O valor "{value_str}" não é um decimal válido para o campo {field_name}.')
            
    def parse_date_value(self, date_str: str, field_name: str = "") -> Optional[str]:
        """
        Converte string de data para o formato YYYY-MM-DD esperado pelo Django.
        Suporta diferentes formatos de entrada comuns no Brasil.
        
        Args:
            date_str: String da data a ser convertida
            field_name: Nome do campo (para mensagens de erro)
            
        Returns:
            Data no formato YYYY-MM-DD ou None se vazia
            
        Raises:
            ValueError: Se a data não puder ser convertida
        """
        if not date_str or date_str.strip() == '':
            return None
            
        date_str = date_str.strip()
        
        # Formatos comuns de data que podem vir da planilha
        date_formats = [
            '%d/%m/%Y %H:%M:%S',  # 09/07/2025 00:00:00
            '%d/%m/%Y',           # 09/07/2025
            '%d-%m-%Y %H:%M:%S',  # 09-07-2025 00:00:00
            '%d-%m-%Y',           # 09-07-2025
            '%Y-%m-%d %H:%M:%S',  # 2025-07-09 00:00:00
            '%Y-%m-%d',           # 2025-07-09 (já no formato correto)
            '%d/%m/%y',           # 09/07/25
            '%d-%m-%y',           # 09-07-25
        ]
        
        parsed_date = None
        
        # Tenta cada formato até encontrar um que funcione
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, date_format)
                break
            except ValueError:
                continue
        
        if parsed_date is None:
            raise ValueError(
                f'O valor "{date_str}" tem um formato de data inválido para o campo {field_name}. '
                f'Formatos suportados: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD'
            )
        
        # Converte para timezone aware se necessário
        if timezone.is_naive(parsed_date):
            parsed_date = timezone.make_aware(parsed_date, timezone.get_current_timezone())
        
        # Retorna no formato YYYY-MM-DD
        return parsed_date.strftime('%Y-%m-%d')
        """
        Converte string no formato brasileiro (ex: "1.234,56") para Decimal.
        Remove separadores de milhares e normaliza vírgula decimal.
        
        Args:
            value_str: String do valor a ser convertido
            field_name: Nome do campo (para mensagens de erro)
            
        Returns:
            Decimal convertido
            
        Raises:
            ValueError: Se o valor não puder ser convertido
        """
        sanitized_value = value_str.strip()
        if not sanitized_value:
            return Decimal('0')
            
        # Remove separador de milhares e normaliza vírgula decimal
        sanitized_value = re.sub(r'\.(?=\d{3}(?:[,\s]|$))', '', sanitized_value)
        sanitized_value = sanitized_value.replace(',', '.')
        
        try:
            return Decimal(sanitized_value)
        except InvalidOperation:
            raise ValueError(f'O valor "{value_str}" não é um decimal válido para o campo {field_name}.')

    def extract_data_from_row(self, row) -> Dict:
        """
        Extrai e sanitiza dados de uma linha da planilha.
        
        Args:
            row: Linha da planilha (pandas tuple)
            
        Returns:
            Dicionário com os dados sanitizados
        """
        # Extrai valores numéricos e os converte
        volume_str = self.sanitize_value(getattr(row, 'cubagemm3', ''))
        weight_str = self.sanitize_value(getattr(row, 'peso', ''))
        price_str = self.sanitize_value(getattr(row, 'valtotnota', ''))
        
        return {
            'cpf': self.sanitize_value(getattr(row, 'doctocliente', '')),
            'full_name': self.sanitize_value(getattr(row, 'nomecliente', '')),
            'email': self.sanitize_value(getattr(row, 'emailcliente', '')),
            'phone': self.sanitize_value(getattr(row, 'telefoneentrega', '')),
            'order_number': self.sanitize_value(getattr(row, 'numerosaida', '')),
            'filial': self.sanitize_value(getattr(row, 'idfilial', '')),
            'street': self.sanitize_value(getattr(row, 'enderecoentrega', '')),
            'number': self.sanitize_value(getattr(row, 'numeroentrega', '')),
            'neighborhood': self.sanitize_value(getattr(row, 'bairroentrega', '')),
            'city_full': self.sanitize_value(getattr(row, 'cidadeentrega', '')),
            'state': self.sanitize_value(getattr(row, 'estadoentrega', 'RJ')),
            'postal_code': self.sanitize_value(getattr(row, 'cepentrega', '')),
            'observation': self.sanitize_value(getattr(row, 'observacao', '')),
            'reference': self.sanitize_value(getattr(row, 'pontoreferenciaentrega', '')),
            'total_volume_m3': self.parse_decimal_value(volume_str, 'total_volume_m3'),
            'total_weight_kg': self.parse_decimal_value(weight_str, 'total_weight_kg'),
            'price': self.parse_decimal_value(price_str, 'price'),
            'date_delivery': self.parse_date_value(self.sanitize_value(getattr(row, 'dataentrega', '')), 'date_delivery')
        }

    def collect_data_from_dataframe(self, df: pd.DataFrame) -> Tuple[List[Dict], Set[str]]:
        """
        Coleta e processa todos os dados da planilha.
        
        Args:
            df: DataFrame com os dados da planilha
            
        Returns:
            Tupla contendo lista de dados e set de CPFs únicos
        """
        total_rows = len(df)
        processed_rows = []
        unique_cpfs = set()
        
        for index, row in enumerate(df.itertuples(index=False), start=1):
            row_data = self.extract_data_from_row(row)
            
            if row_data['cpf']:
                unique_cpfs.add(row_data['cpf'])
            processed_rows.append(row_data)
            
            # Atualiza progresso a cada linha processada
            progress_percent = int(index / total_rows * 10)
            self.send_progress_update(
                f"Coletando dados: {index}/{total_rows}", 
                progress_percent
            )
        
        return processed_rows, unique_cpfs

    def process_customers(self, rows: List[Dict], cpfs: Set[str]) -> Dict[str, Customer]:
        """
        Processa criação e atualização de clientes.
        
        Args:
            rows: Lista com dados das linhas processadas
            cpfs: Set com CPFs únicos encontrados
            
        Returns:
            Mapeamento de CPF para objeto Customer
        """
        # Busca clientes existentes
        existing_customers = Customer.objects.filter(cpf__in=cpfs)
        customer_map = {customer.cpf: customer for customer in existing_customers}
        
        # Identifica novos clientes para criação
        new_customers = self.create_new_customers(rows, cpfs, customer_map)
        
        # Atualiza clientes existentes
        updated_customers = self.update_existing_customers(rows, customer_map)
        
        self.send_progress_update(
            f"{len(new_customers)} clientes criados, {len(updated_customers)} atualizados", 
            25
        )
        
        return customer_map

    def create_new_customers(self, rows: List[Dict], cpfs: Set[str], customer_map: Dict[str, Customer]) -> List[Customer]:
        """
        Cria novos clientes que não existem na base.
        
        Args:
            rows: Dados das linhas processadas
            cpfs: Set com todos os CPFs
            customer_map: Mapeamento atual de clientes
            
        Returns:
            Lista de novos clientes criados
        """
        new_cpfs = cpfs - customer_map.keys()
        
        customers_to_create = []
        for cpf in new_cpfs:
            # Encontra os dados do primeiro registro com este CPF
            customer_data = next(row for row in rows if row['cpf'] == cpf)
            
            customers_to_create.append(Customer(
                cpf=cpf,
                full_name=customer_data['full_name'] or '',
                email=customer_data['email'] or None,
                phone=customer_data['phone'] or None,
            ))
        
        # Bulk create para performance
        if customers_to_create:
            Customer.objects.bulk_create(customers_to_create, batch_size=500)
            
            # Atualiza o mapeamento com os novos clientes
            for customer in Customer.objects.filter(cpf__in=[c.cpf for c in customers_to_create]):
                customer_map[customer.cpf] = customer
        
        return customers_to_create

    def update_existing_customers(self, rows: List[Dict], customer_map: Dict[str, Customer]) -> List[Customer]:
        """
        Atualiza dados de clientes existentes quando necessário.
        
        Args:
            rows: Dados das linhas processadas
            customer_map: Mapeamento de clientes existentes
            
        Returns:
            Lista de clientes atualizados
        """
        customers_to_update = []
        
        for row_data in rows:
            cpf = row_data['cpf']
            customer = customer_map.get(cpf)
            
            if not customer:
                continue
                
            # Verifica se algum campo precisa ser atualizado
            needs_update = False
            
            if row_data['full_name'] and customer.full_name != row_data['full_name']:
                customer.full_name = row_data['full_name']
                needs_update = True
                
            if row_data['email'] and customer.email != row_data['email']:
                customer.email = row_data['email']
                needs_update = True
                
            if row_data['phone'] and customer.phone != row_data['phone']:
                customer.phone = row_data['phone']
                needs_update = True
            
            if needs_update:
                customers_to_update.append(customer)
        
        # Bulk update para performance
        if customers_to_update:
            Customer.objects.bulk_update(
                customers_to_update, 
                ['full_name', 'email', 'phone'], 
                batch_size=500
            )
        
        return customers_to_update

    def should_geocode_delivery(self, delivery: Delivery, existing_delivery: Optional[Delivery]) -> bool:
        """
        Determina se uma entrega precisa ser geocodificada.
        
        Args:
            delivery: Objeto delivery a ser verificado
            existing_delivery: Delivery existente (se houver)
            
        Returns:
            True se precisar geocodificar, False caso contrário
        """
        # Se não tem coordenadas, precisa geocodificar
        if not (delivery.latitude and delivery.longitude):
            return True
            
        # Se não existe delivery anterior, não precisa geocodificar
        if not existing_delivery:
            return False
            
        # Verifica se algum campo de endereço foi alterado
        address_fields = ['street', 'number', 'postal_code', 'neighborhood', 'city', 'state']
        
        for field in address_fields:
            if getattr(existing_delivery, field) != getattr(delivery, field):
                return True
                
        return False

    def geocode_delivery_if_needed(self, delivery: Delivery, existing_delivery: Optional[Delivery]) -> None:
        """
        Executa geocodificação de uma entrega se necessário.
        
        Args:
            delivery: Delivery a ser geocodificada
            existing_delivery: Delivery existente (se houver)
        """
        if self.should_geocode_delivery(delivery, existing_delivery):
            latitude, longitude = geocode_endereco(
                delivery.street,
                delivery.number,
                delivery.postal_code,
                delivery.neighborhood,
                delivery.city,
                delivery.state
            )
            
            if latitude and longitude:
                delivery.latitude = latitude
                delivery.longitude = longitude

    def validate_date_format(self, date_str: Optional[str]) -> bool:
        """
        Valida se a data está no formato correto YYYY-MM-DD.
        
        Args:
            date_str: String da data a ser validada
            
        Returns:
            True se a data é válida ou None, False caso contrário
        """
        if not date_str:
            return True
            
        try:
            # Tenta fazer parse da data no formato esperado
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def extract_city_name(self, city_full: str) -> str:
        """
        Extrai o nome da cidade do campo completo (remove sufixos após hífen).
        
        Args:
            city_full: Nome completo da cidade
            
        Returns:
            Nome da cidade limpo
        """
        if not city_full:
            return ''
        return city_full.split('-')[0].strip()

    def create_delivery_object(self, row_data: Dict, customer_map: Dict[str, Customer]) -> Delivery:
        """
        Cria um objeto Delivery a partir dos dados da linha.
        
        Args:
            row_data: Dados da linha processada
            customer_map: Mapeamento de clientes
            
        Returns:
            Objeto Delivery criado
        """
        city_name = self.extract_city_name(row_data['city_full'])
        
        # Valida formato da data antes de criar o objeto
        if row_data['date_delivery'] and not self.validate_date_format(row_data['date_delivery']):
            raise ValueError(f"Data de entrega inválida: {row_data['date_delivery']}")
        
        return Delivery(
            customer=customer_map.get(row_data['cpf']),
            filial=row_data['filial'],
            order_number=row_data['order_number'],
            street=row_data['street'],
            number=row_data['number'],
            neighborhood=row_data['neighborhood'],
            city=city_name,
            state=row_data['state'],
            postal_code=row_data['postal_code'],
            observation=row_data['observation'],
            reference=row_data['reference'],
            total_volume_m3=row_data['total_volume_m3'],
            total_weight_kg=row_data['total_weight_kg'],
            date_delivery=row_data['date_delivery'],
            price=row_data['price'],
            created_by=self.user
        )

    def update_delivery_object(self, delivery: Delivery, row_data: Dict, customer_map: Dict[str, Customer]) -> None:
        """
        Atualiza um objeto Delivery existente com novos dados.
        
        Args:
            delivery: Delivery existente a ser atualizado
            row_data: Novos dados da linha
            customer_map: Mapeamento de clientes
        """
        city_name = self.extract_city_name(row_data['city_full'])
        
        # Valida formato da data antes de atualizar
        if row_data['date_delivery'] and not self.validate_date_format(row_data['date_delivery']):
            raise ValueError(f"Data de entrega inválida: {row_data['date_delivery']}")
        
        delivery.customer = customer_map.get(row_data['cpf'])
        delivery.filial = row_data['filial']
        delivery.street = row_data['street']
        delivery.number = row_data['number']
        delivery.neighborhood = row_data['neighborhood']
        delivery.city = city_name
        delivery.state = row_data['state']
        delivery.postal_code = row_data['postal_code']
        delivery.observation = row_data['observation']
        delivery.reference = row_data['reference']
        delivery.total_volume_m3 = row_data['total_volume_m3']
        delivery.total_weight_kg = row_data['total_weight_kg']
        delivery.date_delivery = row_data['date_delivery']
        delivery.price = row_data['price']

    def process_deliveries(self, rows: List[Dict], customer_map: Dict[str, Customer]) -> Tuple[List[Delivery], List[Delivery]]:
        """
        Processa criação e atualização de entregas.
        
        Args:
            rows: Lista com dados das linhas processadas
            customer_map: Mapeamento de clientes
            
        Returns:
            Tupla com listas de entregas para criar e atualizar
        """
        # Coleta todos os números de pedido
        order_numbers = {row['order_number'] for row in rows if row['order_number']}
        
        # Busca entregas existentes
        existing_deliveries = Delivery.objects.filter(order_number__in=order_numbers)
        delivery_map = {delivery.order_number: delivery for delivery in existing_deliveries}
        
        deliveries_to_create = []
        deliveries_to_update = []
        total_rows = len(rows)
        
        for index, row_data in enumerate(rows, start=1):
            order_number = row_data['order_number']
            
            if not order_number:
                continue
            
            if order_number in delivery_map:
                # Atualiza entrega existente
                existing_delivery = delivery_map[order_number]
                self.update_delivery_object(existing_delivery, row_data, customer_map)
                self.geocode_delivery_if_needed(existing_delivery, delivery_map[order_number])
                deliveries_to_update.append(existing_delivery)
            else:
                # Cria nova entrega
                new_delivery = self.create_delivery_object(row_data, customer_map)
                self.geocode_delivery_if_needed(new_delivery, None)
                deliveries_to_create.append(new_delivery)
            
            # Atualiza progresso periodicamente
            if index % 10 == 0:
                progress_percent = min(95, 25 + int(index / total_rows * 70))
                self.send_progress_update(f"Preparando entregas: {index}", progress_percent)
        
        return deliveries_to_create, deliveries_to_update

    def save_deliveries(self, deliveries_to_create: List[Delivery], deliveries_to_update: List[Delivery]) -> None:
        """
        Salva as entregas no banco de dados usando bulk operations.
        
        Args:
            deliveries_to_create: Lista de entregas para criar
            deliveries_to_update: Lista de entregas para atualizar
        """
        # Bulk update das entregas existentes
        if deliveries_to_update:
            Delivery.objects.bulk_update(
                deliveries_to_update,
                [
                    'customer', 'street', 'number', 'neighborhood', 'city', 'state',
                    'postal_code', 'observation', 'reference', 'filial',
                    'latitude', 'longitude', 'total_volume_m3', 'total_weight_kg',
                    'price', 'date_delivery'
                ],
                batch_size=500
            )
        
        # Bulk create das novas entregas
        if deliveries_to_create:
            Delivery.objects.bulk_create(deliveries_to_create, batch_size=500)

    def send_progress_update(self, message: str, percent: int, status: str = 'progress') -> None:
        """
        Envia atualização de progresso para o usuário.
        
        Args:
            message: Mensagem de status
            percent: Porcentagem de progresso (0-100)
            status: Status da operação
        """
        send_progress(self.task_id, self.user_id, message, percent, status=status)

    def send_final_notification(self, created_count: int, updated_count: int) -> None:
        """
        Envia notificação final de conclusão da importação.
        
        Args:
            created_count: Número de entregas criadas
            updated_count: Número de entregas atualizadas
        """
        send_notification(
            self.user_id,
            'Importação de entregas concluída',
            f"{created_count} novas entregas criadas e {updated_count} atualizadas.",
            level='success'
        )

    def cleanup_temp_file(self, file_path: str) -> None:
        """
        Remove arquivo temporário após processamento.
        
        Args:
            file_path: Caminho do arquivo temporário
        """
        if os.path.exists(file_path):
            os.remove(file_path)

    def import_deliveries(self, temp_file_path: str) -> Dict:
        """
        Método principal que executa todo o processo de importação.
        
        Args:
            temp_file_path: Caminho do arquivo temporário
            
        Returns:
            Dicionário com resultado da importação
        """
        try:
            # Inicia o processo de importação
            time.sleep(5)  # Pequena pausa para estabilizar
            self.send_progress_update("Importação iniciada", 0, status='started')
            
            # Carrega dados da planilha
            dataframe = read_file_to_dataframe(temp_file_path)
            
            # Processa dados das linhas
            processed_rows, unique_cpfs = self.collect_data_from_dataframe(dataframe)
            
            with transaction.atomic():
                # Processa clientes (criação e atualização)
                customer_map = self.process_customers(processed_rows, unique_cpfs)
                
                # Processa entregas (criação e atualização)
                deliveries_to_create, deliveries_to_update = self.process_deliveries(processed_rows, customer_map)
                
                # Salva as entregas no banco
                self.save_deliveries(deliveries_to_create, deliveries_to_update)
                
                # Envia progresso final
                self.send_progress_update(
                    f"{len(deliveries_to_create)} criados, {len(deliveries_to_update)} atualizados",
                    100,
                    status='success'
                )
                
                # Notifica conclusão
                self.send_final_notification(len(deliveries_to_create), len(deliveries_to_update))
            
            # Remove arquivo temporário
            self.cleanup_temp_file(temp_file_path)
            
            return {
                'status': 'success',
                'created_customers': len([cpf for cpf in unique_cpfs if cpf]),
                'updated_customers': 0,  # Seria necessário rastrear melhor
                'deliveries_created': len(deliveries_to_create),
                'deliveries_updated': len(deliveries_to_update),
            }
            
        except Exception as error:
            # Trata erros e notifica falha
            self.send_final_notification_error(str(error))
            self.send_progress_update("Importação falhou", 100, status='failure')
            
            return {
                "status": "error",
                "error": str(error)
            }

    def send_final_notification_error(self, error_message: str) -> None:
        """
        Envia notificação de erro na importação.
        
        Args:
            error_message: Mensagem de erro
        """
        send_notification(
            self.user_id, 
            "Importação de entregas falhou", 
            error_message, 
            level='danger'
        )


@shared_task(bind=True)
def import_deliveries_from_sheet(self, user_id: int, tkrecord_id: int, temp_file_path: str):
    """
    Tarefa Celery para importação de entregas de planilhas.
    
    Args:
        user_id: ID do usuário
        tkrecord_id: ID do registro da tarefa
        temp_file_path: Caminho do arquivo temporário
        
    Returns:
        Resultado da importação
    """
    try:
        # Vincula o TaskRecord à nova task_id
        task_id = self.request.id
        task_record = TaskRecord.objects.get(pk=tkrecord_id)
        task_record.task_id = task_id
        task_record.save(update_fields=['task_id'])
        
        # Executa a importação usando a classe especializada
        importer = DeliveryImporter(user_id, task_id)
        return importer.import_deliveries(temp_file_path)
        
    except Exception as error:
        # Fallback para erros não tratados pela classe
        send_notification(user_id, "Importação de entregas falhou", str(error), level='danger')
        send_progress(task_id, user_id, "Importação falhou", 100, status='failure')
        return {
            "status": "error",
            "error": str(error)
        }


# Funções auxiliares mantidas para compatibilidade (deprecated)
def sanitize(value) -> str:
    """Função legacy - usar DeliveryImporter.sanitize_value()"""
    importer = DeliveryImporter(0, "")
    return importer.sanitize_value(value)


def parse_decimal(value_str: str, field_name: str = "") -> Decimal:
    """Função legacy - usar DeliveryImporter.parse_decimal_value()"""
    importer = DeliveryImporter(0, "")
    return importer.parse_decimal_value(value_str, field_name)


def parse_date(date_str: str, field_name: str = "") -> Optional[str]:
    """Função legacy - usar DeliveryImporter.parse_date_value()"""
    importer = DeliveryImporter(0, "")
    return importer.parse_date_value(date_str, field_name)


def geocode_deliveries_if_needed(deliveries: list, existing_map: dict) -> list:
    """Função legacy - usar DeliveryImporter.geocode_delivery_if_needed()"""
    # Implementação mantida para compatibilidade
    importer = DeliveryImporter(0, "")
    
    for delivery in deliveries:
        existing_delivery = existing_map.get(delivery.order_number)
        importer.geocode_delivery_if_needed(delivery, existing_delivery)
    
    return deliveries
# StarTrack – Plataforma de Roteirização e Entregas

StarTrack é um sistema de **gestão de rotas e entregas** desenvolvido em **Django**, com processamento assíncrono em **Celery** e servidor **ASGI com Daphne**, integrado ao **OpenRouteService (ORS)** e **VROOM** para otimização de rotas, exibindo tudo em mapa com **OpenStreetMap**.

O objetivo é facilitar o dia a dia da operação logística: cadastro de motoristas e veículos, criação de cargas, geração automática de rotas de entrega e visualização dos trajetos no mapa.

---

## Screenshots

### Login

![Tela de Login](/mnt/data/ac06f61e-00f7-4025-b128-7a8762decd00.png)

Tela de autenticação dos usuários do painel StarTrack.  
Permite login com usuário e senha, opção de “lembrar-me” e link para recuperação de senha.

---

### Dashboard de Frota

![Dashboard de Frota](/mnt/data/91775abd-7bec-44f3-b8e3-7738193f51db.png)

Visão geral da frota:

- Veículos em trânsito
- Quantidade de motoristas
- Veículos ativos
- Transportadoras ativas  
- Gráfico mostrando **volume (m³)** e **peso (kg)** por veículo, ajudando a visualizar a ocupação da frota.

Na parte inferior há listas detalhadas de **Motoristas** e **Veículos**, com informações básicas de contato e vínculo.

---

### Cadastro de Motoristas

![Cadastro de Motorista](/mnt/data/38feb8f4-eedf-4d99-8783-3e4015439d55.png)

Formulário completo para cadastro de motoristas, com abas de:

- **Detalhes:** nome, sobrenome, telefone, e-mail  
- **Documentos:** CNH, categoria, validade etc.  
- **Login e Acessos:** credenciais e permissões do sistema  
- **Segurança:** campos adicionais de controle de acesso

---

### Áreas de Rota (Regionais)

![Áreas de Rota](/mnt/data/f20a58a3-1b28-45c2-8b61-8f3e59b0f02d.png)

Módulo de **Rotas** com:

- Lista de **áreas de rota** (regiões) com status (Ativo/Inativo)  
- Mapa com polígonos desenhados sobre o **OpenStreetMap**, representando cada área de atendimento  
- Gráficos de **Top 5 Áreas por m²** e **Top 5 Distâncias (km)**, ajudando na análise de cobertura e extensão das rotas

As áreas são usadas como base para agrupar entregas e distribuir cargas por região.

---

### Roteirização de Cargas

![Roteirização – Cargas](/mnt/data/6e425842-e18b-47e9-a513-e2894a6df8da.png)

Tela de **Roteirização** de uma roteirização específica (ex.: `RTR-102`):

- Cards com indicadores:
  - Entregas em carga
  - Entregas fora de carga
  - Valor total
  - Peso total
  - Volume total
- Tabela de **Cargas**, com:
  - Código da carga (ex.: `PLC-661`)
  - Quantidade de entregas
  - Veículo
  - Motorista
  - Rota associada
  - Peso, volume e valor
  - Status (ex.: Rascunho)

Na parte inferior há a tabela de **Entregas**, mostrando cliente, pedido, endereço, peso, volume e carga atribuída, com busca por cliente/pedido.

Botão **“Ver mapa”** abre a visualização detalhada da rota no mapa.

---

### Mapa das Rotas

![Mapa das Rotas](/mnt/data/0908877c-347c-40ef-a7f8-0573a5234267.png)

Modal de **Mapa das Rotas**:

- Trajetos otimizados por **ORS + VROOM** exibidos no mapa, cada rota com uma cor diferente  
- Marcadores numerados indicando a **ordem de visita** das entregas  
- Possibilidade de visualizar:
  - Todas as rotas
  - Apenas uma rota específica (filtro no topo)

Base cartográfica com **OpenStreetMap**, integrada via **Leaflet** (ou biblioteca similar).

---

## Principais Funcionalidades

- **Autenticação e Perfis**
  - Login seguro para usuários da operação
  - Perfis de acesso (admin, roteirizador, conferente, etc.)

- **Cadastro de Motoristas**
  - Dados pessoais e de contato
  - Dados da CNH e validade
  - Configuração de acesso ao sistema

- **Cadastro de Veículos**
  - Placa, tipo, capacidade de peso (kg) e volume (m³)
  - Vínculo com motoristas e transportadoras
  - Indicação se o veículo é terceirizado ou próprio

- **Gestão de Áreas de Rota**
  - Desenho de áreas diretamente no mapa
  - Associação de áreas a veículos/rotas
  - Métricas de área (m²) e distância (km)

- **Roteirização**
  - Criação de roteirizações (ex.: `RTR-102`)
  - Agrupamento de entregas em **cargas** (PLC-xxx)
  - Chamada de APIs do **OpenRouteService** e **VROOM** para:
    - Otimizar a ordem das paradas
    - Calcular trajetos, distâncias e tempos
  - Atualização assíncrona via **Celery**, evitando travar o backend

- **Mapa de Entregas**
  - Visualização das entregas no mapa com marcadores numerados
  - Cores diferentes por rota
  - Zoom por região / rota
  - Integração com OpenStreetMap

- **Dashboard da Frota**
  - Indicadores em tempo real da frota
  - Gráficos de peso/volume por veículo
  - Listagem rápida de motoristas e veículos

---

## Arquitetura Técnica

- **Backend**
  - Django (API REST + views web)
  - Django ORM (PostgreSQL ou outro banco relacional)
  - Celery para tarefas de:
    - Otimização de rotas
    - Atualização de status de entregas
    - Cálculo de KPIs (peso, volume, valor por rota)
  - Daphne como servidor ASGI (podendo integrar com Django Channels para atualizações em tempo real)

- **Serviços Externos**
  - **OpenRouteService (ORS):** cálculo de rotas, distâncias e tempos
  - **VROOM:** otimização de sequência de visitas (Vehicle Routing Problem)
  - Ambos podem estar em containers Docker na infraestrutura da aplicação

- **Frontend**
  - Templates Django ou SPA (Vue/React) consumindo a API
  - Mapa renderizado com **Leaflet** + tiles do OpenStreetMap
  - Componentes de UI com tema escuro (dark mode)

---

## Requisitos

- Python 3.x  
- Django  
- Celery  
- Redis ou RabbitMQ (broker para o Celery)  
- PostgreSQL (recomendado)  
- OpenRouteService e VROOM configurados e acessíveis via HTTP  
- Daphne (ou outro servidor ASGI)

---

## Como Executar (exemplo)

1. **Clonar o projeto**

   ```bash
   git clone https://seu-repo/startrack.git
   cd startrack

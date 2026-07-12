# RPG API — Microserviços com FastAPI + Go + .NET

Sistema de mural de missões estilo RPG demonstrando arquitetura de microserviços com FastAPI, API Gateway, HATEOAS, SOAP, WebSocket e Go.

## Arquitetura

```
Frontend React (5173)
        ↓
API Gateway (FastAPI) — porta 8000
├── /api/heroes/*     →  Hero Service (FastAPI) — porta 8001
├── /api/quests/*     →  Quest Service (FastAPI) — porta 8002 ──→  RabbitMQ
├── /api/shop/*       →  Shop Service (.NET/SOAP) — porta 5114
├── /api/inventory/*  →  Inventory Service (Python/gRPC) — porta 50051
└── /ws/boss          →  Boss Service (Go/WebSocket) — porta 8080

                                            ┌─────────────────────────┐
                                            │       RabbitMQ          │
                                            │  exchange: rpg.events   │
                                            │  (topic)                │
                                            │  portas: 5672 / 15672   │
                                            └───────────┬─────────────┘
                                                     ┌──┴──┐
                                                     ▼     ▼
                                               Reward    Log
                                               Subscriber Subscriber
                                               (XP+gold)  (logger)
```

### Serviços

| Serviço | Stack | Porta | Descrição |
|---------|-------|-------|-----------|
| Gateway | FastAPI | 8000 | API Gateway com HATEOAS e proxy WebSocket |
| Hero Service | FastAPI | 8001 | Heróis, stats, XP, gold, checkout de personagens |
| Quest Service | FastAPI | 8002 | Mural de missões (publica eventos no RabbitMQ) |
| Shop Service | .NET 10 / SOAP | 5114 | Loja de itens |
| Inventory Service | Python / gRPC | 50051 | Inventário de itens dos heróis |
| Boss Service | Go / Gorilla WebSocket | 8080 | World Boss em tempo real |

O Inventory Service fala **gRPC**, não REST — o gateway atua como cliente gRPC dele e expõe o
resultado como REST comum em `/api/inventory/*`, do mesmo jeito que já faz com o Shop Service (SOAP).
Ele é o único serviço que precisa dos stubs gerados a partir de um `.proto` — veja
`backend/inventory_service/README.md` para gerar/regenerar esses stubs manualmente, se precisar.
## Message-Oriented Middleware (MOM) — Pub/Sub com RabbitMQ

Paradigma implementado: **Publicar-Assinar (Publish/Subscribe)** com RabbitMQ como broker de mensagens.

### Motivação

Uma mesma ação no jogo (ex: concluir uma missão) deve disparar reações em múltiplos subsistemas de forma **independente e simultânea**:
o sistema de recompensas distribui XP e gold, enquanto o sistema de log registra o evento para auditoria.
Com Pub/Sub, o publicador não conhece os assinantes — garantindo **desacoplamento** entre os componentes.

### Eventos Publicados

O **Quest Service** publica eventos no exchange `rpg.events` (topic) do RabbitMQ:

| Evento | Routing Key | Payload | Quando ocorre |
|--------|-------------|---------|---------------|
| Missão aceita | `quest.accepted` | `{quest_id, hero_id, title}` | `POST /quests/{id}/accept` |
| Missão concluída | `quest.completed` | `{quest_id, hero_id, xp, gold, title}` | `POST /quests/{id}/complete` |

### Subscribers (Assinantes)

| Subscriber | Routing Key | Responsabilidade |
|------------|-------------|------------------|
| **Reward** | `quest.completed` | Escuta conclusão de missões e chama o Hero Service para distribuir XP e gold automaticamente |
| **Log** | `#` (todos) | Escuta **todos** os eventos e registra timestamp + payload no console |

### Como Executar

```bash
# Devcontainer: RabbitMQ já é instalado e iniciado automaticamente
# Apenas execute:
npm start

# Ou iniciar subscribers manualmente em terminais separados:
cd backend && python3 subscribers/reward_subscriber.py
cd backend && python3 subscribers/log_subscriber.py
```

Acesse a UI do RabbitMQ em **http://localhost:15672** (usuário: `guest`, senha: `guest`).

### Demonstração

```bash
# 1. Aceitar missão
curl -X POST http://localhost:8000/api/quests/q1/accept \
  -H 'Content-Type: application/json' \
  -d '{"id_heroi":"1"}'

# 2. Concluir missão
curl -X POST http://localhost:8000/api/quests/q1/complete
```

Nos terminais dos subscribers:
```
[LogSub]    EVENTO: quest.accepted | {"quest_id": "q1", "hero_id": "1", ...}
[LogSub]    EVENTO: quest.completed | {"quest_id": "q1", "hero_id": "1", "xp": 300, "gold": 50, ...}
[RewardSub] Evento: quest.completed | Heroi: 1 | XP: 300 | Gold: 50
```

## Sistema de Checkout (4 Heróis)

Cada pessoa que acessa recebe um herói único da pool de 4. Máximo de 4 jogadores simultâneos.

| Herói | Classe | ATK | DEF | SPD | INT |
|-------|--------|-----|-----|-----|-----|
| Gandalf 🧙 | Mago das Sombras | 72 | 34 | 55 | 91 |
| Lyra 🏹 | Arqueira Ágil | 65 | 20 | 90 | 30 |
| Thorn ⚔️ | Paladino Guardião | 95 | 50 | 25 | 15 |
| Vesper 🌙 | Feiticeira das Sombras | 30 | 15 | 70 | 88 |

## World Boss (Tempo Real)

Batalha global contra o **Dragão de Gelo de Vorheim** via WebSocket.

- Até 4 heróis atacam o mesmo boss simultaneamente
- Dano baseado no ATK do herói
- Cooldown de 2 segundos entre ataques
- Boss foge após 5 minutos
- Recompensa proporcional ao dano causado
- Leaderboard em tempo real (top 5)

### Como usar

1. Acesse o frontend
2. Um herói da pool é atribuído automaticamente
3. Vá até a aba **🔥 Chefe**
4. Clique em **"Invocar Boss"**
5. Ataque com o botão **⚔️ ATACAR**
6. Acompanhe o HP, leaderboard e eventos em tempo real

## Pré-requisitos

| Runtime | Versão | Motivo |
|---------|--------|--------|
| Python | 3.10+ | Gateway, Hero Service, Quest Service |
| Node.js | 20+ | Frontend (React/Vite) + `npm start` |
| Go | 1.21+ | Boss Service |
| .NET SDK | 10.0 | Shop Service (SOAP) |

**Opção 1 — Local:** instale os runtimes acima manualmente, depois:

```bash
pip install aio-pika          # necessário para os subscribers
pip install -r requirements.txt
cd frontend && npm install
npm install   # (concurrently na raiz)
```

**Opção 2 — Devcontainer:** instale apenas o Docker e use o devcontainer incluso (ou GitHub Codespace). RabbitMQ e todas as dependências são instalados automaticamente.

## GitHub Codespace

Abra o projeto no GitHub Codespace. O devcontainer instala automaticamente:

- Python 3.12 + dependências (`pip install -r requirements.txt`)
- Node.js 22 + dependências do frontend
- Go 1.22 + módulos do boss_service
- .NET SDK 10.0

Após o build, execute:

```bash
npm start
```

## Como rodar

```bash
# Todos os serviços + subscribers
npm start

# ------------------------------
# Ou individualmente (terminais separados):
# ------------------------------

cd backend/gateway        && uvicorn main:app --port 8000 --reload
cd backend/hero_service   && uvicorn main:app --port 8001 --reload
cd backend/quest_service  && uvicorn main:app --port 8002 --reload
cd backend/shop_service   && dotnet run
cd backend/boss_service   && go run .
cd frontend               && npm run dev

# Subscribers:
cd backend && python3 subscribers/reward_subscriber.py
cd backend && python3 subscribers/log_subscriber.py
```

Acesse: **http://localhost:5173**
RabbitMQ UI: **http://localhost:15672** (guest/guest)

## Endpoints

### Via Gateway (use estes no frontend)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | /api/heroes/checkout | Pegar herói disponível da pool |
| POST | /api/heroes/{id}/checkin | Liberar herói |
| GET | /api/heroes/{id} | Perfil do herói |
| GET | /api/heroes/{id}/stats | Atributos (ATK, DEF, SPD, INT) |
| PATCH | /api/heroes/{id}/xp | Adicionar XP |
| PATCH | /api/heroes/{id}/gold | Adicionar gold |
| GET | /api/quests | Listar missões |
| GET | /api/quests/{id} | Detalhe da missão |
| POST | /api/quests/{id}/accept | Aceitar missão |
| POST | /api/quests/{id}/complete | Concluir missão |
| GET | /api/shop/items | Listar itens da loja |
| POST | /api/shop/buy | Comprar item |
| POST | /api/inventory/items | Cadastrar item no inventário de um herói (→ gRPC `AdicionarItem`) |
| GET | /api/inventory/{heroi_id} | Listar inventário de um herói (→ gRPC `ListarInventario`) |
| GET | /api/inventory/item/{item_id} | Consultar um item (→ gRPC `ConsultarItem`) |
| DELETE | /api/inventory/item/{item_id} | Remover um item (→ gRPC `RemoverItem`) |
| POST | /api/boss/spawn | Invocar World Boss |
| WS | /ws/boss | WebSocket da batalha |

### Protocolo WebSocket (Boss)

**Cliente → Servidor:**
```json
{"type": "attack"}
```

**Servidor → Cliente:**

| Tipo | Descrição |
|------|-----------|
| welcome | Herói atribuído e conectado |
| lobby_full | 4 slots ocupados |
| boss_spawn | Boss apareceu |
| boss_hp | Atualização de HP |
| top_damage | Leaderboard top 5 |
| hero_joined / hero_left | Alguém entrou/saiu |
| boss_defeated | Boss derrotado |
| boss_escaped | Boss fugiu |
| reward | Recompensa individual |

### HATEOAS

Toda resposta do gateway inclui:
```json
{
  "data": { ... },
  "_gateway": {
    "service_routed": "/api/quests",
    "links": {
      "self": "http://localhost:8000/api/quests",
      "heroi": "http://localhost:8000/api/heroes/1",
      "missoes": "http://localhost:8000/api/quests"
    }
  }
}
```

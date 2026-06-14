# RPG API — Microserviços com FastAPI + Go + .NET

Sistema de mural de missões estilo RPG demonstrando arquitetura de microserviços com FastAPI, API Gateway, HATEOAS, SOAP, WebSocket e Go.

## Arquitetura

```
Frontend React (5173)
        ↓
API Gateway (FastAPI) — porta 8000
├── /api/heroes/*  →  Hero Service (FastAPI) — porta 8001
├── /api/quests/*  →  Quest Service (FastAPI) — porta 8002
├── /api/shop/*    →  Shop Service (.NET/SOAP) — porta 5114
└── /ws/boss       →  Boss Service (Go/WebSocket) — porta 8080
```

### Serviços

| Serviço | Stack | Porta | Descrição |
|---------|-------|-------|-----------|
| Gateway | FastAPI | 8000 | API Gateway com HATEOAS e proxy WebSocket |
| Hero Service | FastAPI | 8001 | Heróis, stats, XP, gold, checkout de personagens |
| Quest Service | FastAPI | 8002 | Mural de missões |
| Shop Service | .NET 10 / SOAP | 5114 | Loja de itens |
| Boss Service | Go / Gorilla WebSocket | 8080 | World Boss em tempo real |

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
pip install -r requirements.txt
cd frontend && npm install
npm install   # (concurrently na raiz)
```

**Opção 2 — Docker/Devcontainer:** instale apenas o Docker e use o devcontainer incluso (ou GitHub Codespace). Todas as dependências são instaladas automaticamente.

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

## Como rodar (local)

```bash
# Desenvolvimento local (todos os serviços)
npm start

# Ou individualmente:
cd backend/gateway    && uvicorn main:app --port 8000 --reload
cd backend/hero_service  && uvicorn main:app --port 8001 --reload
cd backend/quest_service && uvicorn main:app --port 8002 --reload
cd backend/shop_service  && dotnet run
cd backend/boss_service  && go run .
cd frontend           && npm run dev
```

Acesse: **http://localhost:5173**

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

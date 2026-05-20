# RPG API — Microserviços com FastAPI

Sistema de mural de missões estilo RPG demonstrando arquitetura de microserviços com FastAPI, API Gateway e HATEOAS.

## Arquitetura

```
Frontend React (5173)
        ↓
API Gateway — porta 8000
├── /api/heroes/*  →  Serviço do Herói  — porta 8001
└── /api/quests/*  →  Serviço das Missões — porta 8002
```


## Pré-requisitos

```bash
# Python e dependências
pip install -r requirements.txt

# Node.js para o frontend (se ainda não criou)
npm create vite@latest frontend -- --template react
```

## Como rodar (4 terminais)

### Terminal 1 — Hero Service
```bash
cd backend/hero-service
uvicorn main:app --port 8001 --reload
```

### Terminal 2 — Quest Service
```bash
cd backend/quest-service
uvicorn main:app --port 8002 --reload
```

### Terminal 3 — API Gateway
```bash
cd backend/gateway
uvicorn main:app --port 8000 --reload
```

### Terminal 4 — Frontend
```bash
cd frontend
npm install
npm run dev
```

Acesse: **http://localhost:5173**

---

## Endpoints

### Via Gateway (use estes no frontend)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /api/heroes/1 | Perfil do herói |
| GET | /api/heroes/1/stats | Atributos (ATK, DEF, SPD, INT) |
| PATCH | /api/heroes/1/xp | Adicionar XP |
| GET | /api/quests | Listar missões |
| GET | /api/quests/{id} | Detalhe da missão |
| POST | /api/quests/{id}/accept | Aceitar missão |
| POST | /api/quests/{id}/complete | Concluir missão |

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


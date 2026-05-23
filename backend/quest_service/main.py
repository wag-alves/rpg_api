from datetime import datetime

from data import quests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import (
    SolicitacaoAceitarMissao,
    RespostaAceitarMissao,
    RespostaConcluirMissao,
    Missao,
    RespostaListaMissoes,
)

app = FastAPI(title="Quest Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "http://localhost:8002"


def missao_para_resposta(missao: dict) -> Missao:
    return Missao(
        id=missao["id"],
        titulo=missao["titulo"],
        descricao=missao["descricao"],
        dificuldade=missao["dificuldade"],
        cor_dificuldade=missao["cor_dificuldade"],
        recompensa_xp=missao["recompensa_xp"],
        recompensa_ouro=missao["recompensa_ouro"],
        status=missao["status"],
        id_heroi=missao["id_heroi"],
        aceito_em=missao["aceito_em"],
        concluido_em=missao["concluido_em"],
        icone=missao["icone"],
        links={
            "self": f"{BASE_URL}/quests/{missao['id']}",
            "aceitar": f"{BASE_URL}/quests/{missao['id']}/accept"
            if missao["status"] == "available"
            else None,
            "concluir": f"{BASE_URL}/quests/{missao['id']}/complete"
            if missao["status"] == "in_progress"
            else None,
        },
    )


@app.get("/quests", response_model=RespostaListaMissoes)
def listar_missoes():
    return RespostaListaMissoes(
        missoes=[missao_para_resposta(missao) for missao in list(quests.values())],
        links={
            "self": f"{BASE_URL}/quests",
            "available": f"{BASE_URL}/quests?status=available",
            "in_progress": f"{BASE_URL}/quests?status=in_progress",
            "completed": f"{BASE_URL}/quests?status=completed",
        },
    )


@app.get("/quests/{quest_id}", response_model=Missao)
def obter_missao(quest_id: str):
    missao = quests.get(quest_id)
    if not missao:
        raise HTTPException(status_code=404, detail="Quest not found")
    return missao_para_resposta(missao)


@app.post("/quests/{quest_id}/accept", response_model=RespostaAceitarMissao)
def aceitar_missao(quest_id: str, body: SolicitacaoAceitarMissao):
    missao = quests.get(quest_id)
    if not missao:
        raise HTTPException(status_code=404, detail="Quest not found")
    if missao["status"] != "available":
        raise HTTPException(
            status_code=400, detail=f"Quest is already {missao['status']}"
        )

    missao["status"] = "in_progress"
    missao["id_heroi"] = body.id_heroi
    missao["aceito_em"] = datetime.now().isoformat()

    return RespostaAceitarMissao(
        id_missao=quest_id,
        id_heroi=body.id_heroi,
        status="in_progress",
        mensagem=f"Missão '{missao['titulo']}' aceita com sucesso!",
        links={
            "self": f"{BASE_URL}/quests/{quest_id}/accept",
            "missao": f"{BASE_URL}/quests/{quest_id}",
            "concluir": f"{BASE_URL}/quests/{quest_id}/complete",
        },
    )


@app.post("/quests/{quest_id}/complete", response_model=RespostaConcluirMissao)
def concluir_missao(quest_id: str):
    missao = quests.get(quest_id)
    if not missao:
        raise HTTPException(status_code=404, detail="Quest not found")
    if missao["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Quest is not in progress")

    missao["status"] = "completed"
    missao["concluido_em"] = datetime.now().isoformat()

    return RespostaConcluirMissao(
        id_missao=quest_id,
        id_heroi=missao["id_heroi"],
        status="completed",
        recompensa_xp=missao["recompensa_xp"],
        recompensa_ouro=missao["recompensa_ouro"],
        mensagem=f"Missão '{missao['titulo']}' concluída! Recompensas coletadas.",
        links={
            "self": f"{BASE_URL}/quests/{quest_id}/complete",
            "missao": f"{BASE_URL}/quests/{quest_id}",
            "todas_missoes": f"{BASE_URL}/quests",
        },
    )


@app.get("/")
def raiz():
    return {
        "service": "Quest Service",
        "version": "1.0.0",
        "links": {
            "missoes": f"{BASE_URL}/quests",
            "detalhe_missao": f"{BASE_URL}/quests/{{quest_id}}",
        },
    }

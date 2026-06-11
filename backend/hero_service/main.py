from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from data import heroes
from schemas import RespostaHeroi, RespostaEstatisticas, SolicitacaoAdicionarXp, RespostaAdicionarXp
from schemas import SolicitacaoAlterarGold, RespostaAlterarGold

app = FastAPI(title="Hero Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "http://localhost:8001"


@app.get("/heroes/{hero_id}", response_model=RespostaHeroi)
def obter_heroi(hero_id: str):
    heroi = heroes.get(hero_id)
    if not heroi:
        raise HTTPException(status_code=404, detail="Hero not found")

    return RespostaHeroi(
        id=heroi["id"],
        nome=heroi["nome"],
        nome_classe=heroi["classe"],
        nivel=heroi["nivel"],
        avatar=heroi["avatar"],
        hp=heroi["hp"],
        max_hp=heroi["max_hp"],
        mp=heroi["mp"],
        max_mp=heroi["max_mp"],
        xp=heroi["xp"],
        xp_next=heroi["xp_next"],
        gold=heroi["ouro"],
        active_quests=heroi["missoes_ativas"],
        completed_quests=heroi["missoes_concluidas"],
        links={
            "self": f"{BASE_URL}/heroes/{hero_id}",
            "estatisticas": f"{BASE_URL}/heroes/{hero_id}/stats",
            "adicionar_xp": f"{BASE_URL}/heroes/{hero_id}/xp",
        },
    )


@app.get("/heroes/{hero_id}/stats", response_model=RespostaEstatisticas)
def obter_estatisticas_heroi(hero_id: str):
    heroi = heroes.get(hero_id)
    if not heroi:
        raise HTTPException(status_code=404, detail="Hero not found")

    estatisticas = heroi["estatisticas"]
    return RespostaEstatisticas(
        id_heroi=hero_id,
        atk=estatisticas["atk"],
        def_=estatisticas["def"],
        spd=estatisticas["spd"],
        int_=estatisticas["int"],
        links={
            "self": f"{BASE_URL}/heroes/{hero_id}/stats",
            "heroi": f"{BASE_URL}/heroes/{hero_id}",
        },
    )


@app.patch("/heroes/{hero_id}/xp", response_model=RespostaAdicionarXp)
def adicionar_xp(hero_id: str, body: SolicitacaoAdicionarXp):
    heroi = heroes.get(hero_id)
    if not heroi:
        raise HTTPException(status_code=404, detail="Hero not found")

    heroi["xp"] += body.quantidade
    subiu_de_nivel = False
    novo_nivel = None

    if heroi["xp"] >= heroi["xp_next"]:
        heroi["xp"] -= heroi["xp_next"]
        heroi["nivel"] += 1
        heroi["xp_next"] = int(heroi["xp_next"] * 1.5)
        heroi["max_hp"] += 10
        heroi["hp"] = heroi["max_hp"]
        heroi["estatisticas"]["atk"] += 3
        heroi["estatisticas"]["def"] += 2
        subiu_de_nivel = True
        novo_nivel = heroi["nivel"]

    return RespostaAdicionarXp(
        id_heroi=hero_id,
        xp_ganho=body.quantidade,
        xp_total=heroi["xp"],
        subiu_de_nivel=subiu_de_nivel,
        novo_nivel=novo_nivel,
        links={
            "self": f"{BASE_URL}/heroes/{hero_id}/xp",
            "heroi": f"{BASE_URL}/heroes/{hero_id}",
        },
    )


@app.get("/heroes")
def listar_herois():
    herois = []
    for hid, heroi in heroes.items():
        herois.append(RespostaHeroi(
            id=heroi["id"],
            nome=heroi["nome"],
            nome_classe=heroi["classe"],
            nivel=heroi["nivel"],
            avatar=heroi["avatar"],
            hp=heroi["hp"],
            max_hp=heroi["max_hp"],
            mp=heroi["mp"],
            max_mp=heroi["max_mp"],
            xp=heroi["xp"],
            xp_next=heroi["xp_next"],
            gold=heroi["ouro"],
            active_quests=heroi["missoes_ativas"],
            completed_quests=heroi["missoes_concluidas"],
            links={
                "self": f"{BASE_URL}/heroes/{hid}",
                "estatisticas": f"{BASE_URL}/heroes/{hid}/stats",
            },
        ))
    return herois


@app.get("/")
def raiz():
    return {
        "service": "Hero Service",
        "version": "1.0.0",
        "links": {
            "heroi": f"{BASE_URL}/heroes/{{hero_id}}",
            "estatisticas": f"{BASE_URL}/heroes/{{hero_id}}/stats",
        },
    }


@app.patch("/heroes/{hero_id}/gold", response_model=RespostaAlterarGold)
def alterar_gold(hero_id: str, body: SolicitacaoAlterarGold):
    heroi = heroes.get(hero_id)
    if not heroi:
        raise HTTPException(status_code=404, detail="Hero not found")

    heroi["ouro"] += body.quantidade

    return RespostaAlterarGold(
        id_heroi=hero_id,
        gold=heroi["ouro"],
        links={
            "self": f"{BASE_URL}/heroes/{hero_id}/gold",
            "heroi": f"{BASE_URL}/heroes/{hero_id}",
        },
    )

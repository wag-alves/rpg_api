import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importando o Zeep e seus utilitários
from zeep import AsyncClient
from zeep.transports import AsyncTransport
from zeep.exceptions import Fault
from zeep.helpers import serialize_object

app = FastAPI(title="Quest Board — API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICO_HEROI = "http://localhost:8001"
SERVICO_MISSAO = "http://localhost:8002"
SERVICO_LOJA = "http://localhost:5114"
URL_GATEWAY = "http://localhost:8000"


# ── Configuração Zeep (Lazy Load) ────────────────────────────
soap_client_instance = None

def get_soap_client() -> AsyncClient:
    global soap_client_instance
    if soap_client_instance is None:
        # Só tenta conectar e baixar o WSDL na primeira vez que for chamado
        transport = AsyncTransport(client=httpx.AsyncClient(timeout=10.0))
        wsdl_url = f"{SERVICO_LOJA}/Service.asmx?WSDL"
        soap_client_instance = AsyncClient(wsdl_url, transport=transport)
    return soap_client_instance
# ─────────────────────────────────────────────────────────────


def envelope_hateoas(data: dict, path: str) -> dict:
    return {
        "data": data,
        "_gateway": {
            "service_routed": path,
            "links": {
                "self": f"{URL_GATEWAY}{path}",
                "heroi": f"{URL_GATEWAY}/api/heroes/1",
                "missoes": f"{URL_GATEWAY}/api/quests",
            },
        },
    }


async def encaminhar(
    method: str, url: str, path: str, body: dict | None = None
) -> JSONResponse:
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                resp = await client.get(url, timeout=5.0)
            elif method == "POST":
                resp = await client.post(url, json=body, timeout=5.0)
            elif method == "PATCH":
                resp = await client.patch(url, json=body, timeout=5.0)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            if resp.status_code >= 400:
                return JSONResponse(status_code=resp.status_code, content=resp.json())

            return JSONResponse(
                status_code=resp.status_code,
                content=envelope_hateoas(resp.json(), path),
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {url}")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Service timeout")


# ── Hero routes ──────────────────────────────────────────────

@app.get("/api/heroes/{hero_id}")
async def obter_heroi(hero_id: str):
    return await encaminhar(
        "GET", f"{SERVICO_HEROI}/heroes/{hero_id}", f"/api/heroes/{hero_id}"
    )

@app.get("/api/heroes/{hero_id}/stats")
async def obter_estatisticas_heroi(hero_id: str):
    return await encaminhar(
        "GET",
        f"{SERVICO_HEROI}/heroes/{hero_id}/stats",
        f"/api/heroes/{hero_id}/stats",
    )

@app.patch("/api/heroes/{hero_id}/xp")
async def adicionar_xp(hero_id: str, request: Request):
    body = await request.json()
    return await encaminhar(
        "PATCH",
        f"{SERVICO_HEROI}/heroes/{hero_id}/xp",
        f"/api/heroes/{hero_id}/xp",
        body,
    )

@app.patch("/api/heroes/{hero_id}/gold")
async def alterar_ouro(hero_id: str, request: Request):
    body = await request.json()
    return await encaminhar(
        "PATCH",
        f"{SERVICO_HEROI}/heroes/{hero_id}/gold",
        f"/api/heroes/{hero_id}/gold",
        body,
    )


# ── Quest routes ─────────────────────────────────────────────

@app.get("/api/quests")
async def listar_missoes(status: str = None):
    url = f"{SERVICO_MISSAO}/quests"
    if status:
        url += f"?status={status}"
    return await encaminhar("GET", url, "/api/quests")

@app.get("/api/quests/{quest_id}")
async def obter_missao(quest_id: str):
    return await encaminhar(
        "GET", f"{SERVICO_MISSAO}/quests/{quest_id}", f"/api/quests/{quest_id}"
    )

@app.post("/api/quests/{quest_id}/accept")
async def aceitar_missao(quest_id: str, request: Request):
    body = await request.json()
    return await encaminhar(
        "POST",
        f"{SERVICO_MISSAO}/quests/{quest_id}/accept",
        f"/api/quests/{quest_id}/accept",
        body,
    )

@app.post("/api/quests/{quest_id}/complete")
async def concluir_missao(quest_id: str):
    return await encaminhar(
        "POST",
        f"{SERVICO_MISSAO}/quests/{quest_id}/complete",
        f"/api/quests/{quest_id}/complete",
    )


# ── Shop routes (SOAP → gateway com ZEEP) ────────────────────

@app.get("/api/shop/items")
async def listar_itens_loja():
    try:
        # Pega a instância do cliente (cria se não existir)
        client = get_soap_client()
        resultado_soap = await client.service.ObterItens()
        
        # O serialize_object transforma os tipos do Zeep em listas e dicts nativos
        itens_brutos = serialize_object(resultado_soap)
        
        itens = []
        # O retorno costuma ser uma lista se o C# retorna um List<ShopItem>
        # Se for None, lidamos com isso graciosamente
        if itens_brutos:
            for item in itens_brutos:
                itens.append({
                    "id": item.get("Id", 0),
                    "nome": item.get("Nome", ""),
                    "preco": item.get("Preco", 0),
                    "raridade": item.get("Raridade", ""),
                })

        return JSONResponse(
            content=envelope_hateoas({"itens": itens}, "/api/shop/items"),
        )
    except Fault as e:
        raise HTTPException(status_code=502, detail=f"Erro no serviço SOAP: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Shop service unavailable: {e}")


@app.post("/api/shop/buy")
async def comprar_item(request: Request):
    body = await request.json()
    hero_id = body.get("hero_id")
    item_id = body.get("item_id")
    quantidade = body.get("quantidade", 1)
    
    if quantidade <= 0:
        return JSONResponse(status_code=400, content=envelope_hateoas({
            "success": False,
            "status_code": "QuantidadeInvalida",
            "message": "Quantidade deve ser maior que 0.",
        }, "/api/shop/buy"))
    
    try:
        # Busca os itens de forma limpa usando Zeep para descobrir o preço
        client = get_soap_client() 
        resultado_soap = await client.service.ObterItens()
        itens_loja = serialize_object(resultado_soap) or []
        
        preco = None
        for item in itens_loja:
            if item.get("Id") == item_id:
                preco = item.get("Preco", 0)
                break
                
        if preco is None:
            return JSONResponse(status_code=404, content=envelope_hateoas({
                "success": False,
                "status_code": "ItemNaoEncontrado",
                "message": f"Item {item_id} não encontrado na loja.",
            }, "/api/shop/buy"))
            
        preco_total = preco * quantidade

    except Exception as e:
        return JSONResponse(status_code=502, content=envelope_hateoas({
            "success": False,
            "status_code": "ErroAoFetchItens",
            "message": "Erro ao buscar itens da loja para validação.",
        }, "/api/shop/buy"))

    # REST: Validação de saldo (mantida exatamente como você fez)
    try:
        async with httpx.AsyncClient() as client:
            hero_resp = await client.get(f"{SERVICO_HEROI}/heroes/{hero_id}", timeout=5.0)
            if hero_resp.status_code >= 400:
                return JSONResponse(status_code=502, content=envelope_hateoas({
                    "success": False,
                    "status_code": "ErroAoFetchHeroi",
                    "message": "Falha ao buscar informações do herói.",
                }, "/api/shop/buy"))
            
            hero_json = hero_resp.json()
            
            hero_gold = None
            if isinstance(hero_json, dict):
                if "gold" in hero_json: hero_gold = hero_json.get("gold")
                elif "data" in hero_json and isinstance(hero_json["data"], dict): hero_gold = hero_json["data"].get("gold")
                elif "ouro" in hero_json: hero_gold = hero_json.get("ouro")
            
            try: hero_gold = int(hero_gold) if hero_gold is not None else None
            except (ValueError, TypeError): hero_gold = None
            
            if hero_gold is None:
                return JSONResponse(status_code=502, content=envelope_hateoas({
                    "success": False,
                    "status_code": "ErroAoFetchOuro",
                    "message": f"Falha ao ler saldo do herói. Resposta: {hero_json}",
                }, "/api/shop/buy"))

            if hero_gold < preco_total:
                return JSONResponse(status_code=402, content=envelope_hateoas({
                    "success": False,
                    "status_code": "SaldoInsuficiente",
                    "message": f"Saldo insuficiente: precisa de {preco_total}, tem {hero_gold}.",
                    "hero_id": hero_id,
                    "preco_total": preco_total,
                    "hero_gold": hero_gold,
                }, "/api/shop/buy"))
    except Exception as e:
        return JSONResponse(status_code=502, content=envelope_hateoas({
            "success": False,
            "status_code": "ErroValidacao",
            "message": f"Erro durante validação de saldo: {str(e)}",
        }, "/api/shop/buy"))

    # ── Nova Requisição SOAP Elegante com Zeep ──
    try:
        # Enviamos um dicionário que mapeia os campos exigidos pela classe `request` no C#
        resposta_compra = await client.service.ComprarItem( 
            request={
                "HeroId": hero_id,
                "ItemId": item_id,
                "Quantidade": quantidade
            }
        )
        
        # Convertendo o resultado em Dict para extrair os dados facilmente
        resultado = serialize_object(resposta_compra)

        success = resultado.get("Success", False)
        status_code = resultado.get("StatusCode", "")
        message = resultado.get("Message", "")

        hero_update_info = None
        if success and preco_total is not None:
            try:
                patch_body = {"quantidade": -preco_total}
                hero_resp = await encaminhar(
                    "PATCH",
                    f"{SERVICO_HEROI}/heroes/{hero_id}/gold",
                    f"/api/heroes/{hero_id}/gold",
                    patch_body,
                )
                hero_update_info = {"status_code": hero_resp.status_code}
            except Exception:
                hero_update_info = {"error": "failed to update hero gold"}

        return JSONResponse(
            content=envelope_hateoas(
                {
                    "success": success,
                    "status_code": status_code,
                    "message": message,
                    "hero_id": hero_id,
                    "item_id": item_id,
                    "quantidade": quantidade,
                    "preco_total": preco_total,
                    "hero_update": hero_update_info,
                },
                "/api/shop/buy",
            ),
        )
    except Fault as e:
         raise HTTPException(status_code=502, detail=f"Erro interno da Loja (SOAP): {e.message}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Shop service error: {e}")


# ── Root ─────────────────────────────────────────────────────

@app.get("/")
def raiz():
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "routes": {
            "heroi": f"{URL_GATEWAY}/api/heroes/{{hero_id}}",
            "estatisticas_heroi": f"{URL_GATEWAY}/api/heroes/{{hero_id}}/stats",
            "adicionar_xp": f"{URL_GATEWAY}/api/heroes/{{hero_id}}/xp",
            "missoes": f"{URL_GATEWAY}/api/quests",
            "detalhe_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}",
            "aceitar_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}/accept",
            "concluir_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}/complete",
            "itens_loja": f"{URL_GATEWAY}/api/shop/items",
            "comprar_item": f"{URL_GATEWAY}/api/shop/buy",
        },
    }
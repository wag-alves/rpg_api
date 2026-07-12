import os
import sys
import unicodedata
import httpx
import json
import asyncio
import websockets
import grpc
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importando o Zeep e seus utilitários
from zeep import AsyncClient
from zeep.transports import AsyncTransport
from zeep.exceptions import Fault
from zeep.helpers import serialize_object

# ── Inventory Service (gRPC) — reaproveita os stubs gerados em
#    backend/inventory_service/ a partir de inventory.proto ────
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "inventory_service")
)
import inventory_pb2
import inventory_pb2_grpc

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
SERVICO_BOSS = "http://localhost:8080"
SERVICO_INVENTARIO = "localhost:50051"  # gRPC, sem esquema (grpc.aio usa host:porta)
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


# ── Configuração gRPC (Lazy Load) — Inventory Service ─────────
inventory_channel = None
inventory_stub = None

def get_inventory_stub() -> "inventory_pb2_grpc.InventoryServiceStub":
    global inventory_channel, inventory_stub
    if inventory_stub is None:
        # Canal gRPC único e assíncrono, reaproveitado entre requisições
        inventory_channel = grpc.aio.insecure_channel(SERVICO_INVENTARIO)
        inventory_stub = inventory_pb2_grpc.InventoryServiceStub(inventory_channel)
    return inventory_stub


def item_para_dict(item: "inventory_pb2.Item") -> dict:
    return {
        "id": item.id,
        "nome": item.nome,
        "tipo": item.tipo,
        "raridade": item.raridade,
        "quantidade": item.quantidade,
        "heroi_id": item.heroi_id,
    }


# Os itens da loja (SOAP) não têm campo "tipo" — inferimos a partir do id
# fixo do seed e, como fallback, de palavras-chave no nome do item.
TIPO_POR_ITEM_ID_LOJA = {1: "arma", 2: "pocao", 3: "armadura"}

def tipo_por_item_loja(item_id, nome: str) -> str:
    if item_id in TIPO_POR_ITEM_ID_LOJA:
        return TIPO_POR_ITEM_ID_LOJA[item_id]
    nome_lower = (nome or "").lower()
    if any(p in nome_lower for p in ("espada", "arco", "machado", "adaga", "cajado")):
        return "arma"
    if any(p in nome_lower for p in ("escudo", "armadura", "elmo", "peitoral")):
        return "armadura"
    if any(p in nome_lower for p in ("poção", "pocao", "elixir")):
        return "pocao"
    return "material"


RARIDADES_VALIDAS = {"comum", "raro", "epico", "lendario"}

def normalizar_raridade(raridade: str) -> str:
    if not raridade:
        return "comum"
    sem_acento = unicodedata.normalize("NFKD", raridade).encode("ascii", "ignore").decode()
    texto = sem_acento.lower().strip()
    return texto if texto in RARIDADES_VALIDAS else "comum"
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
        
        item_comprado = None
        for item in itens_loja:
            if item.get("Id") == item_id:
                item_comprado = item
                break

        if item_comprado is None:
            return JSONResponse(status_code=404, content=envelope_hateoas({
                "success": False,
                "status_code": "ItemNaoEncontrado",
                "message": f"Item {item_id} não encontrado na loja.",
            }, "/api/shop/buy"))

        preco = item_comprado.get("Preco", 0)
        preco_total = preco * quantidade

    except Exception as e:
        return JSONResponse(status_code=502, content=envelope_hateoas({
            "success": False,
            "status_code": "ErroAoFetchItens",
            "message": "Erro ao buscar itens da loja para validação.",
        }, "/api/shop/buy"))

    # REST: Validação de saldo do herói antes de chamar o SOAP para comprar
    try:
        async with httpx.AsyncClient() as http_client:
            hero_resp = await http_client.get(f"{SERVICO_HEROI}/heroes/{hero_id}", timeout=5.0)
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

    try:
        # Enviamos um dicionário que mapeia os campos exigidos pela classe `request` no C#
        resposta_compra = await client.service.ComprarItem( 
            request={
                "HeroId": int(hero_id),
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

        # Item comprado na loja (SOAP) é registrado no inventário do herói via gRPC.
        # É assim — e só assim — que um item entra no inventário: comprando na loja.
        inventory_update = None
        if success:
            try:
                grpc_stub = get_inventory_stub()
                add_req = inventory_pb2.AdicionarItemRequest(
                    nome=item_comprado.get("Nome", f"Item {item_id}"),
                    tipo=tipo_por_item_loja(item_id, item_comprado.get("Nome", "")),
                    raridade=normalizar_raridade(item_comprado.get("Raridade", "")),
                    quantidade=quantidade,
                    heroi_id=str(hero_id),
                )
                novo_item = await grpc_stub.AdicionarItem(add_req, timeout=5.0)
                inventory_update = {"id": novo_item.id, "nome": novo_item.nome}
            except grpc.aio.AioRpcError as e:
                inventory_update = {"error": f"falha ao registrar no inventário (gRPC): {e.details()}"}

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
                    "inventory_update": inventory_update,
                },
                "/api/shop/buy",
            ),
        )
    except Fault as e:
         raise HTTPException(status_code=502, detail=f"Erro interno da Loja (SOAP): {e.message}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Shop service error: {e}")


# ── Inventory routes (REST → gRPC) ────────────────────────────
# O gateway continua expondo REST para o frontend; internamente ele é um
# CLIENTE gRPC do Inventory Service (backend/inventory_service), demonstrando
# o padrão "gRPC internamente, REST na borda".

@app.post("/api/inventory/items")
async def adicionar_item_inventario(request: Request):
    body = await request.json()
    stub = get_inventory_stub()
    try:
        req = inventory_pb2.AdicionarItemRequest(
            nome=body.get("nome", ""),
            tipo=body.get("tipo", ""),
            raridade=body.get("raridade", ""),
            quantidade=int(body.get("quantidade", 1)),
            heroi_id=body.get("heroi_id", ""),
        )
        item = await stub.AdicionarItem(req, timeout=5.0)
        return JSONResponse(
            content=envelope_hateoas(item_para_dict(item), "/api/inventory/items")
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=503, detail=f"Inventory service (gRPC) indisponível: {e.details()}"
        )


@app.get("/api/inventory/{heroi_id}")
async def listar_inventario(heroi_id: str):
    stub = get_inventory_stub()
    try:
        resp = await stub.ListarInventario(
            inventory_pb2.ListarInventarioRequest(heroi_id=heroi_id), timeout=5.0
        )
        data = {
            "heroi_id": resp.heroi_id,
            "total_itens": resp.total_itens,
            "itens": [item_para_dict(i) for i in resp.itens],
        }
        return JSONResponse(
            content=envelope_hateoas(data, f"/api/inventory/{heroi_id}")
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=503, detail=f"Inventory service (gRPC) indisponível: {e.details()}"
        )


@app.get("/api/inventory/item/{item_id}")
async def consultar_item_inventario(item_id: str):
    stub = get_inventory_stub()
    try:
        item = await stub.ConsultarItem(
            inventory_pb2.ConsultarItemRequest(id=item_id), timeout=5.0
        )
        return JSONResponse(
            content=envelope_hateoas(item_para_dict(item), f"/api/inventory/item/{item_id}")
        )
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        raise HTTPException(
            status_code=503, detail=f"Inventory service (gRPC) indisponível: {e.details()}"
        )


@app.delete("/api/inventory/item/{item_id}")
async def remover_item_inventario(item_id: str):
    stub = get_inventory_stub()
    try:
        resp = await stub.RemoverItem(
            inventory_pb2.RemoverItemRequest(id=item_id), timeout=5.0
        )
        data = {"sucesso": resp.sucesso, "mensagem": resp.mensagem}
        return JSONResponse(
            content=envelope_hateoas(data, f"/api/inventory/item/{item_id}")
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=503, detail=f"Inventory service (gRPC) indisponível: {e.details()}"
        )


# ── Checkout / Checkin ──────────────────────────────────────

@app.post("/api/heroes/checkout")
async def checkout_heroi():
    return await encaminhar(
        "POST", f"{SERVICO_HEROI}/heroes/checkout", "/api/heroes/checkout"
    )

@app.post("/api/heroes/{hero_id}/checkin")
async def checkin_heroi(hero_id: str):
    return await encaminhar(
        "POST", f"{SERVICO_HEROI}/heroes/{hero_id}/checkin", f"/api/heroes/{hero_id}/checkin"
    )


# ── Internal: Boss service uses this to get hero pool ───────

@app.get("/api/boss/hero-pool")
async def boss_hero_pool():
    return await encaminhar("GET", f"{SERVICO_HEROI}/heroes", "/api/boss/hero-pool")


# ── Boss routes ─────────────────────────────────────────────

@app.post("/api/boss/spawn")
async def spawn_boss():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{SERVICO_BOSS}/spawn", timeout=5.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Boss service unavailable")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Boss service timeout")


@app.websocket("/ws/boss")
async def boss_websocket(ws_in: WebSocket):
    await ws_in.accept()
    try:
        async with websockets.connect("ws://localhost:8080/ws") as ws_out:
            async def forward_to_client():
                try:
                    async for msg in ws_out:
                        await ws_in.send_text(msg)
                except WebSocketDisconnect:
                    pass

            async def forward_to_server():
                try:
                    while True:
                        data = await ws_in.receive_text()
                        await ws_out.send(data)
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(
                forward_to_client(),
                forward_to_server(),
            )
    except Exception:
        try:
            await ws_in.close()
        except RuntimeError:
            pass


# ── Root ─────────────────────────────────────────────────────

@app.get("/")
def raiz():
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "routes": {
            "heroi": f"{URL_GATEWAY}/api/heroes/{{hero_id}}",
            "estatisticas_heroi": f"{URL_GATEWAY}/api/heroes/{{hero_id}}/stats",
            "checkout": f"{URL_GATEWAY}/api/heroes/checkout",
            "checkin": f"{URL_GATEWAY}/api/heroes/{{hero_id}}/checkin",
            "adicionar_xp": f"{URL_GATEWAY}/api/heroes/{{hero_id}}/xp",
            "missoes": f"{URL_GATEWAY}/api/quests",
            "detalhe_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}",
            "aceitar_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}/accept",
            "concluir_missao": f"{URL_GATEWAY}/api/quests/{{quest_id}}/complete",
            "itens_loja": f"{URL_GATEWAY}/api/shop/items",
            "comprar_item": f"{URL_GATEWAY}/api/shop/buy",
            "inventario": f"{URL_GATEWAY}/api/inventory/{{heroi_id}}",
            "adicionar_item_inventario": f"{URL_GATEWAY}/api/inventory/items",
            "consultar_item_inventario": f"{URL_GATEWAY}/api/inventory/item/{{item_id}}",
            "remover_item_inventario": f"{URL_GATEWAY}/api/inventory/item/{{item_id}}",
            "boss_spawn": f"{URL_GATEWAY}/api/boss/spawn",
            "boss_websocket": f"{URL_GATEWAY}/ws/boss",
        },
    }
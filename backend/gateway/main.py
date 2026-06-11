import anyio
import httpx
import xml.etree.ElementTree as ET
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import websockets

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

# Namespaces SOAP do shop_service (C# / SoapCore)
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TEMP_NS = "http://tempuri.org/"
DC_NS = "http://schemas.datacontract.org/2004/07/shop_service.DTOs"


def envelope_hateoas(data: dict, path: str) -> dict:
    """Wrap response with gateway-level HATEOAS links."""
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


# ── SOAP helpers (shop_service .NET / SoapCore) ──────────────


def _soap_envelope(body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}">'
        f"<soap:Body>{body_xml}</soap:Body>"
        "</soap:Envelope>"
    )


async def _soap_request(action: str, body_xml: str) -> ET.Element:
    envelope = _soap_envelope(body_xml)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SERVICO_LOJA}/Service.asmx",
            content=envelope,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f"{TEMP_NS}IShopService/{action}",
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Shop service error (HTTP {resp.status_code})",
            )
        return ET.fromstring(resp.content)


async def _extrair_resultado_soap(xml_root: ET.Element, operacao: str) -> ET.Element:
    body = xml_root.find(f"{{{SOAP_NS}}}Body")
    if body is None:
        raise HTTPException(status_code=502, detail="SOAP: body not found")
    response_elem = body.find(f"{{{TEMP_NS}}}{operacao}Response")
    if response_elem is None:
        raise HTTPException(status_code=502, detail=f"SOAP: {operacao}Response not found")
    result = response_elem.find(f"{{{TEMP_NS}}}{operacao}Result")
    if result is None:
        raise HTTPException(status_code=502, detail=f"SOAP: {operacao}Result not found")
    return result


# ── Hero routes ──────────────────────────────────────────────


@app.get("/api/heroes")
async def listar_herois():
    return await encaminhar("GET", f"{SERVICO_HEROI}/heroes", "/api/heroes")


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


# ── Shop routes (SOAP → gateway) ─────────────────────────────


@app.get("/api/shop/items")
async def listar_itens_loja():
    try:
        root = await _soap_request(
            "ObterItens",
            f'<ObterItens xmlns="{TEMP_NS}" />',
        )
        result = await _extrair_resultado_soap(root, "ObterItens")

        itens = []
        for item_elem in result.findall(f"{{{DC_NS}}}ShopItem"):
            itens.append(
                {
                    "id": int(item_elem.findtext(f"{{{DC_NS}}}Id", "0")),
                    "nome": item_elem.findtext(f"{{{DC_NS}}}Nome", ""),
                    "preco": int(item_elem.findtext(f"{{{DC_NS}}}Preco", "0")),
                    "raridade": item_elem.findtext(f"{{{DC_NS}}}Raridade", ""),
                }
            )

        return JSONResponse(
            content=envelope_hateoas({"itens": itens}, "/api/shop/items"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Shop service unavailable: {e}"
        )


@app.post("/api/shop/buy")
async def comprar_item(request: Request):
    body = await request.json()
    hero_id = body.get("hero_id")
    item_id = body.get("item_id")
    quantidade = body.get("quantidade", 1)
    # Try to resolve item price before attempting purchase so we can update hero gold
    preco_total = None
    try:
        root_items = await _soap_request(
            "ObterItens",
            f'<ObterItens xmlns="{TEMP_NS}" />',
        )
        items_result = await _extrair_resultado_soap(root_items, "ObterItens")
        preco = 0
        for item_elem in items_result.findall(f"{{{DC_NS}}}ShopItem"):
            if int(item_elem.findtext(f"{{{DC_NS}}}Id", "0")) == int(item_id):
                preco = int(item_elem.findtext(f"{{{DC_NS}}}Preco", "0"))
                break
        preco_total = preco * (quantidade if quantidade > 0 else 1)
    except Exception:
        preco_total = None

    body_xml = (
        f'<ComprarItem xmlns="{TEMP_NS}">'
        f'<request xmlns:d4p1="{DC_NS}">'
        f"<d4p1:HeroId>{hero_id}</d4p1:HeroId>"
        f"<d4p1:ItemId>{item_id}</d4p1:ItemId>"
        f"<d4p1:Quantidade>{quantidade}</d4p1:Quantidade>"
        f"</request>"
        f"</ComprarItem>"
    )

    try:
        # Ensure hero has enough gold before calling shop service
        if preco_total is not None:
            try:
                async with httpx.AsyncClient() as client:
                    hero_resp = await client.get(f"{SERVICO_HEROI}/heroes/{hero_id}", timeout=5.0)
                    if hero_resp.status_code >= 400:
                        raise HTTPException(status_code=502, detail="Failed to fetch hero info")
                    hero_json = hero_resp.json()
                    # hero service responses are plain JSON; when routed via gateway they wrap, but here we call service directly
                    hero_gold = hero_json.get("gold") or hero_json.get("ouro") or hero_json.get("data", {}).get("gold")
                    if hero_gold is None:
                        # try nested structure
                        hero_gold = hero_json.get("data", {}).get("gold")
                    try:
                        hero_gold = int(hero_gold)
                    except Exception:
                        hero_gold = None

                    if hero_gold is not None and preco_total is not None and hero_gold < preco_total:
                        return JSONResponse(status_code=400, content=envelope_hateoas({
                            "success": False,
                            "status_code": "SaldoInsuficiente",
                            "message": f"Saldo insuficiente: precisa de {preco_total}, tem {hero_gold}.",
                            "hero_id": hero_id,
                            "preco_total": preco_total,
                        }, "/api/shop/buy"))
            except HTTPException:
                raise
            except Exception:
                # If we couldn't verify hero balance, proceed and let downstream handle consistency
                pass

        root = await _soap_request("ComprarItem", body_xml)
        result = await _extrair_resultado_soap(root, "ComprarItem")

        success = (
            result.findtext(f"{{{DC_NS}}}Success", "false").lower() == "true"
        )
        status_code = result.findtext(f"{{{DC_NS}}}StatusCode", "")
        message = result.findtext(f"{{{DC_NS}}}Message", "")

        # If shop reports success and we know the price, update the hero's gold in hero service
        hero_update_info = None
        if success and preco_total is not None:
            try:
                # debit the hero's gold by preco_total
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Shop service error: {e}"
        )


# ── Trade WebSocket Proxy ────────────────────────────────────

SERVICO_TRADE = "ws://localhost:8080"

@app.websocket("/ws/trade")
async def trade_proxy(websocket: WebSocket):
    await websocket.accept()

    hero_id = websocket.query_params.get("hero_id", "")
    go_url = f"{SERVICO_TRADE}/ws/trade?hero_id={hero_id}"

    try:
        async with websockets.connect(go_url) as go_ws:
            async def react_to_go():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await go_ws.send(msg)
                except WebSocketDisconnect:
                    pass

            async def go_to_react():
                try:
                    async for msg in go_ws:
                        await websocket.send_text(msg)
                except websockets.exceptions.ConnectionClosed:
                    pass

            async with anyio.create_task_group() as tg:
                tg.start_soon(react_to_go)
                tg.start_soon(go_to_react)
    except websockets.exceptions.WebSocketException:
        await websocket.close(code=1011, reason="Trade service unavailable")
    except Exception:
        await websocket.close(code=1011, reason="Internal gateway error")


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
            "herois": f"{URL_GATEWAY}/api/heroes",
            "troca_websocket": f"{URL_GATEWAY}/ws/trade?hero_id={{hero_id}}",
        },
    }

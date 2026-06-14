import httpx
import xml.etree.ElementTree as ET
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    
    # Valida quantidade
    if quantidade <= 0:
        return JSONResponse(status_code=400, content=envelope_hateoas({
            "success": False,
            "status_code": "QuantidadeInvalida",
            "message": "Quantidade deve ser maior que 0.",
        }, "/api/shop/buy"))
    
    # Obtém o preço do item
    try:
        root_items = await _soap_request(
            "ObterItens",
            f'<ObterItens xmlns="{TEMP_NS}" />',
        )
        items_result = await _extrair_resultado_soap(root_items, "ObterItens")
        preco = None
        for item_elem in items_result.findall(f"{{{DC_NS}}}ShopItem"):
            if int(item_elem.findtext(f"{{{DC_NS}}}Id", "0")) == int(item_id):
                preco = int(item_elem.findtext(f"{{{DC_NS}}}Preco", "0"))
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
            "message": f"Erro ao buscar itens da loja.",
        }, "/api/shop/buy"))

    # Validação de saldo ANTES de enviar para o shop_service
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
            
            # Tenta extrair ouro em várias formas possíveis
            hero_gold = None
            if isinstance(hero_json, dict):
                # Caso 1: direto no hero_json (hero_service retorna direto)
                if "gold" in hero_json:
                    hero_gold = hero_json.get("gold")
                # Caso 2: dentro de data (se passar pelo gateway)
                elif "data" in hero_json and isinstance(hero_json["data"], dict):
                    hero_gold = hero_json["data"].get("gold")
                # Caso 3: nome alternativo
                elif "ouro" in hero_json:
                    hero_gold = hero_json.get("ouro")
            
            # Converte para int
            try:
                hero_gold = int(hero_gold) if hero_gold is not None else None
            except (ValueError, TypeError):
                hero_gold = None
            
            if hero_gold is None:
                return JSONResponse(status_code=502, content=envelope_hateoas({
                    "success": False,
                    "status_code": "ErroAoFetchOuro",
                    "message": f"Falha ao ler saldo do herói. Resposta: {hero_json}",
                }, "/api/shop/buy"))

            # Validação crítica: saldo insuficiente
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

    # Envia requisição SOAP para o shop_service
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

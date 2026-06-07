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

        return JSONResponse(
            content=envelope_hateoas(
                {
                    "success": result.findtext(f"{{{DC_NS}}}Success", "false").lower()
                    == "true",
                    "status_code": result.findtext(f"{{{DC_NS}}}StatusCode", ""),
                    "message": result.findtext(f"{{{DC_NS}}}Message", ""),
                    "hero_id": hero_id,
                    "item_id": item_id,
                    "quantidade": quantidade,
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

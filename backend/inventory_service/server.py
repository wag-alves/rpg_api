from concurrent import futures
import uuid
import logging

import grpc

import inventory_pb2
import inventory_pb2_grpc

logging.basicConfig(level=logging.INFO, format="[servidor] %(message)s")
log = logging.getLogger(__name__)


class InventoryServiceServicer(inventory_pb2_grpc.InventoryServiceServicer):
    """Implementação dos métodos remotos definidos em inventory.proto."""

    def __init__(self):
        # Armazenamento em memória: id do item -> dict com os dados do item
        self._itens = {}

    def _to_proto(self, item: dict) -> inventory_pb2.Item:
        return inventory_pb2.Item(
            id=item["id"],
            nome=item["nome"],
            tipo=item["tipo"],
            raridade=item["raridade"],
            quantidade=item["quantidade"],
            heroi_id=item["heroi_id"],
        )

    def AdicionarItem(self, request, context):
        item_id = str(uuid.uuid4())[:8]
        item = {
            "id": item_id,
            "nome": request.nome,
            "tipo": request.tipo,
            "raridade": request.raridade,
            "quantidade": request.quantidade,
            "heroi_id": request.heroi_id,
        }
        self._itens[item_id] = item
        log.info(
            "AdicionarItem -> %s '%s' (x%d) para heroi_id=%s [id=%s]",
            item["tipo"], item["nome"], item["quantidade"], item["heroi_id"], item_id,
        )
        return self._to_proto(item)

    def ListarInventario(self, request, context):
        itens_do_heroi = [
            self._to_proto(item)
            for item in self._itens.values()
            if item["heroi_id"] == request.heroi_id
        ]
        log.info(
            "ListarInventario -> heroi_id=%s (%d itens encontrados)",
            request.heroi_id, len(itens_do_heroi),
        )
        return inventory_pb2.InventarioResponse(
            heroi_id=request.heroi_id,
            itens=itens_do_heroi,
            total_itens=len(itens_do_heroi),
        )

    def ConsultarItem(self, request, context):
        item = self._itens.get(request.id)
        if item is None:
            log.info("ConsultarItem -> id=%s NAO ENCONTRADO", request.id)
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Item com id={request.id} não encontrado")
            return inventory_pb2.Item()
        log.info("ConsultarItem -> id=%s encontrado (%s)", request.id, item["nome"])
        return self._to_proto(item)

    def RemoverItem(self, request, context):
        item = self._itens.pop(request.id, None)
        if item is None:
            log.info("RemoverItem -> id=%s NAO ENCONTRADO", request.id)
            return inventory_pb2.RemoverItemResponse(
                sucesso=False,
                mensagem=f"Item com id={request.id} não encontrado",
            )
        log.info("RemoverItem -> id=%s removido (%s)", request.id, item["nome"])
        return inventory_pb2.RemoverItemResponse(
            sucesso=True,
            mensagem=f"Item '{item['nome']}' removido com sucesso",
        )


def serve(port: str = "50051"):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        InventoryServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log.info(f"Inventory Service (gRPC) rodando na porta {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

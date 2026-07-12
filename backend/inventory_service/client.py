import grpc

import inventory_pb2
import inventory_pb2_grpc


def imprimir_item(item: inventory_pb2.Item):
    print(f"  [{item.id}] {item.nome} | tipo={item.tipo} | raridade={item.raridade} "
          f"| qtd={item.quantidade} | heroi_id={item.heroi_id}")


def adicionar_item(stub):
    print("\n-- Adicionar item --")
    nome = input("Nome do item: ")
    tipo = input("Tipo (arma/armadura/pocao/material): ")
    raridade = input("Raridade (comum/raro/epico/lendario): ")
    quantidade = int(input("Quantidade: ") or "1")
    heroi_id = input("ID do herói dono do item: ")

    request = inventory_pb2.AdicionarItemRequest(
        nome=nome, tipo=tipo, raridade=raridade,
        quantidade=quantidade, heroi_id=heroi_id,
    )
    item = stub.AdicionarItem(request)
    print("Item cadastrado com sucesso:")
    imprimir_item(item)


def listar_inventario(stub):
    print("\n-- Listar inventário --")
    heroi_id = input("ID do herói: ")
    request = inventory_pb2.ListarInventarioRequest(heroi_id=heroi_id)
    resposta = stub.ListarInventario(request)
    print(f"Total de itens: {resposta.total_itens}")
    for item in resposta.itens:
        imprimir_item(item)


def consultar_item(stub):
    print("\n-- Consultar item --")
    item_id = input("ID do item: ")
    request = inventory_pb2.ConsultarItemRequest(id=item_id)
    try:
        item = stub.ConsultarItem(request)
        imprimir_item(item)
    except grpc.RpcError as erro:
        print(f"Erro: {erro.code()} - {erro.details()}")


def remover_item(stub):
    print("\n-- Remover item --")
    item_id = input("ID do item: ")
    request = inventory_pb2.RemoverItemRequest(id=item_id)
    resposta = stub.RemoverItem(request)
    print(f"Sucesso={resposta.sucesso} | {resposta.mensagem}")


def menu():
    print("""
==== Inventory Service (Cliente gRPC) ====
1 - Adicionar item
2 - Listar inventário de um herói
3 - Consultar item por id
4 - Remover item
0 - Sair
""")
    return input("Escolha uma opção: ")


def run(endereco: str = "localhost:50051"):
    with grpc.insecure_channel(endereco) as channel:
        stub = inventory_pb2_grpc.InventoryServiceStub(channel)
        print(f"Conectado ao Inventory Service em {endereco}")
        while True:
            opcao = menu()
            if opcao == "1":
                adicionar_item(stub)
            elif opcao == "2":
                listar_inventario(stub)
            elif opcao == "3":
                consultar_item(stub)
            elif opcao == "4":
                remover_item(stub)
            elif opcao == "0":
                print("Encerrando cliente.")
                break
            else:
                print("Opção inválida.")


if __name__ == "__main__":
    run()

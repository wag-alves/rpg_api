using shop_service.Contracts;
using shop_service.DTOs;
using shop_service.Data;
using System.Collections.Generic;

namespace shop_service.Services;

public class ShopService : IShopService
{

    private readonly ShopContext _db;

    public ShopService(ShopContext db)
    {
        _db = db;
    }
    
    public BuyItemResponse ComprarItem(BuyItemRequest request)
    {
        if (!_db.ItensDaLoja.ContainsKey(request.ItemId))
        {
            return new BuyItemResponse { Success = false, StatusCode = "ItemNaoEncontrado", Message = "Este item não existe na loja." };
        }

        if (request.Quantidade <= 0)
        {
            return new BuyItemResponse { Success = false, StatusCode = "QuantidadeInvalida", Message = "Quantidade inválida." };
        }

        var itemDesejado = _db.ItensDaLoja[request.ItemId];

        // Note: wallet / hero balance is the responsibility of Hero Service.
        // The Gateway should verify and debit the hero's gold. Shop only validates item existence and quantity.
        return new BuyItemResponse
        {
            Success = true,
            StatusCode = "Sucesso",
            Message = $"Compra autorizada: {request.Quantidade}x [{itemDesejado.Nome}] ({itemDesejado.Raridade}).",
        };
    }

    public List<ShopItem> ObterItens()
    {
        var itens = new List<ShopItem>();
        foreach (var kvp in _db.ItensDaLoja)
        {
            itens.Add(new ShopItem
            {
                Id = kvp.Key,
                Nome = kvp.Value.Nome,
                Preco = kvp.Value.Preco,
                Raridade = kvp.Value.Raridade
            });
        }
        return itens;
    }
}
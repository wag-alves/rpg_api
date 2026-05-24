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

        if (!_db.CarteiraDosHerois.ContainsKey(request.HeroId))
        {
            return new BuyItemResponse { Success = false, StatusCode = "HeroiNaoEncontrado", Message = "Herói não possui registro financeiro." };
        }

        var itemDesejado = _db.ItensDaLoja[request.ItemId];

        int precoTotal = itemDesejado.Preco * (request.Quantidade > 0 ? request.Quantidade : 1);
        int saldoAtual = _db.CarteiraDosHerois[request.HeroId];

        if (saldoAtual < precoTotal)
        {
            return new BuyItemResponse { Success = false, StatusCode = "SaldoInsuficiente", Message = $"Você precisa de {precoTotal} moedas, mas tem apenas {saldoAtual}." };
        }

        _db.CarteiraDosHerois[request.HeroId] -= precoTotal;

        return new BuyItemResponse 
        { 
            Success = true, 
            StatusCode = "Sucesso", 
            Message = $"Você comprou {request.Quantidade}x [{itemDesejado.Nome}] ({itemDesejado.Raridade})! Novo saldo: {_db.CarteiraDosHerois[request.HeroId]} moedas." 
        };
    }
}
using System.Collections.Generic;
using shop_service.Entities; 

namespace shop_service.Data;

public class ShopContext
{
    public Dictionary<int, Item> ItensDaLoja { get; set; } = new()
    {
        { 1, new Item { Nome = "Espada Básica", Preco = 150, Raridade = "Comum" } },
        { 2, new Item { Nome = "Poção de Vida Média", Preco = 50, Raridade = "Comum" } },
        { 3, new Item { Nome = "Escudo do Dragão", Preco = 500, Raridade = "Épico" } }
    };

    public Dictionary<int, int> CarteiraDosHerois { get; set; } = new()
    {
        { 1, 999 },
        { 99, 200 }, 
        { 55, 10 }   
    };
}
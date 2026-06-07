using System.ServiceModel;
using System.Collections.Generic;
using shop_service.DTOs;

namespace shop_service.Contracts;

[ServiceContract]
public interface IShopService
{
    [OperationContract]
    BuyItemResponse ComprarItem(BuyItemRequest request);

    [OperationContract]
    List<ShopItem> ObterItens();
}
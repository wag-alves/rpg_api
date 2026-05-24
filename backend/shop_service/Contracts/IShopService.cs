using System.ServiceModel;
using shop_service.DTOs;

namespace shop_service.Contracts;

[ServiceContract]
public interface IShopService
{
    [OperationContract]
    BuyItemResponse ComprarItem(BuyItemRequest request);

}
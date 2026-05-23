
using System.ServiceModel;

[ServiceContract]
public interface IShopService
{
    [OperationContract]
    BuyItemResponse ComprarItem(BuyItemRequest request);
}
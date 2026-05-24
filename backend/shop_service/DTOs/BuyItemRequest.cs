using System.Runtime.Serialization;

namespace shop_service.DTOs;

[DataContract]
public class BuyItemRequest
{
    [DataMember]
    public int HeroId { get; set; }

    [DataMember]
    public int ItemId { get; set; }

    [DataMember]
    public int Quantidade { get; set; }
}
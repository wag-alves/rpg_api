using System.Runtime.Serialization;

namespace shop_service.DTOs;

[DataContract]
public class ShopItem
{
    [DataMember]
    public int Id { get; set; }

    [DataMember]
    public string? Nome { get; set; }

    [DataMember]
    public int Preco { get; set; }

    [DataMember]
    public string? Raridade { get; set; }
}

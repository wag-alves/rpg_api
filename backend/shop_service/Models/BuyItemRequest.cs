using System.Runtime.Serialization;

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
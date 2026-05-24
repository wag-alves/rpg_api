using System.Runtime.Serialization;

namespace shop_service.DTOs;

[DataContract]
public class BuyItemResponse
{
    [DataMember]
    public bool Success { get; set; }

    [DataMember]
    public string StatusCode { get; set; }

    [DataMember]
    public string Message { get; set; }
}
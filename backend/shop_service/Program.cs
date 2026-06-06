// var builder = WebApplication.CreateBuilder(args);
// var app = builder.Build();

// app.MapGet("/", () => "Hello World!");

// app.Run();

using SoapCore;
using shop_service.Contracts;
using shop_service.Services;
using shop_service.Data; // Necessário para o ShopContext

var builder = WebApplication.CreateBuilder(args);

// 1. Dizemos ao C# que vamos usar o SoapCore
builder.Services.AddSoapCore();

// 2. Registra o Banco de Dados em Memória para ele não apagar
builder.Services.AddSingleton<ShopContext>();

// 3. Registra o HttpClient para o C# conseguir chamar o FastAPI do Herói
builder.Services.AddHttpClient<ShopService>();

// 4. Registra o nosso serviço para que o servidor saiba que ele existe
builder.Services.AddSingleton<IShopService, ShopService>();

var app = builder.Build();

// Adicione o (IEndpointRouteBuilder) antes do app
((IEndpointRouteBuilder)app).UseSoapEndpoint<IShopService>("/Service.asmx", new SoapEncoderOptions(), SoapSerializer.DataContractSerializer);
app.Run();
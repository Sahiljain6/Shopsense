using Parbad.Builder;
using Parbad.Gateway.ParbadVirtual;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddHttpClient();
builder.Services.AddParbad()
    .ConfigureGateways(gateways =>
    {
        gateways.AddParbadVirtual()
            .WithOptions(options => options.GatewayPath = "/virtual");
    })
    .ConfigureHttpContext(httpContext => httpContext.UseDefaultAspNetCore())
    .ConfigureStorage(storage => storage.UseMemoryCache());

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new
{
    status = "ok",
    paymentProvider = "Parbad Virtual Gateway",
    mode = "sandbox",
    realMoneyPaymentsEnabled = false
}));

app.MapControllers();

// The Virtual Gateway is only mapped in Development. The start endpoint independently
// rejects production use unless an explicit sandbox-only override is configured.
if (app.Environment.IsDevelopment())
{
    app.UseParbadVirtualGateway();
}

await app.RunAsync();

public partial class Program { }

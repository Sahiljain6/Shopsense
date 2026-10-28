using Parbad.Builder;
using Parbad.Gateway.ParbadVirtual;

var builder = WebApplication.CreateBuilder(args);

// Render sets PORT for public web services. Local Docker Compose uses the Dockerfile's 8080 default.
var configuredPort = Environment.GetEnvironmentVariable("PORT");
if (int.TryParse(configuredPort, out var port) && port is > 0 and <= 65535)
{
    builder.WebHost.UseUrls($"http://0.0.0.0:{port}");
}

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

var virtualMode = string.Equals(
    app.Configuration["PARBAD_MODE"], "virtual", StringComparison.OrdinalIgnoreCase);
var productionSandboxOptIn = app.Configuration.GetValue<bool>("PARBAD_ALLOW_VIRTUAL_GATEWAY_IN_PRODUCTION");

// Virtual gateway is enabled in production only for the separately hosted, isolated sandbox stack.
// It remains a simulation and must never be connected to a production order database.
if (virtualMode && (app.Environment.IsDevelopment() || productionSandboxOptIn))
{
    app.UseParbadVirtualGateway();
}

await app.RunAsync();

public partial class Program { }

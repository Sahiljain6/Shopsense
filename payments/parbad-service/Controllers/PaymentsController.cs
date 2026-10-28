using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.WebUtilities;
using Parbad;
using Parbad.AspNetCore;
using Parbad.Gateway.ParbadVirtual;
using ShopSense.ParbadService;

namespace ShopSense.ParbadService.Controllers;

[ApiController]
[Route("api/payments")]
public sealed class PaymentsController : ControllerBase
{
    private const string InternalKeyHeader = "X-ShopSense-Internal-Key";
    private readonly IOnlinePayment _onlinePayment;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly IHostEnvironment _environment;
    private readonly ILogger<PaymentsController> _logger;

    public PaymentsController(
        IOnlinePayment onlinePayment,
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration,
        IHostEnvironment environment,
        ILogger<PaymentsController> logger)
    {
        _onlinePayment = onlinePayment;
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
        _environment = environment;
        _logger = logger;
    }

    [HttpGet("start")]
    public async Task<IActionResult> Start([FromQuery(Name = "token")] string token, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(token) || token.Length is < 32 or > 128)
        {
            return BadRequest("Invalid payment session.");
        }

        if (!IsVirtualGatewayEnabled())
        {
            return StatusCode(StatusCodes.Status503ServiceUnavailable,
                "Parbad Virtual Gateway is sandbox-only and is disabled in this production environment.");
        }

        var backendBase = (_configuration["SHOP_API_BASE_URL"] ?? "").TrimEnd('/');
        var publicBase = (_configuration["PARBAD_PUBLIC_BASE_URL"] ?? "").TrimEnd('/');
        var internalKey = _configuration["PARBAD_INTERNAL_KEY"] ?? "";
        if (string.IsNullOrWhiteSpace(backendBase) ||
            string.IsNullOrWhiteSpace(publicBase) ||
            internalKey.Length < 32)
        {
            return StatusCode(StatusCodes.Status503ServiceUnavailable, "Payment service configuration is incomplete.");
        }

        AuthorizedPayment? payment;
        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Get,
                $"{backendBase}/payments/parbad/authorize?token={Uri.EscapeDataString(token)}");
            request.Headers.TryAddWithoutValidation(InternalKeyHeader, internalKey);
            using var response = await _httpClientFactory.CreateClient("shopsense-api")
                .SendAsync(request, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return StatusCode(
                    response.StatusCode == System.Net.HttpStatusCode.Conflict ? 409 : 400,
                    "The ShopSense payment attempt is invalid, expired, or already being processed.");
            }

            payment = await response.Content.ReadFromJsonAsync<AuthorizedPayment>(
                cancellationToken: cancellationToken);
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            _logger.LogWarning("Payment authorization call failed ({ErrorType}).", exception.GetType().Name);
            return StatusCode(StatusCodes.Status502BadGateway, "Could not validate the checkout with ShopSense.");
        }

        if (payment is null)
        {
            return BadRequest("The payment session could not be validated.");
        }

        var attemptId = payment.AttemptId;
        if (payment.AttemptId <= 0 || payment.TrackingNumber != payment.AttemptId ||
            payment.Amount <= 0 ||
            !string.Equals(payment.Currency, "INR", StringComparison.OrdinalIgnoreCase))
        {
            await NotifyShopSenseAsync(backendBase, internalKey, attemptId, "failed", null, cancellationToken);
            return BadRequest("The checkout amount or currency is not supported by this sandbox.");
        }

        var callbackUrl = $"{publicBase}/api/payments/callback";
        try
        {
            var result = await _onlinePayment.RequestAsync(invoice =>
            {
                invoice.SetCallbackUrl(callbackUrl)
                    .SetAmount(payment.Amount)
                    .SetGateway(ParbadVirtualGateway.Name)
                    .SetTrackingNumber(payment.TrackingNumber);
            }, cancellationToken);

            if (!result.IsSucceed)
            {
                await NotifyShopSenseAsync(backendBase, internalKey, attemptId, "failed", null, cancellationToken);
                return StatusCode(StatusCodes.Status502BadGateway,
                    "The sandbox could not start this payment. No real charge was made.");
            }

            var initiated = await NotifyShopSenseAsync(
                backendBase, internalKey, attemptId, "initiated", null, cancellationToken);
            if (initiated is null)
            {
                await NotifyShopSenseAsync(backendBase, internalKey, attemptId, "failed", null, cancellationToken);
                return StatusCode(StatusCodes.Status502BadGateway,
                    "ShopSense could not register the payment attempt. Please retry checkout.");
            }

            return result.GatewayTransporter.TransportToGateway();
        }
        catch (Exception exception)
        {
            _logger.LogError("Payment start failed ({ErrorType}).", exception.GetType().Name);
            await NotifyShopSenseAsync(backendBase, internalKey, attemptId, "failed", null, cancellationToken);
            return StatusCode(StatusCodes.Status502BadGateway,
                "Could not start the payment sandbox. No real charge was made.");
        }
    }

    [AcceptVerbs("GET", "POST")]
    [Route("callback")]
    public async Task<IActionResult> Callback(CancellationToken cancellationToken)
    {
        if (!IsVirtualGatewayEnabled())
        {
            return StatusCode(StatusCodes.Status503ServiceUnavailable, "Payment callbacks are disabled in this environment.");
        }

        var backendBase = (_configuration["SHOP_API_BASE_URL"] ?? "").TrimEnd('/');
        var internalKey = _configuration["PARBAD_INTERNAL_KEY"] ?? "";
        if (string.IsNullOrWhiteSpace(backendBase) || internalKey.Length < 32)
        {
            return StatusCode(StatusCodes.Status503ServiceUnavailable, "Payment callback configuration is incomplete.");
        }

        try
        {
            var invoice = await _onlinePayment.FetchAsync(cancellationToken);
            var trackingNumber = invoice.TrackingNumber;
            if (trackingNumber <= 0 || trackingNumber > int.MaxValue)
            {
                return Redirect(BuildFrontendReturnUrl("failed", null));
            }

            var attemptId = (int)trackingNumber;
            if (invoice.Status != PaymentFetchResultStatus.ReadyForVerifying)
            {
                // A repeat callback must not downgrade a payment already verified by Parbad.
                if (invoice.IsAlreadyVerified)
                {
                    var alreadyPaid = await NotifyShopSenseAsync(
                        backendBase, internalKey, attemptId, "paid", null, cancellationToken);
                    return Redirect(BuildFrontendReturnUrl(
                        alreadyPaid?.Status == "paid" ? "success" : "failed",
                        alreadyPaid?.OrderId));
                }

                var failed = await NotifyShopSenseAsync(
                    backendBase, internalKey, attemptId, "failed", null, cancellationToken);
                return Redirect(BuildFrontendReturnUrl("failed", failed?.OrderId));
            }

            var verified = await _onlinePayment.VerifyAsync(invoice, cancellationToken);
            if (!verified.IsSucceed)
            {
                var failure = await NotifyShopSenseAsync(
                    backendBase, internalKey, attemptId, "failed", null, cancellationToken);
                return Redirect(BuildFrontendReturnUrl("failed", failure?.OrderId));
            }

            // The order is marked paid only after Parbad reports successful verification.
            var completion = await NotifyShopSenseAsync(
                backendBase,
                internalKey,
                attemptId,
                "paid",
                verified.TransactionCode?.ToString(),
                cancellationToken);

            return Redirect(BuildFrontendReturnUrl(
                completion?.Status == "paid" ? "success" : "failed",
                completion?.OrderId));
        }
        catch (Exception exception)
        {
            _logger.LogWarning("Payment callback could not be verified ({ErrorType}).", exception.GetType().Name);
            return Redirect(BuildFrontendReturnUrl("failed", null));
        }
    }

    private bool IsVirtualGatewayEnabled()
    {
        var configured = string.Equals(
            _configuration["PARBAD_MODE"], "virtual", StringComparison.OrdinalIgnoreCase);
        var productionOverride = _configuration.GetValue<bool>("PARBAD_ALLOW_VIRTUAL_GATEWAY_IN_PRODUCTION");
        return configured && (!_environment.IsProduction() || productionOverride);
    }

    private async Task<PaymentEventResponse?> NotifyShopSenseAsync(
        string backendBase,
        string internalKey,
        int attemptId,
        string status,
        string? transactionCode,
        CancellationToken cancellationToken)
    {
        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Post,
                $"{backendBase}/payments/parbad/events");
            request.Headers.TryAddWithoutValidation(InternalKeyHeader, internalKey);
            request.Content = JsonContent.Create(new PaymentEventRequest(attemptId, status, transactionCode));

            using var response = await _httpClientFactory.CreateClient("shopsense-api")
                .SendAsync(request, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("ShopSense payment event rejected with status {StatusCode}.", (int)response.StatusCode);
                return null;
            }

            return await response.Content.ReadFromJsonAsync<PaymentEventResponse>(
                cancellationToken: cancellationToken);
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            _logger.LogWarning("ShopSense payment event failed ({ErrorType}).", exception.GetType().Name);
            return null;
        }
    }

    private string BuildFrontendReturnUrl(string status, int? orderId)
    {
        var frontendBase = (_configuration["SHOP_FRONTEND_RETURN_URL"] ?? "").Trim();
        if (!Uri.TryCreate(frontendBase, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttps && uri.Host is not "localhost" and not "127.0.0.1"))
        {
            // Do not accept a browser-supplied redirect URL; this fallback is configuration-only.
            frontendBase = "http://localhost:3000/";
        }

        var parameters = new Dictionary<string, string?>
        {
            ["payment"] = status,
        };
        if (orderId.HasValue)
        {
            parameters["order_id"] = orderId.Value.ToString();
        }

        return QueryHelpers.AddQueryString(frontendBase, parameters);
    }
}

using System.Text.Json.Serialization;

namespace ShopSense.ParbadService;

public sealed record AuthorizedPayment(
    [property: JsonPropertyName("attempt_id")] int AttemptId,
    [property: JsonPropertyName("tracking_number")] long TrackingNumber,
    [property: JsonPropertyName("order_id")] int OrderId,
    [property: JsonPropertyName("amount")] decimal Amount,
    [property: JsonPropertyName("currency")] string Currency);

public sealed record PaymentEventRequest(
    [property: JsonPropertyName("attempt_id")] int AttemptId,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("transaction_code")] string? TransactionCode = null);

public sealed record PaymentEventResponse(
    [property: JsonPropertyName("ok")] bool Ok,
    [property: JsonPropertyName("order_id")] int OrderId,
    [property: JsonPropertyName("status")] string Status);

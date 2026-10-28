namespace ShopSense.ParbadService;

public sealed record AuthorizedPayment(
    int AttemptId,
    long TrackingNumber,
    int OrderId,
    decimal Amount,
    string Currency);

public sealed record PaymentEventRequest(
    int AttemptId,
    string Status,
    string? TransactionCode = null);

public sealed record PaymentEventResponse(
    bool Ok,
    int OrderId,
    string Status);

import pytest
from app.services.logistics import lookup_pincode
from app.services.ai import AIOrchestrator


def test_lookup_pincode_valid_metro() -> None:
    res = lookup_pincode("400071")
    assert res["valid"] is True
    assert res["pincode"] == "400071"
    assert res["is_metro"] is True
    assert "Business Days" in res["estimated_days"]
    assert "Maharashtra" in res["state"] or "Mumbai" in res["district"]


def test_lookup_pincode_delhi() -> None:
    res = lookup_pincode("110001")
    assert res["valid"] is True
    assert res["is_metro"] is True
    assert "Delhi" in res["district"] or "Delhi" in res["state"]


def test_lookup_pincode_invalid() -> None:
    res = lookup_pincode("012345")
    assert res["valid"] is False
    assert "Invalid PIN" in res["error"]

    res_short = lookup_pincode("4000")
    assert res_short["valid"] is False


def test_ai_orchestrator_pincode_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("Can you do delivery to 400071?")
    assert chat_res is not None
    assert "Delivery & Shipping Status (PIN: 400071)" in chat_res.answer
    assert "Metro Express Zone" in chat_res.answer


def test_ai_orchestrator_pincode_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("check_delivery_pincode", {"pincode": "560001"})
    import json
    parsed = json.loads(raw)
    assert parsed["valid"] is True
    assert parsed["pincode"] == "560001"
    assert parsed["is_metro"] is True


def test_estimate_shipping_sla_metro_priority() -> None:
    from app.services.logistics import estimate_shipping_sla
    sla = estimate_shipping_sla(is_metro=True, is_express=True)
    assert sla["tier"] == "Same-Day / Next-Day Priority"
    assert sla["min_days"] == 0
    assert sla["max_days"] == 1
    assert sla["eligible_for_instant"] is True


def test_estimate_shipping_sla_metro_standard() -> None:
    from app.services.logistics import estimate_shipping_sla
    sla = estimate_shipping_sla(is_metro=True, is_express=False)
    assert sla["tier"] == "Metro Express"
    assert sla["min_days"] == 1
    assert sla["max_days"] == 2
    assert sla["eligible_for_instant"] is False


def test_estimate_shipping_sla_regional() -> None:
    from app.services.logistics import estimate_shipping_sla
    sla = estimate_shipping_sla(is_metro=False, is_express=False)
    assert sla["tier"] == "Standard Regional"
    assert sla["min_days"] == 3
    assert sla["max_days"] == 5
    assert sla["eligible_for_instant"] is False


def test_lookup_pincode_with_api_key_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    captured_headers = {}
    captured_params = {}

    def mock_get(self, url, headers=None, params=None):
        nonlocal captured_headers, captured_params
        captured_headers = headers or {}
        captured_params = params or {}
        return httpx.Response(
            200,
            json=[{
                "Status": "Success",
                "PostOffice": [{
                    "District": "Pune",
                    "State": "Maharashtra",
                    "Name": "Shivajinagar",
                    "DeliveryStatus": "Deliverable"
                }]
            }],
            request=httpx.Request("GET", url)
        )

    monkeypatch.setenv("PINCODE_API_KEY", "test-secret-key-123")
    monkeypatch.setattr(httpx.Client, "get", mock_get)

    res = lookup_pincode("411005")
    assert res["valid"] is True
    assert res["district"] == "Pune"
    assert captured_headers.get("api-key") == "test-secret-key-123"
    assert captured_headers.get("x-api-key") == "test-secret-key-123"
    assert captured_headers.get("Authorization") == "Bearer test-secret-key-123"
    assert captured_params.get("api_key") == "test-secret-key-123"


def test_lookup_pincode_custom_url_and_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    requested_url = ""

    def mock_get(self, url, headers=None, params=None):
        nonlocal requested_url
        requested_url = url
        return httpx.Response(
            200,
            json={
                "district": "Bengaluru",
                "state": "Karnataka",
                "post_office": "Indiranagar",
                "delivery_status": "Deliverable"
            },
            request=httpx.Request("GET", url)
        )

    monkeypatch.setenv("PINCODE_API_KEY", "custom-key-999")
    monkeypatch.setenv("PINCODE_API_URL", "https://api.pincode-service.com/v1/{pincode}")
    monkeypatch.setattr(httpx.Client, "get", mock_get)

    res = lookup_pincode("560038")
    assert res["valid"] is True
    assert res["district"] == "Bengaluru"
    assert res["state"] == "Karnataka"
    assert res["post_office"] == "Indiranagar"
    assert requested_url == "https://api.pincode-service.com/v1/560038"



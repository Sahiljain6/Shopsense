from app.core import http_client


def test_http_client_is_reused_per_timeout_and_closed_clients_recreate():
    http_client.close_http_clients()

    first = http_client.get_http_client(timeout=7.0)
    second = http_client.get_http_client(timeout=7.0)
    different_timeout = http_client.get_http_client(timeout=8.0)

    assert first is second
    assert different_timeout is not first
    assert first.is_closed is False

    http_client.close_http_clients()
    assert first.is_closed is True
    assert different_timeout.is_closed is True

    recreated = http_client.get_http_client(timeout=7.0)
    assert recreated is not first
    assert recreated.is_closed is False
    http_client.close_http_clients()

"""SSRF validation and safe HTTP fetching for external URLs."""
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB


class SSRFError(ValueError):
    """Raised when a URL violates SSRF security policies."""
    pass


def validate_url(url: str) -> str:
    """Validate a URL against SSRF attack vectors.

    - Restrict scheme to http or https.
    - Restrict port to 80 or 443.
    - Resolve DNS and reject any private, loopback, link-local, multicast,
      or cloud-metadata (169.254.169.254) IP addresses.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string.")

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        raise SSRFError(f"Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SSRFError(f"Prohibited URL scheme '{scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL must include a valid hostname.")

    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in (80, 443):
        raise SSRFError(f"Prohibited port '{port}'. Only ports 80 and 443 are allowed.")

    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError(f"Failed to resolve hostname '{hostname}': {exc}") from exc

    if not addr_info:
        raise SSRFError(f"No IP addresses resolved for hostname '{hostname}'.")

    for entry in addr_info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(f"Invalid resolved IP address: {ip_str}")

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise SSRFError(f"Hostname resolves to prohibited IP address: {ip_str}")

    return url


def safe_fetch_url(
    url: str,
    max_redirects: int = 5,
    timeout: float = 10.0,
    headers: dict[str, str] | None = None
) -> tuple[str, str]:
    """Safely fetch HTML content from a URL with SSRF protection, size caps, and safe redirect validation.

    Returns:
        tuple[str, str]: (final_effective_url, response_text)
    """
    req_headers = headers or {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9"
    }

    current_url = url
    redirect_count = 0

    with httpx.Client(headers=req_headers, timeout=timeout, follow_redirects=False) as client:
        while redirect_count <= max_redirects:
            validated_url = validate_url(current_url)

            with client.stream("GET", validated_url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        break
                    next_url = urljoin(validated_url, location)
                    current_url = next_url
                    redirect_count += 1
                    continue

                response.raise_for_status()

                content_chunks = []
                total_bytes = 0
                for chunk in response.iter_bytes(chunk_size=65536):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_RESPONSE_SIZE:
                        raise SSRFError(f"Response size exceeded limit of {MAX_RESPONSE_SIZE // (1024 * 1024)}MB.")
                    content_chunks.append(chunk)

                encoding = response.encoding or "utf-8"
                html_text = b"".join(content_chunks).decode(encoding, errors="replace")
                return validated_url, html_text

        raise SSRFError(f"Too many redirects (exceeded limit of {max_redirects})")

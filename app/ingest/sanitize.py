from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class URLSanitizationError(ValueError):
    pass


_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}



def _is_blocked_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )



def sanitize_ingestion_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise URLSanitizationError("only http and https URLs are allowed")

    if not parsed.hostname:
        raise URLSanitizationError("URL must include a hostname")

    hostname = parsed.hostname.strip().lower()
    if hostname in _LOCAL_HOSTNAMES:
        raise URLSanitizationError("localhost targets are not allowed")

    try:
        if _is_blocked_ip(hostname):
            raise URLSanitizationError("private or reserved IP targets are not allowed")
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise URLSanitizationError(f"hostname resolution failed: {exc}") from exc

    for info in infos:
        ip_text = info[4][0]
        if _is_blocked_ip(ip_text):
            raise URLSanitizationError("private or reserved IP targets are not allowed")

    return url

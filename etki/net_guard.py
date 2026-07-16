"""SSRF guards for user/config-supplied outbound URLs.

Deliberately narrow: the LLM/embedding/rerank seam legitimately targets localhost and
RFC1918 hosts (Ollama on localhost:11434, a vLLM box on a private/Tailscale IP), so a blanket
private-range block would break the primary use case. What is NEVER a legitimate outbound
target is the link-local range cloud providers use for their instance-metadata service
(169.254.0.0/16 — 169.254.169.254 on AWS/GCP/Azure, plus the IPv6 form), so blocking that
range closes the credential-theft SSRF pivot at zero cost to real deployments.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


def is_cloud_metadata_host(host: str) -> bool:
    """True when `host` is a link-local literal IP (the cloud metadata range)."""
    h = host.lower().strip("[]")  # drop IPv6 brackets
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False  # a hostname: not resolved here (pilot); the literal-IP guard suffices
    return ip.is_link_local


def is_metadata_url(url: str) -> bool:
    """True when `url`'s host is a cloud-metadata (link-local) address."""
    return is_cloud_metadata_host(urlsplit(url.strip()).hostname or "")

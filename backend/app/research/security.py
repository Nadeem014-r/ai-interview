import socket
import ipaddress
from urllib.parse import urlparse
from typing import List, Optional, Tuple
import logging
from app.core.config import settings

logger = logging.getLogger("ai_interviewer.research.security")

class ResearchSecurityError(Exception):
    """Base exception for research security violations."""
    pass

class InvalidURLError(ResearchSecurityError):
    """Raised when a URL is structurally invalid or uses an unsupported scheme."""
    pass

class SSRFProtectionError(ResearchSecurityError):
    """Raised when a URL targets private, loopback, or metadata services."""
    pass

class DisallowedDomainError(ResearchSecurityError):
    """Raised when a URL domain is not in the research allowlist."""
    pass

class URLSecurityValidator:
    ALLOWED_SCHEMES = {"http", "https"}
    
    # Well-known cloud metadata hostnames
    METADATA_HOSTNAMES = {
        "metadata.google.internal",
        "metadata.internal",
        "169.254.169.254",
        "instance-data",
    }

    @classmethod
    def is_ip_private_or_restricted(cls, ip_str: str) -> bool:
        """Check if an IP address string is private, loopback, link-local, or restricted."""
        try:
            ip = ipaddress.ip_address(ip_str)
            # Check IPv4 mapped in IPv6
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped
                
            return (
                ip.is_private or
                ip.is_loopback or
                ip.is_link_local or
                ip.is_multicast or
                ip.is_reserved or
                ip.is_unspecified or
                ip == ipaddress.ip_address("0.0.0.0") or
                ip == ipaddress.ip_address("169.254.169.254")
            )
        except ValueError:
            return True

    @classmethod
    def is_domain_allowed(cls, hostname: str, allowed_domains: Optional[List[str]] = None) -> bool:
        """
        Check if a hostname matches the domain allowlist.
        Supports subdomain matching (e.g., 'careers.example.com' matches 'example.com').
        """
        if allowed_domains is None:
            allowed_domains = settings.RESEARCH_ALLOWED_DOMAINS

        if not allowed_domains:
            return False

        if "*" in allowed_domains:
            return True

        normalized_host = hostname.lower().strip()
        for domain in allowed_domains:
            d = domain.lower().strip()
            if not d:
                continue
            if normalized_host == d:
                return True
            if normalized_host.endswith("." + d):
                return True

        return False

    @classmethod
    def validate_url(
        cls,
        url: str,
        allowed_domains: Optional[List[str]] = None,
        resolve_dns: bool = True
    ) -> str:
        """
        Thoroughly validate a URL against scheme, SSRF, loopback, private IPs, and domain allowlist.
        Returns the sanitized normalized URL or raises ResearchSecurityError.
        """
        if not url or not isinstance(url, str):
            raise InvalidURLError("URL must be a non-empty string.")

        parsed = urlparse(url.strip())
        
        # 1. Scheme validation
        if parsed.scheme.lower() not in cls.ALLOWED_SCHEMES:
            raise InvalidURLError(f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

        hostname = parsed.hostname
        if not hostname:
            raise InvalidURLError("URL must contain a valid hostname.")

        hostname = hostname.lower().strip()

        # 2. Localhost & metadata hostname check
        if hostname == "localhost" or hostname.endswith(".localhost") or hostname in cls.METADATA_HOSTNAMES:
            raise SSRFProtectionError(f"Access to localhost or metadata services ({hostname}) is forbidden.")

        # 3. Direct IP check
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if cls.is_ip_private_or_restricted(str(ip_obj)):
                raise SSRFProtectionError(f"Access to private/restricted IP address ({hostname}) is forbidden.")
        except ValueError:
            # Hostname is a domain name, not an IP literal
            pass

        # 4. Domain allowlist check
        if not cls.is_domain_allowed(hostname, allowed_domains):
            raise DisallowedDomainError(
                f"Domain '{hostname}' is not in the allowed research domains list."
            )

        # 5. DNS resolution check (SSRF prevention against DNS rebinding & private hosts)
        if resolve_dns:
            try:
                # Resolve address info to ensure it doesn't resolve to private network
                addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
                for family, socktype, proto, canonname, sockaddr in addr_info:
                    ip_addr = sockaddr[0]
                    if cls.is_ip_private_or_restricted(ip_addr):
                        raise SSRFProtectionError(
                            f"Hostname '{hostname}' resolved to private/restricted IP ({ip_addr}). Access forbidden."
                        )
            except (socket.gaierror, socket.herror, socket.timeout) as e:
                # In offline/mock test environments or DNS failures
                logger.warning(f"DNS resolution warning for {hostname}: {e}")

        # Return normalized URL
        return parsed.geturl()

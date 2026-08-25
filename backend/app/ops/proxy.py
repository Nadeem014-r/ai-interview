"""Phase 10F: Production Reverse Proxy Configuration & WebSocket Readiness.

Generates and validates production reverse proxy configurations for TLS termination and WebSocket upgrades.
"""

from typing import Dict, Any


class ReverseProxyHelper:
    """Helper for validating and generating NGINX / Caddy reverse-proxy configurations."""

    @staticmethod
    def get_nginx_template() -> str:
        """Returns standard NGINX production reverse-proxy configuration template."""
        return """
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 25M;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # API & WebSocket Proxy
    location / {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
"""

    @staticmethod
    def validate_proxy_config_text(config_text: str) -> Dict[str, bool]:
        """Validates that a proxy configuration contains essential directives."""
        has_ws_upgrade = "Upgrade" in config_text and "Connection" in config_text
        has_forwarded = "X-Forwarded-For" in config_text or "X-Real-IP" in config_text
        has_ssl = "ssl" in config_text.lower()
        has_size_limit = "client_max_body_size" in config_text

        return {
            "has_websocket_upgrade": has_ws_upgrade,
            "has_forwarded_headers": has_forwarded,
            "has_ssl_configuration": has_ssl,
            "has_body_size_limit": has_size_limit,
            "is_production_ready": has_ws_upgrade and has_forwarded and has_ssl
        }

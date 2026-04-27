from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env", "../.env"], env_file_encoding="utf-8", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_expiry_hours: int = 8
    jwt_algorithm: str = "HS256"

    # Redis
    redis_url: str = "redis://localhost:6379"
    session_ttl_seconds: int = 86400   # 24h
    max_history_turns: int = 50

    # Zabbix
    zabbix_url: str = ""
    zabbix_user: str = ""
    zabbix_password: str = ""

    # Datadog
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    # Grafana
    grafana_url: str = ""
    grafana_token: str = ""

    # ThousandEyes
    thousandeyes_token: str = ""

    # MCP server URLs (internal docker network)
    # Containers comunicam pela porta INTERNA (8001), não pela porta mapeada no host
    mcp_zabbix_url: str = "http://mcp-zabbix:8001"
    mcp_datadog_url: str = "http://mcp-datadog:8001"
    mcp_grafana_url: str = "http://mcp-grafana:8001"
    mcp_thousandeyes_url: str = "http://mcp-thousandeyes:8001"
    mcp_catalyst_center_url: str = "http://mcp-catalyst-center:8001"

    # App
    log_level: str = "INFO"
    # Em desenvolvimento aceita qualquer origem local
    # Em produção, defina explicitamente no .env:
    # CORS_ORIGINS=["https://seu-dominio.com","https://app.seu-dominio.com"]
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    cors_allow_all: bool = True   # True em dev, False em produção
    # Em produção, defina o domínio da aplicação:
    # APP_DOMAIN=noc.suaempresa.com
    app_domain: str = ""          # usado nos security headers em prod


settings = Settings()

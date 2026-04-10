from dataclasses import dataclass

from shared import config


@dataclass(frozen=True)
class IBGatewayConfig:
    host: str = config.IB_GATEWAY_HOST
    port: int = config.IB_GATEWAY_PORT
    client_id: int = config.IB_GATEWAY_CLIENT_ID
    timeout: float = config.IB_GATEWAY_TIMEOUT
    read_only: bool = config.IB_GATEWAY_READ_ONLY


DEFAULT_IB_GATEWAY_CONFIG = IBGatewayConfig()

"""配置模块

该模块提供了 Solana 交易机器人的配置信息，包括交易所、币种、账户、api 等信息。
"""

import os
from typing import Any, Literal, cast

import tomli
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    MySQLDsn,
    RedisDsn,
    field_validator,
)
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        dotenv_settings: PydanticBaseSettingsSource,
    ):
        self.settings_cls = settings_cls
        self.config = settings_cls.model_config
        self.dotenv_settings = dotenv_settings

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        env_file = self.config.get("env_file")
        if isinstance(self.dotenv_settings, DotEnvSettingsSource):
            env_file = env_file if env_file else self.dotenv_settings.env_file
        if not env_file:
            raise FileNotFoundError("No toml env_file")
        try:
            with open(env_file, "rb") as ft:  # type: ignore [arg-type]
                file_content_toml = tomli.load(ft)
                field_value = file_content_toml.get(field_name)
                return field_value, field_name, False
        except Exception as e:
            raise RuntimeError(f"Error on open f{env_file}: {e}") from e

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
            field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            if field_value is not None:
                d[field_key] = field_value

        return d


class TomlSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, dotenv_settings),
        )


class WalletConfig(BaseModel):
    private_key: str

    @property
    def pubkey(self) -> str:
        return str(self.keypair.pubkey())

    @property
    def keypair(self) -> Keypair:
        return Keypair.from_base58_string(self.private_key)


class MonitorConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode: str = "wss"  # or "geyser"
    wallets: list[Pubkey] = Field(default_factory=list)

    @field_validator("mode", mode="after")
    def validate_mode(cls, value: str) -> str:
        if value.lower() not in ["wss", "geyser"]:
            raise ValueError(f"Invalid mode: {value}")
        return value

    @field_validator("wallets", mode="before")
    def validate_wallets(cls, value: list[str]) -> list[Pubkey]:
        return [Pubkey.from_string(wallet) for wallet in value]


class GeyserConfig(BaseModel):
    enable: bool = False
    endpoint: str = ""
    api_key: str = ""


class RPCConfig(BaseModel):
    network: str
    endpoints: list[str]
    commitment: Commitment
    geyser: GeyserConfig

    @property
    def rpc_url(self) -> str:
        return self.endpoints[0]

    @field_validator("commitment", mode="before")
    def validate_commitment(cls, value: str) -> Commitment:
        try:
            return Commitment(value.lower())
        except AttributeError:
            raise ValueError(f"Invalid commitment level: {value}")


class TradingConfig(BaseModel):
    unit_price: int
    unit_limit: int
    tx_simulate: bool = False
    preflight_check: bool = False
    use_jito: bool = True
    jito_api: str = "https://mainnet.block-engine.jito.wtf"

    @field_validator("jito_api", mode="before")
    def validate_jito_api(cls, value: str) -> str:
        try:
            HttpUrl(value)
        except ValueError:
            raise ValueError(f"Invalid Jito API URL: {value}")
        return value


class APIConfig(BaseModel):
    helius_api_base_url: str
    helius_api_key: str
    pumpportal_api_data_url: str
    solscan_api_base_url: str
    solscan_api_key: str
    shyft_api_base_url: str
    shyft_api_key: str


class DBConfig(BaseModel):
    mysql: MySQLDsn = Field(..., alias="mysql_url")
    redis: RedisDsn = Field(..., alias="redis_url")

    @property
    def mysql_url(self):
        url = str(self.mysql)
        if url.startswith("mysql://"):
            return url.replace("mysql://", "mysql+pymysql://")
        if url.startswith("mysql+pymysql://"):
            return url
        return url

    @property
    def async_mysql_url(self):
        url = str(self.mysql)
        if url.startswith("mysql+pymysql://"):
            return url.replace("pymysql://", "aiomysql://")
        if url.startswith("mysql://"):
            return url.replace("mysql://", "mysql+aiomysql://")
        return url


class LogConfig(BaseModel):
    level: str


class TgBotConfig(BaseModel):
    token: str
    mode: Literal["private", "public"]
    manager_id: int | None = None
    proxy: str | None = None  # 代理服务器地址，例如：http://127.0.0.1:7890


class CopyTradeConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_wallet: Pubkey
    wallet_alias: str | None = None
    is_fixed_buy: bool = True
    fixed_buy_amount: float = 0.05
    auto_follow: bool = True
    stop_loss: bool = False
    no_sell: bool = False
    priority: float = 0.002
    anti_sandwich: bool = False
    auto_slippage: bool = True
    custom_slippage: float = 10.0
    active: bool = True

    @field_validator("target_wallet", mode="before")
    def validate_target_wallet(cls, value: str) -> Pubkey:
        return Pubkey.from_string(value)


class SentryConfig(BaseModel):
    enable: bool = False
    dsn: str = ""
    traces_sample_rate: float = 1.0


class Settings(TomlSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_file=os.environ.get("ENV_FILE", "config.toml"),
        env_nested_delimiter="__",
    )

    wallet: WalletConfig
    monitor: MonitorConfig
    copytrades: list[CopyTradeConfig] = Field(default_factory=list)
    rpc: RPCConfig
    trading: TradingConfig
    api: APIConfig
    db: DBConfig
    log: LogConfig
    tg_bot: TgBotConfig
    sentry: SentryConfig


class LazySettings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = Settings()  # type: ignore
        return cls._instance


settings: Settings = cast(Settings, LazySettings())

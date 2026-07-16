import logging
from dataclasses import dataclass
from logging.handlers import MemoryHandler
from pathlib import Path

from environs import Env
from marshmallow.validate import OneOf, Range

from app.bot.utils.constants import (
    DB_FORMAT,
    LOG_GZ_ARCHIVE_FORMAT,
    LOG_ZIP_ARCHIVE_FORMAT,
    Currency,
    ReferrerRewardType,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_LOCALES_DIR = BASE_DIR / "locales"
DEFAULT_PLANS_DIR = DEFAULT_DATA_DIR / "plans.json"

DEFAULT_BOT_HOST = "0.0.0.0"
DEFAULT_BOT_PORT = 8080

DEFAULT_SHOP_EMAIL = "support@3xui-shop.com"
DEFAULT_SHOP_CURRENCY = Currency.RUB.code
DEFAULT_SHOP_TRIAL_ENABLED = True
DEFAULT_SHOP_TRIAL_PERIOD = 3
DEFAULT_SHOP_REFERRED_TRIAL_ENABLED = False
DEFAULT_SHOP_REFERRED_TRIAL_PERIOD = 7
DEFAULT_SHOP_REFERRER_REWARD_ENABLED = True
DEFAULT_SHOP_REFERRER_REWARD_TYPE = ReferrerRewardType.DAYS.value
DEFAULT_SHOP_REFERRER_LEVEL_ONE_PERIOD = 30
DEFAULT_SHOP_REFERRER_LEVEL_TWO_PERIOD = 3
DEFAULT_SHOP_REFERRER_LEVEL_ONE_RATE = 50
DEFAULT_SHOP_REFERRER_LEVEL_TWO_RATE = 5
DEFAULT_SHOP_REFERRER_MIN_SUBSCRIPTION_DAYS = 30
DEFAULT_SHOP_BONUS_DEVICES_COUNT = 1
DEFAULT_SHOP_ONBOARDING_BONUS_DAYS = 4
DEFAULT_SHOP_PAYMENT_SBP_ENABLED = False
DEFAULT_SHOP_PAYMENT_CRYPTOPAY_ENABLED = False
DEFAULT_SHOP_CRYPTOPAY_TESTNET = False
DEFAULT_SHOP_CRYPTOPAY_POLL_INTERVAL_SEC = 60
DEFAULT_SHOP_PAYMENT_PERIOD_DAYS = 30
DEFAULT_SHOP_PENDING_PAYMENT_TTL_DAYS = 3
DEFAULT_DB_NAME = "bot_database"

DEFAULT_REDIS_DB_NAME = "0"
DEFAULT_REDIS_HOST = "3xui-shop-redis"
DEFAULT_REDIS_PORT = 6379

DEFAULT_SUBSCRIPTION_PORT = 2096
DEFAULT_SUBSCRIPTION_PATH = "/user/"

DEFAULT_LOG_LEVEL = "DEBUG"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DEFAULT_LOG_ARCHIVE_FORMAT = LOG_ZIP_ARCHIVE_FORMAT

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
memory_handler = MemoryHandler(capacity=100, flushLevel=logging.ERROR)
memory_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
logger.addHandler(memory_handler)


@dataclass
class BotConfig:
    TOKEN: str
    ADMINS: list[int]
    DEV_ID: int
    SUPPORT_ID: int
    DOMAIN: str | None
    PORT: int
    POLLING: bool


@dataclass
class ShopConfig:
    EMAIL: str
    CURRENCY: str
    TRIAL_ENABLED: bool
    TRIAL_PERIOD: int
    REFERRED_TRIAL_ENABLED: bool
    REFERRED_TRIAL_PERIOD: int
    REFERRER_REWARD_ENABLED: bool
    REFERRER_REWARD_TYPE: str
    REFERRER_LEVEL_ONE_PERIOD: int
    REFERRER_LEVEL_TWO_PERIOD: int
    REFERRER_LEVEL_ONE_RATE: int
    REFERRER_LEVEL_TWO_RATE: int
    REFERRER_MIN_SUBSCRIPTION_DAYS: int
    BONUS_DEVICES_COUNT: int
    ONBOARDING_BONUS_DAYS: int
    PAYMENT_SBP_ENABLED: bool
    PAYMENT_CRYPTOPAY_ENABLED: bool
    CRYPTOPAY_TOKEN: str | None
    CRYPTOPAY_TESTNET: bool
    CRYPTOPAY_POLL_INTERVAL_SEC: int
    PAYMENT_PERIOD_DAYS: int
    PENDING_PAYMENT_TTL_DAYS: int
    SBP_PHONE: str | None
    SBP_BANK: str | None


@dataclass
class XUIConfig:
    USERNAME: str
    PASSWORD: str
    TOKEN: str | None
    SUBSCRIPTION_PORT: int
    SUBSCRIPTION_PATH: str


@dataclass
class DatabaseConfig:
    HOST: str | None
    PORT: int | None
    NAME: str
    USERNAME: str | None
    PASSWORD: str | None

    def url(self, driver: str = "sqlite+aiosqlite") -> str:
        if driver.startswith("sqlite"):
            return f"{driver}:////{DEFAULT_DATA_DIR}/{self.NAME}.{DB_FORMAT}"
        return f"{driver}://{self.USERNAME}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"


@dataclass
class RedisConfig:
    HOST: str
    PORT: int
    DB_NAME: str
    USERNAME: str | None
    PASSWORD: str | None

    def url(self) -> str:
        if self.USERNAME and self.PASSWORD:
            return f"redis://{self.USERNAME}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB_NAME}"
        return f"redis://{self.HOST}:{self.PORT}/{self.DB_NAME}"


@dataclass
class LoggingConfig:
    LEVEL: str
    FORMAT: str
    ARCHIVE_FORMAT: str


@dataclass
class Config:
    bot: BotConfig
    shop: ShopConfig
    xui: XUIConfig
    database: DatabaseConfig
    redis: RedisConfig
    logging: LoggingConfig


def load_config() -> Config:
    env = Env()
    env.read_env()

    bot_admins = env.list("BOT_ADMINS", subcast=int, default=[], required=False)
    if not bot_admins:
        logger.warning("BOT_ADMINS list is empty.")

    xui_token = env.str("XUI_TOKEN", default=None)
    if not xui_token:
        logger.warning("XUI_TOKEN is not set.")

    referrer_reward_type = env.str(
        "SHOP_REFERRED_REWARD_TYPE",
        default=DEFAULT_SHOP_REFERRER_REWARD_TYPE,
        validate=OneOf(
            [reward_type.value for reward_type in ReferrerRewardType],
            error="SHOP_REFERRER_REWARD_TYPE must be one of: {choices}",
        ),
    )
    referrer_reward_enabled = env.bool(
        "SHOP_REFERRER_REWARD_ENABLED", default=DEFAULT_SHOP_REFERRER_REWARD_ENABLED
    )
    if referrer_reward_type != ReferrerRewardType.DAYS.value:
        logger.error(
            "Only 'days' option is now available for SHOP_REFERRER_REWARD_TYPE. Referrer reward disabled."
        )
        referrer_reward_enabled = False

    cryptopay_enabled = env.bool(
        "SHOP_PAYMENT_CRYPTOPAY_ENABLED", default=DEFAULT_SHOP_PAYMENT_CRYPTOPAY_ENABLED
    )
    cryptopay_token = env.str("SHOP_CRYPTOPAY_TOKEN", default=None)
    if cryptopay_enabled and not cryptopay_token:
        raise ValueError(
            "SHOP_PAYMENT_CRYPTOPAY_ENABLED is true but SHOP_CRYPTOPAY_TOKEN is empty. "
            "Set the Crypto Pay API token (from @CryptoBot → Crypto Pay → API) or disable the gateway."
        )

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            ADMINS=bot_admins,
            DEV_ID=env.int("BOT_DEV_ID"),
            SUPPORT_ID=env.int("BOT_SUPPORT_ID"),
            DOMAIN=f"https://{env.str('BOT_DOMAIN')}" if env.str("BOT_DOMAIN", default=None) else None,
            PORT=env.int("BOT_PORT", default=DEFAULT_BOT_PORT),
            POLLING=env.bool("BOT_POLLING", default=False),
        ),
        shop=ShopConfig(
            EMAIL=env.str("SHOP_EMAIL", default=DEFAULT_SHOP_EMAIL),
            CURRENCY=env.str(
                "SHOP_CURRENCY",
                default=DEFAULT_SHOP_CURRENCY,
                validate=OneOf(
                    [currency.code for currency in Currency]
                    + [currency.code.lower() for currency in Currency],
                    error="SHOP_CURRENCY must be one of: {choices}",
                ),
            ).upper(),
            TRIAL_ENABLED=env.bool("SHOP_TRIAL_ENABLED", default=DEFAULT_SHOP_TRIAL_ENABLED),
            TRIAL_PERIOD=env.int("SHOP_TRIAL_PERIOD", default=DEFAULT_SHOP_TRIAL_PERIOD),
            REFERRED_TRIAL_ENABLED=env.bool(
                "SHOP_REFERRED_TRIAL_ENABLED", default=DEFAULT_SHOP_REFERRED_TRIAL_ENABLED
            ),
            REFERRED_TRIAL_PERIOD=env.int(
                "SHOP_REFERRED_TRIAL_PERIOD",
                default=DEFAULT_SHOP_REFERRED_TRIAL_PERIOD,
                validate=Range(min=1, error="SHOP_REFERRED_TRIAL_PERIOD must be >= 1"),
            ),
            REFERRER_REWARD_ENABLED=referrer_reward_enabled,
            REFERRER_REWARD_TYPE=referrer_reward_type,
            REFERRER_LEVEL_ONE_PERIOD=env.int(
                "SHOP_REFERRER_LEVEL_ONE_PERIOD",
                default=DEFAULT_SHOP_REFERRER_LEVEL_ONE_PERIOD,
                validate=Range(min=1, error="SHOP_REFERRER_LEVEL_ONE_PERIOD must be >= 1"),
            ),
            REFERRER_LEVEL_TWO_PERIOD=env.int(
                "SHOP_REFERRER_LEVEL_TWO_PERIOD",
                default=DEFAULT_SHOP_REFERRER_LEVEL_TWO_PERIOD,
                validate=Range(min=1, error="SHOP_REFERRER_LEVEL_TWO_PERIOD must be >= 1"),
            ),
            REFERRER_LEVEL_ONE_RATE=env.int(
                "SHOP_REFERRER_LEVEL_ONE_RATE",
                default=DEFAULT_SHOP_REFERRER_LEVEL_ONE_RATE,
                validate=Range(
                    min=1,
                    max=100,
                    error="SHOP_REFERRER_LEVEL_ONE_RATE must be between 1 and 100",
                ),
            ),
            REFERRER_LEVEL_TWO_RATE=env.int(
                "SHOP_REFERRER_LEVEL_TWO_RATE",
                default=DEFAULT_SHOP_REFERRER_LEVEL_TWO_RATE,
                validate=Range(
                    min=1,
                    max=100,
                    error="SHOP_REFERRER_LEVEL_TWO_RATE must be between 1 and 100",
                ),
            ),
            REFERRER_MIN_SUBSCRIPTION_DAYS=env.int(
                "SHOP_REFERRER_MIN_SUBSCRIPTION_DAYS",
                default=DEFAULT_SHOP_REFERRER_MIN_SUBSCRIPTION_DAYS,
                validate=Range(min=1, error="SHOP_REFERRER_MIN_SUBSCRIPTION_DAYS must be >= 1"),
            ),
            BONUS_DEVICES_COUNT=env.int(
                "SHOP_BONUS_DEVICES_COUNT", default=DEFAULT_SHOP_BONUS_DEVICES_COUNT
            ),
            ONBOARDING_BONUS_DAYS=env.int(
                "SHOP_ONBOARDING_BONUS_DAYS", default=DEFAULT_SHOP_ONBOARDING_BONUS_DAYS
            ),
            PAYMENT_SBP_ENABLED=env.bool(
                "SHOP_PAYMENT_SBP_ENABLED", default=DEFAULT_SHOP_PAYMENT_SBP_ENABLED
            ),
            PAYMENT_CRYPTOPAY_ENABLED=cryptopay_enabled,
            CRYPTOPAY_TOKEN=cryptopay_token,
            CRYPTOPAY_TESTNET=env.bool(
                "SHOP_CRYPTOPAY_TESTNET", default=DEFAULT_SHOP_CRYPTOPAY_TESTNET
            ),
            CRYPTOPAY_POLL_INTERVAL_SEC=env.int(
                "SHOP_CRYPTOPAY_POLL_INTERVAL_SEC",
                default=DEFAULT_SHOP_CRYPTOPAY_POLL_INTERVAL_SEC,
                validate=Range(min=10, error="SHOP_CRYPTOPAY_POLL_INTERVAL_SEC must be >= 10"),
            ),
            PAYMENT_PERIOD_DAYS=env.int(
                "SHOP_PAYMENT_PERIOD_DAYS",
                default=DEFAULT_SHOP_PAYMENT_PERIOD_DAYS,
                validate=Range(min=1, error="SHOP_PAYMENT_PERIOD_DAYS must be >= 1"),
            ),
            PENDING_PAYMENT_TTL_DAYS=env.int(
                "SHOP_PENDING_PAYMENT_TTL_DAYS",
                default=DEFAULT_SHOP_PENDING_PAYMENT_TTL_DAYS,
                validate=Range(min=1, error="SHOP_PENDING_PAYMENT_TTL_DAYS must be >= 1"),
            ),
            SBP_PHONE=env.str("SHOP_SBP_PHONE", default=None),
            SBP_BANK=env.str("SHOP_SBP_BANK", default=None),
        ),
        xui=XUIConfig(
            USERNAME=env.str("XUI_USERNAME"),
            PASSWORD=env.str("XUI_PASSWORD"),
            TOKEN=xui_token,
            SUBSCRIPTION_PORT=env.int("XUI_SUBSCRIPTION_PORT", default=DEFAULT_SUBSCRIPTION_PORT),
            SUBSCRIPTION_PATH=env.str(
                "XUI_SUBSCRIPTION_PATH",
                default=DEFAULT_SUBSCRIPTION_PATH,
            ),
        ),
        database=DatabaseConfig(
            HOST=env.str("DB_HOST", default=None),
            PORT=env.int("DB_PORT", default=None),
            USERNAME=env.str("DB_USERNAME", default=None),
            PASSWORD=env.str("DB_PASSWORD", default=None),
            NAME=env.str("DB_NAME", default=DEFAULT_DB_NAME),
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST", default=DEFAULT_REDIS_HOST),
            PORT=env.int("REDIS_PORT", default=DEFAULT_REDIS_PORT),
            DB_NAME=env.str("REDIS_DB_NAME", default=DEFAULT_REDIS_DB_NAME),
            USERNAME=env.str("REDIS_USERNAME", default=None),
            PASSWORD=env.str("REDIS_PASSWORD", default=None),
        ),
        logging=LoggingConfig(
            LEVEL=env.str("LOG_LEVEL", default=DEFAULT_LOG_LEVEL),
            FORMAT=env.str("LOG_FORMAT", default=DEFAULT_LOG_FORMAT),
            ARCHIVE_FORMAT=env.str(
                "LOG_ARCHIVE_FORMAT",
                default=DEFAULT_LOG_ARCHIVE_FORMAT,
                validate=OneOf(
                    [LOG_ZIP_ARCHIVE_FORMAT, LOG_GZ_ARCHIVE_FORMAT],
                    error="LOG_ARCHIVE_FORMAT must be one of: {choices}",
                ),
            ),
        ),
    )

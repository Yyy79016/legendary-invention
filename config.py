"""
Configuration module for TelegramBot.
Centralizes all constants, settings, and configuration management.
"""
import os
from typing import Dict, Any

# Telegram API Configuration
API_ID = 26010560
API_HASH = "6b9c5cf31915896ea54656cd04c7fbbb"

# Telegram Client Configuration
DEVICE_MODEL = "PC 64bit"
SYSTEM_VERSION = "Windows 10.0.22621"
APP_VERSION = "4.15.0 x64"
LANG_CODE = "zh"
SYSTEM_LANG_CODE = "zh-cn"
SESSION_FILE = "session"

# Database Configuration
DB_PATH = "database.db"
DB_TIMEOUT = 30
DB_MAX_POOL_SIZE = 5

# Cache Configuration - 分别定义不同缓存的过期时间
BLACKLIST_CACHE_EXPIRE = 300  # 黑名单缓存：5分钟
PDF_CACHE_EXPIRE = 86400      # PDF缓存：24小时
TASK_CACHE_EXPIRE = 30        # 任务缓存：30秒
GENERAL_CACHE_EXPIRE = 300    # 通用缓存：5分钟

# Queue and Cache Limits
MAX_QUEUE_SIZE = 1000
MAX_CACHE_SIZE = 10000

# Rate Limiting
MAX_MSGS_PER_SEC = int(os.getenv("MAX_MSGS_PER_SEC", 10))
LIMIT_WINDOW_SEC = int(os.getenv("LIMIT_WINDOW_SEC", 1))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 24))
MAX_CONCURRENCY = 10

# Email Configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILES = {
    'pay': {
        'client_secret': 'credentials.json',
        'token': 'token.json'
    }
}

# FastMail Configuration
FASTMAIL_IMAP_HOST = "imap.fastmail.com"
FASTMAIL_IMAP_PORT = 993

# Message Processing
MAX_CAPTION_LENGTH = 1024
DELETE_DELAY = 15  # seconds for auto-delete
REPLY_PAYBACK_DELAY = 1.5  # seconds
PENDING_SEND_DELAY = 2.0  # seconds
PAYBACK_DEDUPE_INTERVAL = 30  # seconds
ORDER_FORWARD_CACHE_TIMEOUT = 30  # seconds

# Timezone Configuration
TIMEZONE_OFFSET = 8  # UTC+8 for Shanghai

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FILE = "bot.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Feature Flags
ENABLE_COLORAMA = True
SHOW_ENV_LOGS = False
ENABLE_AUTO_CLEANUP = True

# Global State
BOT_USER_ID: int | None = None
START_TIME = 0

class Config:
    """Configuration class for dynamic settings."""
    
    @staticmethod
    def get_env_var(key: str, default: Any) -> Any:
        """Get environment variable with default fallback."""
        return os.getenv(key, default)
    
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load configuration from environment or config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                import json
                return json.load(f)
        return {
            "db_path": DB_PATH,
            "max_concurrency": MAX_CONCURRENCY,
            "rate_limit": 5,
            "log_file": LOG_FILE
        }

# Load configuration on import
CONFIG = Config.load_config()
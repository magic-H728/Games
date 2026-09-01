from pydantic_settings import BaseSettings
from functools import lru_cache
import json
import os

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "game_config.json")


class Settings(BaseSettings):
    SECRET_KEY: str = "hide-and-seek-secret-key-change-in-production-2026"
    DATABASE_URL: str = "sqlite+aiosqlite:///./game.db"
    STAFF_USERNAME: str = "admin"
    STAFF_PASSWORD: str = "admin123"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for an event

    class Config:
        env_file = ".env"


def load_game_config():
    """加载游戏配置文件"""
    default_config = {
        "capture_score": 10,
        "survival_interval_seconds": 300,
        "survival_interval_score": 5,
        "max_revive_count": 3,
        "revive_protect_seconds": 120,
        "cat_ratio": 0.1,
        "default_mini_game_rewards": {
            "first": 30,
            "second": 20,
            "third": 10
        }
    }

    if not os.path.exists(CONFIG_FILE_PATH):
        save_game_config(default_config)
        return default_config

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"Error loading game config: {e}")
        return default_config


def save_game_config(config):
    """保存游戏配置文件"""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving game config: {e}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()

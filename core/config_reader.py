import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class ConfigReader:
    _instance = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        env = os.getenv("TEST_ENV", "dev")
        base_dir = Path(__file__).parent.parent / "config"

        # 加载基础配置
        base_file = base_dir / "config.yaml"
        with open(base_file, encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

        # 加载环境覆盖配置
        env_file = base_dir / f"{env}.yaml"
        if env_file.exists():
            with open(env_file, encoding="utf-8") as f:
                env_cfg = yaml.safe_load(f) or {}
            self._deep_merge(self._config, env_cfg)

    def _deep_merge(self, base: dict, override: dict):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def get(self, key: str, default=None):
        """
        支持点号路径访问，同时支持环境变量覆盖
        例: config.get("browser.type") 可被 BROWSER_TYPE 环境变量覆盖
        """
        # 优先从环境变量读取
        env_key = key.upper().replace(".", "_")
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val

        # 从配置字典读取
        parts = key.split(".")
        val = self._config
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return default
        return val if val is not None else default

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self.get(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def all(self) -> dict:
        return self._config.copy()


# 全局单例
config = ConfigReader()
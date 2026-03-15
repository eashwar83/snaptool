import json
import os
from pathlib import Path
from datetime import datetime


DEFAULT_CONFIG = {
    "default_folder": "",
    "image_format": "png",
    "jpg_quality": 95,
    "filename_pattern": "snap_{timestamp}",
    "hotkeys": {
        "fullscreen": "ctrl+print screen",
        "region": "ctrl+shift+s",
        "window": "ctrl+alt+print screen",
        "delayed": "ctrl+shift+d",
    },
    "startup_with_windows": False,
    "show_notification": True,
    "capture_cursor": False,
    "auto_copy_to_clipboard": False,
    "delay_seconds": 3,
    "add_border": False,
    "border_color": "#333333",
    "border_width": 2,
    "add_shadow": False,
    "last_save_dir": "",
    "auto_cleanup_enabled": False,
    "auto_cleanup_days": 30,
}


class Config:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if os.name == "nt":
            appdata = os.environ.get("APPDATA", str(Path.home()))
            self.config_dir = Path(appdata) / "SnapTool"
        else:
            self.config_dir = Path.home() / ".config" / "snaptool"

        self.config_file = self.config_dir / "settings.json"
        self._config = {}
        self._load()

    def _load(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, encoding="utf-8") as f:
                    saved = json.load(f)
                self._config = {**DEFAULT_CONFIG, **saved}
                if isinstance(DEFAULT_CONFIG.get("hotkeys"), dict):
                    merged_hotkeys = {**DEFAULT_CONFIG["hotkeys"], **saved.get("hotkeys", {})}
                    self._config["hotkeys"] = merged_hotkeys
            else:
                self._config = DEFAULT_CONFIG.copy()
        except (json.JSONDecodeError, IOError):
            self._config = DEFAULT_CONFIG.copy()

        if not self._config["default_folder"]:
            self._config["default_folder"] = str(
                Path.home() / "Pictures" / "SnapTool"
            )

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key, default=None):
        return self._config.get(key, DEFAULT_CONFIG.get(key, default))

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def get_all(self):
        return self._config.copy()

    def set_all(self, data):
        self._config.update(data)
        self.save()

    def generate_filename(self):
        pattern = self.get("filename_pattern")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        name = pattern.replace("{timestamp}", timestamp)
        ext = self.get("image_format")
        return f"{name}.{ext}"

    def get_default_save_path(self):
        folder = self.get("default_folder")
        Path(folder).mkdir(parents=True, exist_ok=True)
        return str(Path(folder) / self.generate_filename())

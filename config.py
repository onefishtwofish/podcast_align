import yaml
from pathlib import Path
from typing import Tuple

class Config:
    def __init__(self, path: str = "config.yaml"):
        """
        Reads config YAML and stores the data.
        """
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"Config file not found: {self._path}")
        
        with open(self._path, "r", encoding="utf-8") as stream:
            self._data = yaml.safe_load(stream)

        # Ensure keys exist with defaults
        self._data.setdefault("path", {})
        self._data.setdefault("whisper", {"model": "small", "device": "cuda"})

    # ------------------------
    # Path accessors
    # ------------------------
    def get_audio_path(self) -> str:
        return self._data["path"].get("episode", "")

    def get_transcript_path(self) -> str:
        return self._data["path"].get("transcript", "")

    def get_output_path(self) -> str:
        return self._data["path"].get("subtitles", "untitled.ass")

    # ------------------------
    # Whisper accessors
    # ------------------------
    def get_whisper_params(self) -> Tuple[str, str]:
        """
        Returns (model, device) tuple, which can be unpacked into:
        get_whisper_transcript(path, *config.get_whisper_params())
        """
        model = self._data["whisper"].get("model", "small")
        device = self._data["whisper"].get("device", "cuda")
        return model, device

    def get_whisper_model(self) -> str:
        return self._data["whisper"].get("model", "small")

    def get_whisper_device(self) -> str:
        return self._data["whisper"].get("device", "cuda")

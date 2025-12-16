import whisper
import torch
from threading import Lock

# ---------------------------------------------------------------------
# Private singleton storage
# ---------------------------------------------------------------------

_WHISPER_MODEL_CACHE = {}
_WHISPER_MODEL_LOCK = Lock()


def _get_whisper_model(model_name: str, device: str):
    """
    Private singleton accessor for Whisper models.
    Ensures only one model per (model_name, device) is loaded.
    """
    key = (model_name, device)

    if key not in _WHISPER_MODEL_CACHE:
        with _WHISPER_MODEL_LOCK:
            # Double-checked locking
            if key not in _WHISPER_MODEL_CACHE:
                _WHISPER_MODEL_CACHE[key] = whisper.load_model(
                    model_name,
                    device=device
                )

    return _WHISPER_MODEL_CACHE[key]


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def get_whisper_transcript(
    path: str,
    model: str = "small",
    device: str = "cuda"
):
    """
    Transcribes audio using a singleton Whisper model.

    path: path to audio file
    model: Whisper model size/name (e.g. 'tiny', 'base', 'small', 'medium', 'large')
    device: 'cuda' or 'cpu' (defaults to GPU)

    Returns:
        list of Whisper segments
    """

    # Graceful GPU fallback
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    whisper_model = _get_whisper_model(model, device)

    result = whisper_model.transcribe(
        path,
        language="en",
        condition_on_previous_text=False,
        word_timestamps=True,
        verbose=False
    )

    return result["segments"]

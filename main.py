from pdfminer.high_level import extract_text

from utils import get_config
from cleaning import normalize_transcript, generate_clean_transcript

config = get_config()

text = extract_text(config["path"]["transcript"])

transcript_norm = normalize_transcript(text)
cleaned_transcript_norm, cue_map = generate_clean_transcript(transcript_norm)

print(cue_map)
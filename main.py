from pdfminer.high_level import extract_text

from config import Config
from utils import insert_word_table_times, write_to_ass
from cleaning import normalize_transcript, transcript_to_alignment_tables, whisper_segments_to_word_table
from whisper_utils import get_whisper_transcript
from alignment import align_transcript_to_whisper
from postprocess import interpolate_missing_times, reinsert_cues_with_interpolation, chunk_reintegrated_utterances, normalise_subtitle_timings, annotate_speaker_colors
from ass import transcript_to_ass

config = Config("config.yaml")

text = extract_text(config.get_transcript_path())

transcript = normalize_transcript(text)

formatted_transcript = transcript_to_alignment_tables(transcript)

whisper_segments = get_whisper_transcript(config.get_audio_path(), *config.get_whisper_params())
formatted_whisper_transcript = whisper_segments_to_word_table(whisper_segments)

aligned_transcript = align_transcript_to_whisper(formatted_transcript, formatted_whisper_transcript)
aligned_transcript = interpolate_missing_times(aligned_transcript)

formatted_transcript = insert_word_table_times(formatted_transcript, aligned_transcript)
formatted_transcript = reinsert_cues_with_interpolation(formatted_transcript)

formatted_transcript = chunk_reintegrated_utterances(formatted_transcript)
formatted_transcript = normalise_subtitle_timings(formatted_transcript)
formatted_transcript = annotate_speaker_colors(formatted_transcript)

ass_format_transcript = transcript_to_ass(formatted_transcript)

write_to_ass(ass_format_transcript, config.get_output_path())
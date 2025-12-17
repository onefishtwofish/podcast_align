import re
import unicodedata
from typing import List, Dict, Any

# Regex to remove page number artifacts 
PAGE_NUMBER_PATTERN = re.compile(r"[\n\n\s]{1,}[0-9]{1,}[\n\s]{1,}")

# Regex to detect speaker lines (ic_name [real_name])
SPEAKER_PATTERN = re.compile(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)(?:\s[\[\(]([^\]\)]+)[\]\)])?\s*$')

# Regex to detect standalone actions [like this]
ACTION_PATTERN = re.compile(r'^\s*\[(.+?)\]\s*$')

# Regex to detect Cues
CUE_PATTERN = re.compile(r"\[(.*?)\]")

# Regex to detect individual words from transcript, including leading or trailing Punc
TRANSCRIPT_WORD_PATTERN = re.compile(
    r"""           # verbose mode
    [“"']?         # optional opening quote
    \w+(?:[-']\w+)*  # main word body, allowing internal hyphens/apostrophes
    [.,!?;:…]*     # optional trailing punctuation
    [”"']?         # optional closing quote
    |[.,!?;:…]+    # OR standalone punctuation
    """, re.VERBOSE
)

# Regex to detect individual words from whisper generated transcript
WHISPER_WORD_PATTERN = re.compile(r"\b[\w']+\b")


def normalize_transcript(raw_text):
    transcript_blocks = []
    real_name_lookup = {}  # maps real_name -> canonical speaker
    first_name_lookup = {}  # maps first_name -> canonical speaker
    current_speaker = None
    buffer_lines = []

    # Remove page numbers
    raw_text = PAGE_NUMBER_PATTERN.sub("\n\n", raw_text)
    lines = raw_text.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        speaker_match = SPEAKER_PATTERN.match(line)
        action_match = ACTION_PATTERN.match(line)

        if speaker_match:
            # Flush any buffered speech
            if buffer_lines:
                transcript_blocks.append({
                    "type": "speech",
                    "speaker": current_speaker,
                    "text": " ".join(buffer_lines).strip()
                })
                buffer_lines = []

            in_char_name = speaker_match.group(1)
            real_name = speaker_match.group(2) or in_char_name

            # If this is a first-name-only real_name, attempt to resolve
            if ' ' not in real_name:
                if real_name in first_name_lookup:
                    canonical_name = first_name_lookup[real_name]
                else:
                    canonical_name = real_name
                    first_name_lookup[real_name] = canonical_name
            else:
                canonical_name = real_name
                # Also update first_name lookup
                first_name = real_name.split()[0]
                first_name_lookup[first_name] = canonical_name

            # Update real_name mapping
            if real_name not in real_name_lookup:
                real_name_lookup[real_name] = canonical_name

            current_speaker = canonical_name

        elif action_match:
            # Flush any buffered speech
            if buffer_lines:
                transcript_blocks.append({
                    "type": "speech",
                    "speaker": current_speaker,
                    "text": " ".join(buffer_lines).strip()
                })
                buffer_lines = []

            # Keep square brackets intact
            transcript_blocks.append({
                "type": "action",
                "speaker": None,
                "text": f"[{action_match.group(1).strip()}]"
            })

        else:
            buffer_lines.append(line)

    # Flush remaining buffer
    if buffer_lines:
        transcript_blocks.append({
            "type": "speech",
            "speaker": current_speaker,
            "text": " ".join(buffer_lines).strip()
        })

    def unify_speaker_names(transcript_blocks):
        """
        Replace any first-name-only speaker references with their canonical full names.
        """
        # Build a mapping from first name -> canonical full name
        canonical_mapping = {}
        for block in transcript_blocks:
            speaker = block["speaker"]
            if not speaker:
                continue
            # If it's a full name (2+ words), use it as canonical
            if len(speaker.split()) > 1:
                first_name = speaker.split()[0]
                canonical_mapping[first_name] = speaker

        # Second pass: replace all speaker fields using canonical mapping
        for block in transcript_blocks:
            speaker = block["speaker"]
            if not speaker:
                continue
            first_name = speaker.split()[0]
            if first_name in canonical_mapping:
                block["speaker"] = canonical_mapping[first_name]

        return transcript_blocks


    return unify_speaker_names(transcript_blocks)


def split_cues(normalized_transcript):
    """
    Generates a text-only version of a normalized transcript for alignment.
    
    Removes:
      1) Non-speech segments (type != 'speech')
      2) Any text enclosed in square brackets within 'text'
    
    Returns:
      - clean_transcript: list of dicts, each dict contains:
          'speaker': speaker name
          'text': cleaned spoken text
          'original_index': index in the original transcript (for mapping cues later)
      - cue_map: list of dicts for non-speech and bracketed cues, containing:
          'original_index': position in original transcript
          'text': cue text
    """
    clean_transcript = []
    cue_map = []

    for idx, entry in enumerate(normalized_transcript):
        if entry['type'] == 'speech':
            text = entry['text']
            # Find all bracketed cues in this text
            brackets = re.findall(r'\[.*?\]', text)
            for b in brackets:
                cue_map.append({
                    'original_index': idx,
                    'text': b
                })
            # Remove bracketed cues from the text
            text = re.sub(r"\[.*?\]", "", text)

            if text:  # Only include non-empty lines
                clean_transcript.append({
                    'speaker': entry['speaker'],
                    'text': text,
                    'original_index': idx
                })
        else:
            # Non-speech segment, store for later reinsertion
            cue_map.append({
                'original_index': idx,
                'text': entry['text']
            })

    return clean_transcript, cue_map


def extract_tokens_and_cues(text: str, TRANSCRIPT_WORD_PATTERN=TRANSCRIPT_WORD_PATTERN):
    """
    Returns:
      words: list[str]
      cues: list[tuple[word_offset, cue_text]]
    """

    def attached_to_word(before_text, token):
        """
        Returns True if `token` is attached to a word character immediately before it.
        """
        if not before_text:
            return False
        last_char = before_text[-1]
        return bool(re.match(r"\w", last_char))

    cues = []
    words = []

    pos = 0
    word_index = 0

    for match in CUE_PATTERN.finditer(text):
        # text before cue
        before = text[pos:match.start()]
        for w in TRANSCRIPT_WORD_PATTERN.findall(before):
            # if it's a standalone punctuation
            if re.fullmatch(r"[.,!?;:…]+", w):
                cues.append((word_index, w))
            else:
                words.append(w)
                word_index += 1



        # cue itself
        cues.append((word_index, f"[{match.group(1)}]"))
        pos = match.end()

    # trailing text
    after = text[pos:]
    for w in TRANSCRIPT_WORD_PATTERN.findall(after):
        if re.fullmatch(r"[.,!?]+", w) and not attached_to_word(after, w):
            cues.append((word_index, w))
        else:
            words.append(w)
            word_index += 1

    return words, cues


def transcript_to_alignment_tables(transcript):
    speaker_to_id = {}
    id_to_speaker = {}
    next_speaker_id = 0

    utterances = {}

    # ---- word table ----
    word_norm = []
    word_raw = []
    speaker_id = []
    utterance_id = []
    pos_in_utt = []

    start_time = []
    end_time = []
    aligned = []
    confidence = []

    # ---- cue table ----
    cue_id = []
    cue_utterance_id = []
    cue_word_offset = []
    cue_text = []
    cue_start = []
    cue_end = []
    cue_is_inline = []

    next_cue_id = 0


    def normalize_word(raw: str) -> str:
        """
        Normalization tuned for Whisper-style transcript alignment.

        - Lowercases the word
        - Strips punctuation except apostrophes within contractions
        - Normalizes unicode characters (accents, fancy quotes)
        - Converts ellipses, em dashes, and fancy quotes to plain equivalents
        - Collapses multiple spaces
        """
        word = raw.lower()
        
        # Normalize unicode (accents, fancy quotes)
        word = unicodedata.normalize('NFKD', word)
        
        # Standardize quotes and dashes
        word = word.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        word = word.replace("–", "-").replace("—", "-")
        word = word.replace("…", "...")

        # Keep letters, numbers, internal apostrophes for contractions, and dots for ellipses
        word = re.sub(r"[^\w\s'\.]", "", word)
        
        # Remove apostrophes at start or end of word (not part of contraction)
        word = re.sub(r"(^'+|'+$)", "", word)
        
        # Collapse multiple spaces
        word = re.sub(r"\s+", " ", word).strip()
        
        return word


    for utt_id, entry in enumerate(transcript):
        speaker = entry.get("speaker")
        text = entry["text"]

        # standalone cue (no speaker or empty speech)
        if entry.get("type") != "speech" or speaker is None:
            cue_id.append(next_cue_id)
            cue_utterance_id.append(None)
            cue_word_offset.append(None)
            cue_text.append(text)
            cue_start.append(None)
            cue_end.append(None)
            cue_is_inline.append(False)
            next_cue_id += 1
            continue

        if speaker not in speaker_to_id:
            speaker_to_id[speaker] = next_speaker_id
            id_to_speaker[next_speaker_id] = speaker
            next_speaker_id += 1

        spk_id = speaker_to_id[speaker]

        utterances[utt_id] = {
            "speaker_id": spk_id,
            "speaker": speaker,
            "text": text,
        }

        tokens, cues = extract_tokens_and_cues(text)

        for offset, cue_txt in cues:
            cue_id.append(next_cue_id)
            cue_utterance_id.append(utt_id)
            cue_word_offset.append(offset)
            cue_text.append(cue_txt)
            cue_start.append(None)
            cue_end.append(None)
            cue_is_inline.append(True)
            next_cue_id += 1

        for pos, raw in enumerate(tokens):
            word_raw.append(raw)
            word_norm.append(normalize_word(raw))
            speaker_id.append(spk_id)
            utterance_id.append(utt_id)
            pos_in_utt.append(pos)

            start_time.append(None)
            end_time.append(None)
            aligned.append(False)
            confidence.append(None)
    
    return {
        "word_table": {
            "word_norm": word_norm,
            "word_raw": word_raw,
            "speaker_id": speaker_id,
            "utterance_id": utterance_id,
            "pos_in_utt": pos_in_utt,
            "start_time": start_time,
            "end_time": end_time,
            "aligned": aligned,
            "confidence": confidence,
        },
        "cue_table": {
            "cue_id": cue_id,
            "utterance_id": cue_utterance_id,
            "word_offset": cue_word_offset,
            "text": cue_text,
            "start_time": cue_start,
            "end_time": cue_end,
            "is_inline": cue_is_inline,
        },
        "utterances": utterances,
        "speakers": {
            "to_id": speaker_to_id,
            "to_name": id_to_speaker,
        },
    }


def whisper_segments_to_word_table(segments: List[Dict[str, Any]], WHISPER_WORD_PATTERN=WHISPER_WORD_PATTERN):
    """
    Convert Whisper segments into a flat hypothesis word table.
    """

    hyp_word_norm = []
    hyp_word_raw = []
    hyp_start = []
    hyp_end = []
    hyp_confidence = []

    for seg in segments:
        for w in seg.get("words", []):
            raw = w["word"].strip()

            # normalize in the SAME way as transcript words
            tokens = WHISPER_WORD_PATTERN.findall(raw)
            if not tokens:
                continue

            # Whisper sometimes attaches punctuation; usually 1 token
            norm = tokens[0].lower()

            hyp_word_raw.append(raw)
            hyp_word_norm.append(norm)
            hyp_start.append(float(w["start"]))
            hyp_end.append(float(w["end"]))
            hyp_confidence.append(float(w.get("probability", 1.0)))

    return {
        "word_norm": hyp_word_norm,
        "word_raw": hyp_word_raw,
        "start_time": hyp_start,
        "end_time": hyp_end,
        "confidence": hyp_confidence,
    }

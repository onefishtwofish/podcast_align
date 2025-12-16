import re
from typing import List, Dict, Any

# Regex to remove page number artifacts 
PAGE_NUMBER_PATTERN = re.compile(r"[\n\n\s]{1,}[0-9]{1,}[\n\s]{1,}")

# Regex to detect speaker lines
SPEAKER_PATTERN = re.compile(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)(?:\s\(([^)]+)\))?\s*$')

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

def normalize_transcript(raw_text, PAGE_NUMBER_PATTERN=PAGE_NUMBER_PATTERN, SPEAKER_PATTERN=SPEAKER_PATTERN, ACTION_PATTERN=ACTION_PATTERN):
    """
    Normalize a dialogue transcript into structured blocks.
    
    Returns:
        A list of dictionaries with keys:
            - type: "speech" or "action"
            - speaker: speaker name or None for actions
            - text: cleaned text of speech or action
    """

    # Prepare output list
    transcript_blocks = []
    current_speaker = None
    current_alias = None
    buffer_lines = []

    # Remove page number artifacts 
    raw_text = PAGE_NUMBER_PATTERN.sub("\n\n", raw_text)
    
    # Split lines and iterate
    lines = raw_text.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue  # skip empty lines
        
        speaker_match = SPEAKER_PATTERN.match(line)
        action_match = ACTION_PATTERN.match(line)
        
        if speaker_match:
            # Save previous speech block if exists
            if buffer_lines:
                transcript_blocks.append({
                    "type": "speech",
                    "speaker": current_speaker,
                    "text": " ".join(buffer_lines).strip()
                })
                buffer_lines = []
            
            # Set current speaker
            current_speaker = speaker_match.group(1)
            current_alias = speaker_match.group(2)  # optional, could store if needed
            
        elif action_match:
            # Save any buffered speech first
            if buffer_lines:
                transcript_blocks.append({
                    "type": "speech",
                    "speaker": current_speaker,
                    "text": " ".join(buffer_lines).strip()
                })
                buffer_lines = []
            
            # Save the action as a separate block
            transcript_blocks.append({
                "type": "action",
                "speaker": None,
                "text": action_match.group(1).strip()
            })
            
        else:
            # Regular speech line
            buffer_lines.append(line)
    
    # Append any remaining buffered speech
    if buffer_lines:
        transcript_blocks.append({
            "type": "speech",
            "speaker": current_speaker,
            "text": " ".join(buffer_lines).strip()
        })
    
    return transcript_blocks


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
            word_norm.append(raw.lower())
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

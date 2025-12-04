import re

def normalize_transcript(raw_text):
    """
    Normalize a dialogue transcript into structured blocks.
    
    Returns:
        A list of dictionaries with keys:
            - type: "speech" or "action"
            - speaker: speaker name or None for actions
            - text: cleaned text of speech or action
    """
    # Regex to remove page number artifacts 
    PAGE_NUMBER_PATTERN = re.compile(r"[\n\n\s]{1,}[0-9]{1,}[\n\s]{1,}")

    # Regex to detect speaker lines
    speaker_pattern = re.compile(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)(?:\s\(([^)]+)\))?\s*$')
    
    # Regex to detect standalone actions [like this]
    action_pattern = re.compile(r'^\s*\[(.+?)\]\s*$')
    
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
        
        speaker_match = speaker_pattern.match(line)
        action_match = action_pattern.match(line)
        
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

def generate_clean_transcript(normalized_transcript):
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
            cleaned_text = re.sub(r'\[.*?\]', '', text).strip()
            if cleaned_text:  # Only include non-empty lines
                clean_transcript.append({
                    'speaker': entry['speaker'],
                    'text': cleaned_text,
                    'original_index': idx
                })
        else:
            # Non-speech segment, store for later reinsertion
            cue_map.append({
                'original_index': idx,
                'text': entry['text']
            })

    return clean_transcript, cue_map

from copy import deepcopy

def interpolate_missing_times(aligned_data):
    """
    Fill in start_time and end_time for words with None timestamps
    by linearly interpolating between neighboring words with valid times.
    """
    n = len(aligned_data)
    for i in range(n):
        if aligned_data[i]['start_time'] is None:
            # Find previous valid time
            prev_idx = i - 1
            while prev_idx >= 0 and aligned_data[prev_idx]['start_time'] is None:
                prev_idx -= 1
            
            # Find next valid time
            next_idx = i + 1
            while next_idx < n and aligned_data[next_idx]['start_time'] is None:
                next_idx += 1
            
            if prev_idx >= 0 and next_idx < n:
                # Linear interpolation
                prev_time = aligned_data[prev_idx]['end_time']
                next_time = aligned_data[next_idx]['start_time']
                gap = next_time - prev_time
                steps = next_idx - prev_idx
                delta = gap / steps
                aligned_data[i]['start_time'] = prev_time + delta * (i - prev_idx)
                aligned_data[i]['end_time'] = prev_time + delta * (i - prev_idx + 1)
            elif prev_idx >= 0:
                # Extrapolate forward
                aligned_data[i]['start_time'] = aligned_data[prev_idx]['end_time']
                aligned_data[i]['end_time'] = aligned_data[prev_idx]['end_time'] + 0.2  # default small duration
            elif next_idx < n:
                # Extrapolate backward
                aligned_data[i]['start_time'] = aligned_data[next_idx]['start_time'] - 0.2
                aligned_data[i]['end_time'] = aligned_data[next_idx]['start_time']
            else:
                # No neighboring times, default values
                aligned_data[i]['start_time'] = 0.0
                aligned_data[i]['end_time'] = 0.2
    return aligned_data


def reinsert_cues_with_interpolation(master_transcript, min_display_time=2, max_display_time=6.0):
    """
    Reinserts cues into the word-aligned transcript with interpolated durations.
    Speaker info is stored at the utterance level, not per word.

    Returns a list of utterances ready for SRT generation.
    """
    word_table = master_transcript['word_table']
    cue_table = master_transcript['cue_table']
    words = deepcopy(word_table)
    cues = deepcopy(cue_table)

    # Group words by utterance
    utterance_words = {}
    utterance_speakers = {}
    for i, utt_id in enumerate(words['utterance_id']):
        if utt_id not in utterance_words:
            utterance_words[utt_id] = []
            utterance_speakers[utt_id] = words['speaker_id'][i]  # assume all words in utterance have same speaker

        utterance_words[utt_id].append({
            'word': words['word_raw'][i],
            'start_time': words['start_time'][i],
            'end_time': words['end_time'][i],
            'pos_in_utt': words['pos_in_utt'][i]
        })

    reintegrated_utterances = []

    # Process cues (inline or standalone)
    for cue_idx, cue_id in enumerate(cues['cue_id']):
        utt_id = cues['utterance_id'][cue_idx]
        offset = cues['word_offset'][cue_idx]
        text = cues['text'][cue_idx]
        is_inline = cues.get('is_inline', [True]*len(cues['cue_id']))[cue_idx]

        # Standalone cues
        if not is_inline or utt_id is None:
            start_time = cues['start_time'][cue_idx] or 0.0
            end_time = cues['end_time'][cue_idx] or (start_time + min_display_time)
            duration = end_time - start_time
            if duration < min_display_time:
                end_time = start_time + min_display_time
            elif duration > max_display_time:
                end_time = start_time + max_display_time

            reintegrated_utterances.append({
                'text': text,
                'start_time': start_time,
                'end_time': end_time,
                'type': 'cue',
                'words': [],
                'speaker_id': None,
                'speaker_name': None
            })
            continue

        # Inline cues
        if utt_id in utterance_words:
            word_list = utterance_words[utt_id]

            if offset == 0:
                next_word = word_list[0]
                cue_start = next_word['start_time']
                cue_end = cue_start + min_display_time
            elif offset >= len(word_list):
                prev_word = word_list[-1]
                cue_start = prev_word['end_time']
                cue_end = cue_start + min_display_time
            else:
                prev_word = word_list[offset - 1]
                next_word = word_list[offset]
                cue_start = prev_word['end_time']
                cue_end = next_word['start_time']

            # enforce min/max duration
            duration = cue_end - cue_start
            if duration < min_display_time:
                cue_end = cue_start + min_display_time
            elif duration > max_display_time:
                cue_end = cue_start + max_display_time

            word_list.insert(offset, {
                'word': text,
                'start_time': cue_start,
                'end_time': cue_end,
                'pos_in_utt': offset
            })

    # Convert words back to utterances with speaker info at utterance level
    for utt_id, words_in_utt in utterance_words.items():
        text_pieces = [w['word'] for w in words_in_utt]
        start_times = [w['start_time'] for w in words_in_utt if w['start_time'] is not None]
        end_times = [w['end_time'] for w in words_in_utt if w['end_time'] is not None]

        speaker_id = utterance_speakers[utt_id]
        reintegrated_utterances.append({
            'text': ' '.join(text_pieces),
            'start_time': min(start_times) if start_times else None,
            'end_time': max(end_times) if end_times else None,
            'type': 'speech',
            'words': words_in_utt,
            'speaker_id': speaker_id,
            'speaker_name': master_transcript['speakers']['to_name'][speaker_id]
        })

    reintegrated_utterances.sort(key=lambda x: x['start_time'] if x['start_time'] is not None else float('inf'))
    return reintegrated_utterances


def chunk_utterance_for_srt(utterance, max_words=15, max_duration=6.0, min_duration=2.0):
    """
    Splits a single utterance into SRT-friendly chunks.
    Speaker info is included at the chunk level.

    utterance: dict from reintegrated_utterances
    max_words: maximum words per chunk
    max_duration: maximum seconds per chunk
    min_duration: minimum seconds per chunk

    Returns a list of subtitle chunks with 'text', 'start_time', 'end_time',
    'speaker_name', and 'speaker_id'.
    """
    words = utterance['words']
    chunks = []
    
    start_idx = 0
    while start_idx < len(words):
        # Determine chunk boundaries
        end_idx = min(start_idx + max_words, len(words))

        # Timing
        chunk_start_time = words[start_idx]['start_time'] or 0.0
        chunk_end_time = words[end_idx - 1]['end_time'] or chunk_start_time + min_duration
        duration = chunk_end_time - chunk_start_time

        # Extend chunk if under min_duration
        while duration < min_duration and end_idx < len(words):
            end_idx += 1
            chunk_end_time = words[end_idx - 1]['end_time'] or chunk_end_time
            duration = chunk_end_time - chunk_start_time
            if duration >= max_duration:
                break

        # Clip to max_duration
        if duration > max_duration:
            chunk_end_time = chunk_start_time + max_duration

        chunk_text = ' '.join([w['word'] for w in words[start_idx:end_idx]])
        chunks.append({
            'text': chunk_text,
            'start_time': chunk_start_time,
            'end_time': chunk_end_time,
            'speaker_name': utterance.get('speaker_name'),
            'speaker_id': utterance.get('speaker_id'),
            'type': utterance.get('type')
        })

        start_idx = end_idx

    return chunks


def chunk_reintegrated_utterances(reintegrated_utterances, **kwargs):
    """
    Processes all reintegrated utterances into SRT-ready chunks.
    Each utterance is never merged with another.
    """
    srt_chunks = []
    for utt in reintegrated_utterances:
        chunks = chunk_utterance_for_srt(utt, **kwargs)
        srt_chunks.extend(chunks)
    return srt_chunks


def normalise_subtitle_timings(
    subtitles,
    post_padding=0.25,
    absolute_floor=1.0,
    multi_word_floor=1.5,
    seconds_per_word=0.33
):
    """
    Normalises subtitle timings for readability and temporal sanity.

    Assumes subtitles are sorted by start_time.
    """
    normalised = []

    for i, sub in enumerate(subtitles):
        start = sub['start_time']
        end = sub['end_time']

        # -------------------------
        # 1. Compute minimum duration
        # -------------------------
        words = sub.get('display_text', sub.get('text', '')).strip().split()
        word_count = len(words)

        floor = absolute_floor
        if word_count > 1:
            floor = max(floor, multi_word_floor)

        estimated = word_count * seconds_per_word
        min_duration = max(floor, estimated)

        # Enforce minimum duration (NO overlap logic here)
        if (end - start) < min_duration:
            end = start + min_duration

        # -------------------------
        # 2. Apply post-padding (conditionally)
        # -------------------------
        padded_end = end + post_padding

        if normalised:
            prev = normalised[-1]

            same_speaker = (
                prev.get('speaker_id') == sub.get('speaker_id')
                and sub.get('type') == 'speech'
                and prev.get('type') == 'speech'
            )

            # Cues are invisible for overlap blocking
            if same_speaker and padded_end > prev['start_time']:
                # Clamp padding, NOT minimum duration
                padded_end = min(padded_end, prev['start_time'])

        end = max(end, padded_end)

        # -------------------------
        # 3. Write result
        # -------------------------
        normalised.append({
            **sub,
            'start_time': start,
            'end_time': end
        })

    return normalised


def annotate_speaker_colors(subtitles, speaker_colors=None, cue_color='grey'):
    """
    Adds color and prepends speaker name to first subtitle for each speaker.
    
    subtitles: list of dicts with 'text', 'speaker_name', 'speaker_id', 'type'
    speaker_colors: dict {speaker_id: color_string}
    cue_color: color string for cues
    
    Returns: updated list with 'display_text' and 'color' fields
    """
    if speaker_colors is None:
        # default colors if not provided
        colors = ['red', 'green', 'blue', 'orange', 'purple']
        unique_speakers = list({sub['speaker_id'] for sub in subtitles if sub['speaker_id'] is not None})
        speaker_colors = {sid: colors[i % len(colors)] for i, sid in enumerate(unique_speakers)}
    
    for sub in subtitles:
        if sub['type'] == 'cue':
            sub['color'] = cue_color
        else:
            sub['color'] = speaker_colors.get(sub['speaker_id'], 'white')
    
    return subtitles
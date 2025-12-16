from rapidfuzz import fuzz

def align_transcript_to_whisper_seq(transcript, whisper_transcript, seq_len=2, initial_window=5, max_window=12, match_threshold=70, log_candidates=False):
    """
    Align transcript to whisper using sequence-aware fuzzy matching.
    
    Returns:
        aligned: list of dicts with:
            - ref_idx
            - hyp_idx
            - start_time
            - end_time
            - score
    """
    transcript_words = transcript['word_table']['word_norm']
    whisper_words = whisper_transcript['word_norm']
    start_times = whisper_transcript['start_time']
    end_times = whisper_transcript['end_time']
    aligned = []
    ref_idx = 0
    hyp_idx = 0
    len_ref = len(transcript_words)
    len_hyp = len(whisper_words)
    
    while ref_idx < len_ref:
        # Build transcript sequence
        ref_seq = " ".join(transcript_words[ref_idx:ref_idx+seq_len])
        
        # Determine current sliding window in whisper
        window_end = min(hyp_idx + initial_window, len_hyp)
        candidates = []

        while True:
            for idx in range(hyp_idx, window_end):
                hyp_seq = " ".join(whisper_words[idx:idx+seq_len])
                score = fuzz.ratio(ref_seq, hyp_seq)
                if score >= match_threshold:
                    candidates.append((idx, score, len(hyp_seq.split())))
            
            if candidates or window_end >= min(hyp_idx + max_window, len_hyp):
                break
            window_end = min(window_end + 2, len_hyp)

        if candidates:
            # Pick best candidate
            best_idx, best_score, hyp_seq_len = max(candidates, key=lambda x: x[1])
            
            # Assign all words in sequence
            for i in range(seq_len):
                if ref_idx + i < len_ref and best_idx + i < len_hyp:
                    aligned.append({
                        'ref_idx': ref_idx + i,
                        'hyp_idx': best_idx + i,
                        'start_time': start_times[best_idx + i],
                        'end_time': end_times[best_idx + i],
                        'score': best_score
                    })
            if log_candidates:
                print(f"Ref seq '{ref_seq}' candidates:", [(whisper_words[i: i+seq_len], s) for i, s, _ in candidates])
            
            # Update indices
            ref_idx += seq_len
            hyp_idx = best_idx + hyp_seq_len
        else:
            # No match found
            aligned.append({
                'ref_idx': ref_idx,
                'hyp_idx': None,
                'start_time': None,
                'end_time': None,
                'score': None
            })
            ref_idx += 1

    return aligned

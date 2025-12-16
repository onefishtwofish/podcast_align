def write_to_ass(data, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

def insert_word_table_times(master_transcript, interpolated_transcript):
    """
    Updates the word_table with start/end times from the interpolated aligned transcript.
    Assumes order of words matches.
    """
    word_table = master_transcript['word_table']

    for i, word_info in enumerate(interpolated_transcript):
        word_table['start_time'][i] = word_info['start_time']
        word_table['end_time'][i] = word_info['end_time']
        word_table['aligned'][i] = True if word_info['start_time'] is not None else False
        word_table['confidence'][i] = word_info['score']
    
    master_transcript['word_table'] = word_table

    return master_transcript
from datetime import timedelta

# Color mapping from names to ASS BGR codes
ASS_COLOR_MAP = {
    'red':    '&H000000FF&',
    'green':  '&H0000FF00&',
    'blue':   '&H00FF0000&',
    'yellow': '&H0000FFFF&',
    'purple': '&H00FF00FF&',
    'cyan':   '&H00FFFF00&',
    'white':  '&H00FFFFFF&'
}


def color_name_to_ass(color_name: str) -> str:
    return ASS_COLOR_MAP.get(color_name.lower(), "&H00FFFFFF&")  # default white

def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass_styles(subtitles, base_style_name='Default'):
    """
    Builds per-speaker ASS styles based on annotated speaker colours.
    """
    styles = {}
    styles[base_style_name] = {
        'Name': base_style_name,
        'Fontname': 'Arial',
        'Fontsize': '36',
        'PrimaryColour': '&H00FFFFFF&'
    }

    for sub in subtitles:
        speaker = sub.get('speaker_name')
        color = sub.get('color')

        if not speaker or not color:
            continue

        style_name = f"Speaker_{speaker.replace(' ', '_')}"
        if style_name in styles:
            continue

        styles[style_name] = {
            'Name': style_name,
            'Fontname': 'Arial',
            'Fontsize': '36',
            'PrimaryColour': ASS_COLOR_MAP.get(color, '&H00FFFFFF&')
        }

    return styles


def transcript_to_ass(subtitles):
    """
    Converts normalised subtitles to ASS format using per-speaker styles.
    """
    styles = build_ass_styles(subtitles)

    lines = []

    # Script header
    lines.append("[Script Info]")
    lines.append("Title: Generated Subtitles")
    lines.append("ScriptType: v4.00+")
    lines.append("Collisions: Normal")
    lines.append("PlayResX: 1920")
    lines.append("PlayResY: 1080")
    lines.append("Timer: 100.0000\n")

    # Styles
    lines.append("[V4+ Styles]")
    lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )

    for style in styles.values():
        lines.append(
            f"Style: {style['Name']},"
            f"{style['Fontname']},"
            f"{style['Fontsize']},"
            f"{style['PrimaryColour']},"
            "&H000000FF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1"
        )

    lines.append("\n[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    for sub in subtitles:
        style_name = "Default"
        if sub.get('speaker_name'):
            style_name = f"Speaker_{sub['speaker_name'].replace(' ', '_')}"

        text = sub.get('display_text', sub.get('text', ''))

        lines.append(
            f"Dialogue: 0,"
            f"{format_ass_time(sub['start_time'])},"
            f"{format_ass_time(sub['end_time'])},"
            f"{style_name},"
            f"{sub.get('speaker_name','')},0,0,0,,"
            f"{text}"
        )

    return "\n".join(lines)
"""JSON schema for the structured Ad Plan produced by the Seed LLM script agent.
Kept flat and well-described per BytePlus structured-output guidance."""

AD_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "Short internal name for this ad"},
        "brand": {"type": "string", "description": "Brand / dealer name"},
        "product": {"type": "string", "description": "Product being advertised"},
        "language": {"type": "string", "description": "Spoken language mix, e.g. 'Hindi + English'"},
        "duration_seconds": {"type": "integer", "description": "Target length, 8-30"},
        "aspect": {"type": "string", "description": "Aspect ratio, e.g. '9:16'"},
        "music_mood": {"type": "string", "description": "Background music mood/tempo"},
        "hooks": {"type": "array", "description": "2-3 alternative opening hook lines (Hindi+English)",
                  "items": {"type": "string"}},
        "scenes": {
            "type": "array",
            "description": "Ordered beats of ONE continuous ad on a single timeline",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer", "description": "1-based beat order"},
                    "t_start": {"type": "number", "description": "Beat start time in seconds"},
                    "t_end": {"type": "number", "description": "Beat end time in seconds"},
                    "action": {"type": "string", "description": "What happens visually: subject, camera, setting, motion"},
                    "camera": {"type": "string", "description": "Camera framing/movement, e.g. 'medium tracking'"},
                    "vo_hindi": {"type": "string", "description": "Voiceover line in Hindi (Devanagari), '' if none"},
                    "vo_english": {"type": "string", "description": "English meaning of the VO line, '' if none"},
                    "on_screen_text": {"type": "string", "description": "Short badge text for this beat (English/number only), '' if none"}
                },
                "required": ["index", "t_start", "t_end", "action", "camera",
                             "vo_hindi", "vo_english", "on_screen_text"]
            }
        },
        "director_brief": {
            "type": "string",
            "description": ("ONE continuous prompt for Seedance 2.5 describing the whole "
                            "ad as a single coherent video: sequential beats with cuts, "
                            "camera moves, on-screen action, and each spoken line wrapped "
                            "in double quotes. <= 900 words.")
        },
        "overlay_text": {
            "type": "array",
            "description": "Exact brand text to composite in POST (logo, contact, Hindi/number badges)",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string"},
                    "position": {"type": "string", "description": "e.g. 'top-center', 'bottom-bar', 'top-left'"},
                    "t_start": {"type": "number"},
                    "t_end": {"type": "number"}
                },
                "required": ["text", "position", "t_start", "t_end"]
            }
        }
    },
    "required": ["title", "brand", "product", "language", "duration_seconds",
                 "aspect", "music_mood", "hooks", "scenes", "director_brief", "overlay_text"]
}

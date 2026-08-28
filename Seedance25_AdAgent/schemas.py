"""JSON schema for the structured Ad Plan produced by the Seed LLM script agent.
Kept flat and well-described per BytePlus structured-output guidance."""

AD_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "Short internal name for this ad"},
        "brand": {"type": "string", "description": "Brand / dealer name"},
        "product": {"type": "string", "description": "Product being advertised"},
        "presenter": {"type": "string", "description": (
            "A concise physical description of the on-screen presenter (age, gender, look, "
            "wardrobe) — used ONLY as a fallback to generate the first keyframe when the user "
            "has NOT provided a presenter reference image. Keyframe/scene prompts must NOT "
            "repeat this; they refer to 'the presenter' generically.")},
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
                    "action": {"type": "string", "description": "What happens in the VIDEO for this beat: subject, camera, motion, cuts, effects"},
                    "camera": {"type": "string", "description": "Camera framing/movement, e.g. 'medium tracking'"},
                    "keyframe_prompt": {"type": "string", "description": (
                        "A CLEAN still-image prompt for Seedream (the storyboard frame for this beat). "
                        "Refer to the person ONLY as 'the presenter' and the product ONLY generically "
                        "('the product'/'the shoe'/'the car'). Do NOT describe the presenter's face, hair, "
                        "age, ethnicity, build or wardrobe, and do NOT invent the product's brand, colour, "
                        "model or markings (identity AND product appearance come from the reference images, "
                        "bound by the app as @image1, @image2). Describe ONLY: the presenter's pose/action, "
                        "how the product is shown, the environment, camera framing and lighting, in "
                        "Seedream's 6-part style. MUST NOT include camera cuts/transitions, motion, floating "
                        "icons/holograms/UI/graphic props, on-screen text, badges, or Hindi text (added "
                        "later). Exactly one product/vehicle in frame.")},
                    "vo_hindi": {"type": "string", "description": "Voiceover line in Hindi (Devanagari), '' if none"},
                    "vo_english": {"type": "string", "description": "English meaning of the VO line, '' if none"},
                    "on_screen_text": {"type": "string", "description": "Short badge text for this beat (English/number only), '' if none"}
                },
                "required": ["index", "t_start", "t_end", "action", "camera", "keyframe_prompt",
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
    "required": ["title", "brand", "product", "presenter", "language", "duration_seconds",
                 "aspect", "music_mood", "hooks", "scenes", "director_brief", "overlay_text"]
}

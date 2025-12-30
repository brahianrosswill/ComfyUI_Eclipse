# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from ..core import CATEGORY


def _is_tags_format(text: str) -> bool:
    """Detect if text is tag-based prompt format (Danbooru/NAI style).
    
    Checks for multiple indicators:
    - Underscore tags: long_hair, blue_eyes
    - Weight syntax: (tag:1.2)
    - Double parentheses: ((emphasis))
    - Common quality tags: masterpiece, best quality, highres, etc.
    - Count tags: 1girl, 2boys, 1other
    """
    tag_indicators = [
        r'\b\w+_\w+',                              # underscore tags
        r'\([^)]+:\d+\.?\d*\)',                    # weight syntax
        r'\(\([^)]+\)\)',                          # double parens
        r'\b(?:masterpiece|best[_\s]?quality|highres|absurdres|4k|8k)\b',  # quality tags
        r'\b\d+(?:girl|boy|other)s?\b',            # count tags
    ]
    return any(re.search(p, text, re.I) for p in tag_indicators)


class RvText_ReplaceStringV3:
    CATEGORY = CATEGORY.MAIN.value + CATEGORY.TEXT.value
    RETURN_TYPES = ("STRING",)
    FUNCTION = "execute"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "string": ("STRING", {"default": "", "forceInput": False,"tooltip": "Input string to process."}),
                "regex": ("STRING", {"default": "", "tooltip": "Regular expression pattern to match."}),
                "replace_with": ("STRING", {"default": "", "tooltip": "Replacement string for matches."}),
                "remove_instructions": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, extract content from quotes at the start of the string, or if no quotes, remove everything before the first colon (:) including the colon itself."}),                                
                "list_select_first": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If enabled, extract the first numbered quoted choice (1.) from LLM output and use it as the result."}),
                "list_to_string": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If enabled, convert a numbered tips list into a single-line prompt and remove short labels (e.g., 'Lighting:')."}),
                "remove_background": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove background description matches."}),
                "remove_subject": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove subject description matches."}),
                "remove_subject_aggressive": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, remove pronoun-led subject clauses and possessive subject phrases (aggressive)."}),
                "remove_mood": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove mood description matches."}),
                "remove_image": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove image description matches."}),
                "remove_shot_style": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove camera angles and shot types (close-up, portrait, from above, cowboy shot, looking at viewer, etc.)."}),
                "adjust_age": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Replace age references with the specified target age."}),
                "age": ("INT", {"default": 25, "min": 18, "max": 99, "step": 1, "tooltip": "Target age to use when adjust_age is enabled."}),
                "remove_nsfw": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove explicit NSFW content (nude, nipples, genitals, sex acts, etc.). Does NOT remove breast sizes or underwear."}),
                "remove_watermark": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove phrases containing 'watermark' (e.g., 'has a watermark in the top left corner')."}),
                "cleanup": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, trim whitespace and remove surrounding quotes from the final output."}),
                
            }
        }

    def execute(
        self,
        string: str,
        regex: str,
        replace_with: str,
        remove_background: bool = False,
        remove_subject: bool = False,
        remove_subject_aggressive: bool = False,
        remove_mood: bool = False,
        remove_image: bool = False,
        remove_shot_style: bool = False,
        adjust_age: bool = False,
        age: int = 25,
        remove_nsfw: bool = False,
        remove_watermark: bool = False,
        cleanup: bool = False,
        list_select_first: bool = False,
        list_to_string: bool = False,
        remove_instructions: bool = False,
    ) -> tuple[str]:

        # Process string with regex replacement and optional description removals
        s = string or ""

        # Return unchanged if no operations requested
        try:
            no_toggles = not any([
                list_select_first,
                list_to_string,
                remove_background,
                remove_subject,
                remove_subject_aggressive,
                remove_mood,
                remove_image,
                remove_shot_style,
                adjust_age,
                remove_nsfw,
                remove_watermark,
                remove_instructions,
            ])
        except Exception:
            no_toggles = True

        if no_toggles and not (regex and str(regex).strip()):
            return (s,)

        # Preprocessing steps
        try:
            if remove_instructions and s.strip():
                # First check for quoted content at start
                quote_match = re.match(r'^\s*["\']([^"\']*)["\']', s.strip())
                if quote_match:
                    s = quote_match.group(1)
                else:
                    # Check for instruction-like prefix (case insensitive)
                    # Matches: "Here is your prompt:", "Description:", "Prompt:", "Image description:", "Output:", etc.
                    instruction_pat = r'^(?:here\s+is\s+(?:your\s+|the\s+)?(?:expanded\s+)?)?(?:expanded\s+)?(?:prompt|description|caption|image\s+description|output|result|response|answer|text)\s*:\s*'
                    match = re.match(instruction_pat, s.strip(), re.I)
                    if match:
                        s = s.strip()[match.end():].strip()
                    else:
                        # Handle multiline: check if first line is instruction header ending with colon
                        lines = s.strip().split('\n')
                        if len(lines) > 1:
                            first_line = lines[0].strip()
                            if first_line.endswith(':') and len(first_line) < 60:
                                instruction_words = ['prompt', 'description', 'caption', 'output', 'result', 'expanded', 'here', 'text', 'image']
                                if any(word in first_line.lower() for word in instruction_words):
                                    s = '\n'.join(lines[1:]).strip()

            if list_select_first and s.strip():
                m = re.search(r'(?s)^\s*1\.\s*(?:["\'])(.*?)(?:["\'])', s, flags=re.M)
                if m:
                    s = m.group(1)

            if list_to_string and s.strip():
                s = re.sub(r'(?s)^.*?(?=\d+\.)', '', s)  # remove header up to first numbered item
                s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)  # remove bold markup
                s = re.sub(r'(?m)^\s*\d+\.\s*', '||', s)  # mark numbered items with delimiter
                s = re.sub(r'(?i)\b(?:lighting|composition|details|background|pose|makeup|props|editing|focus|storytelling)\s*:\s*', '', s)  # remove short label tokens
                s = re.sub(r'[\r\n\t]+', ' ', s)  # collapse newlines/tabs
                s = s.replace('||', ', ')  # replace delimiters with comma
                s = re.sub(r'^,\s+', '', s)  # clean leading comma
                s = re.sub(r'[ ]{2,}', ' ', s).strip()  # collapse extra spaces
        except Exception:
            pass

        if s.strip():
            try:
                # Regex patterns for description removal
                # Background: removes background/environment descriptions, stops before ", the" or ". the" to preserve "the overall" phrases
                background_pat = r"(?i)(?:(?:(?:the\s+)?backgrounds?|environment|setting|scene|surroundings|in the backgrounds?|in the environment|in the setting|in the scene|in the surroundings)\s*[:\-–]?\s*.*?(?=,\s+the|\.\s+the)|(?:[\.\?!,]\s*(?:The\s+)?(?:backgrounds?|environment|setting|scene|surroundings|in the background)\s+.*?(?=,\s+the|\.\s+the)))"
                # Subject: removes subject/person labels and descriptions
                # For structured prompts with "Subject:" label - remove entire section
                subject_label_pat = r"(?i)(?:^|[\s,]+)subject\s*:\s*[^.!?\n]+[.!?\n]?"
                # Subject words to match (with word boundary to avoid 1girl/1boy)
                subject_words = r"\b(?:woman|man|girl|boy|person|people|figure|individual|character|lady|gentleman|child|baby|teenager|adult)\b"
                # Mood: removes mood/atmosphere/vibe descriptions, including "overall" phrases, stops before ", the" or ". the" to preserve other "the overall" descriptions
                mood_pat = r"(?is)(?:\b(?:mood|moods|feeling|feelings|atmosphere|vibe|vibes|overall)\b\s*[:\-–]?\s*.*?(?=,\s+the|\.\s+the|[\n\.;]*$)|(?:^|[\.\?!,]\s*)(?:The\s+)?overall\s+.*?(?=,\s+the|\.\s+the|[\n\.;]*$)|(?:^|[\.\?!,]\s*)(?:The\s+)?(?:mood|moods|feeling|feelings|atmosphere|vibe|vibes)(?:\s+of(?:\s+the)?\s+(?:image|photograph|photo|scene|shot))?(?:\s+is|\s+are)?\s+.*?(?=,\s+the|\.\s+the|[\n\.;]*$))"
                # Image: removes image/photo labels and descriptions, avoids subject words like portrait/woman/man
                image_pat = r"(?i)(?:(?:\b(?:image|photo|photograph|picture|shot|render|illustration)\b)\s*(?:[:\-–]\s*|(?:is|was)\s+)(?![^\n\.;]{0,120}\b(?:portrait|woman|man|girl|boy|person|people|subject)\b)[^\n\.;]{1,200}[\n\.;]?)"

                def _preserve_lead(match):
                    lead = re.match(r'^\s*([\.\?!,])\s*', match.group(0))
                    if lead:
                        return lead.group(1) + ' '
                    return ''

                if remove_background:
                    s = re.sub(background_pat, _preserve_lead, s, flags=re.S)  # remove background descriptions
                if remove_subject:
                    original_for_fallback = s  # Save original in case removal leaves nothing
                    
                    if _is_tags_format(s):
                        # TAGS FORMAT: Remove subject-related tags, keep background/setting tags
                        tags = [t.strip() for t in s.split(',')]
                        
                        # Subject-related tag patterns (to REMOVE)
                        subject_tag_patterns = [
                            r'^\d*(?:girl|boy|woman|man|person|people)s?$',  # 1girl, 2boys, woman, etc.
                            r'^(?:solo|duo|trio|group|crowd)$',  # count indicators
                            r'^(?:male|female)_focus$',  # focus tags
                            r'^(?:blonde|black|brown|red|blue|green|pink|purple|white|grey|gray|silver|golden|orange)_(?:hair|eyes?)$',  # hair/eye color
                            r'^(?:long|short|medium|wavy|curly|straight|messy|wet)_hair$',  # hair style
                            r'^(?:ponytail|braid|twin_?tails|bun|pigtails|bob_cut|bangs|ahoge|hair_ornament|hairpin|hairclip)$',  # hair styles
                            r'^(?:large|medium|small|huge|flat)_breasts?$',  # body
                            r'^(?:slim|muscular|chubby|tall|short|petite)$',  # body type
                            r'^(?:smile|smiling|frown|angry|sad|happy|crying|blushing|blush|open_mouth|closed_mouth|teeth|tongue|fangs)$',  # expressions
                            r'^(?:sitting|standing|lying|kneeling|crouching|walking|running|jumping|posing|leaning)$',  # poses
                            r'^(?:looking_at_viewer|looking_away|looking_down|looking_up|looking_back|from_behind|from_side|from_above|from_below)$',  # viewpoint
                            r'^(?:nude|naked|topless|bottomless|barefoot|bare_(?:legs|arms|shoulders|back|feet))$',  # nudity
                            r'^(?:nipples?|areola|pussy|vagina|penis|cock|genitals?|anus|pubic_hair)$',  # explicit body parts
                            r'^(?:sex|sexual|uncensored|explicit|spread_legs|cameltoe|no_panties|no_bra)$',  # explicit content
                            r'^(?:bdsm|bondage|hentai|ahegao|futanari?|loli|shota)$',  # explicit tags
                            r'^(?:dress|shirt|skirt|pants|shorts|uniform|bikini|swimsuit|lingerie|underwear|panties|bra|stockings|socks|shoes|boots|heels|gloves|jacket|coat|sweater|hoodie|tank_top|crop_top|t-shirt|jeans|leggings|tights)$',  # clothing
                            r'^(?:jewelry|earrings?|necklace|bracelet|ring|watch|glasses|sunglasses|hat|cap|ribbon|bow|collar|choker|piercing)$',  # accessories
                            r'^(?:tattoo|scar|mole|freckles|makeup|lipstick|eyeshadow|nail_polish|painted_nails)$',  # body details
                            r'^(?:upper_body|lower_body|full_body|cowboy_shot|portrait|close-?up|headshot)$',  # framing (subject-focused)
                            r'^(?:young|old|elderly|teenage|mature|child|baby|adult|milf|loli|shota)$',  # age
                            r'^(?:dark_skin|pale_skin|tan|skin_texture)$',  # skin
                            r'^(?:navel|cleavage|thighs?|legs?|arms?|hands?|feet|ass|butt|hips)$',  # body parts
                            r'^(?:spread_legs|crossed_arms|hands_on_hips|arm_up|arms_up|legs_up|on_back|on_stomach|all_fours|lying_on_back)$',  # poses
                            r'^(?:aesthetic|beautiful|gorgeous|stunning|amazing|perfect|flawless)$',  # subject aesthetics
                            r'^(?:sharp[_\s]?focus|detailed[_\s]?face|detailed[_\s]?skin|detailed[_\s]?eyes)$',  # subject detail focus
                        ]
                        
                        # Background/setting tag patterns (to KEEP)
                        background_tag_patterns = [
                            r'_background$',  # anything ending in _background
                            r'^(?:indoors?|outdoors?)$',
                            r'^(?:day|night|sunset|sunrise|dusk|dawn|evening|morning)$',
                            r'^(?:forest|garden|beach|ocean|sea|mountain|city|town|street|room|bedroom|bathroom|kitchen|living_room|office|school|classroom|library|gym|pool|park|cafe|restaurant|bar|club|church|temple|castle|palace|dungeon|cave|desert|jungle|meadow|field|farm|barn|bridge|tower|ruins|graveyard)$',
                            r'^(?:sky|clouds?|sun|moon|stars?|rain|snow|fog|mist|wind|storm|lightning|rainbow)$',
                            r'^(?:water|river|lake|pond|waterfall|fountain)$',
                            r'^(?:tree|trees|grass|flowers?|plants?|leaves|petals)$',
                            r'^(?:window|door|wall|floor|ceiling|stairs|bed|chair|table|desk|sofa|couch)$',
                            r'^(?:realistic|photorealistic|detailed|high_quality|best_quality|masterpiece|aesthetic)$',  # quality tags
                            r'^(?:dramatic_lighting|soft_lighting|natural_lighting|backlighting|rim_lighting|studio_lighting)$',
                            r'^(?:bokeh|depth_of_field|blurry_background|motion_blur)$',
                            r'^(?:cinematic|film_grain|lens_flare|light_rays|volumetric_lighting)$',
                        ]
                        
                        kept_tags = []
                        for tag in tags:
                            tag_clean = tag.strip().lower().replace(' ', '_').replace('-', '_')
                            
                            # Check if it's a subject tag
                            is_subject = any(re.match(pat, tag_clean, re.I) for pat in subject_tag_patterns)
                            
                            # Check if it's explicitly a background tag
                            is_background = any(re.match(pat, tag_clean, re.I) for pat in background_tag_patterns)
                            
                            # Keep if it's a background tag OR if it's not identified as subject
                            if is_background or not is_subject:
                                kept_tags.append(tag)
                        
                        if kept_tags:
                            s = ', '.join(kept_tags)
                        # If nothing left, s will be empty and we'll restore original below
                    
                    else:
                        # PROSE FORMAT: Extract setting, remove subject descriptions
                        # 1. Remove "Subject: ..." labeled sections (structured prompts)
                        s = re.sub(subject_label_pat, ' ', s)
                        
                        # 2. For prose: Find setting descriptions and extract them
                        setting_words = r'(?:setting|room|space|studio|environment|background|scene|area|place|location|forest|garden|field|beach|city|town|street|building|house|office|bedroom|bathroom|kitchen|living|patio|balcony|terrace|yard|park|plaza|square|alley|hallway|corridor|warehouse|factory|gym|pool|arena|stadium|theater|church|temple|castle|palace|dungeon|cave|mountain|valley|river|lake|ocean|sea|shore|cliff|desert|jungle|swamp|meadow|prairie|tundra|island|village|farm|barn|stable|garage|basement|attic|rooftop|deck|dock|pier|bridge|tunnel|subway|station|airport|hospital|school|library|museum|gallery|restaurant|cafe|bar|club|hotel|motel|cabin|cottage|mansion|apartment|condo|loft|penthouse)'
                        
                        # Check if text STARTS with a setting word (no subject before it)
                        first_words = s.split()[:5]
                        starts_with_setting = False
                        for i, word in enumerate(first_words):
                            clean_word = re.sub(r'[,.]', '', word.lower())
                            if re.match(setting_words, clean_word, re.I):
                                words_before = [re.sub(r'[,.]', '', w.lower()) for w in first_words[:i]]
                                has_subject_before = any(re.search(subject_words, w, re.I) for w in words_before)
                                if not has_subject_before:
                                    starts_with_setting = True
                                break
                        
                        if not starts_with_setting:
                            # Pattern: [preposition] [article] [optional adjectives] [setting word]
                            setting_pattern = rf'(?i)\s+(in|at|on|by|near|against|beside|within|inside|outside|through|across|around|along|under|over|beneath|above)\s+(a|an|the)\s+(?:[\w\-,]+\s+)*?{setting_words}\b[^.]*'
                            
                            setting_match = re.search(setting_pattern, s)
                            if setting_match:
                                before_setting = s[:setting_match.start()]
                                if re.search(subject_words, before_setting, re.I):
                                    s = setting_match.group(0).strip()
                        
                        # 3. Remove standalone sentences starting with subject references
                        pronoun_sentence_pat = r"(?i)(?:^|(?<=\.\s))(?:he|she|they|the\s+(?:woman|man|girl|boy|person|figure))\s+[^.!?]+[.!?]\s*"
                        s = re.sub(pronoun_sentence_pat, '', s)
                        
                        # 4. Clean up artifacts
                        s = re.sub(r'(?i)^[\s,]*(?:and|or|but|while|as)\s+', '', s)
                        s = re.sub(r'^\s*[,\.]\s*', '', s)
                        s = re.sub(r'\s*,\s*,', ',', s)
                    
                    # SAFETY: If removal left nothing meaningful, restore original
                    s_clean = re.sub(r'[\s,]+', '', s)
                    if not s_clean or len(s_clean) < 3:
                        s = original_for_fallback
                    
                if remove_mood:
                    s = re.sub(mood_pat, _preserve_lead, s, flags=re.S)  # remove mood/atmosphere descriptions
                if remove_image:
                    if _is_tags_format(s):
                        # TAG FORMAT: Remove quality/style/image type tags
                        tags = [t.strip() for t in s.split(',')]
                        
                        # Image/quality tag patterns to remove
                        image_tag_patterns = [
                            r'^(?:masterpiece|best[_\s]?quality|high[_\s]?quality|highest[_\s]?quality|low[_\s]?quality|worst[_\s]?quality)$',
                            r'^(?:extremely[_\s]?detailed|highly[_\s]?detailed|very[_\s]?detailed|ultra[_\s]?detailed|intricate[_\s]?details?)$',
                            r'^(?:realistic|photorealistic|photo[_\s]?realistic|hyper[_\s]?realistic|semi[_\s]?realistic)$',
                            r'^(?:4k|8k|hd|uhd|high[_\s]?resolution|absurdres|highres|incredibly[_\s]?absurdres)$',
                            r'^(?:illustration|digital[_\s]?illustration|digital[_\s]?art|digital[_\s]?painting|cg|3dcg|2d)$',
                            r'^(?:render|rendered|3d[_\s]?render|octane[_\s]?render|unreal[_\s]?engine)$',
                            r'^(?:photo|photograph|photography|professional[_\s]?photo|raw[_\s]?photo)$',
                            r'^(?:painting|oil[_\s]?painting|watercolor|sketch|drawing|artwork|anime|manga)$',
                            r'^(?:award[_\s]?winning|trending[_\s]?on[_\s]?artstation|artstation|deviantart|pixiv)$',
                            r'^(?:concept[_\s]?art|official[_\s]?art|promotional[_\s]?art|game[_\s]?cg|visual[_\s]?novel)$',
                            r'^(?:nsfw|sfw|safe|explicit|questionable|suggestive)$',  # rating tags
                        ]
                        
                        kept_tags = []
                        for tag in tags:
                            tag_clean = tag.strip().lower().replace(' ', '_').replace('-', '_')
                            is_image_tag = any(re.match(pat, tag_clean, re.I) for pat in image_tag_patterns)
                            if not is_image_tag:
                                kept_tags.append(tag)
                        
                        s = ', '.join(kept_tags) if kept_tags else s
                    else:
                        # PROSE FORMAT: Original remove_image logic
                        s = re.sub(r'(?i)^[\s]*the\s+image\s+is\s+', '', s)  # remove "the image is" prefix
                        s = re.sub(r'(?i)^(?:.*?\b)?(?:close[- ]?up\s+portrait\s+of\s+|portrait\s+of\s+|headshot\s+of\s+)', '', s)  # remove portrait prefixes
                        
                        # Handle "a [adjectives] [image type] in [complex style], it depicts/featuring" 
                        # e.g., "a highly detailed, digital illustration in a semi-realistic, anime-inspired style, it depicts a young woman"
                        # e.g., "a highly detailed, digital illustration in an anime style, featuring a young woman"
                        s = re.sub(
                            r'(?i)^(?:a|an)\s+(?:[\w\-]+[,\s]+)*?(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+in\s+.*?style,?\s*(?:it\s+depicts|featuring)\s+',
                            '', s)
                        
                        # Handle "a [adjectives] [image type] depicting" (e.g., "a digital illustration depicting a girl")
                        s = re.sub(
                            r'(?i)^(?:a|an)\s+(?:[\w\-]+[,\s]+)*?(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+depicting\s+',
                            '', s)
                        
                        # Handle "[Style]-style [image type] of" at start (e.g., "Anime-style illustration of a girl")
                        s = re.sub(
                            r'(?i)^[\w\-]+-style\s+(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+of\s+',
                            '', s)
                        
                        # Handle "A/An [adjectives] [style]-style [image type] of" (e.g., "A vibrant anime-style illustration of")
                        s = re.sub(
                            r'(?i)^(?:a|an)\s+(?:[\w\-]+\s+)*?[\w\-]+-style\s+(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+of\s+',
                            '', s)
                        
                        # Handle "[image type] in [style] style of" (e.g., "Digital illustration in anime style of")
                        s = re.sub(
                            r'(?i)^(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+in\s+(?:an?\s+)?[\w\-]+\s+style\s+of\s+',
                            '', s)
                        
                        # Handle "A/An [image type] in [style] style of"
                        s = re.sub(
                            r'(?i)^(?:a|an)\s+(?:[\w\-]+\s+)*?(?:digital\s+)?(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)\s+in\s+(?:an?\s+)?[\w\-]+\s+style\s+of\s+',
                            '', s)
                        
                        # Remove style descriptors before subjects (e.g., "anime-style girl" -> "girl")
                        # Pattern: [style]-style [subject] -> [subject]
                        style_before_subject = (
                            r'\b(?:anime|cartoon|manga|comic|realistic|photorealistic|semi[- ]?realistic|'
                            r'hyper[- ]?realistic|stylized|cel[- ]?shaded|3d|2d|cgi|digital|painted|'
                            r'illustrated|artistic|fantasy|sci[- ]?fi|cyberpunk|steampunk|gothic|'
                            r'vintage|retro|modern|classic|traditional|western|eastern|japanese|'
                            r'korean|chinese|american)[- ]?(?:style|styled)?\s+'
                            r'(?=(?:girl|boy|woman|man|person|figure|character|lady|gentleman|'
                            r'child|teen|teenager|adult|individual|model|subject)\b)'
                        )
                        s = re.sub(style_before_subject, '', s, flags=re.I)
                    
                        # Handle "A [adjectives] digital illustration/photo/etc of [subject]" - REMOVE article + type, keep subject
                        # e.g. "A highly detailed and realistic digital illustration of a menacing man" -> "a menacing man"
                        # e.g. "A black and white photo shoot from angle about a portrait of a woman" -> "a woman"
                        s = re.sub(
                            r'(?i)^[\s]*(?:a|an)\s+'  # article
                            r'(?:[\w\-]+[,\s]+)*?'  # adjectives (highly, detailed, realistic, etc.)
                            r'(?:semi-?realistic\s+)?'  # optional semi-realistic
                            r'(?:photo[- ]?realistic\s+)?'  # optional photo-realistic
                            r'(?:digital\s+)?'  # optional digital
                            r'(?:illustration|painting|drawing|sketch|photograph|photo|render|image|picture)'  # image type
                            r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?'  # optional "in a style"
                            r'\s+of\s+',  # "of " 
                            '', s)  # Remove everything including "of ", keep what follows
                        
                        # Handle "A [adjectives] [style]-style [image type] from [angle] camera angle, depicting a [subject]"
                        # e.g. "A vibrant anime-style digital illustration from a side camera angle, depicting a young woman"
                        # Remove image type/style but PRESERVE angle info for remove_shot_style to handle
                        s = re.sub(
                            r'(?i)^[\s]*(?:a|an)\s+'  # article
                            r'(?:[\w\-]+\s+)*?'  # optional adjectives (vibrant, etc.)
                            r'[\w\-]+-style\s+'  # style descriptor (anime-style, etc.)
                            r'(?:(?:digital\s+)?(?:illustration|painting|drawing|sketch|photograph|photo|render|image|picture)\s+)?'  # optional image type
                            r'(from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*,?\s*)?'  # capture angle (group 1) - optional
                            r'depicting\s+(?=a\s+|an\s+|\w)',  # depicting - lookahead to preserve article
                            r'\1', s)  # Keep angle if present, remove rest
                        
                        # Handle "A [adjectives] shoot from [angle] about [a portrait of] a [subject]"
                        # e.g. "A black and white photo shoot from a close-up camera angle about a portrait of a young woman"
                        # Remove image type but PRESERVE angle info for remove_shot_style to handle
                        s = re.sub(
                            r'(?i)^[\s]*(?:a|an)\s+'  # article
                            r'(?:[\w\-]+[,\s]+)*?'  # adjectives
                            r'(?:photo[- ]?realistic\s+)?'  # optional photo-realistic
                            r'(?:photo\s+)?'  # optional "photo"
                            r'shoot\s+'  # shoot
                            r'(from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*)?'  # capture angle (group 1) - optional
                            r'about\s+(?:(?:a\s+)?portrait\s+of\s+)?(?=a\s+|an\s+|\w)',  # about [a portrait of] - lookahead to preserve article
                            r'\1', s)  # Keep angle if present, remove rest
                        
                        # Handle "A [adjectives] digital illustration/photo/etc [continuation]" - preserve meaningful descriptors
                        # This handles cases with "shoot", "shot", "where", "depicting" etc.
                        # e.g. "A photo-realistic shoot from..." -> "A shoot from..."
                        # e.g. "A digital illustration shoot from the side" -> "A shoot from the side"
                        s = re.sub(
                            r'(?i)^([\s]*(?:a|an)\s+)'  # capture article - group 1
                            r'((?:close[- ]?up|wide[- ]?angle|full[- ]?body|half[- ]?body|waist[- ]?up|medium[- ]?shot|establishing|extreme)[,\s]*)?'  # capture meaningful shot descriptor (optional) - group 2
                            r'(?:[\w\-]+[,\s]+)*?'  # skip other adjectives like anime-style (non-greedy)
                            r'(?:semi-?realistic\s+)?'  # optional semi-realistic
                            r'(?:photo[- ]?realistic\s+)?'  # optional photo-realistic
                            r'(?:digital\s+)?'  # optional digital
                            r'(?:illustration|painting|drawing|sketch|photograph|photo|render|image|picture)'  # image type
                            r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?'  # optional "in a style"
                            r'(\s+(?:featuring|shoot|shot|where|depicting|showing)\b)',  # capture continuation word - group 3 (NOT "of")
                            lambda m: m.group(1) + (m.group(2).rstrip(', ') + ' ' if m.group(2) else '') + m.group(3).lstrip(), s)  # keep article + shot descriptor + continuation
                        
                        # Now apply the simpler patterns
                        s = re.sub(r'(?i)^[\s]*(?:a|an)\s+(?:[\w\-]+\s+)*(?:illustration|painting|drawing|sketch|photograph|photo)\s+(?:of\s+|featuring\s+)', '', s)  # remove "a [adjectives] illustration of/featuring"
                        s = re.sub(r'(?i)^[\s]*(?:a|an)\s+(?:[\w\-]+\s+)*(?:illustration|painting|drawing|sketch|photograph|photo)\s+in\s+(?:an?\s+)?[\w\s]+(?:style|art)\s*,?\s*featuring\s+', '', s)  # remove "a [adjectives] illustration in style, featuring"
                        
                        # Handle "A [adjectives] digital illustration/photo/etc in a [style]" without continuation - remove entire phrase
                        # e.g. "A semi-realistic digital illustration in a nontraditional anime style" -> ""
                        s = re.sub(
                            r'(?i)^[\s]*(?:a|an)\s+'  # article
                            r'(?:[\w\-]+[,\s]+)*?'  # optional adjectives
                            r'(?:semi-?realistic\s+)?'  # optional semi-realistic
                            r'(?:photo[- ]?realistic\s+)?'  # optional photo-realistic
                            r'(?:digital\s+)?'  # optional digital
                            r'(?:illustration|painting|drawing|sketch|photograph|photo|render|image|picture)'  # image type
                            r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?'  # optional "in a style"
                            r'[,\s]*$',  # end of string (possibly with trailing comma/space)
                            '', s)
                        
                        # Handle standalone image type words with adjectives that should be removed entirely
                        # e.g. "photo realistic" -> "" or "digital illustration" -> ""
                        s = re.sub(
                            r'(?i)\b(?:semi-?realistic\s+)?(?:photo[- ]?realistic|digital\s+illustration|digital\s+painting|digital\s+art)\b[,\s]*',
                            '', s)
                        
                        # Remove dangling style descriptors like "anime-style" when followed by "of" or comma
                        s = re.sub(r'(?i)[,\s]*[\w\-]+-style[,\s]*(?=of\b)', '', s)
                        
                        # Clean up "A where" -> capitalize what follows where
                        s = re.sub(r'(?i)^([\s]*(?:a|an)\s+)(where\b)', lambda m: m.group(2).capitalize(), s)
                        
                        # Clean up multiple spaces and commas
                        s = re.sub(r',\s*,', ',', s)  # collapse double commas
                        s = re.sub(r',\s+(?=of\b)', ' ', s)  # remove comma before "of"
                        s = re.sub(r' {2,}', ' ', s)
                        s = re.sub(r'^[,\s]+', '', s)  # remove leading comma/space
                        
                        image_inner = (
                            r"(?:\b(?:image|photo|photograph|picture|shot|render|illustration)\b)"
                            r"\s*(?:[:\-–]\s*|(?:is|was)\s+)"
                            r"(?![^\n\.;]{0,120}\b(?:portrait|woman|man|girl|boy|person|people|subject)\b)"
                            r"[^\n\.;]{1,200}[\n\.;]?"
                        )
                        s = re.sub(r'(^|[\.\?!]\s)'+image_inner, r'\1', s, flags=re.S|re.I)  # remove inline image descriptions
                if remove_subject_aggressive:
                    try:
                        pronoun_copula = re.compile(r'(?i)(^|[\.\?!]\s+)(?:The\s+)?\b(?:she|he|they|her|him|them|his|our|my)\b\s+(?:is|are|was|were|seems|appear(?:s)?|looks?)\s+', flags=re.S)
                        def _strip_pronoun_copula(m):
                            return m.group(1) or ''
                        s = pronoun_copula.sub(_strip_pronoun_copula, s)  # strip pronoun + copula
                    except Exception:
                        pass

                    pronoun_sentence_anchor = r'(^|[\.\?!]\s+)(?:The\s+)?(?:she|he|they|her|his|them|him)\b[^\n\.;]{0,200}[\n\.;]?'
                    s = re.sub(pronoun_sentence_anchor, _preserve_lead, s, flags=re.I|re.S)  # remove pronoun sentences
                    possessive_phrases = r"\b(?:her|his|their|my|our)\s+(?:face|eyes|hands|hair|skin|expression|eyebrows|mouth|nose|chin|cheeks|lips|teeth)\b[\w\s,\-]{0,80}"
                    s = re.sub(possessive_phrases, '', s, flags=re.I)  # remove possessive phrases
                    pronoun_sentence_any = r'(?<!\w)(?:she|he|they|her|him|them|his)\b[^\n\.;]{0,200}[\n\.;]?'
                    s = re.sub(pronoun_sentence_any, '', s, flags=re.I|re.S)  # remove pronoun fragments
                
                # ============================================================
                # SHOT STYLE REMOVAL
                # ============================================================
                if remove_shot_style:
                    # Handle standalone "from a X camera angle," at start of text (left over from remove_image)
                    s = re.sub(r'(?i)^[\s]*from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*,?\s*', '', s)
                    
                    # Prose patterns - "shoot from a X angle about" or "shoot from the X about"
                    s = re.sub(r'\bshoot\s+from\s+(?:a\s+)?(?:the\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front|top[- ]?down)\s*(?:angle|camera\s+angle|perspective)?\s*(?:about\s+)?', 'shoot about ', s, flags=re.IGNORECASE)
                    # Handle "captured from a X angle" - keep trailing punctuation
                    s = re.sub(r'\bcaptured\s+from\s+(?:a\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front)\s*(?:angle|camera\s+angle)?\s*([.,])', r'\1', s, flags=re.IGNORECASE)
                    s = re.sub(r'\bcaptured\s+from\s+(?:a\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front)\s*(?:angle|camera\s+angle)?', '', s, flags=re.IGNORECASE)
                    s = re.sub(r'\bshot\s+from\s+(?:a\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front)\s*(?:view)?\b\.?', 'shot', s, flags=re.IGNORECASE)
                    
                    # "from a X camera angle" standalone (after period or comma)
                    s = re.sub(r'\.\s*from\s+(?:a\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front|full[- ]?body)\s*(?:camera\s+)?(?:angle)?\b', '.', s, flags=re.IGNORECASE)
                    s = re.sub(r',\s*from\s+(?:a\s+)?(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front|full[- ]?body)\s*(?:camera\s+)?(?:angle)?\b', ',', s, flags=re.IGNORECASE)
                    
                    # Prose standalone - handle "about a portrait of" first (after shoot patterns)
                    # "shoot about a portrait of a" -> "shoot about a"
                    s = re.sub(r'about\s+(?:a\s+)?(?:black\s+and\s+white\s+)?portrait\s+of\s+a\s+', 'about a ', s, flags=re.IGNORECASE)
                    s = re.sub(r'about\s+(?:a\s+)?(?:black\s+and\s+white\s+)?portrait\s+of\b', 'about', s, flags=re.IGNORECASE)
                    
                    # Shot type + "of" patterns - remove shot descriptor, keep subject
                    # "A close-up of a person" -> "a person"
                    # "a close-up of a person" -> "a person" 
                    # "an extreme close-up of" -> ""
                    shot_of_patterns = [
                        r'close[- ]?up',
                        r'extreme\s+close[- ]?up',
                        r'medium\s+(?:close[- ]?up|shot)',
                        r'wide[- ]?(?:angle\s+)?shot',
                        r'full[- ]?body(?:\s+shot)?',
                        r'half[- ]?body(?:\s+shot)?',
                        r'upper[- ]?body(?:\s+shot)?',
                        r'cowboy\s+shot',
                        r'portrait(?:\s+shot)?',
                        r'headshot',
                        r'bust\s+shot',
                        r'waist[- ]?up(?:\s+shot)?',
                        r'knee[- ]?up(?:\s+shot)?',
                        r'low[- ]?angle(?:\s+shot)?',
                        r'high[- ]?angle(?:\s+shot)?',
                        r'bird\'?s?[- ]?eye(?:\s+view)?',
                        r'worm\'?s?[- ]?eye(?:\s+view)?',
                        r'dutch[- ]?angle',
                        r'over[- ]?the[- ]?shoulder(?:\s+shot)?',
                    ]
                    for shot_pat in shot_of_patterns:
                        # At start: "A/An close-up of" -> "" (removes article too since subject has its own)
                        s = re.sub(rf'^(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', '', s, flags=re.IGNORECASE)
                        # After period: ". A close-up of" -> ". "
                        s = re.sub(rf'(\.\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                        # After comma: ", a close-up of" -> ", "
                        s = re.sub(rf'(,\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                    
                    # "A close-up shot of" and "A portrait of" handling
                    # If remove_image is also enabled, just remove entirely (avoid redundant "A picture of")
                    # If remove_image is NOT enabled, use replacement to preserve sentence structure
                    if remove_image:
                        s = re.sub(r'^(?:a|an)\s+close[- ]?up\s+shot\s+of\s+', '', s, flags=re.IGNORECASE)
                        s = re.sub(r'(\.\s+)(?:a|an)\s+close[- ]?up\s+shot\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                        s = re.sub(r'^(?:a|an)\s+(?:black\s+and\s+white\s+)?portrait\s+of\s+', '', s, flags=re.IGNORECASE)
                        s = re.sub(r'(\.\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?portrait\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                    else:
                        s = re.sub(r'\bA\s+close[- ]?up\s+shot\s+of\b', 'A shot of', s, flags=re.IGNORECASE)
                        s = re.sub(r'^A\s+(?:black\s+and\s+white\s+)?portrait\s+of\b', 'A picture of', s, flags=re.IGNORECASE)
                        s = re.sub(r'\.\s+A\s+(?:black\s+and\s+white\s+)?portrait\s+of\b', '. A picture of', s, flags=re.IGNORECASE)
                    
                    # "back to the camera" phrase in prose
                    s = re.sub(r',?\s*(?:her|his|their)\s+back\s+to\s+(?:the\s+)?camera,?\s*', ', ', s, flags=re.IGNORECASE)
                    
                    # Inline shot style sentences - "The image/photo is taken from a low angle"
                    # These describe camera position/framing, not content
                    # Pattern: "The [image type] is [taken/shot/captured] from a [angle] [, looking ...]"
                    s = re.sub(
                        r'(?:The\s+)?(?:image|photo|photograph|picture|shot)\s+is\s+(?:taken|shot|captured|framed)\s+from\s+(?:a\s+)?'
                        r'(?:low|high|side|front|behind|top|bottom|bird\'?s?[- ]?eye|worm\'?s?[- ]?eye|dutch|canted|tilted|overhead|ground[- ]?level)\s*'
                        r'(?:angle|perspective|view|position)?\s*'
                        r'(?:,\s*looking\s+(?:up|down|straight|directly)\s+at\s+(?:the\s+)?(?:subject|person|viewer|camera))?\s*[.,]?\s*',
                        '', s, flags=re.IGNORECASE)
                    
                    # "The focus of the image is on" -> just remove the framing phrase
                    s = re.sub(r'(?:The\s+)?focus\s+of\s+(?:the\s+)?(?:image|photo|shot)\s+is\s+on\s+', '', s, flags=re.IGNORECASE)
                    
                    # "looking up at the person with a serious expression" - remove "looking up at the person"
                    s = re.sub(r',?\s*looking\s+(?:up|down|directly|straight)\s+at\s+(?:the\s+)?(?:person|subject|viewer|camera)\s*(?:with\s+)?', ', ', s, flags=re.IGNORECASE)
                    
                    # Tag patterns - comma separated shot types
                    tag_shots = [
                        r'close[- ]?up',
                        r'portrait',
                        r'upper\s+body',
                        r'lower\s+body', 
                        r'full\s+body',
                        r'cowboy\s+shot',
                        r'medium\s+shot',
                        r'wide\s+shot',
                        r'extreme\s+close[- ]?up',
                        r'from\s+(?:above|below|behind|side|front)',
                        r'looking\s+at\s+viewer',
                        r'looking\s+back',
                        r'pov',
                        r'foreshortening',
                        r'top[- ]?down(?:[- ]?bottom[- ]?up)?',
                    ]
                    
                    for pattern in tag_shots:
                        # Match pattern surrounded by commas or at start/end
                        s = re.sub(r',\s*' + pattern + r'\s*(?=,|$)', '', s, flags=re.IGNORECASE)
                        s = re.sub(r'^' + pattern + r'\s*,\s*', '', s, flags=re.IGNORECASE)
                        # Match pattern at end of string after comma
                        s = re.sub(r',\s*' + pattern + r'\s*$', '', s, flags=re.IGNORECASE)
                    
                    # Clean up artifacts
                    s = re.sub(r'shoot\s+about\s+about', 'shoot about', s)
                    s = re.sub(r',\s*,', ',', s)
                    s = re.sub(r',\s*\.', '.', s)  # Fix ",. " -> ". "
                    s = re.sub(r'\.\s*,', '.', s)  # Fix ". ," -> "."
                    s = re.sub(r'\s+', ' ', s)
                    s = re.sub(r',\s*$', '', s)
                    s = re.sub(r'^\s*,\s*', '', s)
                    s = re.sub(r'\s+([.,])', r'\1', s)  # Remove space before punctuation
                    # Remove orphaned ", with" at end of sentences
                    s = re.sub(r',\s*with\s*[.,]', '.', s, flags=re.IGNORECASE)
                    s = re.sub(r',\s*with\s*$', '', s, flags=re.IGNORECASE)
                    # Capitalize first letter after cleanup
                    s = s.strip()
                    if s and s[0].islower():
                        s = s[0].upper() + s[1:]
                
                # ============================================================
                # AGE ADJUSTMENT
                # ============================================================
                # Skip if remove_subject is active (no subject to adjust age for)
                if adjust_age and not remove_subject:
                    target_age = age
                    
                    # ===== COMMA-ENCLOSED PATTERNS FIRST (preserve sentence structure) =====
                    # "the woman, who appears to be in her late teens or early twenties, is"
                    s = re.sub(
                        r',\s*who\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\s*,',
                        f', who is {target_age}-year-old,',
                        s, flags=re.IGNORECASE
                    )
                    # "the woman, who appears to be in her mid-twenties, is"
                    s = re.sub(
                        r',\s*who\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\s*,',
                        f', who is {target_age}-year-old,',
                        s, flags=re.IGNORECASE
                    )
                    
                    # ===== NON-COMMA PATTERNS =====
                    # "who appears to be in her late teens or early twenties" (not in commas)
                    s = re.sub(
                        r'\bwho\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b',
                        f'{target_age}-year-old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # Pronoun-starting patterns (she/he/they appears) - need "is" after pronoun
                    # "she appears to be in her late teens or early twenties" -> "she is 30-year-old"
                    s = re.sub(
                        r'\b(she|he|they)\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b',
                        rf'\1 is {target_age}-year-old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "appears to be in her late teens or early twenties" (without who/pronoun)
                    s = re.sub(
                        r'\bappears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b',
                        f'is {target_age}-year-old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # ===== REDUNDANT AGE CLEANUP =====
                    # When we already have "X-year-old [subject]" followed by ", appears/is X years old" - remove redundant part
                    # e.g. "a 18-year-old woman, is 18 years old" -> "a 18-year-old woman"
                    s = re.sub(
                        rf',\s*is\s+{target_age}\s+years?\s+old\b',
                        '',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "who appears to be in her mid-twenties" (not in commas)
                    s = re.sub(
                        r'\bwho\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b',
                        f'is {target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # Pronoun-starting patterns for mid-X
                    # "she appears to be in her mid-twenties" -> "she is 30 years old"
                    s = re.sub(
                        r'\b(she|he|they)\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b',
                        rf'\1 is {target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "appearing to be in her mid-twenties" 
                    s = re.sub(
                        r'\bappearing\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b',
                        f'{target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "[subject] appears to be in her late twenties" - keep subject, replace age phrase with "is X years old"
                    s = re.sub(
                        r'\bappears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b',
                        f'is {target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "who appears to be around 25" - remove "who"
                    s = re.sub(
                        r'\bwho\s+appears?\s+to\s+be\s+(?:around\s+)?\d{1,2}(?:\s+years?\s+old)?\b',
                        f'{target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "appears to be around 25" - replace with "is X years old"
                    s = re.sub(
                        r'\bappears?\s+to\s+be\s+(?:around\s+)?\d{1,2}(?:\s+years?\s+old)?\b',
                        f'is {target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # "in her early twenties" (standalone)
                    s = re.sub(
                        r'\bin\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b',
                        f'{target_age} years old',
                        s, flags=re.IGNORECASE
                    )
                    
                    # Explicit ages: "10 years old", "17 years old"
                    s = re.sub(r'\b\d{1,2}\s+years?\s+old\b', f'{target_age}-year-old', s, flags=re.IGNORECASE)
                    
                    # Already hyphenated: "20-year-old"
                    s = re.sub(r'\b\d{1,2}-year-old\b', f'{target_age}-year-old', s, flags=re.IGNORECASE)
                    
                    # Short forms: "10yr", "17yo"
                    s = re.sub(r'\b\d{1,2}yr\b', f'{target_age}yr', s, flags=re.IGNORECASE)
                    s = re.sub(r'\b\d{1,2}yo\b', f'{target_age}yo', s, flags=re.IGNORECASE)
                    
                    # Standalone number in tags that's likely an age (comma-separated, before hair color)
                    s = re.sub(r',\s*(\d{1,2})\s*,(?=\s*(?:long|short|blonde|brown|black|red|white|pink)\s+hair)', f', {target_age},', s)
                    
                    # Age-appropriate term mapping based on target age
                    # Since min age is 18 (legal adult):
                    # Female: woman (18-29), mature woman (30-59), elderly woman (60+)
                    # Male: man (18-29), mature man (30-59), elderly man (60+)
                    def get_age_appropriate_term(match, target_age):
                        original_term = match.group(1).lower()
                        
                        # Determine gender from original term
                        female_terms = {'woman', 'girl', 'lady'}
                        male_terms = {'man', 'boy'}
                        
                        if original_term in female_terms:
                            if target_age <= 29:
                                term = 'woman'
                            elif target_age <= 59:
                                term = 'mature woman'
                            else:
                                term = 'elderly woman'
                        elif original_term in male_terms:
                            if target_age <= 29:
                                term = 'man'
                            elif target_age <= 59:
                                term = 'mature man'
                            else:
                                term = 'elderly man'
                        else:
                            # Keep neutral terms as-is
                            term = original_term
                        
                        return f'{target_age}-year-old {term}'
                    
                    # "young woman/man/person" -> age-appropriate term
                    s = re.sub(
                        r'\byoung\s+(woman|man|person|girl|boy|lady|adult|individual|figure)\b',
                        lambda m: get_age_appropriate_term(m, target_age),
                        s, flags=re.IGNORECASE
                    )
                    
                    # Teenage variants
                    s = re.sub(
                        r'\b(?:teenage|teenaged|teen)\s+(girl|boy|woman|man)\b',
                        lambda m: get_age_appropriate_term(m, target_age),
                        s, flags=re.IGNORECASE
                    )
                    
                    # ===== FINAL AGE CLEANUP =====
                    # Remove redundant ", is X-year-old" when we already have "X-year-old [subject]" before it
                    s = re.sub(rf',\s*is\s+{target_age}-year-old\b', '', s, flags=re.IGNORECASE)
                    # Remove redundant ", is X years old" 
                    s = re.sub(rf',\s*is\s+{target_age}\s+years?\s+old\b', '', s, flags=re.IGNORECASE)
                    # Remove redundant ", X years old" (without "is")
                    s = re.sub(rf',\s+{target_age}\s+years?\s+old\b', '', s, flags=re.IGNORECASE)
                    
            except Exception:
                pass
        
        # ============================================================
        # NSFW CONTENT REMOVAL
        # ============================================================
        # Skip if remove_subject is active (subject content already removed)
        if remove_nsfw and not remove_subject:
            try:
                # NSFW tag patterns (comma-separated tags format)
                nsfw_tag_patterns = [
                    # Nudity
                    r'\bnude\b', r'\bnaked\b', r'\bnudity\b',
                    r'\btopless\b', r'\bbottomless\b',
                    r'\bbare[- ]?breasted\b', r'\bbare[- ]?chested\b',
                    r'\bcompletely[- ]?nude\b', r'\bfully[- ]?nude\b',
                    r'\bshirtless\b',
                    # Explicit body parts
                    r'\bnipples?\b', r'\bareola[es]?\b', r'\btits\b',
                    r'\bpussy\b', r'\bvagina\b', r'\bvulva\b', r'\blabia\b', r'\bclit\b',
                    r'\bpenis\b', r'\bcock\b', r'\bdick\b', r'\bphallus\b',
                    r'\bballs\b', r'\btesticles?\b', r'\bscrotum\b',
                    r'\bgenitals?\b', r'\bgenital[- ]?area\b',
                    r'\banus\b', r'\banal\b',
                    r'\bpubic[- ]?hair\b', r'\bfemale[- ]?pubic\b', r'\bmale[- ]?pubic\b',
                    r'\bpubic[- ]?area\b', r'\bpubic[- ]?region\b',
                    # Sexual acts
                    r'\bsex\b', r'\bsexual\b', r'\bintercourse\b',
                    r'\bpenetration\b', r'\bpenetrating\b',
                    r'\bmasturbat(?:ion|ing|e)\b', r'\bfingering\b',
                    r'\boral[- ]?sex\b', r'\bblowjob\b', r'\bfellatio\b', r'\bcunnilingus\b',
                    r'\bdeepthroat\b', r'\bfacefuck\b',
                    r'\bhandjob\b', r'\bfootjob\b', r'\btitjob\b', r'\btitfuck\b', r'\btitty[- ]?fuck\b',
                    r'\bpaizuri\b', r'\bboobjob\b',
                    r'\borgasm\b', r'\bcum(?:ming|shot)?\b', r'\bejaculat(?:ion|ing|e)\b',
                    r'\bsemen\b', r'\bgrool\b', r'\bpussy[- ]?juice\b',
                    r'\berect(?:ion|ed)?\b', r'\baroused\b', r'\barousal\b',
                    r'\bcreampie\b', r'\bgangbang\b', r'\bthreesome\b',
                    r'\bdoggystyle\b', r'\bcowgirl\b', r'\bmissionary\b',
                    r'\bmating[- ]?press\b', r'\bprone[- ]?bone\b',
                    # Explicit poses/states
                    r'\bspread[- ]?(?:legs|pussy|vagina|ass)\b',
                    r'\buncensored\b', r'\bexplicit\b',
                    r'\bcameltoe\b',
                    r'\bno[- ]?panties\b', r'\bno[- ]?bra\b',
                    r'\bexposed[- ]?(?:nipples?|genitals?|pussy|penis)\b',
                    # BDSM/Fetish explicit
                    r'\bbdsm\b', r'\bbondage\b',
                    r'\bfetish\b',
                    r'\bslavery\b', r'\bslave\b',
                    r'\btorture\b',
                    r'\bdildo\b', r'\bvibrator\b',
                    # Labels/tags
                    r'\bhentai\b', r'\bahegao\b',
                    r'\bfuta(?:nari)?\b',
                    r'\byaoi\b', r'\byuri\b',
                    r'\bloli\b', r'\bshota\b',
                    r'\bnsfw\b', r'\bxxx\b', r'\bporn\b', r'\brating[_-]?explicit\b',
                    r'\berotic\b',
                    # Suggestive clothing
                    r'\bsexy\b', r'\blingerie\b',
                    r'\bthong\b', r'\bpanties\b',
                    r'\bskimpy\b', r'\brevealing\b', r'\bsee[- ]?through\b', r'\bfishnet\b',
                    # Suggestive body focus
                    r'\bcleavage\b', r'\bsideboob\b', r'\bunderboob\b',
                    # Suggestive mood/pose
                    r'\bseductive\b', r'\bsensual\b', r'\bprovocative\b', r'\bsuggestive\b',
                    r'\blustful\b', r'\blust\b', r'\bslutty\b', r'\bflirty\b', r'\bnaughty\b',
                    # Suggestive labels
                    r'\becchi\b', r'\bpinup\b', r'\brisque\b',
                ]
                
                # Prose patterns for NSFW content
                nsfw_prose_patterns = [
                    # Nude descriptions
                    r'\bstripped\s+(?:bare|naked)\b',
                    r'\bbaring\s+(?:her|his|their)\s+(?:breasts?|chest|body)\b',
                    # Explicit body descriptions
                    r'\b(?:erect|hardened|stiff)\s+nipples?\b',
                    r'\b(?:exposed|visible|bare)\s+(?:nipples?|genitals?|breasts?)\b',
                    r'\b(?:her|his)\s+(?:bare|naked)\s+(?:breasts?|chest)\b',
                    r'\bnipples?\s+(?:visible|exposed|erect|hardened)\b',
                    r'\bbare[- ]?(?:breasted|chested)\b',
                    # Sexual descriptions
                    r'\bsexual(?:ly)?\s+(?:explicit|arousing|stimulating)\b',
                    r'\bintimate\s+(?:parts?|areas?|regions?)\b',
                    r'\bsensual(?:ly)?\s+(?:touching|caressing|stroking)\b',
                ]
                
                if _is_tags_format(s):
                    # Remove NSFW tags
                    tags = [t.strip() for t in s.split(',')]
                    kept_tags = []
                    for tag in tags:
                        tag_lower = tag.lower().strip()
                        is_nsfw = any(re.search(pat, tag_lower, re.I) for pat in nsfw_tag_patterns)
                        if not is_nsfw:
                            kept_tags.append(tag)
                    s = ', '.join(kept_tags) if kept_tags else s
                else:
                    # Prose format - handle special cases first, then remove remaining NSFW phrases
                    
                    # Handle full nude description clauses - remove entire clause
                    # "her body is completely nude, with no clothing or accessories on" -> remove entirely
                    s = re.sub(r'\.\s*(?:her|his|their)\s+body\s+is\s+(?:completely|fully|entirely)?\s*(?:nude|naked)[^.]*\.', '.', s, flags=re.I)
                    # Same pattern without leading period (at start or after comma)
                    s = re.sub(r',?\s*(?:her|his|their)\s+body\s+is\s+(?:completely|fully|entirely)?\s*(?:nude|naked)[^.]*(?=\.|\s*$)', '', s, flags=re.I)
                    
                    # Handle "with no clothing or accessories on" as standalone (cleanup if previous pattern didn't catch it)
                    s = re.sub(r',?\s*with\s+no\s+(?:clothing|clothes)\s+(?:or\s+accessories?\s+)?(?:on|visible)\b', '', s, flags=re.I)
                    
                    # Handle "is completely/fully/entirely nude/naked" without the full context - remove clause to period
                    s = re.sub(r'\bis\s+(?:completely|fully|entirely)\s+(?:nude|naked)\b[^.]*', '', s, flags=re.I)
                    
                    # Handle "completely/fully nude" without "is" (adjective context) - remove entire phrase
                    s = re.sub(r'\b(?:completely|fully|entirely)\s+(?:nude|naked)\b', '', s, flags=re.I)
                    
                    # Handle "a nude woman" -> "a woman" (keep article)
                    s = re.sub(r'\b(a|an)\s+(?:nude|naked)\s+(woman|man|girl|boy|person|figure|model)\b', r'\1 \2', s, flags=re.I)
                    
                    for pattern in nsfw_tag_patterns + nsfw_prose_patterns:
                        # Remove the word/phrase and clean up
                        s = re.sub(pattern, '', s, flags=re.I)
                    
                    # Clean up artifacts from removal
                    s = re.sub(r',\s*,', ',', s)
                    s = re.sub(r'\s+,', ',', s)
                    s = re.sub(r',\s*\.', '.', s)
                    s = re.sub(r'\s{2,}', ' ', s)
                
            except Exception:
                pass

        # Apply user regex
        try:
            if regex and str(regex).strip():
                replaced = re.sub(regex, replace_with, s)  # apply custom regex replacement
            else:
                replaced = s
        except Exception:
            replaced = s

        # Remove watermark phrases and related tags
        if remove_watermark:
            # Detect if text is tag format (comma-separated, no periods) vs prose
            is_tags_for_watermark = bool(re.search(r'_', replaced)) or (replaced.count(',') > 2 and not re.search(r'\.\s', replaced))
            
            if is_tags_for_watermark or '.' not in replaced:
                # Tag/clause format: remove clause between commas containing watermark
                # e.g., "quality, there is a watermark, 1girl" -> "quality, 1girl"
                replaced = re.sub(r'(?i),\s*[^,]*\bwatermark\b[^,]*(?=,|$)', '', replaced)
                replaced = re.sub(r'(?i)^[^,]*\bwatermark\b[^,]*,\s*', '', replaced)
            else:
                # Prose format: remove entire sentence containing watermark
                # e.g., "Nice quality. There is a watermark. Good colors." -> "Nice quality. Good colors."
                replaced = re.sub(r'(?i)(?:(?<=\.\s)|^)[^.]*\bwatermark\b[^.]*\.\s*', '', replaced)
                # Handle end of string without period
                replaced = re.sub(r'(?i)(?:(?<=\.\s)|^)[^.]*\bwatermark\b[^.]*$', '', replaced)
            
            # Remove remaining watermark-related tags: copyright, signature, logo, etc.
            watermark_tags_pat = r"(?i),?\s*\b(?:watermarked|copyright|copyrighted|artist[_\s]?name|signature|signed|logo|username|user[_\s]?name|web[_\s]?address|url|patreon|twitter[_\s]?(?:username|handle|name)?|instagram[_\s]?(?:username|handle|name)?|deviantart|pixiv|text|dated|sample|preview)\b,?\s*"
            replaced = re.sub(watermark_tags_pat, ', ', replaced)
            # Clean up leftover comma artifacts
            replaced = re.sub(r',\s*,', ',', replaced)
            replaced = re.sub(r'^\s*,\s*', '', replaced)
            replaced = re.sub(r',\s*$', '', replaced)

        # Optional cleanup
        if cleanup:
            replaced = re.sub(r"[\r\n]+", " ", replaced)  # normalize whitespace
            replaced = re.sub(r"[ ]{2,}", " ", replaced)  # collapse multiple spaces
            try:
                replaced = re.sub(r'\s*\.\s+(?=[a-z])', ' ', replaced)  # fix dangling periods
            except Exception:
                pass
            replaced = replaced.strip()  # remove leading/trailing whitespace
            replaced = replaced.replace('"', '')  # remove double quotes
            replaced = re.sub(r'\. ,\s*', '. ', replaced)  # fix ". ,"
            # Iteratively clean multiple consecutive punctuation marks throughout the string
            while re.search(r'[,.]\s*[,.]', replaced):
                replaced = re.sub(r'[,.]\s*[,.]', ',', replaced)  # collapse multiple punctuation to single comma
                replaced = re.sub(r',\s*,', ',', replaced)  # collapse comma-space-comma to comma
            # Clean trailing punctuation until only one dot remains
            while re.search(r'[,.]\s*$', replaced) or re.search(r'\.\s*\.', replaced):
                replaced = re.sub(r'[,.]\s*$', '', replaced).strip()  # remove trailing commas/periods
                replaced = re.sub(r'\.\s*\.', '.', replaced)  # collapse multiple periods
            # Remove all ending punctuation
            replaced = re.sub(r'[.,;:!?]+$', '', replaced).strip()
        return (replaced,)

NODE_NAME = 'Replace String v3 [Eclipse]'
NODE_DESC = 'Replace String v3'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvText_ReplaceStringV3
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}
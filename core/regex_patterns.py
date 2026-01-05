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

# Centralized pre-compiled regex patterns for common text operations.
#
# This module contains patterns that are:
# 1. Used frequently across multiple files
# 2. Called in loops or hot paths where compilation overhead matters
# 3. Generic enough to be reusable (not domain-specific)
#
# For specialized patterns (prompt processing, model-specific parsing),
# keep them local to their respective files.
#
# Usage:
#     from ..core.regex_patterns import RE_NEWLINES, RE_MULTI_SPACE
#     text = RE_NEWLINES.sub(" ", text)

import re


# ============================================================================
# Text Cleanup Patterns - Used across many files for prompt/text normalization
# ============================================================================

# Newline normalization - collapse all newline variants to single space
# Used in: RvConversion_Join, RvConversion_MergeStrings, RvConversion_WidgetToString,
#          RvText_ReplaceString, RvText_ReplaceStringV2, RvText_ReplaceStringV3
RE_NEWLINES = re.compile(r'[\r\n]+')

# Whitespace collapse - collapse multiple spaces to single space
# Used in: RvText_ReplaceStringV2, RvText_ReplaceStringV3, common text cleanup
RE_MULTI_SPACE = re.compile(r'[ ]{2,}')

# All whitespace collapse (spaces, tabs, newlines)
RE_ALL_WHITESPACE = re.compile(r'\s+')

# Newlines and tabs to space
RE_NEWLINES_TABS = re.compile(r'[\r\n\t]+')


# ============================================================================
# Punctuation Cleanup Patterns - Common prompt cleanup
# ============================================================================

# Double punctuation: ",." or ".," or ",," etc.
RE_DOUBLE_PUNCT = re.compile(r'[,.]\s*[,.]')

# Trailing punctuation
RE_TRAILING_PUNCT = re.compile(r'[,.;:!?]+$')

# Leading comma with optional space
RE_LEADING_COMMA = re.compile(r'^,\s*')

# Comma before period: ", ." -> "."
RE_COMMA_PERIOD = re.compile(r',\s*\.')

# Period before comma: ". ," -> "."
RE_PERIOD_COMMA = re.compile(r'\.\s*,')

# Multiple periods: ".." or ". ." -> "."
RE_MULTI_PERIOD = re.compile(r'\.\s*\.')

# Space before punctuation
RE_SPACE_BEFORE_PUNCT = re.compile(r'\s+([.,])')


# ============================================================================
# Markdown/Markup Cleanup Patterns
# ============================================================================

# Bold markdown: **text** -> text
RE_BOLD_MARKDOWN = re.compile(r'\*\*(.*?)\*\*')

# Code fence opening: ```python, ```json, etc.
RE_CODE_FENCE_OPEN = re.compile(r'^```[a-zA-Z]*\n?')

# Code fence closing
RE_CODE_FENCE_CLOSE = re.compile(r'\n?```\s*$')


# ============================================================================
# JSON Extraction Patterns
# ============================================================================

# Extract JSON object from text
RE_JSON_OBJECT = re.compile(r'\{[\s\S]*\}')

# Extract JSON array from text
RE_JSON_ARRAY = re.compile(r'\[[\s\S]*\]')


# ============================================================================
# Numbered List Patterns
# ============================================================================

# Numbered list item: "1. ", "2. ", etc.
RE_NUMBERED_ITEM = re.compile(r'(?m)^\s*\d+\.\s*')

# Find header before first numbered item
RE_HEADER_BEFORE_LIST = re.compile(r'(?s)^.*?(?=\d+\.)')


# ============================================================================
# Bracket/Quote Patterns
# ============================================================================

# Square brackets: [text]
RE_SQUARE_BRACKETS = re.compile(r'^\[|\]$')

# Single quotes
RE_SINGLE_QUOTES = re.compile(r"'")

# Quoted string at start: "text" or 'text'
RE_QUOTED_START = re.compile(r'^\s*["\']([^"\']*)["\']')

# First numbered item with quotes: 1. "text"
RE_FIRST_NUMBERED_QUOTED = re.compile(r'(?s)^\s*1\.\s*(?:["\'])(.*?)(?:["\'])', re.M)


# ============================================================================
# Leading Number Patterns (used in file/folder name processing)
# ============================================================================

# Leading numbers and underscores: "001_filename" -> "filename"
RE_LEADING_NUMBERS = re.compile(r'^[0-9_]+')


# ============================================================================
# Quality/URL Parameter Patterns
# ============================================================================

# Quality parameter in URLs: quality=80 -> quality=100
RE_QUALITY_PARAM = re.compile(r'quality=\d+')


# ============================================================================
# LoRA Extraction Patterns (used in SaveImages and related)
# ============================================================================

# Extract LoRA name from <lora:name:weight> syntax
RE_LORA_TAG = re.compile(r'<lora:([^>:]+)')

# Extract all LoRA tags with optional weight
RE_LORA_ALL = re.compile(r'<lora:([^>:]+):?([0-9\.]+)?[^>]*>')

# Split by common separators (comma, semicolon, whitespace)
RE_SPLIT_SEPARATORS = re.compile(r'[,;\s]+')


# ============================================================================
# Florence/Location Token Patterns
# ============================================================================

# Florence location tokens: <loc_123>
RE_LOC_TOKEN = re.compile(r'<loc_(\d+)>')


# ============================================================================
# Age Patterns (used in prompt processing)
# ============================================================================

# Age in words: "25 years old"
RE_AGE_WORDS = re.compile(r'\b\d{1,2}\s+years?\s+old\b', re.IGNORECASE)

# Age hyphenated: "25-year-old"
RE_AGE_HYPHEN = re.compile(r'\b\d{1,2}-year-old\b', re.IGNORECASE)

# Age abbreviations: "25yr", "25yo"
RE_AGE_YR = re.compile(r'\b\d{1,2}yr\b', re.IGNORECASE)
RE_AGE_YO = re.compile(r'\b\d{1,2}yo\b', re.IGNORECASE)

# Age format: "aged 28", "age 30"
RE_AGE_SIMPLE_FORMAT = re.compile(r'\b(?:aged?|age)\s+\d+\b', re.IGNORECASE)


# ============================================================================
# Prompt Processing Patterns - Shared by ReplaceStringV2/V3
# (V3 is source of truth - patterns extracted from V3)
# ============================================================================

# Background removal pattern - removes background/environment descriptions
# Stops before ", the" or ". the" to preserve "the overall" phrases
RE_BACKGROUND = re.compile(
    r"(?:(?:(?:the\s+)?backgrounds?|environment|setting|scene|surroundings|"
    r"in the backgrounds?|in the environment|in the setting|in the scene|in the surroundings)"
    r"\s*[:\-–]?\s*.*?(?=,\s+the|\.\s+the)|"
    r"(?:[\.\?!,]\s*(?:The\s+)?(?:backgrounds?|environment|setting|scene|surroundings|in the background)"
    r"\s+.*?(?=,\s+the|\.\s+the)))",
    re.IGNORECASE | re.DOTALL
)

# Mood removal pattern - removes mood/atmosphere/vibe descriptions
# More conservative approach to avoid removing descriptive content
RE_MOOD = re.compile(
    r"(?:\b(?:mood|moods|feeling|feelings|atmosphere|vibe|vibes|overall)\b"
    r"\s*[:\-–]?\s*(?:[^,\.]{1,30})(?=,\s+the|\.\s+the|[\n\.;]*$)|"
    r"(?:^|[\.\?!,]\s*)(?:The\s+)?overall\s+(?:[^,\.]{1,30})(?=,\s+the|\.\s+the|[\n\.;]*$)|"
    r"(?:^|[\.\?!,]\s*)(?:The\s+)?(?:mood|moods|feeling|feelings|atmosphere|vibe|vibes)"
    r"(?:\s+of(?:\s+the)?\s+(?:scene|setting|environment))?"
    r"(?:\s+is|\s+are)?\s+(?:[^,\.]{1,20})(?=,\s|\.\s|$))",
    re.IGNORECASE | re.DOTALL
)

# Image description removal pattern - removes image/photo labels
# Only protects mood/atmosphere terms and very specific portrait contexts
RE_IMAGE_DESCRIPTION = re.compile(
    r"(?:(?:\b(?:image|photo|photograph|picture|shot|render|illustration)\b)"
    r"\s*(?:[:\-–]\s*|(?:is|was)\s+(?:a|an)\s+)"
    r"(?![^\n\.;]{0,120}\b(?:portrait|mood|atmosphere|feeling|one\s+of)\b)"
    r"[^\n\.;]{1,200}[\n\.;]?)",
    re.IGNORECASE
)

# Subject label pattern - "Subject: ..." sections
RE_SUBJECT_LABEL = re.compile(
    r"(?:^|[\s,]+)subject\s*:\s*[^.!?\n]+[.!?\n]?",
    re.IGNORECASE
)

# Subject words - common subject references (with word boundary)
# Updated to include formal, casual, royal, and fantasy terms
SUBJECT_WORDS = (
    r"\b(?:woman|man|girl|boy|person|people|figure|individual|character|"
    r"lady|gentleman|child|baby|teenager|adult|hero|heroine|protagonist|"
    r"lord|duke|baron|earl|count|sir|mister|mr\.|nobleman|aristocrat|patriarch|"
    r"duchess|countess|baroness|madam|madame|dame|mistress|matriarch|"
    r"fellow|guy|dude|lad|chap|gent|bloke|mate|"
    r"gal|lass|chick|miss|ms\.|mrs\.|belle|maiden|"
    r"queen|king|prince|princess|emperor|empress|"
    r"knight|wizard|mage|warrior|champion|defender|adventurer|paladin|bard|ranger|"
    r"goddess|sorceress|enchantress|deity|being|entity|subject|model|performer)\b"
)
RE_SUBJECT_WORDS = re.compile(SUBJECT_WORDS, re.IGNORECASE)

# Pronoun + copula pattern for aggressive subject removal
RE_PRONOUN_COPULA = re.compile(
    r"(^|[\.\?!]\s+)(?:The\s+)?\b(?:she|he|they|her|him|them|his|our|my)\b"
    r"\s+(?:is|are|was|were|seems|appear(?:s)?|looks?)\s+",
    re.IGNORECASE | re.DOTALL
)

# Pronoun sentence anchor pattern
RE_PRONOUN_SENTENCE = re.compile(
    r"(^|[\.\?!]\s+)(?:The\s+)?(?:she|he|they|her|his|them|him)\b[^\n\.;]{0,200}[\n\.;]?",
    re.IGNORECASE | re.DOTALL
)

# Possessive phrases pattern
RE_POSSESSIVE_PHRASES = re.compile(
    r"\b(?:her|his|their|my|our)\s+"
    r"(?:face|eyes|hands|hair|skin|expression|eyebrows|mouth|nose|chin|cheeks|lips|teeth)\b"
    r"[\w\s,\-]{0,80}",
    re.IGNORECASE
)

# Pronoun fragment pattern
RE_PRONOUN_FRAGMENT = re.compile(
    r"(?<!\w)(?:she|he|they|her|him|them|his)\b[^\n\.;]{0,200}[\n\.;]?",
    re.IGNORECASE | re.DOTALL
)

# Tag format detection patterns
RE_TAG_UNDERSCORE = re.compile(r'\b\w+_\w+')
RE_TAG_WEIGHT = re.compile(r'\([^)]+:\d+\.?\d*\)')
RE_TAG_DOUBLE_PARENS = re.compile(r'\(\([^)]+\)\)')
RE_TAG_QUALITY = re.compile(r'\b(?:masterpiece|best[_\s]?quality|highres|absurdres|4k|8k)\b', re.IGNORECASE)
RE_TAG_COUNT = re.compile(r'\b\d+(?:girl|boy|other)s?\b', re.IGNORECASE)

# "The image is" prefix pattern
RE_IMAGE_IS_PREFIX = re.compile(r'^[\s]*the\s+image\s+is\s+', re.IGNORECASE)

# Portrait/headshot prefix patterns
RE_PORTRAIT_PREFIX = re.compile(
    r'^(?:.*?\b)?(?:close[- ]?up\s+portrait\s+of\s+|portrait\s+of\s+|headshot\s+of\s+)',
    re.IGNORECASE
)

# Instruction prefix pattern for remove_instructions
# Matches flexible multi-word titles ending with known instruction words
RE_INSTRUCTION_PREFIX = re.compile(
    r'^(?:here\s+is\s+(?:your\s+|the\s+)?(?:expanded\s+)?)?'
    r'(?:expanded\s+)?'
    r'(?:(?:\w+\s+)*(?:analysis|report|summary|description|overview|details?|brief|breakdown|concept|vision|expansion|design|version)|'  # Multi-word titles
    r'(?:(?:expanded|detailed?|enhanced|creative|character|scene|art|visual|artistic)\s+)?(?:prompt|description|caption|direction|brief)|'
    r'image\s+description|output|result|response|answer|text|example'
    r')\s*:\s*',
    re.IGNORECASE
)

# More flexible colon header pattern
RE_INSTRUCTION_COLON_HEADER = re.compile(
    r'^[^\n:]{1,80}(?:prompt|description|caption|direction|brief|analysis|breakdown|concept|vision|expansion|design|version|output|result)\s*:\s*',
    re.IGNORECASE
)

# Additional instruction header patterns for specific missed cases
RE_INSTRUCTION_EXPANSION = re.compile(
    r'(?i)^(?:prompt\s+)?expansion\s*:\s*',
)

RE_INSTRUCTION_DESIGN = re.compile(
    r'(?i)^(?:character\s+)?design\s*:\s*',
)

RE_INSTRUCTION_VERSION = re.compile(
    r'(?i)^(?:enhanced\s+)?version\s*:\s*',
)

# Quote extraction pattern
RE_QUOTED_CONTENT = re.compile(r'^\s*["\']([^"\']*)["\']')

# List processing patterns
RE_LIST_FIRST_QUOTED = re.compile(r'(?s)^\s*1\.\s*(?:["\'])(.*?)(?:["\'])', re.MULTILINE)
RE_LIST_HEADER = re.compile(r'(?s)^.*?(?=\d+\.)')
RE_LIST_NUMBERED = re.compile(r'(?m)^\s*\d+\.\s*')
RE_LIST_LABELS = re.compile(
    r'\b(?:lighting|composition|details|background|pose|makeup|props|editing|focus|storytelling)\s*:\s*',
    re.IGNORECASE
)

# ============================================================================
# Pattern Lists for Tag/Prose Processing
# (Centralized from ReplaceStringV3 - both V2 and V3 can use these)
# ============================================================================

# Subject-related tag patterns (for removal in tag format)
# These identify tags describing people/characters that should be removed
SUBJECT_TAG_PATTERNS = [
    r'^\d*(?:girl|boy|woman|man|person|people)s?$',  # 1girl, 2boys, woman, etc.
    r'^(?:lady|gentleman|lord|duke|baron|duchess|countess|sir|madam|fellow|guy|gal|lass)$',  # formal/casual terms
    r'^(?:hero|heroine|protagonist|knight|wizard|mage|warrior|queen|king|prince|princess)$',  # fantasy/royal terms
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

# Background/setting tag patterns (to KEEP when removing subjects)
# These identify tags describing environment/setting that should be preserved
BACKGROUND_TAG_PATTERNS = [
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

# Image/quality tag patterns (for removal - describes image type, not content)
IMAGE_TAG_PATTERNS = [
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

# Setting/location words for prose format subject removal
# Used to detect and extract setting descriptions when removing subject
SETTING_WORDS = (
    r'(?:setting|room|space|studio|environment|background|scene|area|place|location|'
    r'forest|garden|field|beach|city|town|street|building|house|office|bedroom|bathroom|'
    r'kitchen|living|patio|balcony|terrace|yard|park|plaza|square|alley|hallway|corridor|'
    r'warehouse|factory|gym|pool|arena|stadium|theater|church|temple|castle|palace|dungeon|'
    r'cave|mountain|valley|river|lake|ocean|sea|shore|cliff|desert|jungle|swamp|meadow|'
    r'prairie|tundra|island|village|farm|barn|stable|garage|basement|attic|rooftop|deck|'
    r'dock|pier|bridge|tunnel|subway|station|airport|hospital|school|library|museum|gallery|'
    r'restaurant|cafe|bar|club|hotel|motel|cabin|cottage|mansion|apartment|condo|loft|penthouse)'
)

# Shot type patterns for "X of" removal (e.g., "a close-up of" -> "")
SHOT_OF_PATTERNS = [
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

# Tag-format shot patterns (comma-separated)
TAG_SHOT_PATTERNS = [
    r'close[- ]?up',
    r'portrait',
    r'upper\s+body',
    r'lower\s+body',
    r'full\s+body',
    r'full[- ]?body[- ]?shot',
    r'cowboy\s+shot',
    r'medium\s+shot',
    r'wide\s+shot',
    r'wide[- ]?angle',
    r'extreme\s+close[- ]?up',
    r'from\s+(?:above|below|behind|side|front)',
    r'looking\s+at\s+viewer',
    r'looking\s+back',
    r'pov',
    r'foreshortening',
    r'top[- ]?down(?:[- ]?bottom[- ]?up)?',
    # Camera techniques
    r'bird[\'s]?[- ]?eye[- ]?view',
    r'worm[\'s]?[- ]?eye[- ]?view',
    r'dolly[- ]?shot',
    r'crane[- ]?shot',
    r'tracking[- ]?shot',
    r'handheld[- ]?shot',
    r'panning[- ]?shot',
    r'aerial[- ]?shot',
    r'macro[- ]?shot',
    r'establishing[- ]?shot',
    r'time[- ]?lapse[- ]?shot',
    r'long[- ]?exposure[- ]?shot',
    # Shot styles and contexts
    r'headshot',
    r'portrait[- ]?shot',
    r'candid[- ]?shot',
    r'group[- ]?shot',
    r'environmental[- ]?portrait',
    r'action[- ]?shot',
    r'motion[- ]?blur[- ]?shot',
    r'freeze[- ]?frame[- ]?shot',
    r'sports[- ]?shot',
    r'golden[- ]?hour[- ]?shot',
    r'documentary[- ]?style[- ]?shot',
    r'artistic[- ]?portrait[- ]?shot',
    # Location and lighting
    r'shot\s+on\s+location',
    r'natural\s+lighting\s+shot',
    r'studio\s+shot',
]

# Style descriptors that appear before subject words
# Pattern matches: "anime-style girl" -> "girl"
STYLE_BEFORE_SUBJECT = (
    r'\b(?:anime|cartoon|manga|comic|realistic|photorealistic|semi[- ]?realistic|'
    r'hyper[- ]?realistic|stylized|cel[- ]?shaded|3d|2d|cgi|digital|painted|'
    r'illustrated|artistic|fantasy|sci[- ]?fi|cyberpunk|steampunk|gothic|'
    r'vintage|retro|modern|classic|traditional|western|eastern|japanese|'
    r'korean|chinese|american)[- ]?(?:style|styled)?\s+'
    r'(?=(?:girl|boy|woman|man|person|figure|character|lady|gentleman|'
    r'child|teen|teenager|adult|individual|model|subject)\b)'
)
RE_STYLE_BEFORE_SUBJECT = re.compile(STYLE_BEFORE_SUBJECT, re.IGNORECASE)

# NSFW tag patterns (for removal)
NSFW_TAG_PATTERNS = [
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
    r'\bsex\b', r'\bsexual\b', r'\bintercourse\b', r'\bintimate[_\s]acts?\b',
    r'\bsexual[_\s]intercourse\b', r'\bgraphic[_\s]sexual[_\s]detail\b',
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
    r'\bimplied[_\s]nudity\b', r'\bsuggestive[_\s]pose\b', r'\bsensual[_\s]atmosphere\b',
    r'\bboudoir[_\s]photography\b', r'\bintimate[_\s]portrait\b', r'\bromantic[_\s]atmosphere\b',
    r'\bfigure[_\s]drawing\b', r'\banatomy[_\s]study\b', r'\beducational[_\s]art[_\s]reference\b',
    # Swimwear and beach contexts
    r'\bswimwear[_\s]photography\b', r'\bbikini[_\s]model(?:ing|l?ing)?\b', r'\bbeach[_\s]fashion\b',
    # Medical and educational contexts (conservative patterns)
    r'\bbreast[_\s]cancer[_\s]awareness\b', r'\bmedical[_\s]examination\b', r'\bmedical[_\s]context\b',
    r'\bnursing[_\s]mother\b', r'\bmaternal[_\s]care\b', r'\bfamily[_\s]friendly[_\s]content\b',
    r'\banatomical[_\s]diagram\b', r'\bmedical[_\s]illustration\b', r'\beducational[_\s]material\b',
    r'\bclassical[_\s]art[_\s]history\b', r'\bmuseum[_\s]context\b', r'\bsculpture[_\s]appreciation\b',
    r'\bhealth[_\s]awareness[_\s]campaign\b', r'\bmedical[_\s]research[_\s]imagery\b',
    # Suggestive labels
    r'\becchi\b', r'\bpinup\b', r'\brisque\b',
]

# NSFW prose patterns (for removal in prose format)
NSFW_PROSE_PATTERNS = [
    # Nude descriptions
    r'\bstripped\s+(?:bare|naked)\b',
    r'\bbaring\s+(?:her|his|their)\s+(?:breasts?|chest|body)\b',
    r'\bposes?\s+artistically\s+without\s+clothing\b',
    r'\bartistic\s+nudity\s+serves?\s+the\s+composition\b',
    r'\bthe\s+figure\'s\s+natural\s+state\s+contributes?\b',
    r'\bwearing\s+nothing\b', r'\bbarely\s+clothed\b', r'\bwithout\s+clothing\b',
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
    # Explicitly suggestive combinations (more targeted)
    r'\b(?:naked|nude|bare)\s+(?:.*?\s+)?(?:spread|splayed|parted)\b',  # nude + spread combinations
    r'\bthighs?\s+spread\s+(?:wide\s+)?(?:revealing|exposing|displaying)\b',  # explicitly revealing
    r'\b(?:legs?|thighs?)\s+(?:spread|parted)\s+(?:wide\s+)?(?:open|apart)\s+(?:revealing|showing|exposing)\b',
    r'\bopen\s+book\s+waiting\s+to\s+be\s+read\b',  # Sexual metaphor in context
    r'\babove\s+(?:her\s+)?pubic\s+triangle\b',  # Explicit anatomical reference
    r'\b(?:breasts?|bust)\s+swell\s+beneath\b',  # Sexualized description
]

# NSFW sentence/clause patterns (for prose format - removes entire sentences/clauses)
NSFW_PROSE_SENTENCE_PATTERNS = [
    # Sentences with explicit anatomy + suggestive action
    r'\b[^.!?]*(?:breasts?|bust)\s+swell\s+beneath[^.!?]*[.!?]',
    r'\b[^.!?]*thighs?\s+spread\s+wide\s+apart[^.!?]*[.!?]',
    r'\b[^.!?]*open\s+book\s+waiting\s+to\s+be\s+read[^.!?]*[.!?]',
    r'\b[^.!?]*pubic\s+triangle[^.!?]*[.!?]',
    r'\b[^.!?]*public\s+hair[^.!?]*[.!?]',  # Common typo: "public" instead of "pubic"
    # Clauses (sentence fragments between commas/periods)
    r'[,.]?\s*[^,.!?]*(?:breasts?|bust)\s+swell\s+beneath[^,.!?]*(?=\s*[,.!?])',
    r'[,.]?\s*[^,.!?]*thighs?\s+spread\s+wide\s+apart[^,.!?]*(?=\s*[,.!?])',
    r'[,.]?\s*[^,.!?]*open\s+book\s+waiting\s+to\s+be\s+read[^,.!?]*(?=\s*[,.!?])',
    r'[,.]?\s*[^,.!?]*above\s+(?:her\s+)?pubic\s+triangle[^,.!?]*(?=\s*[,.!?])',
]




# Watermark-related tags (for removal)
WATERMARK_TAGS_PATTERN = (
    r"(?i),?\s*\b(?:watermarked|copyright|copyrighted|artist[_\s]?name|signature|signed|"
    r"logo|username|user[_\s]?name|web[_\s]?address|url|patreon|"
    r"twitter[_\s]?(?:username|handle|name)?|instagram[_\s]?(?:username|handle|name)?|"
    r"deviantart|pixiv|text|dated|sample|preview)\b,?\s*"
)
RE_WATERMARK_TAGS = re.compile(WATERMARK_TAGS_PATTERN, re.IGNORECASE)

# Simple subject pattern (V2-style - less aggressive than V3)
RE_SUBJECT_SIMPLE = re.compile(
    r"(?:subject|person|people|man|woman|girl|boy|character)\s*[:\-–]?\s*[^\n\.;]+[\n\.;]?",
    re.IGNORECASE
)


# ============================================================================
# Image Type Prose Removal Patterns (remove_image feature)
# Pre-compiled patterns for removing image type descriptions from prose text.
# These are applied sequentially in order. Used by ReplaceStringV2 and V3.
# ============================================================================

# Common image type words used in patterns
_IMAGE_TYPES = r'(?:illustration|painting|drawing|photo|photograph|picture|render|image|artwork)'
_IMAGE_TYPES_EXT = r'(?:illustration|painting|drawing|sketch|photograph|photo|render|image|picture)'

# Pattern 1: "a [adjectives] [image type] in [complex style], it depicts/featuring"
# e.g., "a highly detailed, digital illustration in a semi-realistic, anime-inspired style, it depicts a young woman"
RE_IMAGE_IN_STYLE_DEPICTS = re.compile(
    r'(?i)^(?:a|an)\s+(?:[\w\-]+[,\s]+)*?(?:digital\s+)?' + _IMAGE_TYPES +
    r'\s+in\s+.*?style,?\s*(?:it\s+depicts|featuring)\s+',
)

# Pattern 2: "a [adjectives] [image type] depicting"
# e.g., "a digital illustration depicting a girl"
RE_IMAGE_DEPICTING = re.compile(
    r'(?i)^(?:a|an)\s+(?:[\w\-]+[,\s]+)*?(?:digital\s+)?' + _IMAGE_TYPES + r'\s+depicting\s+',
)

# Pattern 8: "A [adjectives] [style]-style [image type] depicting [subject]"
# e.g. "A vibrant anime-style digital illustration from a side camera angle, depicting a young woman"
# Preserves angle info for remove_shot_style to handle
RE_STYLE_IMAGE_DEPICTING = re.compile(
    r'(?i)^[\s]*(?:a|an)\s+'
    r'(?:[\w\-]+\s+)*?'
    r'[\w\-]+-style\s+'
    r'(?:(?:digital\s+)?' + _IMAGE_TYPES_EXT + r'\s+)?'
    r'(from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*,?\s*)?'
    r'depicting\s+(?=a\s+|an\s+|\w)',
)

# ========================================================================
# CONSOLIDATED PATTERN FACTORY FUNCTIONS
# ========================================================================

def _create_shoot_pattern(image_only=False, photo_realistic=False):
    """Factory function to create shoot patterns with consistent structure"""
    base_prefix = (
        r'(?i)^[\s]*(?:a|an)\s+'
        r'(?:[\w\-]+[,\s]+)*?'
    )
    
    if photo_realistic:
        # Photo-realistic specific pattern
        image_part = r'photo[- ]?realistic\s+shoot\s+'
    else:
        # General digital/illustration shoot pattern
        image_part = (
            r'(?:photo[- ]?realistic\s+)?'
            r'(?:photo\s+)?'
            r'(?:digital\s+)?(?:illustration|painting|art|artwork|photo)\s+'
            r'shoot\s+'
        )
    
    if image_only:
        # Image-only version preserves shot style elements
        return base_prefix + image_part + r'(?=from\s+|about\s+)'
    else:
        # Complete removal version
        return (
            base_prefix + image_part +
            r'(from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*)?'
            r'about\s+(?:(?:a\s+)?portrait\s+of\s+)?(?=a\s+|an\s+|\w)'
        )

def _create_image_type_pattern(from_angle=False, image_only=False):
    """Factory function for image type patterns"""
    base = (
        r'(?i)^[\s]*(?:a|an)\s+'
        r'((?:close[- ]?up|wide[- ]?angle|full[- ]?body|half[- ]?body|waist[- ]?up|medium[- ]?shot|establishing|extreme)[,\s]*)?'
        r'(?:[\w\-]+[,\s]+)*?'
        r'(?:semi-?realistic\s+)?'
        r'(?:photo[- ]?realistic\s+)?'
        r'(?:digital\s+)?'
        + _IMAGE_TYPES_EXT
    )
    
    if from_angle:
        if image_only:
            return base + r'\s+(?=from\s+)'
        else:
            return base + r'\s+from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*[,\s]*'
    else:
        return base

# ========================================================================
# OPTIMIZED CONSOLIDATED PATTERNS
# ========================================================================

# Consolidated shoot patterns using factory functions
RE_SHOOT_FROM_ABOUT_IMAGE_ONLY = re.compile(_create_shoot_pattern(image_only=True, photo_realistic=False))
RE_SHOOT_FROM_ABOUT = re.compile(_create_shoot_pattern(image_only=False, photo_realistic=False))
RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY = re.compile(_create_shoot_pattern(image_only=True, photo_realistic=True))
RE_PHOTO_SHOOT_FROM_ABOUT = re.compile(_create_shoot_pattern(image_only=False, photo_realistic=True))

# Consolidated image type patterns
RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY = re.compile(_create_image_type_pattern(from_angle=True, image_only=True))
RE_IMAGE_TYPE_FROM_ANGLE = re.compile(_create_image_type_pattern(from_angle=True, image_only=False))

# Style patterns using factory approach
def _create_style_pattern(comma_separated=False, image_only=False):
    """Factory for style-based patterns"""
    base = r'(?i)^[\s]*(?:a|an)\s+(?:digital\s+)?' + _IMAGE_TYPES_EXT
    
    if comma_separated:
        style_part = r',\s*[\w\-]+\s+style,?\s*'
        if image_only:
            return base + style_part + r'(?=shot\s+from)'
        else:
            return base + style_part + r'shot\s+from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*[,\s]*'
    else:
        return base

# Universal image description pattern factory
def _create_universal_image_pattern(pattern_type, image_only=False):
    """Universal factory for all image description patterns"""
    common_prefix = (
        r'(?i)^[\s]*(?:a|an)\s+'
        r'(?:[\w\-]+[,\s]+)*?'
        r'(?:semi-?realistic\s+)?'
        r'(?:photo[- ]?realistic\s+)?'
        r'(?:digital\s+)?'
    )
    
    patterns = {
        'of': common_prefix + _IMAGE_TYPES_EXT + r'\s+of\s+',
        'depicting': common_prefix + _IMAGE_TYPES_EXT + r'\s+depicting\s+',
        'featuring': common_prefix + _IMAGE_TYPES_EXT + r'\s+featuring\s+',
        'in_style_of': r'(?i)^(?:digital\s+)?' + _IMAGE_TYPES_EXT + r'\s+in\s+(?:an?\s+)?[\w\-]+\s+style\s+of\s+',
        'style_of': r'(?i)^[\w\-]+-style\s+(?:digital\s+)?' + _IMAGE_TYPES_EXT + r'\s+of\s+',
        'adj_style_of': common_prefix + r'[\w\-]+-style\s+(?:digital\s+)?' + _IMAGE_TYPES_EXT + r'\s+of\s+',
        'a_in_style_of': common_prefix + _IMAGE_TYPES_EXT + r'\s+in\s+(?:an?\s+)?[\w\-]+\s+style\s+of\s+',
        'adj_of': (
            common_prefix + _IMAGE_TYPES_EXT +
            r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?\s+of\s+'
        ),
    }
    
    return patterns.get(pattern_type, '')

# Consolidated style patterns
RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY = re.compile(_create_style_pattern(comma_separated=True, image_only=True))
RE_IMAGE_STYLE_SHOT_FROM = re.compile(_create_style_pattern(comma_separated=True, image_only=False))

# ========================================================================
# OPTIMIZED UNIVERSAL PATTERNS (Reduced redundancy)
# ========================================================================

# Universal patterns - generated by factory functions
RE_UNIVERSAL_IMAGE_OF = re.compile(_create_universal_image_pattern('of'))
RE_UNIVERSAL_IMAGE_DEPICTING = re.compile(_create_universal_image_pattern('depicting'))
RE_UNIVERSAL_IMAGE_FEATURING = re.compile(_create_universal_image_pattern('featuring'))

# Specific style patterns  
RE_STYLE_IMAGE_OF = re.compile(_create_universal_image_pattern('style_of'))
RE_IMAGE_IN_STYLE_OF = re.compile(_create_universal_image_pattern('in_style_of'))
RE_ADJ_STYLE_IMAGE_OF = re.compile(_create_universal_image_pattern('adj_style_of'))
RE_A_IMAGE_IN_STYLE_OF = re.compile(_create_universal_image_pattern('a_in_style_of'))
RE_ADJ_IMAGE_OF = re.compile(_create_universal_image_pattern('adj_of'))

# Pattern 10: "A [adjectives] digital illustration/photo/etc [continuation]"
# Preserves meaningful shot descriptors and continuation words
# e.g. "A photo-realistic shoot from..." -> "A shoot from..."
RE_ADJ_IMAGE_CONTINUATION = re.compile(
    r'(?i)^([\s]*(?:a|an)\s+)'
    r'((?:close[- ]?up|wide[- ]?angle|full[- ]?body|half[- ]?body|waist[- ]?up|medium[- ]?shot|establishing|extreme)[,\s]*)?'
    r'(?:[\w\-]+[,\s]+)*?'
    r'(?:semi-?realistic\s+)?'
    r'(?:photo[- ]?realistic\s+)?'
    r'(?:digital\s+)?'
    + _IMAGE_TYPES_EXT +
    r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?'
    r'(\s+(?:featuring|shoot|shot|where|depicting|showing)\b)',
)

# Pattern 11: Simple "a [adjectives] illustration of/featuring"
RE_SIMPLE_IMAGE_OF = re.compile(
    r'^[\s]*(?:a|an)\s+(?:[\w\-]+\s+)*(?:illustration|painting|drawing|sketch|photograph|photo)\s+(?:of\s+|featuring\s+)',
)

# Pattern 11b: Common image description verbs
RE_IMAGE_SHOWS = re.compile(
    r'\b(?:the\s+)?(?:image|photo|picture|illustration|painting|artwork)\s+(?:shows?|features?|captures?|illustrates?|showcases?|demonstrates?|reveals?|exposes?|presents?|displays?)\s+',
)

# Pattern 11c: More image description patterns  
RE_IMAGE_DESCRIPTION_VERBS = re.compile(
    r'^[\s]*(?:this\s+)?(?:image|photo|picture|illustration|painting|artwork)\s+(?:shows?|features?|captures?|illustrates?|showcases?|demonstrates?|reveals?|exposes?|presents?|displays?)\s+',
)

# Pattern 11d: "A picture of" and "A photograph" patterns
RE_PICTURE_OF = re.compile(
    r'^[\s]*(?:a|an)\s+(?:picture|photograph|photo)\s+of\s+',
)

# Pattern 11e: "This photograph captures" type descriptions
RE_PHOTO_CAPTURES = re.compile(
    r'^[\s]*(?:this\s+)?(?:photograph|photo)\s+(?:captures?|depicts?)\s+(?:the\s+)?',
)

# Pattern 11f: "Visual representation" and exhibition/study patterns
RE_VISUAL_REPRESENTATION = re.compile(
    r'^[\s]*(?:this\s+)?(?:visual\s+representation|exhibition\s+piece|artistic\s+study|commercial\s+photography\s+sample)\s+',
)

# Pattern 11g: Professional terminology patterns
RE_PROFESSIONAL_PHOTOGRAPHY = re.compile(
    r'(?i)^[\s]*(?:a\s+)?(?:professional\s+headshot|documentary\s+image)\s+',
)

# Pattern 11h: Missing image description patterns for better coverage
RE_AN_IMAGE_OF = re.compile(
    r'^[\s]*an\s+image\s+of\s+',
)

RE_PHOTO_DEPICTS = re.compile(
    r'\b(?:the\s+)?photo\s+depicts\b',
)

RE_ARTISTIC_RENDERING = re.compile(
    r'^[\s]*(?:a|an)\s+artistic\s+rendering\s+of\s+',
)

RE_DIGITAL_PAINTING_SHOWING = re.compile(
    r'^[\s]*(?:a|an)\s+digital\s+painting\s+showing\s+(?:a\s+)?',
)

RE_ARTISTIC_STUDY = re.compile(
    r'^[\s]*(?:the\s+)?artistic\s+study\s+(?:explores?|examines?|shows?)\s+',
)

# Pattern 11i: Digital/artistic shoot/session patterns
RE_DIGITAL_ART_SHOOT = re.compile(
    r'^[\s]*(?:a|an)\s+digital\s+(?:illustration|painting|art|artwork)\s+shoot\b[,\s]*',
)

# Pattern 12: "a [adjectives] illustration in style, featuring"
RE_IMAGE_IN_STYLE_FEATURING = re.compile(
    r'^[\s]*(?:a|an)\s+(?:[\w\-]+\s+)*(?:illustration|painting|drawing|sketch|photograph|photo)\s+in\s+(?:an?\s+)?[\w\s]+(?:style|art)\s*,?\s*featuring\s+',
)

# Pattern 13: "A [adjectives] digital illustration/photo/etc in a [style]" without continuation
# e.g. "A semi-realistic digital illustration in a nontraditional anime style" -> ""
RE_IMAGE_IN_STYLE_END = re.compile(
    r'^[\s]*(?:a|an)\s+'
    r'(?:[\w\-]+[,\s]+)*?'
    r'(?:semi-?realistic\s+)?'
    r'(?:photo[- ]?realistic\s+)?'
    r'(?:digital\s+)?'
    + _IMAGE_TYPES_EXT +
    r'(?:\s+in\s+(?:an?\s+)?[\w\s\-]+(?:style|art))?'
    r'[,\s]*$',
)

# Pattern 14: Standalone image type words
# e.g. "photo realistic" -> "" or "digital illustration" -> ""
RE_STANDALONE_IMAGE_TYPE = re.compile(
    r'\b(?:semi-?realistic\s+)?(?:photo[- ]?realistic|digital\s+illustration|digital\s+painting|digital\s+art)\b[,\s]*',
)

# Pattern 15: Dangling style descriptors before "of"
RE_DANGLING_STYLE = re.compile(r'[,\s]*[\w\-]+-style[,\s]*(?=of\b)')

# Pattern 16: "A where" cleanup - capitalize what follows
RE_A_WHERE = re.compile(r'^([\s]*(?:a|an)\s+)(where\b)')

# Cleanup patterns for remove_image
RE_DOUBLE_COMMA = re.compile(r',\s*,')
RE_COMMA_BEFORE_OF = re.compile(r',\s+(?=of\b)')
RE_MULTI_SPACE_INLINE = re.compile(r' {2,}')
RE_LEADING_COMMA_SPACE = re.compile(r'^[,\s]+')


# ============================================================================
# Shot Style Removal Patterns (remove_shot_style feature)
# Pre-compiled patterns for removing camera angles and shot types from prose.
# Used by ReplaceStringV3.
# ============================================================================

# Common angle words used in shot patterns
_ANGLE_WORDS = r'(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front|top[- ]?down|wide[- ]?angle|full[- ]?body|macro|aerial)'
_ANGLE_WORDS_EXT = r'(?:close[- ]?up|portrait|side|low|high|behind|frontal|profile|front|full[- ]?body|wide[- ]?angle|macro|aerial|establishing|tracking|dolly|crane|handheld)'
_CAMERA_ANGLES = r'(?:low|high|side|front|behind|top|bottom|bird\'?s?[- ]?eye|worm\'?s?[- ]?eye|dutch|canted|tilted|overhead|ground[- ]?level|wide[- ]?angle)'

# Additional shot type patterns
_SHOT_TYPES = r'(?:wide[- ]?(?:angle|shot)|medium[- ]?shot|long[- ]?shot|extreme[- ]?(?:close[- ]?up|wide)|establishing[- ]?shot|tracking[- ]?shot|dolly[- ]?shot|crane[- ]?shot|handheld[- ]?shot|macro[- ]?shot|aerial[- ]?shot|time[- ]?lapse|long[- ]?exposure|headshot)'

# "from a X camera angle," at start (leftover from remove_image)
RE_SHOT_ANGLE_START = re.compile(
    r'(?i)^[\s]*from\s+(?:a\s+)?(?:[\w\-]+\s+)*?(?:camera\s+)?(?:angle|perspective)\s*,?\s*'
)

# "shoot from a X angle about"
RE_SHOT_SHOOT_FROM = re.compile(
    r'(?i)\bshoot\s+from\s+(?:a\s+)?(?:the\s+)?' + _ANGLE_WORDS +
    r'\s*(?:angle|camera\s+angle|perspective)?\s*(?:about\s+)?'
)

# "captured from a X angle" with trailing punctuation
RE_SHOT_CAPTURED_PUNCT = re.compile(
    r'(?i)\bcaptured\s+from\s+(?:a\s+)?' + _ANGLE_WORDS +
    r'\s*(?:angle|camera\s+angle)?\s*([.,])'
)

# "captured from a X angle" without punctuation
RE_SHOT_CAPTURED = re.compile(
    r'(?i)\bcaptured\s+from\s+(?:a\s+)?' + _ANGLE_WORDS +
    r'\s*(?:angle|camera\s+angle)?'
)

# "shot from a X view"
RE_SHOT_FROM_VIEW = re.compile(
    r'(?i)\bshot\s+from\s+(?:a\s+)?' + _ANGLE_WORDS + r'\s*(?:view)?\b\.?'
)

# "taken from a X angle/position"
RE_SHOT_TAKEN_FROM = re.compile(
    r'(?i)\btaken\s+from\s+(?:a\s+)?(?:the\s+)?' + _ANGLE_WORDS_EXT + r'\s*(?:angle|position|perspective)?\b',
)

# Shot type at beginning of sentence
RE_SHOT_TYPE_START = re.compile(
    r'(?i)^[\s]*(?:a\s+|an\s+)?' + _SHOT_TYPES + r'\s+(?:of\s+)?',
)

# Full-body and specific shot types
RE_SHOT_FULL_BODY = re.compile(
    r'(?i)^[\s]*(?:a\s+)?full[- ]?body[- ]?shot\s+(?:displays?|shows?)\s+',
)

# View-specific shots
RE_SHOT_VIEWS = re.compile(
    r'(?i)\b(?:bird.*eye.*view|worm.*eye.*view)\s+(?:provides?|makes?|creates?|reveals?|shows?|gives?|offers?)\b',
)

# Camera movement shots
RE_SHOT_CAMERA_MOVEMENT = re.compile(
    r'(?i)\b(?:the\s+)?(?:dolly|crane|tracking|panning)[- ]?shot\s+(?:creates?|provides?|follows?)\s+',
)

# Shot location and context
RE_SHOT_CONTEXT = re.compile(
    r'(?i)\bshot\s+on\s+location\s+with\b',
)

# Technical shot descriptions
RE_SHOT_TECHNICAL = re.compile(
    r'(?i)\b(?:a\s+)?(?:time[- ]?lapse|long[- ]?exposure|freeze[- ]?frame)[- ]?shot\b',
)

# Missing shot patterns for better coverage
RE_SHOT_CAPTURED_AT = re.compile(
    r'(?i)\bcaptured\s+at\s+(?:eye\s+level|(?:a\s+)?(?:low|high|medium)\s+(?:angle|level))\b',
)

RE_SHOT_CAPTURED_USING = re.compile(
    r'(?i)\bcaptured\s+using\s+(?:a\s+)?(?:telephoto|wide[- ]?angle|macro|fisheye)\s+lens\b',
)

RE_SHOT_BIRDS_EYE = re.compile(
    r'(?i)\btaken\s+from\s+(?:a\s+)?(?:bird.*eye.*view|high\s+above|overhead|above)',
)

# "from a X camera angle" after period
RE_SHOT_AFTER_PERIOD = re.compile(
    r'(?i)\.\s*from\s+(?:a\s+)?' + _ANGLE_WORDS_EXT + r'\s*(?:camera\s+)?(?:angle)?\b'
)

# "from a X camera angle" after comma
RE_SHOT_AFTER_COMMA = re.compile(
    r'(?i),\s*from\s+(?:a\s+)?' + _ANGLE_WORDS_EXT + r'\s*(?:camera\s+)?(?:angle)?\b'
)

# "about a portrait of a" -> "about a"
RE_SHOT_ABOUT_PORTRAIT_A = re.compile(
    r'(?i)about\s+(?:a\s+)?(?:black\s+and\s+white\s+)?portrait\s+of\s+a\s+'
)

# "about a portrait of" -> "about"
RE_SHOT_ABOUT_PORTRAIT = re.compile(
    r'(?i)about\s+(?:a\s+)?(?:black\s+and\s+white\s+)?portrait\s+of\b'
)

# "A close-up shot of" (for removal when remove_image active)
RE_SHOT_CLOSEUP_OF_START = re.compile(r'(?i)^(?:a|an)\s+close[- ]?up\s+shot\s+of\s+')
RE_SHOT_CLOSEUP_OF_AFTER = re.compile(r'(?i)(\.\s+)(?:a|an)\s+close[- ]?up\s+shot\s+of\s+')

# "extreme close-up" without "shot" (standalone shot style)
RE_SHOT_EXTREME_CLOSEUP = re.compile(r'\bextreme\s+close[-\s]?up\b', re.IGNORECASE)

# "A portrait of" (for removal when remove_image active)
RE_SHOT_PORTRAIT_OF_START = re.compile(r'(?i)^(?:a|an)\s+(?:black\s+and\s+white\s+)?portrait\s+of\s+')
RE_SHOT_PORTRAIT_OF_AFTER = re.compile(r'(?i)(\.\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?portrait\s+of\s+')

# "A close-up shot of" -> "A shot of" (replacement when remove_image not active)
RE_SHOT_CLOSEUP_REPLACE = re.compile(r'(?i)\bA\s+close[- ]?up\s+shot\s+of\b')

# "A portrait of" -> "A picture of" (replacement when remove_image not active)
RE_SHOT_PORTRAIT_REPLACE_START = re.compile(r'(?i)^A\s+(?:black\s+and\s+white\s+)?portrait\s+of\b')
RE_SHOT_PORTRAIT_REPLACE_AFTER = re.compile(r'(?i)\.\s+A\s+(?:black\s+and\s+white\s+)?portrait\s+of\b')

# "back to the camera" phrase
RE_SHOT_BACK_TO_CAMERA = re.compile(
    r'(?i),?\s*(?:her|his|their)\s+back\s+to\s+(?:the\s+)?camera,?\s*'
)

# "The image is taken from a low angle"
RE_SHOT_IMAGE_TAKEN_FROM = re.compile(
    r'(?i)(?:The\s+)?(?:image|photo|photograph|picture|shot)\s+is\s+(?:taken|shot|captured|framed)\s+from\s+(?:a\s+)?'
    + _CAMERA_ANGLES +
    r'\s*(?:angle|perspective|view|position)?\s*'
    r'(?:,\s*looking\s+(?:up|down|straight|directly)\s+at\s+(?:the\s+)?(?:subject|person|viewer|camera))?\s*[.,]?\s*'
)

# "The focus of the image is on"
RE_SHOT_FOCUS_ON = re.compile(
    r'(?i)(?:The\s+)?focus\s+of\s+(?:the\s+)?(?:image|photo|shot)\s+is\s+on\s+'
)

# "looking up at the person"
RE_SHOT_LOOKING_AT = re.compile(
    r'(?i),?\s*looking\s+(?:up|down|directly|straight)\s+at\s+(?:the\s+)?(?:person|subject|viewer|camera)\s*(?:with\s+)?'
)

# Shot style cleanup patterns
RE_SHOT_DOUBLE_ABOUT = re.compile(r'shoot\s+about\s+about')
RE_SHOT_COMMA_PERIOD = re.compile(r',\s*\.')
RE_SHOT_PERIOD_COMMA = re.compile(r'\.\s*,')
RE_SHOT_TRAILING_COMMA = re.compile(r',\s*$')
RE_SHOT_LEADING_COMMA = re.compile(r'^\s*,\s*')
RE_SHOT_SPACE_PUNCT = re.compile(r'\s+([.,])')
RE_SHOT_ORPHAN_WITH = re.compile(r'(?i),\s*with\s*[.,]')
RE_SHOT_TRAILING_WITH = re.compile(r'(?i),\s*with\s*$')


# ============================================================================
# Age Adjustment Patterns (adjust_age feature)
# Pre-compiled patterns for replacing age references.
# Used by ReplaceStringV3.
# Note: Patterns with {target_age} are templates - use .format() or f-string substitution
# ============================================================================

# Comma-enclosed: ", who appears to be in her late teens or early twenties,"
RE_AGE_LATE_TEENS_COMMA = re.compile(
    r'(?i),\s*who\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\s*,'
)

# Comma-enclosed: ", who appears to be in her mid-twenties,"
RE_AGE_MID_DECADE_COMMA = re.compile(
    r'(?i),\s*who\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\s*,'
)

# "who appears to be in her late teens or early twenties" (not in commas)
RE_AGE_WHO_LATE_TEENS = re.compile(
    r'(?i)\bwho\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b'
)

# Pronoun + "appears to be in her late teens or early twenties"
RE_AGE_PRONOUN_LATE_TEENS = re.compile(
    r'(?i)\b(she|he|they)\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b'
)

# "appears to be in her late teens or early twenties" (without who/pronoun)
RE_AGE_APPEARS_LATE_TEENS = re.compile(
    r'(?i)\bappears?\s+to\s+be\s+in\s+(?:her|his|their)\s+late\s+teens\s+or\s+early\s+twenties\b'
)

# "who appears to be in her mid-twenties" (not in commas)
RE_AGE_WHO_MID_DECADE = re.compile(
    r'(?i)\bwho\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b'
)

# Pronoun + "appears to be in her mid-twenties"
RE_AGE_PRONOUN_MID_DECADE = re.compile(
    r'(?i)\b(she|he|they)\s+appears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b'
)

# "appearing to be in her mid-twenties"
RE_AGE_APPEARING_MID_DECADE = re.compile(
    r'(?i)\bappearing\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b'
)

# "appears to be in her mid-twenties" (without who/pronoun)
RE_AGE_APPEARS_MID_DECADE = re.compile(
    r'(?i)\bappears?\s+to\s+be\s+in\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b'
)

# "who appears to be around 25"
RE_AGE_WHO_AROUND = re.compile(
    r'(?i)\bwho\s+appears?\s+to\s+be\s+(?:around\s+)?\d{1,2}(?:\s+years?\s+old)?\b'
)

# "appears to be around 25"
RE_AGE_APPEARS_AROUND = re.compile(
    r'(?i)\bappears?\s+to\s+be\s+(?:around\s+)?\d{1,2}(?:\s+years?\s+old)?\b'
)

# "in her early twenties" (standalone)
RE_AGE_IN_DECADE = re.compile(
    r'(?i)\bin\s+(?:her|his|their)\s+(?:early|mid|late)[- ]?(?:teens?|twenties|thirties|forties|fifties)\b'
)

# Standalone number in tags before hair color
RE_AGE_TAG_BEFORE_HAIR = re.compile(
    r',\s*(\d{1,2})\s*,(?=\s*(?:long|short|blonde|brown|black|red|white|pink)\s+hair)'
)

# "young woman/man/person" -> replacement
RE_AGE_YOUNG_SUBJECT = re.compile(
    r'(?i)\byoung\s+(woman|man|person|girl|boy|lady|adult|individual|figure)\b'
)

# "teenage/teen girl/boy"
RE_AGE_TEENAGE = re.compile(
    r'(?i)\b(?:teenage|teenaged|teen)\s+(girl|boy|woman|man)\b'
)


# ============================================================================
# NSFW Prose Removal Patterns (remove_nsfw feature)
# Pre-compiled patterns for removing explicit content from prose.
# Used by ReplaceStringV3.
# ============================================================================

# "her body is completely nude, with no clothing..."
RE_NSFW_BODY_NUDE_SENTENCE = re.compile(
    r'(?i)\.\s*(?:her|his|their)\s+body\s+is\s+(?:completely|fully|entirely)?\s*(?:nude|naked)[^.]*\.'
)

# Same without leading period
RE_NSFW_BODY_NUDE_CLAUSE = re.compile(
    r'(?i),?\s*(?:her|his|their)\s+body\s+is\s+(?:completely|fully|entirely)?\s*(?:nude|naked)[^.]*(?=\.|\s*$)'
)

# "with no clothing or accessories on"
RE_NSFW_NO_CLOTHING = re.compile(
    r'(?i),?\s*with\s+no\s+(?:clothing|clothes)\s+(?:or\s+accessories?\s+)?(?:on|visible)\b'
)

# "is completely/fully nude/naked"
RE_NSFW_IS_NUDE = re.compile(
    r'(?i)\bis\s+(?:completely|fully|entirely)\s+(?:nude|naked)\b[^.]*'
)

# "completely/fully nude" without "is"
RE_NSFW_COMPLETELY_NUDE = re.compile(
    r'(?i)\b(?:completely|fully|entirely)\s+(?:nude|naked)\b'
)

# "a nude woman" -> "a woman"
RE_NSFW_A_NUDE_SUBJECT = re.compile(
    r'(?i)\b(a|an)\s+(?:nude|naked)\s+(woman|man|girl|boy|person|figure|model)\b'
)


# ============================================================================
# Watermark Removal Patterns (remove_watermark feature)
# Pre-compiled patterns for removing watermark references.
# Used by ReplaceStringV3.
# ============================================================================

# Detect underscore (tag format indicator)
RE_WATERMARK_UNDERSCORE = re.compile(r'_')

# Detect period followed by space (prose indicator)
RE_WATERMARK_PERIOD_SPACE = re.compile(r'\.\s')

# Tag format: remove clause containing watermark
RE_WATERMARK_TAG_CLAUSE = re.compile(r'(?i),\s*[^,]*\bwatermark\b[^,]*(?=,|$)')
RE_WATERMARK_TAG_START = re.compile(r'(?i)^[^,]*\bwatermark\b[^,]*,\s*')


# ============================================================================
# NSFW Level Detection (centralized for SavePrompt and other nodes)
# ============================================================================

# X-rated keywords (explicit content)
NSFW_KEYWORDS_X = [
    # Explicit sexual acts
    'sex', 'intercourse', 'penetration', 'doggystyle', 'cowgirl', 'missionary',
    'mating press', 'prone bone', 'creampie', 'gangbang', 'threesome',
    # Oral
    'fellatio', 'blowjob', 'oral', 'cunnilingus', 'deepthroat', 'facefuck',
    # Manual
    'handjob', 'fingering', 'masturbat', 'paizuri', 'titfuck', 'titty fuck', 'boobjob',
    # Body parts (explicit)
    'penis', 'cock', 'dick', 'vagina', 'pussy', 'clit', 'genitals', 'anus',
    # Nudity (explicit)
    'nude', 'naked', 'nipple', 'nipples', 'tits', 'areola',
    # Fluids
    'cum', 'cumshot', 'ejaculation', 'semen', 'creampie', 'grool', 'pussy juice',
    # Fetish/kink
    'bondage', 'bdsm', 'futanari', 'futa', 'ahegao', 'dildo', 'vibrator',
    # Labels
    'nsfw', 'xxx', 'porn', 'hentai', 'explicit', 'rating_explicit', 'uncensored',
    # States
    'orgasm', 'erotic', 'spread legs', 'spread pussy', 'spread ass',
]

# Mature keywords (suggestive content)
NSFW_KEYWORDS_MATURE = [
    # Suggestive clothing
    'sexy', 'lingerie', 'underwear', 'bikini', 'thong', 'panties', 'bra',
    'skimpy', 'revealing', 'see-through', 'fishnet',
    # Suggestive body focus
    'cleavage', 'sideboob', 'underboob', 'cameltoe', 'topless', 'shirtless', 'bare', 'exposed',
    # Suggestive mood/pose
    'seductive', 'sensual', 'provocative', 'suggestive', 'lustful', 'lust',
    'slutty', 'aroused', 'flirty', 'naughty',
    # Labels
    'ecchi', 'pinup', 'risque', 'mature',
    # Body descriptions
    'breast', 'breasts', 'boob', 'boobs',
]




# Prose format: remove sentence containing watermark
RE_WATERMARK_PROSE_SENTENCE = re.compile(r'(?i)(?:(?<=\.\s)|^)[^.]*\bwatermark\b[^.]*\.\s*')
RE_WATERMARK_PROSE_END = re.compile(r'(?i)(?:(?<=\.\s)|^)[^.]*\bwatermark\b[^.]*$')


# ============================================================================
# Additional Enhanced Patterns
# ============================================================================

# New shot style patterns for missing photography terms
RE_SHOT_TAKEN_FROM = re.compile(
    r'(?i)\btaken\s+from\s+(?:a\s+)?(?:the\s+)?' + _ANGLE_WORDS_EXT + r'\s*(?:angle|position|perspective)?\b',
)

RE_SHOT_TYPE_START = re.compile(
    r'(?i)^[\s]*(?:a\s+|an\s+)?' + _SHOT_TYPES + r'\s+(?:of\s+)?',
)

# Enhanced instruction detection for colon headers
RE_INSTRUCTION_COLON_HEADER = re.compile(
    r'^[^\n:]{1,80}(?:prompt|description|caption|direction|brief|analysis|breakdown|concept|vision|output|result)\s*:\s*',
    re.IGNORECASE
)


# ============================================================================
# PATTERN GROUPS FOR OPTIMIZED IMPORTS
# ============================================================================

# Core whitespace patterns (needed by both V2 and V3)
CORE_WHITESPACE_PATTERNS = [
    'RE_NEWLINES', 'RE_MULTI_SPACE', 'RE_ALL_WHITESPACE', 'RE_NEWLINES_TABS',
    'RE_MULTI_SPACE_INLINE', 'RE_LEADING_COMMA', 'RE_LEADING_COMMA_SPACE'
]

# Core punctuation patterns (needed by both V2 and V3)
CORE_PUNCTUATION_PATTERNS = [
    'RE_DOUBLE_PUNCT', 'RE_TRAILING_PUNCT', 'RE_COMMA_BEFORE_OF', 'RE_DOUBLE_COMMA'
]

# Core image patterns (needed by both V2 and V3)
CORE_IMAGE_PATTERNS = [
    'RE_IMAGE_SHOWS', 'RE_IMAGE_DESCRIPTION_VERBS', 'RE_PICTURE_OF', 
    'RE_PHOTO_CAPTURES', 'RE_VISUAL_REPRESENTATION', 'RE_PROFESSIONAL_PHOTOGRAPHY',
    'RE_AN_IMAGE_OF', 'RE_PHOTO_DEPICTS', 'RE_ARTISTIC_RENDERING',
    'RE_DIGITAL_PAINTING_SHOWING', 'RE_ARTISTIC_STUDY', 'RE_DIGITAL_ART_SHOOT'
]

# Core instruction patterns (needed by both V2 and V3)
CORE_INSTRUCTION_PATTERNS = [
    'RE_INSTRUCTION_PREFIX', 'RE_INSTRUCTION_COLON_HEADER', 'RE_INSTRUCTION_EXPANSION',
    'RE_INSTRUCTION_DESIGN', 'RE_INSTRUCTION_VERSION'
]

# Core list patterns (needed by both V2 and V3)
CORE_LIST_PATTERNS = [
    'RE_LIST_FIRST_QUOTED', 'RE_LIST_HEADER', 'RE_LIST_NUMBERED', 'RE_LIST_LABELS'
]

# Core style patterns (needed by both V2 and V3)
CORE_STYLE_PATTERNS = [
    'RE_IMAGE_DEPICTING', 'RE_IMAGE_IN_STYLE_DEPICTS', 'RE_STYLE_IMAGE_DEPICTING',
    'RE_STYLE_BEFORE_SUBJECT', 'RE_IMAGE_IN_STYLE_END', 'RE_IMAGE_IN_STYLE_FEATURING'
]

# Universal image patterns (replace duplicates)
UNIVERSAL_IMAGE_PATTERNS = [
    'RE_UNIVERSAL_IMAGE_OF', 'RE_UNIVERSAL_IMAGE_DEPICTING', 'RE_UNIVERSAL_IMAGE_FEATURING'
]

# Core pattern lists (needed by both V2 and V3)
CORE_PATTERN_LISTS = [
    'SUBJECT_TAG_PATTERNS', 'BACKGROUND_TAG_PATTERNS', 'IMAGE_TAG_PATTERNS', 'SETTING_WORDS'
]

# Core subject/pronoun patterns (needed by both V2 and V3)
CORE_SUBJECT_PATTERNS = [
    'RE_SUBJECT_LABEL', 'RE_SUBJECT_WORDS', 'RE_PRONOUN_COPULA', 'RE_PRONOUN_SENTENCE',
    'RE_POSSESSIVE_PHRASES', 'RE_PRONOUN_FRAGMENT', 'RE_IMAGE_IS_PREFIX', 'RE_PORTRAIT_PREFIX'
]

# Core markdown/text patterns (needed by both V2 and V3)
CORE_TEXT_PATTERNS = [
    'RE_BOLD_MARKDOWN', 'RE_QUOTED_CONTENT', 'RE_BACKGROUND', 'RE_MOOD', 'RE_IMAGE_DESCRIPTION'
]

# Image removal patterns shared by V2/V3
CORE_IMAGE_REMOVAL_PATTERNS = [
    'RE_SHOOT_FROM_ABOUT_IMAGE_ONLY', 'RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY',
    'RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY', 'RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY',
    'RE_ADJ_IMAGE_CONTINUATION', 'RE_SIMPLE_IMAGE_OF', 'RE_STANDALONE_IMAGE_TYPE',
    'RE_DANGLING_STYLE', 'RE_A_WHERE'
]

# All core patterns (V2 + V3 common)
ALL_CORE_PATTERNS = (
    CORE_WHITESPACE_PATTERNS + CORE_PUNCTUATION_PATTERNS + CORE_IMAGE_PATTERNS +
    CORE_INSTRUCTION_PATTERNS + CORE_LIST_PATTERNS + CORE_STYLE_PATTERNS +
    UNIVERSAL_IMAGE_PATTERNS + CORE_PATTERN_LISTS + CORE_SUBJECT_PATTERNS +
    CORE_TEXT_PATTERNS + CORE_IMAGE_REMOVAL_PATTERNS
)

# === V3 EXTENDED PATTERNS ===

# Shot style removal patterns (V3 only)
SHOT_STYLE_PATTERNS = [
    'RE_SHOT_ANGLE_START', 'RE_SHOT_SHOOT_FROM', 'RE_SHOT_CAPTURED_PUNCT',
    'RE_SHOT_CAPTURED', 'RE_SHOT_FROM_VIEW', 'RE_SHOT_AFTER_PERIOD',
    'RE_SHOT_AFTER_COMMA', 'RE_SHOT_ABOUT_PORTRAIT_A', 'RE_SHOT_ABOUT_PORTRAIT',
    'RE_SHOT_CLOSEUP_OF_START', 'RE_SHOT_CLOSEUP_OF_AFTER', 'RE_SHOT_PORTRAIT_OF_START',
    'RE_SHOT_PORTRAIT_OF_AFTER', 'RE_SHOT_CLOSEUP_REPLACE', 'RE_SHOT_PORTRAIT_REPLACE_START',
    'RE_SHOT_PORTRAIT_REPLACE_AFTER', 'RE_SHOT_BACK_TO_CAMERA', 'RE_SHOT_IMAGE_TAKEN_FROM',
    'RE_SHOT_FOCUS_ON', 'RE_SHOT_LOOKING_AT', 'RE_SHOT_DOUBLE_ABOUT',
    'RE_SHOT_COMMA_PERIOD', 'RE_SHOT_PERIOD_COMMA', 'RE_SHOT_TRAILING_COMMA',
    'RE_SHOT_LEADING_COMMA', 'RE_SHOT_SPACE_PUNCT', 'RE_SHOT_ORPHAN_WITH',
    'RE_SHOT_TRAILING_WITH', 'RE_SHOT_TAKEN_FROM', 'RE_SHOT_TYPE_START',
    'RE_SHOT_FULL_BODY', 'RE_SHOT_VIEWS', 'RE_SHOT_CAMERA_MOVEMENT',
    'RE_SHOT_CONTEXT', 'RE_SHOT_TECHNICAL', 'RE_SHOT_CAPTURED_AT',
    'RE_SHOT_CAPTURED_USING', 'RE_SHOT_BIRDS_EYE', 'RE_SHOT_EXTREME_CLOSEUP',
    'SHOT_OF_PATTERNS', 'TAG_SHOT_PATTERNS'
]

# Age adjustment patterns (V3 only)
AGE_ADJUSTMENT_PATTERNS = [
    'RE_AGE_WORDS', 'RE_AGE_HYPHEN', 'RE_AGE_YR', 'RE_AGE_YO',
    'RE_AGE_LATE_TEENS_COMMA', 'RE_AGE_MID_DECADE_COMMA', 'RE_AGE_WHO_LATE_TEENS',
    'RE_AGE_PRONOUN_LATE_TEENS', 'RE_AGE_APPEARS_LATE_TEENS', 'RE_AGE_WHO_MID_DECADE',
    'RE_AGE_PRONOUN_MID_DECADE', 'RE_AGE_APPEARING_MID_DECADE', 'RE_AGE_APPEARS_MID_DECADE',
    'RE_AGE_WHO_AROUND', 'RE_AGE_APPEARS_AROUND', 'RE_AGE_IN_DECADE',
    'RE_AGE_TAG_BEFORE_HAIR', 'RE_AGE_TEENAGE', 'RE_AGE_YOUNG_SUBJECT'
]

# NSFW removal patterns (V3 only) 
NSFW_REMOVAL_PATTERNS = [
    'NSFW_TAG_PATTERNS', 'NSFW_PROSE_PATTERNS'
]

# Watermark removal patterns (V3 only)
WATERMARK_REMOVAL_PATTERNS = [
    'RE_WATERMARK_TAGS', 'RE_WATERMARK_PERIOD_SPACE', 'RE_WATERMARK_PROSE_END',
    'RE_WATERMARK_PROSE_SENTENCE', 'RE_WATERMARK_TAG_CLAUSE', 'RE_WATERMARK_TAG_START',
    'RE_WATERMARK_UNDERSCORE'
]

# V3-specific image patterns (full removal versions)
V3_IMAGE_PATTERNS = [
    'RE_SHOOT_FROM_ABOUT', 'RE_PHOTO_SHOOT_FROM_ABOUT', 'RE_IMAGE_STYLE_SHOT_FROM',
    'RE_IMAGE_TYPE_FROM_ANGLE'
]

# All V3 extended patterns
ALL_V3_EXTENDED_PATTERNS = (
    SHOT_STYLE_PATTERNS + AGE_ADJUSTMENT_PATTERNS + NSFW_REMOVAL_PATTERNS +
    WATERMARK_REMOVAL_PATTERNS + V3_IMAGE_PATTERNS
)


# ============================================================================
# OPTIMIZED PATTERNS - 100% Sense Preservation (Based on Testing Results)
# ============================================================================
# These patterns were tested on 964 real-world prompts and achieved 100% 
# sense preservation when combined with smart grammar cleanup

# Remove image type but preserve shot angles (for when remove_image=True but remove_shot_style=False)
RE_IMAGE_START_OPTIMIZED = re.compile(
    r'^(?:A|An)\s+(?:highly\s+detailed\s+(?:and\s+realistic\s+)?)?'
    r'(?:photo[-\s]realistic\s+)?(?:digital\s+)?'
    r'(?:illustration|image|photo|picture|artwork)\s+(?:of|depicting|featuring|showing)\s+',
    re.IGNORECASE
)

# Remove image type from combined image+shot descriptions  
RE_IMAGE_SHOT_COMBINED_OPTIMIZED = re.compile(
    r'^(?:A|An)\s+(?:photo[-\s]realistic\s+)?(?:digital\s+)?'
    r'(?:illustration|image|photo|picture|artwork)\s+'
    r'(?=(?:shoot|shot)\s+(?:from|taken\s+from))',
    re.IGNORECASE
)

# Remove trailing "depicting/featuring/showing" after shot descriptions
RE_IMAGE_CONNECTORS_OPTIMIZED = re.compile(
    r',\s+(?:depicting|featuring|showing)\s+',
    re.IGNORECASE
)

# Remove shot angle descriptions (only when remove_shot_style=True)
RE_SHOT_STYLE_OPTIMIZED = re.compile(
    r'(?:shoot|shot)\s+(?:from|taken\s+from)\s+(?:a\s+)?'
    r'(?:low\s+angle|side\s+angle|frontal\s+camera\s+angle|close[-\s]up\s+(?:camera\s+)?angle|'
    r'portrait\s+angle|behind|above)(?:\s+about\s*|,?\s*)',
    re.IGNORECASE
)

# Remove anime/manga style prefixes
RE_ANIME_STYLE_OPTIMIZED = re.compile(
    r'(?:A|An)\s+(?:anime[-\s]style|manga[-\s]style|digital)\s+(?:illustration|image)\s+(?:of|depicting)\s+',
    re.IGNORECASE
)

# Remove age appearance descriptions in clauses
RE_AGE_CLAUSE_OPTIMIZED = re.compile(
    r',\s+who\s+appears\s+to\s+be\s+in\s+her\s+(?:early\s+|late\s+|mid[-\s])?(?:teens|twenties|thirties)',
    re.IGNORECASE
)

# Remove specific age mentions like "20-year-old"
RE_AGE_SPECIFIC_OPTIMIZED = re.compile(
    r',\s+(?:a\s+)?\d{1,2}[-\s]?(?:year[-\s]?old|years?\s+old)(?:\s+woman|\s+girl)?',
    re.IGNORECASE
)

# Remove standalone nudity descriptions
RE_NUDITY_SENTENCE_OPTIMIZED = re.compile(
    r'\.\s+(?:she\s+is\s+)?(?:completely\s+|entirely\s+)?nude(?:\s*[,.]|$)',
    re.IGNORECASE
)

# Remove "with no clothing" clauses  
RE_CLOTHING_NONE_OPTIMIZED = re.compile(
    r',\s+with\s+no\s+clothing(?:\s+or\s+accessories)?(?:\s+(?:present|on|visible))?',
    re.IGNORECASE
)

# Remove body part visibility descriptions
RE_BODY_VISIBILITY_OPTIMIZED = re.compile(
    r',\s+(?:with\s+)?(?:her\s+)?(?:large\s+|small\s+)?(?:breasts|nipples)\s+(?:visible|prominently\s+displayed)',
    re.IGNORECASE
)

# Remove sexual act descriptions in clauses
RE_SEXUAL_ACT_OPTIMIZED = re.compile(
    r',\s+(?:performing\s+oral\s+sex|engaged\s+in\s+(?:a\s+)?sexual\s+act)',
    re.IGNORECASE
)

# Optimized pattern collections for easy access
OPTIMIZED_IMAGE_PATTERNS = [
    RE_IMAGE_START_OPTIMIZED, RE_IMAGE_SHOT_COMBINED_OPTIMIZED, RE_IMAGE_CONNECTORS_OPTIMIZED, RE_ANIME_STYLE_OPTIMIZED
]

# V2-specific optimized patterns (preserves shot styles - no shot removal)
OPTIMIZED_IMAGE_PATTERNS_V2 = [
    RE_IMAGE_START_OPTIMIZED, RE_IMAGE_SHOT_COMBINED_OPTIMIZED, RE_IMAGE_CONNECTORS_OPTIMIZED, RE_ANIME_STYLE_OPTIMIZED
]

OPTIMIZED_AGE_PATTERNS = [
    RE_AGE_CLAUSE_OPTIMIZED, RE_AGE_SPECIFIC_OPTIMIZED, RE_AGE_SIMPLE_FORMAT
]

OPTIMIZED_NSFW_PATTERNS = [
    RE_NUDITY_SENTENCE_OPTIMIZED, RE_CLOTHING_NONE_OPTIMIZED, 
    RE_BODY_VISIBILITY_OPTIMIZED, RE_SEXUAL_ACT_OPTIMIZED
]

ALL_OPTIMIZED_PATTERNS = (
    OPTIMIZED_IMAGE_PATTERNS + OPTIMIZED_AGE_PATTERNS + OPTIMIZED_NSFW_PATTERNS
)

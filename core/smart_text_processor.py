import os
import json
import re
from typing import Dict, List, Optional, Any

from .logger import log

_LOG_PREFIX = "SmartTextProcessor"


class SmartTextProcessor:
    """Load pattern files from templates/patterns and provide detection/edit APIs.

    Basic behavior:
    - Loads files listed in templates/patterns/index.json
    - Compiles one regex per category (file)
    - detect() returns list of match dicts: {category, text, span, score}
    - remove_matches() removes matched spans cleanly
    - soften_matches() replaces matched spans using a mapping dict
    """

    def __init__(self, patterns_dir: Optional[str] = None):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        default_patterns_dir = os.path.join(base, 'templates', 'patterns')
        self.patterns_dir = patterns_dir or default_patterns_dir
        self.index = {}
        self.raw_patterns: Dict[str, List[str]] = {}
        self.compiled: Dict[str, re.Pattern] = {}
        self.connectors: List[str] = []
        log.debug(_LOG_PREFIX, f"Initializing with patterns_dir: {self.patterns_dir}")
        self._load_patterns()
        self._compile_detectors()
        log.debug(_LOG_PREFIX, f"Initialized with {len(self.compiled)} compiled patterns")

    def _load_json(self, path: str) -> Any:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)

    def _load_patterns(self) -> None:
        index_path = os.path.join(self.patterns_dir, 'index.json')
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Pattern index not found: {index_path}")
        log.debug(_LOG_PREFIX, f"Loading pattern index from {index_path}")
        self.index = self._load_json(index_path)
        files = self.index.get('files', {})
        log.debug(_LOG_PREFIX, f"Found {len(files)} pattern files in index")
        for key, fname in files.items():
            path = os.path.join(self.patterns_dir, fname)
            if not os.path.exists(path):
                self.raw_patterns[key] = []
                continue
            data = self._load_json(path)
            
            # Check if this is a component-based pattern file
            if key in ('image_styles', 'subjects', 'shot_styles', 'backgrounds', 'moods') and (
                'core_terms' in data or 'core_subjects' in data or 'medium_types' in data or
                'indoor_locations' in data or 'outdoor_locations' in data or
                'subject_moods' in data or 'atmosphere_moods' in data
            ):
                # Store raw component data for later compilation
                self.raw_patterns[key] = data
            # Check if this is a categorized pattern file (backgrounds, moods, etc.)
            elif 'terms' not in data and isinstance(data, dict):
                # Flatten all category arrays/dicts into single terms list
                terms = []
                for k, v in data.items():
                    if k == 'description':
                        continue
                    if isinstance(v, list):
                        terms.extend(v)
                    elif isinstance(v, dict):
                        # Nested dict (like subjects.core_subjects.people)
                        for sublist in v.values():
                            if isinstance(sublist, list):
                                terms.extend(sublist)
                self.raw_patterns[key] = [t.strip() for t in terms if t and isinstance(t, str)]
            else:
                # Legacy: extract terms list
                terms = data.get('terms', [])
                # normalize terms (strip, skip empties)
                self.raw_patterns[key] = [t.strip() for t in terms if t and isinstance(t, str)]
        # connectors special
        self.connectors = self.raw_patterns.get('connectors', [])
        
        log.debug(_LOG_PREFIX, f"Loaded {len(self.raw_patterns)} pattern categories")

    def _term_to_pattern(self, term: str) -> str:
        # If term contains regex escape or special tokens, assume it's a pattern
        if re.search(r'[\\\^\$\*\+\?\{\}\[\]\|\(\)\.]', term):
            return term
        # else escape
        return re.escape(term)

    def _compile_subjects(self) -> None:
        """Generate context-aware patterns for subjects. Optimized for 28,537 real-world mentions."""
        data = self.raw_patterns.get('subjects', {})
        patterns = []  # Initialize early to avoid UnboundLocalError
        log.debug(_LOG_PREFIX, "Compiling subjects patterns...")
        
        if isinstance(data, list):
            # Fallback: legacy terms list
            terms_sorted = sorted(set(data), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            alternation = '|'.join(parts)
            self.compiled['subjects'] = re.compile(rf'(?P<term>\b(?:{alternation})\b)', re.I | re.U)
            return
        
        # Component-based structure - collect all patterns
        
        # Get count tags (Danbooru style: 1girl, 2girls, etc.)
        count_tags = data.get('count_tags', [])
        if count_tags:
            count_esc = [re.escape(t) for t in count_tags]
            count_alt = '|'.join(count_esc)
            # Pattern 1: Count tags (highest priority - exact match)
            patterns.append(rf'\b(?:{count_alt})\b')
        
        # Get all subject categories and flatten
        all_subjects = []
        core_subjects_data = data.get('core_subjects', {})
        if isinstance(core_subjects_data, dict):
            for category_list in core_subjects_data.values():
                if isinstance(category_list, list):
                    all_subjects.extend(category_list)
        
        # Collect from nsfw category
        nsfw_data = data.get('nsfw', {})
        if isinstance(nsfw_data, dict):
            for category_list in nsfw_data.values():
                if isinstance(category_list, list):
                    all_subjects.extend(category_list)
        
        # Get attributes (hair, features, etc.)
        attributes_data = data.get('attributes', {})
        if isinstance(attributes_data, dict):
            for category_list in attributes_data.values():
                if isinstance(category_list, list):
                    all_subjects.extend(category_list)
        
        # Get actions
        actions_data = data.get('actions', {})
        if isinstance(actions_data, dict):
            for category_list in actions_data.values():
                if isinstance(category_list, list):
                    all_subjects.extend(category_list)
        
        if all_subjects:
            # Build patterns for subjects (all categories)
            subjects_esc = [re.escape(t) for t in sorted(set(all_subjects), key=lambda s: -len(s))]
            subjects_alt = '|'.join(subjects_esc)
            # Pattern 2: All subject terms
            patterns.append(rf'\b(?:{subjects_alt})\b')
        
        # Combine all patterns
        if patterns:
            combined = '|'.join(patterns)
            self.compiled['subjects'] = re.compile(rf'(?P<term>{combined})', re.I | re.U)



    def _compile_image_styles(self) -> None:
        """Generate context-aware patterns for image styles. Optimized for 14,562 real-world mentions."""
        data = self.raw_patterns.get('image_styles', {})
        log.debug(_LOG_PREFIX, f"Compiling image_styles patterns... (data type: {type(data).__name__}, is_list: {isinstance(data, list)})")
        if isinstance(data, list):
            # Fallback: legacy terms list
            log.debug(_LOG_PREFIX, f"Using legacy list mode with {len(data)} terms")
            terms_sorted = sorted(set(data), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            alternation = '|'.join(parts)
            self.compiled['image_styles'] = re.compile(rf'(?P<term>\\b(?:{alternation})\\b)', re.I | re.U)
            return
        
        # Component-based structure
        medium_types = data.get('medium_types', [])
        style_modifiers = data.get('style_modifiers', [])
        quality_descriptors = data.get('quality_descriptors', [])
        color_modes = data.get('color_modes', [])
        technique_modifiers = data.get('technique_modifiers', [])
        presentation_styles = data.get('presentation_styles', [])
        descriptor_nouns = data.get('descriptor_nouns', [])
        shoot_suffixes = data.get('shoot_suffixes', [])
        connector_verbs = data.get('connector_verbs', [])
        
        log.debug(_LOG_PREFIX, f"Loaded components: medium={len(medium_types)}, style={len(style_modifiers)}, shoot={len(shoot_suffixes)}")
        
        if not medium_types and not technique_modifiers:
            log.debug(_LOG_PREFIX, "Early return: no medium_types or technique_modifiers found")
            return
        
        # Escape and create alternations
        medium_esc = [re.escape(m) for m in medium_types]
        style_esc = [re.escape(s) for s in style_modifiers]
        quality_esc = [re.escape(q) for q in quality_descriptors]
        color_esc = [re.escape(c) for c in color_modes]
        technique_esc = [re.escape(t) for t in technique_modifiers]
        presentation_esc = [re.escape(p) for p in presentation_styles]
        descriptor_esc = [re.escape(d) for d in descriptor_nouns]
        shoot_esc = [re.escape(sh) for sh in shoot_suffixes]
        
        medium_alt = '|'.join(medium_esc) if medium_esc else None
        style_alt = '|'.join(style_esc) if style_esc else None
        quality_alt = '|'.join(quality_esc) if quality_esc else None
        color_alt = '|'.join(color_esc) if color_esc else None
        technique_alt = '|'.join(technique_esc) if technique_esc else None
        presentation_alt = '|'.join(presentation_esc) if presentation_esc else None
        descriptor_alt = '|'.join(descriptor_esc) if descriptor_esc else None
        shoot_alt = '|'.join(shoot_esc) if shoot_esc else None
        connector_esc = [re.escape(c) for c in connector_verbs]
        connector_alt = '|'.join(connector_esc) if connector_esc else None
        
        # Load connectors
        articles = data.get('articles', [])
        prepositions = data.get('prepositions', [])
        ARTICLES = '|'.join([re.escape(a) for a in articles]) if articles else r'a|an|the'
        PREPS = '|'.join([re.escape(p) for p in prepositions]) if prepositions else None
        
        # Generate patterns (ordered by specificity - LONGEST/MOST SPECIFIC FIRST)
        patterns = []
        
        # Pattern 0a: [article] [quality/color] and [quality/color] [style] [medium]
        # Matches: "A highly detailed and realistic digital illustration", "A vibrant and colorful digital illustration"
        # Combines quality_descriptors and color_modes into one alternation for conjunction matching
        quality_color_alt = None
        if quality_alt and color_alt:
            quality_color_alt = f'(?:{quality_alt}|{color_alt})'
        elif quality_alt:
            quality_color_alt = quality_alt
        elif color_alt:
            quality_color_alt = color_alt
        
        if quality_color_alt and medium_alt:
            style_part = f'(?:{style_alt}\\s+)?' if style_alt else ''
            if PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{quality_color_alt})\s+and\s+(?:{quality_color_alt}\s+)?{style_part}(?:{medium_alt})(?:\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{quality_color_alt})\s+and\s+(?:{quality_color_alt}\s+)?{style_part}(?:{medium_alt})')
        
        # Pattern 0b: [article] [style] [medium] shoot [preposition] (COMPOUND PHRASE - HIGHEST PRIORITY)
        # Matches: "a digital illustration shoot", "an anime photo shoot", "digital illustration shoot about"
        # BUT NOT when followed by shot_styles markers like "from" (negative lookahead)
        if shoot_alt and style_alt and medium_alt:
            if PREPS:
                p0 = rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt}\s+)?(?:{medium_alt})\s+(?:{shoot_alt})(?!\s+from)(?:\s+(?:{PREPS}))?' 
            else:
                p0 = rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt}\s+)?(?:{medium_alt})\s+(?:{shoot_alt})(?!\s+from)'
            patterns.append(p0)
            log.debug(_LOG_PREFIX, f"Pattern 0 (first 200 chars): {p0[:200]}")
        elif shoot_alt and medium_alt:
            if PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{medium_alt})\s+(?:{shoot_alt})(?!\s+from)(?:\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{medium_alt})\s+(?:{shoot_alt})(?!\s+from)')
        
        # Pattern 0b: [article] [style] shoot [preposition] (style without medium)
        # Matches: "a photo-realistic shoot", "realistic shoot about"
        # BUT NOT when followed by "from"
        if shoot_alt and style_alt:
            if PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{shoot_alt})(?!\s+from)(?:\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{shoot_alt})(?!\s+from)')
        
        # Pattern 0c: [article] [style] [medium-derived-word] [descriptor_noun] [, connector]
        # Matches: "a digitally illustrated scene", "the digitally illustrated scene featuring", "an artistically rendered composition"
        # BUT NOT when "illustrated" is part of a different context
        # This catches medium-derived words (illustrated from illustration, rendered from render, etc.)
        if style_alt and descriptor_alt and connector_alt:
            # Build alternation of medium-derived adjectives: illustrated, rendered, painted, etc.
            medium_derived = r'(?:illustrated|rendered|painted|drawn|sketched|photographed)'
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+{medium_derived}\s+(?:{descriptor_alt})(?:,?\s+(?:{connector_alt}))?')
        elif style_alt and descriptor_alt:
            medium_derived = r'(?:illustrated|rendered|painted|drawn|sketched|photographed)'
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+{medium_derived}\s+(?:{descriptor_alt})')
        
        # Pattern 1: [article] [color_mode] [medium] [preposition]
        # Matches: "a black and white photo", "colorful digital illustration of"
        if color_alt and medium_alt:
            if PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{color_alt})\s+(?:{medium_alt})(?:\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{color_alt})\s+(?:{medium_alt})')
        
        # Pattern 2: [article] [quality] [style] [medium]
        # Matches: "a highly detailed realistic illustration", "the professional cinematic render"
        if quality_alt and style_alt and medium_alt:
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{quality_alt})\s+(?:{style_alt}\s+)?(?:{medium_alt})')
        
        # Pattern 3: [article] [quality] [medium]
        # Matches: "a detailed illustration", "highly detailed artwork"
        if quality_alt and medium_alt:
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{quality_alt})\s+(?:{medium_alt})')
        
        # Pattern 4: [article] [quality and quality] [style] [medium] in [article] [style] style [, connector] (MUST come before Pattern 5!)
        # Matches: "illustration in an anime style", "A digital illustration in a realistic style", 
        # "A highly detailed and realistic digital illustration in a semi-realistic style, featuring"
        if medium_alt and style_alt:
            # Optional quality prefix with conjunction support
            quality_prefix = ''
            if quality_color_alt:
                quality_prefix = rf'(?:(?:{quality_color_alt})\s+(?:and\s+)?(?:{quality_color_alt}\s+)?)?'
            
            if connector_alt:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?{quality_prefix}(?:{style_alt}\s+)?(?:{medium_alt})\s+in\s+(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+style(?:,?\s+(?:{connector_alt}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?{quality_prefix}(?:{style_alt}\s+)?(?:{medium_alt})\s+in\s+(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+style')
        
        # Pattern 5: [article] [style] [medium] [,] [connector] [preposition]
        # Matches: "a realistic photo", "digital illustration, depicting", "realistic illustration of"
        # BUT NOT when followed by "[article] [style] style" (that's Pattern 4)
        if style_alt and medium_alt:
            # Negative lookahead to avoid matching Pattern 4 scenarios
            not_pattern4 = rf'(?!\s+in\s+(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+style)'
            if connector_alt and PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{medium_alt})\b{not_pattern4}(?:,?\s+(?:{connector_alt}))?(?:\s+(?:{PREPS}))?')
            elif connector_alt:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{medium_alt})\b{not_pattern4}(?:,?\s+(?:{connector_alt}))?')
            elif PREPS:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{medium_alt})\b{not_pattern4}(?:\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+(?:{medium_alt})\b{not_pattern4}')
        
        # Pattern 6: [technique_modifier] (includes medium implicitly)
        # Matches: "oil painting", "digital illustration", "3d rendering", "watercolor"
        if technique_alt:
            patterns.append(rf'\b(?:{technique_alt})\b')
        
        # Pattern 7b: in [article] [style] style [, connector]
        # Matches: "in an anime style", "in a realistic style", "in an anime style, featuring"
        if style_alt:
            if connector_alt:
                patterns.append(rf'\bin\s+(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+style(?:,?\s+(?:{connector_alt}))?\b')
            else:
                patterns.append(rf'\bin\s+(?:(?:{ARTICLES})\s+)?(?:{style_alt})\s+style\b')
        
        # Pattern 8: [style] style (standalone style descriptor)
        # Matches: "anime style", "realistic style", "surreal style"
        if style_alt:
            patterns.append(rf'\b(?:{style_alt})\s+style\b')
        
        # Pattern 8b: [article] [style] [optional descriptor noun + preposition]
        # Matches: "A photo-realistic", "A photo-realistic depiction of", "the hyperrealistic portrayal of"
        # Used when style appears alone or before shot_styles patterns
        # Does NOT match when followed by medium, 'style' keyword, or hyphen (compound words)
        if style_alt and medium_alt:
            # Optional descriptor nouns that commonly follow style modifiers
            descriptor_nouns = r'(?:depiction|portrayal|rendering|representation|scene|view)'
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{style_alt})(?:\s+{descriptor_nouns}\s+(?:{PREPS}))?(?!\s+(?:{medium_alt}|style)|-)' + r'\b')
        
        # Pattern 9: standalone medium types [,] [connector] [preposition]
        # Matches: "illustration", "illustration, depicting", "photo of", "render of"
        # BUT NOT when part of hyphenated compound like "photo-realistic"
        # OR when preceded by spatial prepositions like "of the image", "in the image"
        # OR when followed by object suffixes like "picture frame", "picture book"
        # OR when preceded by object adjectives like "framed picture", "wedding picture"
        # OR when "the image/picture" is followed by descriptive verbs like "is", "shows", "features" (legitimate prose)
        if medium_alt:
            # Fixed-width lookbehinds to prevent matching in spatial contexts
            # Checks: "of ", "of a ", "of an ", "of the ", "in ", "in a ", "in an ", "in the ", "on ", "on a ", "on an ", "on the "
            spatial_lookbehind = r'(?<!of\s)(?<!of\sa\s)(?<!of\san\s)(?<!of\sthe\s)(?<!in\s)(?<!in\sa\s)(?<!in\san\s)(?<!in\sthe\s)(?<!on\s)(?<!on\sa\s)(?<!on\san\s)(?<!on\sthe\s)'
            # Negative lookbehind for object adjectives (framed picture, wedding picture, etc.)
            not_object_adj = r'(?<!framed\s)(?<!wedding\s)(?<!family\s)(?<!profile\s)'
            # Negative lookahead to prevent matching compound objects like "picture frame", "picture book"
            not_compound = r'(?!\s+(?:frame|book|gallery|window))'
            # Negative lookahead to prevent removing "the image/picture" when followed by legitimate descriptive verbs
            # Protects: "the image is set in", "the image shows", "the image features", "the image also shows"
            not_descriptive = r'(?!(?:\s+(?:is|also|shows|features|has|includes)\b))'
            if connector_alt and PREPS:
                patterns.append(rf'{spatial_lookbehind}{not_object_adj}\b(?:{medium_alt})(?!-){not_compound}{not_descriptive}(?:,?\s+(?:{connector_alt}))?(?:\s+(?:{PREPS}))?\b')
            elif connector_alt:
                patterns.append(rf'{spatial_lookbehind}{not_object_adj}\b(?:{medium_alt})(?!-){not_compound}{not_descriptive}(?:,?\s+(?:{connector_alt}))?\b')
            elif PREPS:
                patterns.append(rf'{spatial_lookbehind}{not_object_adj}\b(?:{medium_alt})(?!-){not_compound}{not_descriptive}(?:\s+(?:{PREPS}))?\b')
            else:
                patterns.append(rf'{spatial_lookbehind}{not_object_adj}\b(?:{medium_alt})(?!-){not_compound}{not_descriptive}\b')
        
        # Pattern 9: standalone presentation styles
        # Matches: "portrait", "landscape orientation", "studio"
        if presentation_alt:
            patterns.append(rf'\b(?:{presentation_alt})\b')
        
        # Combine all patterns
        if patterns:
            combined = '|'.join(patterns)
            self.compiled['image_styles'] = re.compile(rf'(?P<term>{combined})', re.I | re.U)

    def _compile_shot_styles(self) -> None:
        """Generate context-aware patterns for shot styles. Enhanced with additional combinations for better coverage."""
        data = self.raw_patterns.get('shot_styles', {})
        log.debug(_LOG_PREFIX, "Compiling shot_styles patterns...")
        if isinstance(data, list):
            # Fallback: legacy flat list
            terms_sorted = sorted(set(data), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            alternation = '|'.join(parts)
            self.compiled['shot_styles'] = re.compile(rf'\b(?P<term>(?:{alternation}))\b', re.I | re.U)
            return
        
        # Component-based structure
        shoot_prefixes = data.get('shoot_prefixes', [])  # "shoot", "shot" - high confidence
        shoot_verbs = data.get('shoot_verbs', [])  # "viewed", "captured", "taken", etc. - also used in negative lookbehinds
        simple_directions = data.get('simple_directions', [])  # "behind", "above", etc.
        prefixes = data.get('prefixes', [])  # "from", "at", "captured at", etc.
        core_terms = data.get('core_terms', [])  # camera angles, framing (safe standalone)
        directional_terms = data.get('directional_terms', [])  # ambiguous terms (need context)
        suffixes = data.get('suffixes', [])  # "shot", "view", "angle", etc.
        hyphenated_compounds = data.get('hyphenated_compounds', [])  # safe hyphenated terms
        
        if not core_terms and not directional_terms:
            return
        
        # Escape components
        shoot_prefix_esc = [re.escape(p) for p in shoot_prefixes]
        shoot_verb_esc = [re.escape(v) for v in shoot_verbs]
        simple_dir_esc = [re.escape(d) for d in simple_directions]
        prefix_esc = [re.escape(p) for p in prefixes]
        core_esc = [re.escape(t) for t in core_terms]
        directional_esc = [re.escape(t) for t in directional_terms]
        suffix_esc = [re.escape(s) for s in suffixes]
        hyphen_esc = [re.escape(h) for h in hyphenated_compounds]
        
        shoot_prefix_alt = '|'.join(shoot_prefix_esc) if shoot_prefix_esc else None
        shoot_verb_alt = '|'.join(shoot_verb_esc) if shoot_verb_esc else None
        simple_dir_alt = '|'.join(simple_dir_esc) if simple_dir_esc else None
        prefix_alt = '|'.join(prefix_esc) if prefix_esc else None
        core_alt = '|'.join(core_esc) if core_esc else None
        directional_alt = '|'.join(directional_esc) if directional_esc else None
        suffix_alt = '|'.join(suffix_esc) if suffix_esc else None
        hyphen_alt = '|'.join(hyphen_esc) if hyphen_esc else None
        
        # Combine core + directional for patterns that require prefix/suffix
        all_terms_esc = core_esc + directional_esc
        all_terms_alt = '|'.join(all_terms_esc) if all_terms_esc else None
        
        # Load connectors from JSON and convert to regex patterns
        articles = data.get('articles', [])
        prepositions = data.get('prepositions', [])
        
        # Convert to regex alternations (case-insensitive matching via re.I flag)
        ARTICLES = '|'.join([re.escape(a) for a in articles]) if articles else r'(?:A|An|The|a|an|the)'
        PREPS = '|'.join([re.escape(p) for p in prepositions]) if prepositions else None
        
        # Image connector verbs that often follow shot styles (from image_styles.json)
        # E.g., "from a low angle, depicting" - capture the trailing connector
        image_data = self.raw_patterns.get('image_styles', {})
        connector_verbs = image_data.get('connector_verbs', [])
        CONNECTORS = '|'.join([re.escape(c) for c in connector_verbs]) if connector_verbs else None
        
        # Generate patterns (ordered by specificity and frequency)
        patterns = []
        
        # Pattern 0: shoot/shot from [article] [hyphenated] [suffix+] [preposition] [, connector] (hyphenated compounds first!)
        # Matches: "shoot from a low-angle perspective", "shot from a high-angle view"
        if shoot_prefix_alt and hyphen_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:(?:\s+(?:{suffix_alt}))+)?')
        
        # Pattern 1: shoot/shot from [article] [term] [suffix+] [preposition] [, connector] (highest confidence)
        # Matches: "shoot from a low angle", "shoot from a low angle, depicting"
        if shoot_prefix_alt and all_terms_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?')
        
        # Pattern 2: [shoot_verb] from [article] [term] [suffix+] [preposition] [, connector]
        # Matches: "captured from a low angle", "captured from a low angle, depicting"
        if shoot_verb_alt and all_terms_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:(?:\s+(?:{suffix_alt}))+)?')
        
        # Pattern 2b: shoot/shot from [simple_direction] [, preposition] [, connector]
        # Matches: "shot from behind", "shoot from behind about", "shoot from the side, about", "shoot from above, depicting"
        # These patterns intentionally include the verb since it's part of the boilerplate phrase
        # Negative lookahead prevents matching when direction is part of hyphenated compound (e.g., "side-by-side")
        if shoot_prefix_alt and simple_dir_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'(?:{shoot_prefix_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)')
        
        # Pattern 2c: [shoot_verb] from [simple_direction] [, preposition] [, connector]
        # Matches: "viewed from behind", "captured from above", "taken from the side, depicting"
        # Same as 2b but for shoot_verbs (viewed, captured, etc.) instead of shoot_prefixes (shoot, shot)
        # Negative lookahead prevents matching when direction is part of hyphenated compound (e.g., "side-by-side")
        if shoot_verb_alt and simple_dir_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'(?:{shoot_verb_alt})\s+from\s+(?:{simple_dir_alt})(?!-\w)')
        
        # Pattern 3: from [simple_direction] [preposition] [, connector] (very common)
        # Matches: "from behind", "from above", "from behind, depicting"
        # BUT NOT when preceded by shoot verbs (e.g., "viewed from behind") to prevent orphaned verbs
        if simple_dir_alt:
            # Build negative lookbehind from shoot_verbs list in JSON
            if shoot_verbs:
                verb_lookbehinds = [rf'(?<!{re.escape(v)}\s)' for v in shoot_verbs]
                not_shoot_verb = ''.join(verb_lookbehinds)
            else:
                not_shoot_verb = ''
            
            # Load prepositions for trailing connector words
            shot_preps = data.get('prepositions', [])
            if shot_preps and CONNECTORS:
                preps_alt = '|'.join([re.escape(p) for p in shot_preps])
                patterns.append(rf'{not_shoot_verb}from\s+(?:{simple_dir_alt})(?:\s+(?:{preps_alt}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif shot_preps:
                preps_alt = '|'.join([re.escape(p) for p in shot_preps])
                patterns.append(rf'{not_shoot_verb}from\s+(?:{simple_dir_alt})(?:\s+(?:{preps_alt}))?')
            elif CONNECTORS:
                patterns.append(rf'{not_shoot_verb}from\s+(?:{simple_dir_alt})(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'{not_shoot_verb}from\s+(?:{simple_dir_alt})\b')
        
        # Pattern 4: from [article] [term] [suffix+] [preposition] [, connector] (dominant pattern)
        # Matches: "from a low angle", "from a low angle, depicting", "from a frontal camera angle about"
        if all_terms_alt and suffix_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 5: in [article] [term] [suffix+] [preposition] [, connector]
        # Matches: "in a close-up shot", "in an overhead camera angle, depicting"
        if all_terms_alt and suffix_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'in\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'in\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'in\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'in\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 6: [term] [suffix+] of
        # Matches: "close-up shot of", "overhead camera angle of", "side angle of"
        if all_terms_alt and suffix_alt:
            patterns.append(rf'(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+\s+of\b')
        
        # Pattern 6b: from [article] [term] camera [suffix+] [preposition]
        # Matches: "from a frontal camera angle", "from the side camera view about"
        if all_terms_alt and suffix_alt:
            if PREPS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})\s+camera(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{PREPS}))?')
            else:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})\s+camera(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 7: [article] [term] camera [suffix+]
        # Matches: "a low camera angle", "the side camera view"
        if directional_alt and suffix_alt:
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{directional_alt})\s+camera(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 7b: from [article] [hyphenated] [suffix+] [preposition] [, connector]
        # Matches: "from a top-down perspective", "from a bird's-eye view, depicting"
        if hyphen_alt and suffix_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 8: [prefix (excluding 'from')] [article] [term]
        # Matches: "at a low angle", "about a scene" but NOT "from" (handled by Patterns 1-7b)
        if prefix_alt and all_terms_alt:
            # Filter out "from" since it has specific patterns above
            prefixes_no_from = [p for p in data.get('prefixes', []) if p.lower() != 'from']
            if prefixes_no_from:
                prefix_no_from_esc = [re.escape(p) for p in prefixes_no_from]
                prefix_no_from_alt = '|'.join(prefix_no_from_esc)
                # Require article for generic prefixes
                patterns.append(rf'(?:{prefix_no_from_alt})\s+(?:(?:{ARTICLES})\s+)(?:{all_terms_alt})')
            # Add specific safe standalone combos like "at eye level"
            safe_at_combos = ['eye level', 'ground level']
            if any(term in core_terms for term in safe_at_combos):
                safe_esc = [re.escape(t) for t in safe_at_combos if t in core_terms]
                safe_alt = '|'.join(safe_esc)
                patterns.append(rf'at\s+(?:{safe_alt})\b')
        
        # Pattern 9: from [article] [term] [suffix+] [preposition] [, connector] (general fallback for 'from' patterns)
        # Matches: "from a portrait angle about", "from a camera angle, depicting"  
        if all_terms_alt and suffix_alt:
            if PREPS and CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:\s+(?:{PREPS}))?(?:,?\s+(?:{CONNECTORS}))?')
            elif PREPS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:\s+(?:{PREPS}))?')
            elif CONNECTORS:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+(?:,?\s+(?:{CONNECTORS}))?')
            else:
                patterns.append(rf'from\s+(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 10: [article] [term] [suffix+] (standalone, no prefix - only matches when not preceded by 'from')
        # Matches: "close-up shot", "high camera angle", "portrait shot" but NOT "from a portrait angle"
        if all_terms_alt and suffix_alt:
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{all_terms_alt})(?:\s+(?:{suffix_alt}))+')
        
        # Pattern 11: Hyphenated compounds (safe anywhere)
        # Matches: "close-up", "bird's-eye", "full-body", optionally with article "A close-up"
        if hyphen_alt:
            patterns.append(rf'(?:(?:{ARTICLES})\s+)?(?:{hyphen_alt})\b')
        
        # Pattern 12: Standalone core at sentence start
        # Matches: "Close-up", "Overhead" but only at sentence boundaries
        if core_alt:
            patterns.append(rf'(?:^|(?<=\. ))(?:{core_alt})\b')
        
        # Combine all patterns
        if patterns:
            combined = '|'.join(patterns)
            self.compiled['shot_styles'] = re.compile(rf'(?P<term>{combined})', re.I | re.U)
            log.debug(_LOG_PREFIX, f"Compiled shot_styles with {len(patterns)} patterns")
            for i, p in enumerate(patterns, 1):
                log.debug(_LOG_PREFIX, f"  Pattern {i}: {p}")

    def _compile_backgrounds(self) -> None:
        """Generate context-aware patterns for backgrounds. Optimized for 7,616 real-world mentions."""
        data = self.raw_patterns.get('backgrounds', {})
        patterns = []  # Initialize early to avoid UnboundLocalError
        log.debug(_LOG_PREFIX, "Compiling backgrounds patterns...")
        
        if isinstance(data, list):
            # Fallback: legacy flat list
            terms_sorted = sorted(set(data), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            alternation = '|'.join(parts)
            self.compiled['backgrounds'] = re.compile(rf'\b(?P<term>(?:{alternation}))\b', re.I | re.U)
            return
        
        # Component-based structure
        lighting = data.get('lighting_descriptors', [])
        indoor = data.get('indoor_locations', [])
        outdoor = data.get('outdoor_locations', [])
        natural = data.get('natural_elements', [])
        architectural = data.get('architectural', [])
        modifiers = data.get('background_modifiers', [])
        indicators = data.get('background_indicators', [])
        indoor_outdoor = data.get('indoor_outdoor', [])
        
        # Combine all locations
        all_locations = indoor + outdoor
        
        if not all_locations and not indicators:
            return
        
        # Escape and create alternations
        lighting_esc = [re.escape(l) for l in lighting]
        location_esc = [re.escape(loc) for loc in all_locations]
        natural_esc = [re.escape(n) for n in natural]
        arch_esc = [re.escape(a) for a in architectural]
        modifier_esc = [re.escape(m) for m in modifiers]
        indicator_esc = [re.escape(i) for i in indicators]
        indoor_outdoor_esc = [re.escape(io) for io in indoor_outdoor]
        
        lighting_alt = '|'.join(lighting_esc) if lighting_esc else None
        location_alt = '|'.join(location_esc) if location_esc else None
        natural_alt = '|'.join(natural_esc) if natural_esc else None
        arch_alt = '|'.join(arch_esc) if arch_esc else None
        modifier_alt = '|'.join(modifier_esc) if modifier_esc else None
        indicator_alt = '|'.join(indicator_esc) if indicator_esc else None
        indoor_outdoor_alt = '|'.join(indoor_outdoor_esc) if indoor_outdoor_esc else None
        
        # Load connectors
        articles = data.get('articles', [])
        ARTICLES = '|'.join([re.escape(a) for a in articles]) if articles else r'(?:a|an|the)'
        
        # Generate patterns (ordered by specificity)
        patterns = []
        
        # Pattern 1: "background:" or "the background is/features/shows [description]"
        # Matches: "background: soft gradient", "the background is blurred"
        if indicator_alt:
            patterns.append(rf'(?:{indicator_alt})[:\s]+(?:is\s+|features\s+|shows\s+)?[\w\s,]+')
            patterns.append(rf'the\s+(?:{indicator_alt})\s+(?:is|features|shows)\s+[\w\s,]+')
        
        # Pattern 2: in [article] [lighting] [location]
        # Matches: "in a dimly lit room", "in the brightly lit studio"
        if lighting_alt and location_alt:
            patterns.append(rf'in\s+(?:{ARTICLES}\s+)?(?:{lighting_alt})\s+(?:{location_alt})')
        
        # Pattern 3: in [article] [location]
        # Matches: "in a bedroom", "in the forest"
        if location_alt:
            patterns.append(rf'in\s+(?:{ARTICLES}\s+)?(?:{location_alt})')
        
        # Pattern 4: against [article] [modifier] background OR against [article] background
        # Matches: "against a plain background", "against the blurred backdrop", "against a background"
        if indicator_alt:
            if modifier_alt:
                patterns.append(rf'against\s+(?:{ARTICLES}\s+)?(?:(?:{modifier_alt})\s+)?(?:{indicator_alt})')
            else:
                patterns.append(rf'against\s+(?:{ARTICLES}\s+)?(?:{indicator_alt})')
        
        # Pattern 5: set in [article] [location]
        # Matches: "set in a forest", "set in the city"
        if location_alt:
            patterns.append(rf'set\s+in\s+(?:{ARTICLES}\s+)?(?:{location_alt})')
        
        # Pattern 6: surrounded by [description]
        # Matches: "surrounded by flowers", "surrounded by trees"
        if natural_alt:
            patterns.append(rf'surrounded\s+by\s+(?:{ARTICLES}\s+)?(?:{natural_alt})')
        
        # Pattern 7: [indoor/outdoor] (setting|scene|location)
        # Matches: "outdoor setting", "indoor scene"
        if indoor_outdoor_alt:
            patterns.append(rf'\b(?:{indoor_outdoor_alt})(?:\s+(?:setting|scene|location))?\b')
        
        # Pattern 8: Standalone locations
        # Matches: "bedroom", "forest", "beach"
        if location_alt:
            patterns.append(rf'\b(?:{location_alt})\b')
        
        # Combine all patterns
        if patterns:
            combined = '|'.join(patterns)
            self.compiled['backgrounds'] = re.compile(rf'(?P<term>{combined})', re.I | re.U)

    def _compile_moods(self) -> None:
        """Generate context-aware patterns for moods. Split into subject expressions (keep) and atmosphere (remove)."""
        data = self.raw_patterns.get('moods', {})
        patterns = []  # Initialize early to avoid UnboundLocalError
        all_patterns = []  # Initialize early to avoid UnboundLocalError
        log.debug(_LOG_PREFIX, "Compiling moods patterns (subject_moods + atmosphere_moods)...")
        
        if isinstance(data, list):
            # Fallback: legacy flat list - treat all as atmosphere moods
            terms_sorted = sorted(set(data), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            alternation = '|'.join(parts)
            self.compiled['moods'] = re.compile(rf'\b(?P<term>(?:{alternation}))\b', re.I | re.U)
            self.compiled['subject_moods'] = re.compile(r'(?!)', re.I | re.U)  # Never matches
            self.compiled['atmosphere_moods'] = self.compiled['moods']
            return
        
        # Component-based structure with subject_moods (keep) and atmosphere_moods (remove)
        
        # 1. Compile SUBJECT MOODS (emotions/expressions of the person - KEEP for neutral prompts)
        subject_data = data.get('subject_moods', {})
        subject_moods = []
        
        if isinstance(subject_data, dict):
            for category_list in subject_data.values():
                if isinstance(category_list, list):
                    subject_moods.extend(category_list)
                elif category_list != subject_data.get('description'):  # Skip description field
                    continue
        
        if subject_moods:
            subject_esc = [re.escape(m) for m in sorted(set(subject_moods), key=lambda s: -len(s))]
            subject_alt = '|'.join(subject_esc)
            # Subject moods are simpler - just detect the adjectives/expressions
            # Pattern: standalone expressions with word boundaries (e.g., "smiling", "happy", "sad")
            self.compiled['subject_moods'] = re.compile(rf'\b(?P<term>{subject_alt})\b', re.I | re.U)
        else:
            self.compiled['subject_moods'] = re.compile(r'(?!)', re.I | re.U)  # Never matches
        
        # 2. Compile ATMOSPHERE MOODS (image/scene mood - REMOVE for neutral prompts)
        atmosphere_data = data.get('atmosphere_moods', {})
        atmosphere_moods = []
        
        if isinstance(atmosphere_data, dict):
            for category_list in atmosphere_data.values():
                if isinstance(category_list, list):
                    atmosphere_moods.extend(category_list)
                elif category_list != atmosphere_data.get('description'):  # Skip description field
                    continue
        
        # Get mood indicators and modifiers
        indicators = data.get('mood_indicators', [])
        intensity = data.get('intensity_modifiers', [])
        
        if not atmosphere_moods:
            self.compiled['atmosphere_moods'] = re.compile(r'(?!)', re.I | re.U)  # Never matches
            self.compiled['moods'] = self.compiled['subject_moods']  # Fallback to subject_moods only
            return
        
        # Escape and create alternations
        atmo_esc = [re.escape(m) for m in sorted(set(atmosphere_moods), key=lambda s: -len(s))]
        atmo_alt = '|'.join(atmo_esc)
        
        indicator_esc = [re.escape(i) for i in indicators]
        indicator_alt = '|'.join(indicator_esc) if indicator_esc else None
        
        intensity_esc = [re.escape(i) for i in intensity]
        intensity_alt = '|'.join(intensity_esc) if intensity_esc else None
        
        # Load connectors
        articles = data.get('articles', [])
        ARTICLES = '|'.join([re.escape(a) for a in articles]) if articles else r'(?:a|an|the)'
        
        # Generate patterns for atmosphere moods (ordered by specificity)
        patterns = []
        
        # Pattern 1: "(mood|atmosphere|vibe):" or "the mood/atmosphere is [adjective]"
        # Matches: "mood: dramatic", "the atmosphere is peaceful"
        if indicator_alt and atmo_alt:
            patterns.append(rf'(?:{indicator_alt})[:\s]+(?:{atmo_alt})')
            patterns.append(rf'the\s+(?:{indicator_alt})\s+is\s+(?:{intensity_alt}\s+)?(?:{atmo_alt})')
        
        # Pattern 2: [article] [atmosphere] (mood|atmosphere|vibe)
        # Matches: "a dramatic mood", "an intimate atmosphere"
        if indicator_alt and atmo_alt:
            patterns.append(rf'(?:{ARTICLES}\s+)?(?:{intensity_alt}\s+)?(?:{atmo_alt})\s+(?:{indicator_alt})')
        
        # Pattern 3: Standalone atmosphere adjectives
        # Matches: "dramatic", "peaceful", "ethereal" (word boundaries)
        if atmo_alt:
            patterns.append(rf'\b(?:{atmo_alt})\b')
        
        # Combine atmosphere patterns
        if patterns:
            combined = '|'.join(patterns)
            self.compiled['atmosphere_moods'] = re.compile(rf'(?P<term>{combined})', re.I | re.U)
        else:
            self.compiled['atmosphere_moods'] = re.compile(r'(?!)', re.I | re.U)  # Never matches
        
        # For backward compatibility: 'moods' combines both (but removal should use atmosphere_moods only)
        all_moods = subject_moods + atmosphere_moods
        if all_moods:
            all_esc = [re.escape(m) for m in sorted(set(all_moods), key=lambda s: -len(s))]
            all_alt = '|'.join(all_esc)
            # Use same pattern structure as atmosphere for consistency
            all_patterns = []
            if indicator_alt:
                all_patterns.append(rf'(?:{indicator_alt})[:\s]+(?:{all_alt})')
                all_patterns.append(rf'the\s+(?:{indicator_alt})\s+is\s+(?:{intensity_alt}\s+)?(?:{all_alt})')
                all_patterns.append(rf'(?:{ARTICLES}\s+)?(?:{intensity_alt}\s+)?(?:{all_alt})\s+(?:{indicator_alt})')
            all_patterns.append(rf'\b(?:{all_alt})\b')
            combined_all = '|'.join(all_patterns)
            self.compiled['moods'] = re.compile(rf'(?P<term>{combined_all})', re.I | re.U)
        else:
            self.compiled['moods'] = re.compile(r'(?!)', re.I | re.U)  # Never matches

    def _compile_detectors(self) -> None:
        """Compile a pattern for each category into self.compiled"""
        log.debug(_LOG_PREFIX, "Compiling simple category patterns...")
        # First compile simple categories (alternations)
        # Categories where we want strict word-boundary matching to avoid partial hits
        WORD_BOUND_CATEGORIES = {
            'subjects', 'relationship_roles', 'age_indicators',
            'shot_styles', 'technical_tags', 'tags', 'backgrounds', 'moods',
            'professional_roles'
        }

        simple_categories_compiled = 0
        for category, terms in self.raw_patterns.items():
            if not terms:
                continue
            # We'll treat a few categories specially below
            if category in ('prose_triggers', 'instruction_prefixes', 'image_styles', 'subjects', 'shot_styles', 'backgrounds', 'moods'):
                continue
            # sort by length to prefer longer matches first
            terms_sorted = sorted(set(terms), key=lambda s: -len(s))
            parts = [self._term_to_pattern(t) for t in terms_sorted]
            # Join as alternation
            alternation = '|'.join(parts)

            # Use word-boundary anchors for sensitive categories to avoid partial matches
            if category in WORD_BOUND_CATEGORIES:
                pattern = rf'(?P<term>\b(?:{alternation})\b)'
            else:
                # permissive group (no strict \b) for symbols like © or multi-token phrases
                pattern = rf'(?P<term>(?:{alternation}))'

            try:
                self.compiled[category] = re.compile(pattern, re.I | re.U)
                simple_categories_compiled += 1
            except re.error:
                # fallback to joining escaped terms (safe)
                safe_parts = [re.escape(t) for t in terms_sorted]
                alternation = '|'.join(safe_parts)
                if category in WORD_BOUND_CATEGORIES:
                    pattern = rf'(?P<term>\b(?:{alternation})\b)'
                else:
                    pattern = rf'(?P<term>(?:{alternation}))'
                self.compiled[category] = re.compile(pattern, re.I | re.U)
                simple_categories_compiled += 1
        
        log.debug(_LOG_PREFIX, f"Compiled {simple_categories_compiled} simple category patterns")
        log.debug(_LOG_PREFIX, "Compiling special component-based patterns...")
        
        # Special: compile component-based patterns
        self._compile_subjects()
        self._compile_image_styles()
        self._compile_shot_styles()
        self._compile_backgrounds()
        self._compile_moods()
        
        # Special: compile instruction_prefixes as anchored alternatives (start-of-line prefixes)
        ip = self.raw_patterns.get('instruction_prefixes', [])
        if ip:
            ip_parts = [self._term_to_pattern(t) for t in sorted(set(ip), key=lambda s: -len(s))]
            ip_alt = '|'.join(ip_parts)
            try:
                self.compiled['instruction_prefixes'] = re.compile(rf'^(?:\s*(?:{ip_alt}))', re.I | re.U)
            except re.error:
                self.compiled['instruction_prefixes'] = re.compile(rf'^(?:\s*(?:{re.escape(ip[0])}))', re.I | re.U)

        # Special: compile prose detector using subject terms + trigger verbs
        triggers = self.raw_patterns.get('prose_triggers', [])
        subjects_data = self.raw_patterns.get('subjects', [])
        
        # Extract subject terms from component-based structure if needed
        subject_terms = []
        if isinstance(subjects_data, dict):
            # Component-based structure - extract core_subjects
            core_subjects = subjects_data.get('core_subjects', {})
            if isinstance(core_subjects, dict):
                for category_list in core_subjects.values():
                    if isinstance(category_list, list):
                        subject_terms.extend(category_list)
        elif isinstance(subjects_data, list):
            # Already a flat list
            subject_terms = subjects_data
        
        if triggers and subject_terms:
            # create alternations (limit term lengths)
            trig_parts = [self._term_to_pattern(t) for t in sorted(set(triggers), key=lambda s: -len(s))]
            subj_parts = [self._term_to_pattern(t) for t in sorted(set(subject_terms), key=lambda s: -len(s))]
            trig_alt = '|'.join(trig_parts)
            subj_alt = '|'.join(subj_parts)
            # Match subject (or pronouns) then optional small phrase and a trigger verb
            prose_pattern = rf'(?:(?:\b(?:{subj_alt})\b|\b(?:she|he|they|the subject|the character)\b)(?:[\s\w\-\'"\(\)]{{0,40}})?\b(?:{trig_alt})\b)'
            try:
                self.compiled['prose'] = re.compile(prose_pattern, re.I | re.U)
            except re.error:
                # fallback to simple trigger-only detector
                self.compiled['prose'] = re.compile('|'.join(trig_parts), re.I | re.U)

    def detect(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Detect pattern matches in text.

        Returns list of dicts: {category, text, span, score}
        """
        if not text:
            return []
        results: List[Dict[str, Any]] = []
        cats = categories or list(self.compiled.keys())
        log.debug(_LOG_PREFIX, f"Detecting patterns in {len(text)} chars for categories: {cats if categories else 'all'}")
        
        for c in cats:
            pat = self.compiled.get(c)
            if not pat:
                log.debug(_LOG_PREFIX, f"  {c}: no compiled pattern available")
                continue
            
            category_matches = []
            for m in pat.finditer(text):
                # Some special detectors may not define a named group 'term'
                try:
                    matched_text = m.group('term')
                    start, end = m.span('term')
                except IndexError:
                    matched_text = m.group(0)
                    start, end = m.span(0)
                score = self._score_match(matched_text)
                
                match_info = {
                    'category': c,
                    'text': matched_text,
                    'span': (start, end),
                    'score': score,
                }
                category_matches.append(match_info)
                results.append(match_info)
            
            # Log results for this category
            if category_matches:
                sample_texts = [m['text'] for m in category_matches[:3]]  # First 3 matches
                log.debug(_LOG_PREFIX, f"  {c}: found {len(category_matches)} matches (samples: {sample_texts})")
            else:
                log.debug(_LOG_PREFIX, f"  {c}: found 0 matches")
        
        # sort by start
        results.sort(key=lambda r: r['span'][0])
        return results

    def _score_match(self, matched: str) -> int:
        # simple heuristic: longer matches or multi-word phrases get higher score
        words = re.findall(r"\w+", matched)
        score = len(words)
        if score >= 2:
            score += 1
        return score

    def remove_matches(self, text: str, matches: List[Dict[str, Any]], preserve_categories: Optional[List[str]] = None) -> str:
        """Remove spans specified in matches from text and clean leftover punctuation.

        For certain categories (like image prefixes), attempt to include preceding adjective
        tokens from tag/technical lists to remove phrases like 'digital illustration' rather
        than only 'illustration' which can leave dangling adjectives.
        
        Args:
            text: The input text
            matches: List of match dicts with 'span', 'text', 'category' keys
            preserve_categories: Optional list of category names to preserve even if they overlap
                                 with matches to be removed. Useful when "shoot" appears in both
                                 image_styles and shot_styles - if preserve_categories=['shot_styles'],
                                 overlapping shot_style patterns will be kept.
        
        Returns:
            Text with matches removed and overlapping preserved categories retained.
        """
        if not matches:
            return text
        
        log.debug(_LOG_PREFIX, f"remove_matches called with {len(matches)} matches to remove")
        # Log what's being removed
        removal_samples = [f"{m['category']}:'{m['text']}'" for m in matches[:3]]
        log.debug(_LOG_PREFIX, f"  Removal samples: {removal_samples}")
        
        # If preserve_categories specified, re-detect those patterns to protect them
        preserve_spans = []
        if preserve_categories:
            log.debug(_LOG_PREFIX, f"Smart overlap handling: preserving categories {preserve_categories}")
            for cat in preserve_categories:
                preserved_matches = self.detect(text, categories=[cat])
                for pm in preserved_matches:
                    preserve_spans.append(pm['span'])
            log.debug(_LOG_PREFIX, f"Found {len(preserve_spans)} preserve spans for protection")
        
        s = text
        # Build prefix candidate set (lowercased words) from technical_tags and tags
        prefix_terms = set()
        for key in ('technical_tags', 'tags'):
            for t in self.raw_patterns.get(key, []):
                for w in re.findall(r"[A-Za-z'-]+", t):
                    prefix_terms.add(w.lower())
        
        # Calculate final removal spans (with expansion) and de-duplicate overlaps
        removal_spans = []
        expanded_count = 0
        for m in matches:
            start, end = m['span']
            original_start = start
            start = max(0, min(len(text), start))
            end = max(0, min(len(text), end))
            
            # Expand start backwards for image_styles to include preceding adjective words
            if m.get('category') == 'image_styles':
                # Check if match already starts with article/quality/style words (e.g., Pattern 0a conjunction matches)
                # These patterns already include quality/color words, so no expansion needed
                matched_text = text[start:end]
                starts_with_article = re.match(r'^(?:a|an|the)\s+', matched_text, re.IGNORECASE)
                has_conjunction = ' and ' in matched_text or ' or ' in matched_text
                
                # Skip expansion if match already has article + conjunction (Pattern 0a style matches)
                if not (starts_with_article and has_conjunction):
                    # Get quality adjectives from patterns
                    quality_terms = self.raw_patterns.get('image_styles', {}).get('quality_descriptors', [])
                    style_terms = self.raw_patterns.get('image_styles', {}).get('style_modifiers', [])
                    color_terms = self.raw_patterns.get('image_styles', {}).get('color_modes', [])
                    
                    # Build word sets from multi-word terms (e.g., "highly detailed" → ["highly", "detailed"])
                    quality_words = set()
                    for term in quality_terms:
                        for word in re.findall(r"[A-Za-z'-]+", term):
                            quality_words.add(word.lower())
                    
                    style_words = set()
                    for term in style_terms:
                        for word in re.findall(r"[A-Za-z'-]+", term):
                            style_words.add(word.lower())
                    
                    color_words = set()
                    for term in color_terms:
                        for word in re.findall(r"[A-Za-z'-]+", term):
                            color_words.add(word.lower())
                    
                    # Common adverbs that modify quality adjectives
                    adverbs = {'highly', 'very', 'extremely', 'incredibly', 'beautifully', 'stunningly'}
                    
                    # find all preceding adjective words and article
                    prefix_text = text[:start]
                    words = re.findall(r"[A-Za-z'-]+", prefix_text)
                    if words:
                        # Collect all quality adjectives and style modifiers immediately before the match
                        to_take = []
                        for w in reversed(words[-10:]):  # Look back up to 10 words
                            w_lower = w.lower()
                            # Include hyphenated style adjectives (e.g., "anime-style", "fantasy-themed")
                            is_style_adjective = '-' in w and w_lower.endswith(('style', 'styled', 'themed'))
                            # Include quality words, style words, color words, adverbs, conjunctions, and articles
                            if (w_lower in quality_words or w_lower in style_words or w_lower in color_words or 
                                w_lower in adverbs or w_lower in ('and', 'or', 'a', 'an', 'the') or is_style_adjective):
                                to_take.insert(0, w)
                            else:
                                # Stop at first non-image-descriptor word
                                break
                        
                        if to_take:
                            # Compute new start by finding the span of the taken words
                            # Use [\s,]+ to handle commas between adjectives (e.g., "detailed, realistic")
                            patt = r'(?:' + r'[\s,]+'.join([re.escape(x) for x in to_take]) + r')[\s,]*$'
                            m_pre = re.search(patt, prefix_text, re.IGNORECASE)
                            if m_pre:
                                start = m_pre.start()
                                if start != original_start:
                                    expanded_count += 1
            
            removal_spans.append((start, end))
        
        if expanded_count > 0:
            log.debug(_LOG_PREFIX, f"Expanded {expanded_count} image_styles spans to include preceding adjectives")
        
        # De-duplicate overlapping spans by merging them
        if removal_spans:
            removal_spans.sort()
            merged = [removal_spans[0]]
            for current_start, current_end in removal_spans[1:]:
                last_start, last_end = merged[-1]
                # If current overlaps with last, merge them
                if current_start <= last_end:
                    merged[-1] = (last_start, max(last_end, current_end))
                else:
                    merged.append((current_start, current_end))
            removal_spans = merged
        
        # Subtract preserved category spans from removal spans
        # BUT: Only preserve spans that extend BEYOND removal spans
        # Don't preserve spans completely contained within removal spans (e.g., "vibrant" inside "A vibrant and colorful illustration")
        if preserve_spans and removal_spans:
            # Filter out preserve spans completely contained within any removal span
            filtered_preserve_spans = []
            for pres_start, pres_end in preserve_spans:
                is_contained = False
                for rem_start, rem_end in removal_spans:
                    # Check if preserve span is completely contained within removal span
                    if rem_start <= pres_start and pres_end <= rem_end:
                        is_contained = True
                        break
                if not is_contained:
                    filtered_preserve_spans.append((pres_start, pres_end))
            
            log.debug(_LOG_PREFIX, f"Filtered preserve spans: {len(preserve_spans)} → {len(filtered_preserve_spans)} (removed {len(preserve_spans) - len(filtered_preserve_spans)} contained spans)")
            preserve_spans = filtered_preserve_spans
            
            adjusted_removals = []
            for rem_start, rem_end in removal_spans:
                # Check if this removal span overlaps with any preserved span
                fragments = [(rem_start, rem_end)]  # Start with full span
                
                for pres_start, pres_end in preserve_spans:
                    # Check each fragment for overlap with this preserved span
                    new_fragments = []
                    for frag_start, frag_end in fragments:
                        # No overlap - keep fragment as-is
                        if frag_end <= pres_start or frag_start >= pres_end:
                            new_fragments.append((frag_start, frag_end))
                        # Preserved span completely covers this fragment - remove it
                        elif pres_start <= frag_start and pres_end >= frag_end:
                            pass  # Fragment removed
                        # Preserved span overlaps start of fragment
                        elif pres_start <= frag_start < pres_end < frag_end:
                            new_fragments.append((pres_end, frag_end))
                        # Preserved span overlaps end of fragment
                        elif frag_start < pres_start < frag_end <= pres_end:
                            new_fragments.append((frag_start, pres_start))
                        # Preserved span is in middle of fragment - split it
                        elif frag_start < pres_start and pres_end < frag_end:
                            new_fragments.append((frag_start, pres_start))
                            new_fragments.append((pres_end, frag_end))
                    fragments = new_fragments
                
                # Add remaining fragments to adjusted removals
                adjusted_removals.extend(fragments)
            
            removal_spans = adjusted_removals
        
        # Sort by start descending and remove
        removal_spans.sort(reverse=True)
        original_len = len(s)
        removed_chars = 0
        for start, end in removal_spans:
            removed_chars += (end - start)
            s = s[:start] + s[end:]
        
        log.debug(_LOG_PREFIX, f"Removed {removed_chars} chars from {original_len} char text ({len(removal_spans)} spans)")
        
        # Clean up double punctuation and whitespace
        s = re.sub(r"\s{2,}", " ", s)
        s = re.sub(r"\s*,\s*", ", ", s)
        s = re.sub(r",\s*\.", ".", s)  # Comma before period
        s = re.sub(r"(^[,;\s]+)|([,;\s]+$)", "", s)
        
        # Grammar fixes for orphaned articles and prepositions after removal
        s = re.sub(r'\b(a|an|the)\s+of\s+(a|an|the)\b', r'of \2', s, flags=re.IGNORECASE)  # "a of a" → "of a"
        s = re.sub(r'\b(and|or)\s+of\s+(a|an|the)\b', r'of \2', s, flags=re.IGNORECASE)  # "and of a" → "of a"
        
        # Remove orphaned prepositions/conjunctions only when followed by article + word pattern
        # This catches "of a woman", "about the man" but keeps "With her hand raised"
        s = re.sub(r'^(?:of|about|and|or)\s+(?=(?:a|an|the)\s+\w+)', '', s, flags=re.IGNORECASE)
        
        # Remove other orphaned leading words only if they don't start valid phrases
        # "in a" at start is usually orphaned, but "In the distance" is valid - be conservative
        s = re.sub(r'^(?:in|with|at)\s+(?=(?:a|an)\s+\w+)', '', s, flags=re.IGNORECASE)
        
        # Clean up duplicate articles (a a, an an, the the)
        s = re.sub(r'\b(a|an|the)\s+\1\b', r'\1', s, flags=re.I)
        s = s.strip()
        return s

    def soften_matches(self, text: str, matches: List[Dict[str, Any]], soften_map: Dict[str, str]) -> str:
        """Replace matched spans using soften_map (keys are lower-cased terms)."""
        if not matches:
            return text
        
        log.debug(_LOG_PREFIX, f"soften_matches called with {len(matches)} matches")
        # Log what's being softened
        soften_samples = []
        for m in matches[:3]:
            key = m['text'].lower().strip()
            replacement = soften_map.get(key, '')
            soften_samples.append(f"{m['category']}:'{m['text']}'→'{replacement}'")
        log.debug(_LOG_PREFIX, f"  Softening samples: {soften_samples}")
        
        s = text
        # Replace from back to front to preserve spans
        ordered = sorted(matches, key=lambda m: m['span'][0], reverse=True)
        replacements_made = 0
        for m in ordered:
            start, end = m['span']
            key = m['text'].lower().strip()
            replacement = soften_map.get(key, '')
            if replacement or key in soften_map:  # Count even empty replacements
                replacements_made += 1
            s = s[:start] + replacement + s[end:]
        
        log.debug(_LOG_PREFIX, f"Made {replacements_made} soften replacements")
        
        # Cleanup whitespace and punctuation
        s = re.sub(r'\s+', ' ', s)  # Multiple spaces → single
        s = re.sub(r'\s+([,.;:])', r'\1', s)  # Space before punctuation
        s = re.sub(r',\s*,', ',', s)  # Double commas
        s = re.sub(r'\.\s*\.', '.', s)  # Double periods
        s = re.sub(r',\s*\.', '.', s)  # Comma before period
        
        # Grammar fixes for broken constructions after NSFW removal
        s = re.sub(r'\b(with|of|in|at|on|by|for|from|to)\s+(showing|depicting|featuring)\b', r'\2', s, flags=re.IGNORECASE)  # "with showing" → "showing"
        s = re.sub(r'\b(with|of|in|at|on|by|for|from|to)\s+(and|or)\b', r'\2', s, flags=re.IGNORECASE)  # "with and" → "and"
        s = re.sub(r'\b(a|an|the)\s+(and|or|but)\b', r'\2', s, flags=re.IGNORECASE)  # "a and" → "and"
        s = re.sub(r'\b(and|or)\s+\1\b', r'\1', s, flags=re.IGNORECASE)  # "and and" → "and"
        s = re.sub(r"'s\s+(and|or)\s+(\w+)(?!\w)", r"'s \2", s)  # "woman's and ass" → "woman's ass"
        s = re.sub(r'\b(and|or)\s+([,.;:])', r'\2', s)  # "and ," → ","
        s = re.sub(r',\s+(and|or)\s*([,.;:]|$)', r'\2', s)  # ", and," or ", and." → "."
        s = re.sub(r'\b(\w+)\s+and\s+\1\b', r'\1', s, flags=re.IGNORECASE)  # "clothing and clothing" → "clothing"
        s = re.sub(r'\b(\w+)\s+or\s+\1\b', r'\1', s, flags=re.IGNORECASE)  # "alluring or alluring" → "alluring"
        s = re.sub(r'\s+(and|or)\s+(\w+),', r' \2,', s)  # "scene and penetration," → "scene penetration,"
        s = re.sub(r'\s+(and|or)\s+(?=\w+\s*[,.])', r' ', s)  # Remove orphaned conjunctions before end punctuation
        
        s = s.strip()
        return s

    def export_debug(self, path: str, data: Any) -> None:
        dirpath = os.path.dirname(path)
        os.makedirs(dirpath, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)


# Simple singleton convenience
_default_processor: Optional[SmartTextProcessor] = None
_pattern_file_mtimes: Dict[str, float] = {}


def get_default_processor() -> SmartTextProcessor:
    global _default_processor
    if _default_processor is None:
        log.debug(_LOG_PREFIX, "Creating default processor (first access)")
        _default_processor = SmartTextProcessor()
        _cache_pattern_mtimes(_default_processor.patterns_dir)
    else:
        # Check if pattern files have changed
        if _patterns_have_changed(_default_processor.patterns_dir):
            log.debug(_LOG_PREFIX, "Pattern files changed, reloading processor")
            _default_processor = SmartTextProcessor()
            _cache_pattern_mtimes(_default_processor.patterns_dir)
    return _default_processor


def invalidate_processor() -> None:
    """Force reload of pattern processor on next access."""
    global _default_processor, _pattern_file_mtimes
    log.debug(_LOG_PREFIX, "Invalidating processor cache - will reload on next access")
    _default_processor = None
    _pattern_file_mtimes.clear()


def _cache_pattern_mtimes(patterns_dir: str) -> None:
    """Cache modification times of all pattern files."""
    global _pattern_file_mtimes
    _pattern_file_mtimes.clear()
    
    index_path = os.path.join(patterns_dir, 'index.json')
    if os.path.exists(index_path):
        _pattern_file_mtimes[index_path] = os.path.getmtime(index_path)
        
        # Read index and cache mtimes of all pattern files
        try:
            with open(index_path, 'r', encoding='utf-8') as fh:
                index_data = json.load(fh)
            files = index_data.get('files', {})
            for fname in files.values():
                pattern_file = os.path.join(patterns_dir, fname)
                if os.path.exists(pattern_file):
                    _pattern_file_mtimes[pattern_file] = os.path.getmtime(pattern_file)
        except Exception:
            pass


def _patterns_have_changed(patterns_dir: str) -> bool:
    """Check if any pattern files have been modified."""
    global _pattern_file_mtimes
    
    index_path = os.path.join(patterns_dir, 'index.json')
    if not os.path.exists(index_path):
        return False
    
    # Check index.json mtime
    if index_path in _pattern_file_mtimes:
        if os.path.getmtime(index_path) != _pattern_file_mtimes[index_path]:
            return True
    else:
        return True
    
    # Check all pattern files
    try:
        with open(index_path, 'r', encoding='utf-8') as fh:
            index_data = json.load(fh)
        files = index_data.get('files', {})
        for fname in files.values():
            pattern_file = os.path.join(patterns_dir, fname)
            if os.path.exists(pattern_file):
                cached_mtime = _pattern_file_mtimes.get(pattern_file)
                current_mtime = os.path.getmtime(pattern_file)
                if cached_mtime is None or current_mtime != cached_mtime:
                    return True
    except Exception:
        return False
    
    return False

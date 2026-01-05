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
from ..core.regex_helper import is_tags_format, smart_phrase_removal, smart_cleanup
from ..core.regex_patterns import (
    # ===== CORE PATTERNS (shared with V2) =====
    # Whitespace/punctuation
    RE_NEWLINES, RE_MULTI_SPACE, RE_ALL_WHITESPACE, RE_NEWLINES_TABS,
    RE_MULTI_SPACE_INLINE, RE_LEADING_COMMA, RE_LEADING_COMMA_SPACE,
    RE_DOUBLE_PUNCT, RE_TRAILING_PUNCT, RE_COMMA_BEFORE_OF, RE_DOUBLE_COMMA,
    
    # Subject patterns
    RE_SUBJECT_LABEL, RE_SUBJECT_WORDS, RE_PRONOUN_SENTENCE,
    RE_POSSESSIVE_PHRASES, RE_IMAGE_IS_PREFIX, RE_PORTRAIT_PREFIX,
    RE_BACKGROUND, RE_MOOD, RE_IMAGE_DESCRIPTION,
    
    # Instruction patterns
    RE_INSTRUCTION_PREFIX, RE_INSTRUCTION_COLON_HEADER, RE_INSTRUCTION_EXPANSION,
    RE_INSTRUCTION_DESIGN, RE_INSTRUCTION_VERSION,
    
    # List/markdown patterns
    RE_LIST_FIRST_QUOTED, RE_LIST_HEADER, RE_LIST_NUMBERED, RE_LIST_LABELS,
    RE_BOLD_MARKDOWN, RE_QUOTED_CONTENT,
    
    # Image description patterns
    RE_IMAGE_SHOWS, RE_IMAGE_DESCRIPTION_VERBS, RE_PICTURE_OF,
    RE_PHOTO_CAPTURES, RE_VISUAL_REPRESENTATION, RE_PROFESSIONAL_PHOTOGRAPHY,
    RE_AN_IMAGE_OF, RE_PHOTO_DEPICTS, RE_ARTISTIC_RENDERING,
    RE_DIGITAL_PAINTING_SHOWING, RE_ARTISTIC_STUDY, RE_DIGITAL_ART_SHOOT,
    
    # Pattern lists
    SUBJECT_TAG_PATTERNS, BACKGROUND_TAG_PATTERNS, IMAGE_TAG_PATTERNS, SETTING_WORDS,
    
    # Style and composition patterns
    RE_STYLE_BEFORE_SUBJECT, RE_IMAGE_DEPICTING, RE_IMAGE_IN_STYLE_DEPICTS,
    RE_STYLE_IMAGE_DEPICTING, RE_IMAGE_IN_STYLE_END, RE_IMAGE_IN_STYLE_FEATURING,
    
    # Universal image patterns (consolidated)
    RE_UNIVERSAL_IMAGE_OF, RE_UNIVERSAL_IMAGE_DEPICTING, RE_UNIVERSAL_IMAGE_FEATURING,
    RE_STYLE_IMAGE_OF, RE_ADJ_STYLE_IMAGE_OF, RE_IMAGE_IN_STYLE_OF,
    RE_A_IMAGE_IN_STYLE_OF, RE_ADJ_IMAGE_OF,
    
    # Image removal patterns  
    RE_SHOOT_FROM_ABOUT, RE_SHOOT_FROM_ABOUT_IMAGE_ONLY,
    RE_PHOTO_SHOOT_FROM_ABOUT, RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY,
    RE_IMAGE_STYLE_SHOT_FROM, RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY,
    RE_IMAGE_TYPE_FROM_ANGLE, RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY,
    RE_ADJ_IMAGE_CONTINUATION, RE_SIMPLE_IMAGE_OF, RE_STANDALONE_IMAGE_TYPE,
    RE_DANGLING_STYLE, RE_A_WHERE,
    
    # ===== V3 EXTENDED PATTERNS =====
    # Shot style removal patterns (39 patterns)
    SHOT_OF_PATTERNS, TAG_SHOT_PATTERNS,
    RE_SHOT_ANGLE_START, RE_SHOT_SHOOT_FROM, RE_SHOT_CAPTURED_PUNCT,
    RE_SHOT_CAPTURED, RE_SHOT_FROM_VIEW, RE_SHOT_AFTER_PERIOD,
    RE_SHOT_AFTER_COMMA, RE_SHOT_ABOUT_PORTRAIT_A, RE_SHOT_ABOUT_PORTRAIT,
    RE_SHOT_CLOSEUP_OF_START, RE_SHOT_CLOSEUP_OF_AFTER, RE_SHOT_PORTRAIT_OF_START,
    RE_SHOT_PORTRAIT_OF_AFTER, RE_SHOT_CLOSEUP_REPLACE, RE_SHOT_PORTRAIT_REPLACE_START,
    RE_SHOT_PORTRAIT_REPLACE_AFTER, RE_SHOT_BACK_TO_CAMERA, RE_SHOT_IMAGE_TAKEN_FROM,
    RE_SHOT_FOCUS_ON, RE_SHOT_LOOKING_AT, RE_SHOT_DOUBLE_ABOUT,
    RE_SHOT_COMMA_PERIOD, RE_SHOT_PERIOD_COMMA, RE_SHOT_TRAILING_COMMA,
    RE_SHOT_LEADING_COMMA, RE_SHOT_SPACE_PUNCT, RE_SHOT_ORPHAN_WITH,
    RE_SHOT_TRAILING_WITH, RE_SHOT_TAKEN_FROM, RE_SHOT_TYPE_START,
    RE_SHOT_FULL_BODY, RE_SHOT_VIEWS, RE_SHOT_CAMERA_MOVEMENT,
    RE_SHOT_CONTEXT, RE_SHOT_TECHNICAL, RE_SHOT_CAPTURED_AT,
    RE_SHOT_CAPTURED_USING, RE_SHOT_BIRDS_EYE,
    
    # Age adjustment patterns (19 patterns)
    RE_AGE_WORDS, RE_AGE_HYPHEN, RE_AGE_YR, RE_AGE_YO,
    RE_AGE_LATE_TEENS_COMMA, RE_AGE_MID_DECADE_COMMA, RE_AGE_WHO_LATE_TEENS,
    RE_AGE_PRONOUN_LATE_TEENS, RE_AGE_APPEARS_LATE_TEENS, RE_AGE_WHO_MID_DECADE,
    RE_AGE_PRONOUN_MID_DECADE, RE_AGE_APPEARING_MID_DECADE, RE_AGE_APPEARS_MID_DECADE,
    RE_AGE_WHO_AROUND, RE_AGE_APPEARS_AROUND, RE_AGE_IN_DECADE,
    RE_AGE_TAG_BEFORE_HAIR, RE_AGE_YOUNG_SUBJECT, RE_AGE_TEENAGE,
    
    # NSFW removal patterns (8 patterns)
    NSFW_TAG_PATTERNS, NSFW_PROSE_PATTERNS,
    RE_NSFW_BODY_NUDE_SENTENCE, RE_NSFW_BODY_NUDE_CLAUSE,
    RE_NSFW_NO_CLOTHING, RE_NSFW_IS_NUDE, RE_NSFW_COMPLETELY_NUDE,
    RE_NSFW_A_NUDE_SUBJECT,
    
    # Watermark removal patterns (7 patterns)
    RE_WATERMARK_TAGS, RE_WATERMARK_UNDERSCORE, RE_WATERMARK_PERIOD_SPACE,
    RE_WATERMARK_TAG_CLAUSE, RE_WATERMARK_TAG_START, RE_WATERMARK_PROSE_SENTENCE,
    RE_WATERMARK_PROSE_END,
    
    # Optimized patterns (100% sense preservation)
    OPTIMIZED_IMAGE_PATTERNS, OPTIMIZED_AGE_PATTERNS, OPTIMIZED_NSFW_PATTERNS,
    RE_IMAGE_START_OPTIMIZED, RE_IMAGE_SHOT_COMBINED_OPTIMIZED, RE_IMAGE_CONNECTORS_OPTIMIZED, RE_ANIME_STYLE_OPTIMIZED,
    RE_SHOT_STYLE_OPTIMIZED,
)


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
                "sense_preservation": ("BOOLEAN", {"default": True, "forceInput": False, "tooltip": "Apply grammar fixes for proper capitalization and punctuation. Disable if faulty."}),
                "remove_instructions": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, extract content from quotes at the start of the string, or if no quotes, remove everything before the first colon (:) including the colon itself."}),                                
                "list_select_first": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If enabled, extract the first numbered quoted choice (1.) from LLM output and use it as the result."}),
                "list_to_string": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If enabled, convert a numbered tips list into a single-line prompt and remove short labels (e.g., 'Lighting:')."}),
                "remove_image": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove image description matches."}),
                "remove_shot_style": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove camera angles and shot types (close-up, portrait, from above, cowboy shot, looking at viewer, etc.)."}),
                "remove_subject": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove subject description matches."}),
                "remove_background": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove background description matches."}),
                "remove_mood": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove mood description matches."}),
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
        sense_preservation: bool = True,
        remove_instructions: bool = False,
        list_select_first: bool = False,
        list_to_string: bool = False,
        remove_image: bool = False,
        remove_shot_style: bool = False,
        remove_subject: bool = False,
        remove_background: bool = False,
        remove_mood: bool = False,
        adjust_age: bool = False,
        age: int = 25,
        remove_nsfw: bool = False,
        remove_watermark: bool = False,
        cleanup: bool = False,
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
                quote_match = RE_QUOTED_CONTENT.match(s.strip())
                if quote_match:
                    s = quote_match.group(1)
                else:
                    # Check for instruction-like prefix (case insensitive)
                    match = RE_INSTRUCTION_PREFIX.match(s.strip())
                    if match:
                        s = s.strip()[match.end():].strip()
                    else:
                        # Enhanced colon header detection
                        colon_match = RE_INSTRUCTION_COLON_HEADER.match(s.strip())
                        if colon_match:
                            s = s.strip()[colon_match.end():].strip()
                        else:
                            # Check for specific enhanced instruction patterns
                            for enhanced_pattern in [RE_INSTRUCTION_EXPANSION, RE_INSTRUCTION_DESIGN, RE_INSTRUCTION_VERSION]:
                                enhanced_match = enhanced_pattern.match(s.strip())
                                if enhanced_match:
                                    s = s.strip()[enhanced_match.end():].strip()
                                    break
                            else:
                                # Handle multiline: check if first line is instruction header ending with colon
                                lines = s.strip().split('\n')
                            if len(lines) > 1:
                                first_line = lines[0].strip()
                                if first_line.endswith(':') and len(first_line) < 60:
                                    instruction_words = ['prompt', 'description', 'caption', 'output', 'result', 'expanded', 'here', 'text', 'image', 'brief', 'analysis', 'breakdown', 'concept', 'vision']
                                    if any(word in first_line.lower() for word in instruction_words):
                                        s = '\n'.join(lines[1:]).strip()
                            elif len(lines) == 1:
                                # Handle single-line titles ending with colon (like "Character's Artwork: ")
                                first_line = lines[0].strip()
                                if (first_line.endswith(':') and 
                                    len(first_line) > 10 and len(first_line) < 80 and
                                    not first_line.lower().startswith(('http', 'www', 'ftp')) and
                                    first_line.count(' ') >= 1):  # At least 2 words
                                    # This looks like a title, remove it (return empty string)
                                    s = ''

            if list_select_first and s.strip():
                m = RE_LIST_FIRST_QUOTED.search(s)
                if m:
                    s = m.group(1)

            if list_to_string and s.strip():
                s = RE_LIST_HEADER.sub('', s)  # remove header up to first numbered item
                s = RE_BOLD_MARKDOWN.sub(r'\1', s)  # remove bold markup
                s = RE_LIST_NUMBERED.sub('||', s)  # mark numbered items with delimiter
                s = RE_LIST_LABELS.sub('', s)  # remove short label tokens
                s = RE_NEWLINES_TABS.sub(' ', s)  # collapse newlines/tabs
                s = s.replace('||', ', ')  # replace delimiters with comma
                s = RE_LEADING_COMMA.sub('', s)  # clean leading comma
                s = RE_MULTI_SPACE.sub(' ', s).strip()  # collapse extra spaces
        except Exception:
            pass

        if s.strip():
            try:
                # Using centralized patterns from core/regex_patterns.py
                # V3-specific patterns remain inline for specialized tag/prose handling

                def _preserve_lead(match):
                    lead = re.match(r'^\s*([\.\?!,])\s*', match.group(0))
                    if lead:
                        return lead.group(1) + ' '
                    return ''

                # ============================================================
                # NSFW CONTENT REMOVAL (First when both NSFW and subject removal are active)
                # ============================================================
                # Do NSFW removal first to preserve context for smart_phrase_removal
                if (remove_nsfw or remove_subject) and s.strip():
                    try:
                        # Using centralized NSFW_TAG_PATTERNS and NSFW_PROSE_PATTERNS
                        # from core/regex_patterns.py
                        
                        if is_tags_format(s):
                            # Remove NSFW tags
                            tags = [t.strip() for t in s.split(',')]
                            kept_tags = []
                            for tag in tags:
                                tag_lower = tag.lower().strip()
                                is_nsfw = any(re.search(pat, tag_lower, re.I) for pat in NSFW_TAG_PATTERNS)
                                if not is_nsfw:
                                    kept_tags.append(tag)
                            s = ', '.join(kept_tags) if kept_tags else s
                        else:
                            if sense_preservation:
                                # Use optimized NSFW patterns with smart cleanup for 100% sense preservation
                                for pattern in OPTIMIZED_NSFW_PATTERNS:
                                    s = pattern.sub('', s)
                                s = smart_cleanup(s)
                            else:
                                # Original behavior for compatibility
                                # Prose format - use smart removal to maintain grammar
                                s = smart_phrase_removal(s, NSFW_TAG_PATTERNS + NSFW_PROSE_PATTERNS, "NSFW")
                                
                                # Apply individual NSFW prose patterns for targeted removal
                                s = RE_NSFW_BODY_NUDE_SENTENCE.sub('', s)
                                s = RE_NSFW_BODY_NUDE_CLAUSE.sub('', s)
                                s = RE_NSFW_NO_CLOTHING.sub('', s)
                                s = RE_NSFW_IS_NUDE.sub('', s)
                                s = RE_NSFW_COMPLETELY_NUDE.sub('', s)
                                s = RE_NSFW_A_NUDE_SUBJECT.sub('', s)
                        
                    except Exception:
                        pass

                if remove_background:
                    s = RE_BACKGROUND.sub(_preserve_lead, s)  # remove background descriptions
                    
                # ============================================================
                # PATTERN PROCESSING - Apply lowercase preprocessing for all remaining patterns
                # ============================================================
                if any([remove_subject, remove_mood, remove_image, remove_shot_style, adjust_age, remove_watermark]):
                    # Convert to lowercase for all pattern matching (except tags format)
                    if not is_tags_format(s):
                        s = s.lower()
                    
                if remove_subject:
                    original_for_fallback = s  # Save original in case removal leaves nothing
                    
                    if is_tags_format(s):
                        # TAGS FORMAT: Remove subject-related tags, keep background/setting tags
                        # Using centralized patterns from core/regex_patterns.py
                        tags = [t.strip() for t in s.split(',')]
                        
                        kept_tags = []
                        for tag in tags:
                            tag_clean = tag.strip().lower().replace(' ', '_').replace('-', '_')
                            
                            # Check if it's a subject tag (using centralized SUBJECT_TAG_PATTERNS)
                            is_subject = any(re.match(pat, tag_clean, re.I) for pat in SUBJECT_TAG_PATTERNS)
                            
                            # Check if it's explicitly a background tag (using centralized BACKGROUND_TAG_PATTERNS)
                            is_background = any(re.match(pat, tag_clean, re.I) for pat in BACKGROUND_TAG_PATTERNS)
                            
                            # Keep if it's a background tag OR if it's not identified as subject
                            if is_background or not is_subject:
                                kept_tags.append(tag)
                        
                        if kept_tags:
                            s = ', '.join(kept_tags)
                        # If nothing left, s will be empty and we'll restore original below
                    
                    else:
                        # PROSE FORMAT: Extract setting, remove subject descriptions
                        # 1. Remove "Subject: ..." labeled sections (structured prompts)
                        s = RE_SUBJECT_LABEL.sub(' ', s)
                        
                        # 2. For prose: Find setting descriptions and extract them
                        # Using centralized SETTING_WORDS from core/regex_patterns.py
                        
                        # Check if text STARTS with a setting word (no subject before it)
                        first_words = s.split()[:5]
                        starts_with_setting = False
                        for i, word in enumerate(first_words):
                            clean_word = re.sub(r'[,.]', '', word.lower())
                            if re.match(SETTING_WORDS, clean_word, re.I):
                                words_before = [re.sub(r'[,.]', '', w.lower()) for w in first_words[:i]]
                                has_subject_before = any(RE_SUBJECT_WORDS.search(w) for w in words_before)
                                if not has_subject_before:
                                    starts_with_setting = True
                                break
                        
                        if not starts_with_setting:
                            # Pattern: [preposition] [article] [optional adjectives] [setting word]
                            setting_pattern = rf'(?i)\s+(in|at|on|by|near|against|beside|within|inside|outside|through|across|around|along|under|over|beneath|above)\s+(a|an|the)\s+(?:[\w\-,]+\s+)*?{SETTING_WORDS}\b[^.]*'
                            
                            setting_match = re.search(setting_pattern, s)
                            if setting_match:
                                before_setting = s[:setting_match.start()]
                                if RE_SUBJECT_WORDS.search(before_setting):
                                    s = setting_match.group(0).strip()
                        
                        # 3. Enhanced subject detection using sophisticated pronoun patterns
                        # Remove possessive phrases about physical features (conservative application)
                        if RE_POSSESSIVE_PHRASES.search(s):
                            s = RE_POSSESSIVE_PHRASES.sub('', s)
                        
                        # 4. Remove pronoun-led sentences that clearly describe subjects
                        if RE_PRONOUN_SENTENCE.search(s):
                            # Apply more conservatively - only if the sentence seems subject-focused
                            def _check_and_remove_pronoun_sentence(match):
                                sentence = match.group(0)
                                # Only remove if it contains appearance or character-related words
                                appearance_words = r'\b(?:hair|eyes|face|skin|tall|short|young|old|beautiful|handsome|appearance|looks?|seems?)\b'
                                if re.search(appearance_words, sentence, re.I):
                                    return ''
                                return sentence
                            s = RE_PRONOUN_SENTENCE.sub(_check_and_remove_pronoun_sentence, s)
                        
                        # 4. Clean up artifacts
                        s = re.sub(r'(?i)^[\s,]*(?:and|or|but|while|as)\s+', '', s)
                        s = re.sub(r'^\s*[,\.]\s*', '', s)
                        s = re.sub(r'\s*,\s*,', ',', s)
                    
                    # SAFETY: If removal left nothing meaningful, restore original
                    s_clean = re.sub(r'[\s,]+', '', s)
                    if not s_clean or len(s_clean) < 3:
                        s = original_for_fallback
                    
                if remove_mood:
                    s = RE_MOOD.sub(_preserve_lead, s)  # remove mood/atmosphere descriptions
                if remove_image:
                    if is_tags_format(s):
                        # TAG FORMAT: Remove quality/style/image type tags
                        # Using centralized IMAGE_TAG_PATTERNS from core/regex_patterns.py
                        tags = [t.strip() for t in s.split(',')]
                        
                        kept_tags = []
                        for tag in tags:
                            tag_clean = tag.strip().lower().replace(' ', '_').replace('-', '_')
                            is_image_tag = any(re.match(pat, tag_clean, re.I) for pat in IMAGE_TAG_PATTERNS)
                            if not is_image_tag:
                                kept_tags.append(tag)
                        
                        s = ', '.join(kept_tags) if kept_tags else s
                    else:
                        # PROSE FORMAT: Remove image type descriptions
                        if sense_preservation:
                            # Use optimized patterns with smart cleanup for 100% sense preservation
                            # Only apply image patterns, not age or other patterns automatically
                            s = RE_IMAGE_START_OPTIMIZED.sub('', s)
                            s = RE_IMAGE_SHOT_COMBINED_OPTIMIZED.sub('', s)
                            s = RE_IMAGE_CONNECTORS_OPTIMIZED.sub(' ', s)  # Replace with space to avoid word concatenation
                            s = RE_ANIME_STYLE_OPTIMIZED.sub('', s)
                            
                            # Apply shot style removal only if remove_shot_style is True
                            if remove_shot_style:
                                s = RE_SHOT_STYLE_OPTIMIZED.sub('', s)
                            
                            s = smart_cleanup(s)
                        else:
                            # Original behavior for compatibility
                            # Using centralized patterns from core/regex_patterns.py
                            s = RE_IMAGE_IS_PREFIX.sub('', s)
                            s = RE_PORTRAIT_PREFIX.sub('', s)
                            
                            # Universal image patterns (catch basic descriptions first)
                            s = RE_UNIVERSAL_IMAGE_OF.sub('', s)
                            s = RE_UNIVERSAL_IMAGE_DEPICTING.sub('', s)
                            s = RE_UNIVERSAL_IMAGE_FEATURING.sub('', s)
                            
                            # Sequential pattern application (order matters)
                            s = RE_IMAGE_IN_STYLE_DEPICTS.sub('', s)
                            s = RE_IMAGE_DEPICTING.sub('', s)
                            s = RE_STYLE_IMAGE_OF.sub('', s)
                            s = RE_ADJ_STYLE_IMAGE_OF.sub('', s)
                            s = RE_IMAGE_IN_STYLE_OF.sub('', s)
                            s = RE_A_IMAGE_IN_STYLE_OF.sub('', s)
                            
                            # Enhanced image description patterns
                            s = RE_IMAGE_SHOWS.sub('', s)
                            s = RE_IMAGE_DESCRIPTION_VERBS.sub('', s)
                            s = RE_PICTURE_OF.sub('', s)
                            s = RE_PHOTO_CAPTURES.sub('', s)
                            s = RE_VISUAL_REPRESENTATION.sub('', s)
                            s = RE_PROFESSIONAL_PHOTOGRAPHY.sub('', s)
                            s = RE_AN_IMAGE_OF.sub('', s)
                            s = RE_PHOTO_DEPICTS.sub('', s)
                            s = RE_ARTISTIC_RENDERING.sub('', s)
                            s = RE_DIGITAL_PAINTING_SHOWING.sub('', s)
                            s = RE_ARTISTIC_STUDY.sub('', s)
                            
                            # Apply complex patterns BEFORE simpler ones (order matters!)
                            # Image removal only handles image description, not shot style
                            s = RE_SHOOT_FROM_ABOUT_IMAGE_ONLY.sub('', s)  # Handle "A digital illustration shoot" but keep "from X angle"
                            s = RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY.sub('', s)  # Handle "A photo-realistic shoot" but keep "from X angle"
                            s = RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY.sub('', s)  # Handle "A digital illustration, anime style," but keep "shot from X"
                            s = RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY.sub(r'A \1', s)  # Handle "A close-up digital illustration" but keep shot descriptor
                            s = RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY.sub('', s)  # Handle "A photo-realistic shoot" but keep "from X angle"
                            s = RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY.sub('', s)  # Handle "A digital illustration, anime style," but keep "shot from X"
                            s = RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY.sub(r'A \1', s)  # Handle "A close-up digital illustration" but keep shot descriptor
                            
                            s = RE_DIGITAL_ART_SHOOT.sub('', s)    # Then handle simpler "digital illustration shoot"
                        
                            s = RE_STYLE_BEFORE_SUBJECT.sub('', s)
                            
                            # Protect mood descriptions from aggressive removal
                            s = s.replace('the overall mood of the', 'the overall mood is')
                            
                            s = RE_ADJ_IMAGE_OF.sub('', s)
                        s = RE_STYLE_IMAGE_DEPICTING.sub(r'\1', s)
                        s = RE_ADJ_IMAGE_CONTINUATION.sub(
                            lambda m: m.group(1) + (m.group(2).rstrip(', ') + ' ' if m.group(2) else '') + m.group(3).lstrip(), s)
                        
                        s = RE_SIMPLE_IMAGE_OF.sub('', s)
                        s = RE_IMAGE_IN_STYLE_FEATURING.sub('', s)
                        s = RE_IMAGE_IN_STYLE_END.sub('', s)
                        s = RE_STANDALONE_IMAGE_TYPE.sub('', s)
                        s = RE_DANGLING_STYLE.sub('', s)
                        s = RE_A_WHERE.sub(lambda m: m.group(2).capitalize(), s)
                        
                        # Cleanup
                        s = RE_DOUBLE_COMMA.sub(',', s)
                        s = RE_COMMA_BEFORE_OF.sub(' ', s)
                        s = RE_MULTI_SPACE_INLINE.sub(' ', s)
                        s = RE_LEADING_COMMA_SPACE.sub('', s)
                        
                        # Remove inline image descriptions using centralized pattern
                        s = RE_IMAGE_DESCRIPTION.sub('', s)
                
                # ============================================================
                # SHOT STYLE REMOVAL
                # ============================================================
                if remove_shot_style:
                    # Using centralized patterns from core/regex_patterns.py
                    # Handle complex "shoot from about" patterns first
                    s = RE_SHOOT_FROM_ABOUT.sub('', s)  # Complete removal: image description AND shot style
                    s = RE_PHOTO_SHOOT_FROM_ABOUT.sub('', s)  # Complete removal: photo-realistic shoot patterns
                    s = RE_IMAGE_STYLE_SHOT_FROM.sub('', s)  # Complete removal: comma-separated style patterns
                    s = RE_IMAGE_TYPE_FROM_ANGLE.sub('', s)  # Complete removal: image type from angle patterns
                    
                    s = RE_SHOT_ANGLE_START.sub('', s)
                    s = RE_SHOT_SHOOT_FROM.sub('shoot about ', s)
                    s = RE_SHOT_CAPTURED_PUNCT.sub(r'\1', s)
                    s = RE_SHOT_CAPTURED.sub('', s)
                    s = RE_SHOT_FROM_VIEW.sub('shot', s)
                    s = RE_SHOT_AFTER_PERIOD.sub('.', s)
                    s = RE_SHOT_AFTER_COMMA.sub(',', s)
                    
                    # Enhanced shot style patterns
                    s = RE_SHOT_TAKEN_FROM.sub('', s)
                    s = RE_SHOT_TYPE_START.sub('', s)
                    s = RE_SHOT_FULL_BODY.sub('', s)
                    s = RE_SHOT_VIEWS.sub('', s)
                    s = RE_SHOT_CAMERA_MOVEMENT.sub('', s)
                    s = RE_SHOT_CONTEXT.sub('', s)
                    s = RE_SHOT_TECHNICAL.sub('', s)
                    s = RE_SHOT_CAPTURED_AT.sub('', s)
                    s = RE_SHOT_CAPTURED_USING.sub('', s)
                    s = RE_SHOT_BIRDS_EYE.sub('', s)
                    
                    # Handle "about a portrait of"
                    s = RE_SHOT_ABOUT_PORTRAIT_A.sub('about a ', s)
                    s = RE_SHOT_ABOUT_PORTRAIT.sub('about', s)
                    
                    # Shot type + "of" patterns - using centralized SHOT_OF_PATTERNS
                    for shot_pat in SHOT_OF_PATTERNS:
                        s = re.sub(rf'^(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', '', s, flags=re.IGNORECASE)
                        s = re.sub(rf'(\.\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                        s = re.sub(rf'(,\s+)(?:a|an)\s+(?:black\s+and\s+white\s+)?{shot_pat}\s+of\s+', r'\1', s, flags=re.IGNORECASE)
                    
                    # "A close-up shot of" and "A portrait of" handling - dual approach
                    # First try gentler replacement, then complete removal for remaining cases
                    s = RE_SHOT_CLOSEUP_REPLACE.sub('A shot of', s)  # Gentle: "close-up shot" -> "shot"
                    s = RE_SHOT_PORTRAIT_REPLACE_START.sub('A picture of', s)  # Gentle: "portrait" -> "picture"
                    s = RE_SHOT_PORTRAIT_REPLACE_AFTER.sub('. A picture of', s)  # Gentle replacement after period
                    
                    # Complete removal for remaining cases
                    s = RE_SHOT_CLOSEUP_OF_START.sub('', s)
                    s = RE_SHOT_CLOSEUP_OF_AFTER.sub(r'\1', s)
                    s = RE_SHOT_PORTRAIT_OF_START.sub('', s)
                    s = RE_SHOT_PORTRAIT_OF_AFTER.sub(r'\1', s)
                    
                    s = RE_SHOT_BACK_TO_CAMERA.sub(', ', s)
                    s = RE_SHOT_IMAGE_TAKEN_FROM.sub('', s)
                    s = RE_SHOT_FOCUS_ON.sub('', s)
                    s = RE_SHOT_LOOKING_AT.sub(', ', s)
                    
                    # Tag patterns - using centralized TAG_SHOT_PATTERNS
                    for pattern in TAG_SHOT_PATTERNS:
                        s = re.sub(r',\s*' + pattern + r'\s*(?=,|$)', '', s, flags=re.IGNORECASE)
                        s = re.sub(r'^' + pattern + r'\s*,\s*', '', s, flags=re.IGNORECASE)
                        s = re.sub(r',\s*' + pattern + r'\s*$', '', s, flags=re.IGNORECASE)
                    
                    # Clean up artifacts
                    s = RE_SHOT_DOUBLE_ABOUT.sub('shoot about', s)
                    s = RE_DOUBLE_COMMA.sub(',', s)
                    s = RE_SHOT_COMMA_PERIOD.sub('.', s)
                    s = RE_SHOT_PERIOD_COMMA.sub('.', s)
                    s = RE_ALL_WHITESPACE.sub(' ', s)
                    s = RE_SHOT_TRAILING_COMMA.sub('', s)
                    s = RE_SHOT_LEADING_COMMA.sub('', s)
                    s = RE_SHOT_SPACE_PUNCT.sub(r'\1', s)
                    s = RE_SHOT_ORPHAN_WITH.sub('.', s)
                    s = RE_SHOT_TRAILING_WITH.sub('', s)
                    
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
                    
                    if sense_preservation:
                        # For sense preservation, don't use the OPTIMIZED_AGE_PATTERNS (they're removal patterns)
                        # Instead, use careful original patterns that preserve context
                        s = RE_AGE_LATE_TEENS_COMMA.sub(f', who is {target_age}-year-old,', s)
                        s = RE_AGE_MID_DECADE_COMMA.sub(f', who is {target_age}-year-old,', s)
                        s = RE_AGE_WHO_LATE_TEENS.sub(f'{target_age}-year-old', s)
                        s = RE_AGE_PRONOUN_LATE_TEENS.sub(rf'\1 is {target_age}-year-old', s)
                        s = RE_AGE_APPEARS_LATE_TEENS.sub(f'is {target_age}-year-old', s)
                        s = RE_AGE_WORDS.sub(f'{target_age}-year-old', s)
                        s = RE_AGE_HYPHEN.sub(f'{target_age}-year-old', s)
                        s = smart_cleanup(s)
                    else:
                        # Original behavior for compatibility
                        # Using centralized patterns from core/regex_patterns.py
                        # Comma-enclosed patterns first (preserve sentence structure)
                        s = RE_AGE_LATE_TEENS_COMMA.sub(f', who is {target_age}-year-old,', s)
                        s = RE_AGE_MID_DECADE_COMMA.sub(f', who is {target_age}-year-old,', s)
                        
                        # Non-comma patterns
                        s = RE_AGE_WHO_LATE_TEENS.sub(f'{target_age}-year-old', s)
                        s = RE_AGE_PRONOUN_LATE_TEENS.sub(rf'\1 is {target_age}-year-old', s)
                        s = RE_AGE_APPEARS_LATE_TEENS.sub(f'is {target_age}-year-old', s)
                        
                        # Redundant age cleanup (first pass)
                        s = re.sub(rf',\s*is\s+{target_age}\s+years?\s+old\b', '', s, flags=re.IGNORECASE)
                        
                        # Mid-decade patterns
                        s = RE_AGE_WHO_MID_DECADE.sub(f'is {target_age} years old', s)
                        s = RE_AGE_PRONOUN_MID_DECADE.sub(rf'\1 is {target_age} years old', s)
                        s = RE_AGE_APPEARING_MID_DECADE.sub(f'{target_age} years old', s)
                        s = RE_AGE_APPEARS_MID_DECADE.sub(f'is {target_age} years old', s)
                        
                        # Around/approximate age patterns
                        s = RE_AGE_WHO_AROUND.sub(f'{target_age} years old', s)
                        s = RE_AGE_APPEARS_AROUND.sub(f'is {target_age} years old', s)
                        s = RE_AGE_IN_DECADE.sub(f'{target_age} years old', s)
                        
                        # Explicit ages (already centralized)
                        s = RE_AGE_WORDS.sub(f'{target_age}-year-old', s)
                        s = RE_AGE_HYPHEN.sub(f'{target_age}-year-old', s)
                        s = RE_AGE_YR.sub(f'{target_age}yr', s)
                        s = RE_AGE_YO.sub(f'{target_age}yo', s)
                        
                        # Tag format age before hair color
                        s = RE_AGE_TAG_BEFORE_HAIR.sub(f', {target_age},', s)
                    
                    # Age-appropriate term mapping
                    def get_age_appropriate_term(match, target_age):
                        original_term = match.group(1).lower()
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
                            term = original_term
                        return f'{target_age}-year-old {term}'
                    
                    # Young/teenage subject terms
                    s = RE_AGE_YOUNG_SUBJECT.sub(lambda m: get_age_appropriate_term(m, target_age), s)
                    s = RE_AGE_TEENAGE.sub(lambda m: get_age_appropriate_term(m, target_age), s)
                    
                    # Final age cleanup
                    s = re.sub(rf',\s*is\s+{target_age}-year-old\b', '', s, flags=re.IGNORECASE)
                    s = re.sub(rf',\s*is\s+{target_age}\s+years?\s+old\b', '', s, flags=re.IGNORECASE)
                    s = re.sub(rf',\s+{target_age}\s+years?\s+old\b', '', s, flags=re.IGNORECASE)
                    
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
            is_tags_for_watermark = RE_WATERMARK_UNDERSCORE.search(replaced) or (replaced.count(',') > 2 and not RE_WATERMARK_PERIOD_SPACE.search(replaced))
            
            if is_tags_for_watermark or '.' not in replaced:
                # Tag/clause format: remove clause between commas containing watermark
                # e.g., "quality, there is a watermark, 1girl" -> "quality, 1girl"
                replaced = RE_WATERMARK_TAG_CLAUSE.sub('', replaced)
                replaced = RE_WATERMARK_TAG_START.sub('', replaced)
            else:
                # Prose format: remove entire sentence containing watermark
                # e.g., "Nice quality. There is a watermark. Good colors." -> "Nice quality. Good colors."
                replaced = RE_WATERMARK_PROSE_SENTENCE.sub('', replaced)
                # Handle end of string without period
                replaced = RE_WATERMARK_PROSE_END.sub('', replaced)
            
            # Remove remaining watermark-related tags using centralized RE_WATERMARK_TAGS
            replaced = RE_WATERMARK_TAGS.sub(', ', replaced)
            # Clean up leftover comma artifacts
            replaced = re.sub(r',\s*,', ',', replaced)
            replaced = re.sub(r'^\s*,\s*', '', replaced)
            replaced = re.sub(r',\s*$', '', replaced)

        # Optional cleanup
        if cleanup:
            replaced = RE_NEWLINES.sub(' ', replaced)  # normalize whitespace
            replaced = RE_MULTI_SPACE.sub(' ', replaced)  # collapse multiple spaces
            try:
                replaced = re.sub(r'\s*\.\s+(?=[a-z])', ' ', replaced)  # fix dangling periods
            except Exception:
                pass
            replaced = replaced.strip()  # remove leading/trailing whitespace
            replaced = replaced.replace('"', '')  # remove double quotes
            replaced = re.sub(r'\. ,\s*', '. ', replaced)  # fix ". ,"
            # Iteratively clean multiple consecutive punctuation marks throughout the string
            while RE_DOUBLE_PUNCT.search(replaced):
                replaced = RE_DOUBLE_PUNCT.sub(',', replaced)  # collapse multiple punctuation to single comma
                replaced = re.sub(r',\s*,', ',', replaced)  # collapse comma-space-comma to comma
            # Clean trailing punctuation until only one dot remains
            while re.search(r'[,.]\s*$', replaced) or re.search(r'\.\s*\.', replaced):
                replaced = re.sub(r'[,.]\s*$', '', replaced).strip()  # remove trailing commas/periods
                replaced = re.sub(r'\.\s*\.', '.', replaced)  # collapse multiple periods
            # Remove all ending punctuation
            replaced = RE_TRAILING_PUNCT.sub('', replaced).strip()
        return (replaced,)

NODE_NAME = 'Replace String v3 [Eclipse]'
NODE_DESC = 'Replace String v3'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvText_ReplaceStringV3
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

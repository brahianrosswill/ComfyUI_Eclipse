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

# ReplaceStringV2 - Simplified version of V3 with core options only.
# Uses the same tag/prose detection and processing logic as V3.
# For advanced options (shot_style, age, nsfw, watermark), use V3.

import re
from ..core import CATEGORY
from ..core.regex_helper import is_tags_format, smart_cleanup
from ..core.regex_patterns import (
    # Core whitespace/punctuation patterns
    RE_NEWLINES, RE_MULTI_SPACE, RE_NEWLINES_TABS,
    RE_MULTI_SPACE_INLINE, RE_LEADING_COMMA, RE_LEADING_COMMA_SPACE,
    RE_DOUBLE_PUNCT, RE_TRAILING_PUNCT, RE_COMMA_BEFORE_OF, RE_DOUBLE_COMMA,
    
    # Core subject patterns
    RE_SUBJECT_LABEL, RE_SUBJECT_WORDS, RE_PRONOUN_SENTENCE,
    RE_POSSESSIVE_PHRASES, RE_IMAGE_IS_PREFIX, RE_PORTRAIT_PREFIX,
    RE_BACKGROUND, RE_MOOD, RE_IMAGE_DESCRIPTION,
    
    # Core instruction patterns
    RE_INSTRUCTION_PREFIX, RE_INSTRUCTION_COLON_HEADER, RE_INSTRUCTION_EXPANSION,
    RE_INSTRUCTION_DESIGN, RE_INSTRUCTION_VERSION,
    
    # Core list/markdown patterns
    RE_LIST_FIRST_QUOTED, RE_LIST_HEADER, RE_LIST_NUMBERED, RE_LIST_LABELS,
    RE_BOLD_MARKDOWN, RE_QUOTED_CONTENT,
    
    # Core image description patterns
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
    
    # Image-only patterns (V2 specific - preserve shot style elements)
    RE_SHOOT_FROM_ABOUT_IMAGE_ONLY, RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY,
    RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY, RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY,
    RE_ADJ_IMAGE_CONTINUATION, RE_SIMPLE_IMAGE_OF, RE_STANDALONE_IMAGE_TYPE,
    RE_DANGLING_STYLE, RE_A_WHERE,
    
    # Optimized patterns (100% sense preservation, V2 - shot style preserving)
    OPTIMIZED_IMAGE_PATTERNS_V2,
    RE_IMAGE_CONNECTORS_OPTIMIZED,
)


class RvText_ReplaceStringV2:
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
                "remove_subject": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove subject description matches."}),
                "remove_background": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove background description matches."}),
                "remove_mood": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove mood description matches."}),
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
        remove_subject: bool = False,
        remove_background: bool = False,
        remove_mood: bool = False,
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
                            # Enhanced instruction removal with new patterns
                            s = RE_INSTRUCTION_EXPANSION.sub('', s)
                            s = RE_INSTRUCTION_DESIGN.sub('', s)
                            s = RE_INSTRUCTION_VERSION.sub('', s)
                            
                            # Handle multiline: check if first line is instruction header ending with colon
                            lines = s.strip().split('\n')
                        if len(lines) > 1:
                            first_line = lines[0].strip()
                            if first_line.endswith(':') and len(first_line) < 60:
                                instruction_words = ['prompt', 'description', 'caption', 'output', 'result', 'expanded', 'here', 'text', 'image']
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
                # Same tag/prose detection logic as V3

                def _preserve_lead(match):
                    lead = re.match(r'^\s*([\.\?!,])\s*', match.group(0))
                    if lead:
                        return lead.group(1) + ' '
                    return ''

                if remove_background:
                    s = RE_BACKGROUND.sub(_preserve_lead, s)  # remove background descriptions
                
                # ============================================================
                # PATTERN PROCESSING - Apply lowercase preprocessing for all remaining patterns
                # ============================================================
                if any([remove_subject, remove_mood, remove_image]):
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
                            # V2-specific optimized patterns (preserves shot styles, 100% sense preservation)
                            for pattern in OPTIMIZED_IMAGE_PATTERNS_V2:
                                if pattern == RE_IMAGE_CONNECTORS_OPTIMIZED:
                                    # Replace connectors with space to avoid word concatenation
                                    s = pattern.sub(' ', s)
                                else:
                                    s = pattern.sub('', s)
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
                            
                            s = RE_STYLE_BEFORE_SUBJECT.sub('', s)
                            
                            s = RE_ADJ_IMAGE_OF.sub('', s)
                            s = RE_STYLE_IMAGE_DEPICTING.sub(r'\1', s)
                            
                            # Apply complex patterns BEFORE simpler ones (order matters!)
                            # V2 only has remove_image, so preserve shot style elements
                            s = RE_SHOOT_FROM_ABOUT_IMAGE_ONLY.sub('', s)  # Handle "A digital illustration shoot" but keep "from X angle"
                            s = RE_PHOTO_SHOOT_FROM_ABOUT_IMAGE_ONLY.sub('', s)  # Handle "A photo-realistic shoot" but keep "from X angle"
                            s = RE_IMAGE_STYLE_SHOT_FROM_IMAGE_ONLY.sub('', s)  # Handle "A digital illustration, anime style," but keep "shot from X"
                            s = RE_IMAGE_TYPE_FROM_ANGLE_IMAGE_ONLY.sub(r'A \1', s)  # Handle "A close-up digital illustration" but keep shot descriptor
                            
                            s = RE_ADJ_IMAGE_CONTINUATION.sub(
                                lambda m: m.group(1) + (m.group(2).rstrip(', ') + ' ' if m.group(2) else '') + m.group(3).lstrip(), s)
                            
                            s = RE_SIMPLE_IMAGE_OF.sub('', s)
                            
                            # Enhanced image description patterns for complete detection
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
                        s = RE_DIGITAL_ART_SHOOT.sub('', s)  # Apply simpler pattern after complex ones
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
                    
            except Exception:
                pass

        # Apply user regex
        try:
            if regex and str(regex).strip():
                replaced = re.sub(regex, replace_with, s)
            else:
                replaced = s
        except Exception:
            replaced = s

        # Optional cleanup
        if cleanup:
            replaced = RE_NEWLINES.sub(' ', replaced)
            replaced = RE_MULTI_SPACE.sub(' ', replaced)
            try:
                replaced = re.sub(r'\s*\.\s+(?=[a-z])', ' ', replaced)
            except Exception:
                pass
            replaced = replaced.strip()
            replaced = replaced.replace('"', '')
            replaced = re.sub(r'\. ,\s*', '. ', replaced)
            while RE_DOUBLE_PUNCT.search(replaced):
                replaced = RE_DOUBLE_PUNCT.sub(',', replaced)
                replaced = re.sub(r',\s*,', ',', replaced)
            while re.search(r'[,.]\s*$', replaced) or re.search(r'\.\s*\.', replaced):
                replaced = re.sub(r'[,.]\s*$', '', replaced).strip()
                replaced = re.sub(r'\.\s*\.', '.', replaced)
            replaced = RE_TRAILING_PUNCT.sub('', replaced).strip()
        return (replaced,)

NODE_NAME = 'Replace String v2 [Eclipse]'
NODE_DESC = 'Replace String v2'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvText_ReplaceStringV2
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

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

from typing import Any, Dict, List, Tuple
from ..core import CATEGORY
from ..core.logger import log
from ..core.styles import (
    get_all_styles,
    invalidate_styles_cache,
    find_template_by_name,
)

_LOG_PREFIX = "Style Loader"


class RvText_PromptStyler:
    # Load and apply prompt styles from JSON or CSV files.
    # Replaces {prompt} placeholder with your positive prompt and combines negative prompts.
    # Style files should be placed in the 'templates/styles' folder of ComfyUI_Eclipse.
    
    # Class-level storage for styles by mode
    styles_by_mode = {}
    names_by_mode = {}

    def __init__(self):
        pass

    @classmethod
    def reload_styles(cls):
        # Reload styles from disk. Call this when style files are modified.
        invalidate_styles_cache()  # Force cache invalidation
        cls.styles_by_mode, cls.names_by_mode = get_all_styles()
        total = sum(len(v) for v in cls.names_by_mode.values())
        return {
            "success": True,
            "total_styles": total,
            "tag_based": len(cls.names_by_mode.get('tag_based', [])),
            "natural_language": len(cls.names_by_mode.get('natural_language', [])),
            "custom": len(cls.names_by_mode.get('custom', []))
        }

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        # Load all styles organized by mode (with caching)
        cls.styles_by_mode, cls.names_by_mode = get_all_styles()
        
        # Default to tag_based mode styles for initial dropdown
        default_mode = 'tag_based'
        default_styles = cls.names_by_mode.get(default_mode, [])
        
        # Provide a default if no styles found
        if not default_styles:
            default_styles = ["No styles found"]
        
        return {
            "required": {
                "text_positive": ("STRING", {"default": "", "forceInput": True, "tooltip": "Positive prompt text. Will replace {prompt} in the style template."}),
                "style_mode": (["tag_based", "natural_language", "custom"], {"default": "tag_based", "tooltip": "Select style format: tag_based uses comma-separated tags, natural_language uses flowing sentences, custom shows user-added style files."}),
                "style": (default_styles, {"tooltip": "Select style to apply (contains both positive and negative prompts)."}),
                "index": ("INT", {"default": 0, "min": -3, "max": 999999, "step": 1, "tooltip": "Style index: 0+ = fixed position, -1 = random, -2 = increment, -3 = decrement. Use navigation buttons to control."}),
                "spaces_to_underscores": ("BOOLEAN", {"default": False, "label_on": "yes", "label_off": "no", "tooltip": "Convert spaces to underscores in tag-like segments (comma-separated parts with few words)."}),
                "max_words_to_combine": ("INT", {"default": 3, "min": 2, "max": 10, "step": 1, "tooltip": "Maximum words in a segment to apply underscore conversion. Segments with more words are treated as natural language and left unchanged."}),
                "apply_to_positive": ("BOOLEAN", {"default": True, "label_on": "yes", "label_off": "no", "tooltip": "Apply style to positive prompt."}),
                "apply_to_negative": ("BOOLEAN", {"default": True, "label_on": "yes", "label_off": "no", "tooltip": "Apply style to negative prompt."}),
                "log_prompt": ("BOOLEAN", {"default": False, "label_on": "yes", "label_off": "no", "tooltip": "Log the styled prompts to console."}),
            },
            "optional": {
                "text_negative": ("STRING", {"default": "", "forceInput": True, "tooltip": "Negative prompt text. Will be combined with the style's negative prompt."}),
            },
        }

    RETURN_TYPES = ('STRING', 'STRING',)
    RETURN_NAMES = ('text_positive', 'text_negative',)
    FUNCTION = 'prompt_styler'
    CATEGORY = CATEGORY.MAIN.value + CATEGORY.TEXT.value

    def _convert_spaces_to_underscores(self, text: str, max_words: int) -> str:
        # Convert spaces to underscores in comma-separated segments that have
        # at most max_words words. Segments with more words are left unchanged
        # (assumed to be natural language).
        if not text:
            return text
        
        segments = text.split(',')
        converted_segments = []
        
        for segment in segments:
            stripped = segment.strip()
            if not stripped:
                converted_segments.append(segment)
                continue
            
            # Count words (split by whitespace)
            words = stripped.split()
            
            # Only convert if word count is within the limit
            if len(words) <= max_words:
                # Preserve leading/trailing whitespace from original segment
                leading_space = segment[:len(segment) - len(segment.lstrip())]
                trailing_space = segment[len(segment.rstrip()):]
                converted = stripped.replace(' ', '_')
                converted_segments.append(f"{leading_space}{converted}{trailing_space}")
            else:
                # Leave natural language segments unchanged
                converted_segments.append(segment)
        
        return ','.join(converted_segments)

    def prompt_styler(
        self, 
        style_mode: str,
        style: str,
        index: int,
        spaces_to_underscores: bool,
        max_words_to_combine: int,
        text_positive: str, 
        apply_to_positive: bool,
        apply_to_negative: bool,
        log_prompt: bool,
        text_negative: str = ""
    ) -> Tuple[str, str]:
        # Process and combine prompts in templates.
        # The function replaces the positive prompt placeholder in the template,
        # and combines the negative prompt with the template's negative prompt, if they exist.
        
        # Always fetch fresh styles from the cached core module (handles hot reload)
        styles_by_mode, _ = get_all_styles()
        
        # Get styles for the selected mode
        mode_styles = styles_by_mode.get(style_mode, [])
        
        # If index >= 0, use index to select style (with wrapping)
        if index >= 0 and mode_styles:
            actual_index = index % len(mode_styles)
            template = mode_styles[actual_index]
            style = template.get('name', style)
            if log_prompt:
                log.debug(_LOG_PREFIX, f"Using index {index} (wrapped to {actual_index}) - style: {style} (mode: {style_mode})")
        else:
            # Find template in pre-loaded data by name for the selected mode
            template = find_template_by_name(mode_styles, style)
        
        # Apply style
        if template:
            prompt_template = template['prompt']
            
            # Split template on {prompt} and clean up parts
            if '{prompt}' in prompt_template:
                parts = prompt_template.split('{prompt}')
                prefix = parts[0].strip()
                suffix = parts[1].strip() if len(parts) > 1 else ""
                
                # Remove leading punctuation from suffix (dots, commas, spaces)
                suffix = suffix.lstrip('., ')
                
                # Clean up user prompt - remove trailing punctuation to avoid double punctuation
                text_positive_clean = text_positive.strip().rstrip('.,;: ')
                
                # Determine separator based on style mode (comma for tag_based, space for natural_language)
                prefix_sep = ", " if style_mode == "tag_based" else " "
                
                # Build final prompt: prefix, user prompt, comma, suffix
                if prefix and suffix:
                    text_positive_styled = f"{prefix}{prefix_sep}{text_positive_clean}, {suffix}"
                elif prefix:
                    text_positive_styled = f"{prefix}{prefix_sep}{text_positive_clean}"
                elif suffix:
                    text_positive_styled = f"{text_positive_clean}, {suffix}"
                else:
                    text_positive_styled = text_positive_clean
            else:
                # No placeholder, just use template as-is
                text_positive_styled = prompt_template
            
            json_negative_prompt = template.get('negative_prompt', "")
            text_negative_styled = f"{json_negative_prompt}, {text_negative}" if json_negative_prompt and text_negative else json_negative_prompt or text_negative
        else:
            text_positive_styled = text_positive
            text_negative_styled = text_negative
            if log_prompt:
                log.warning(_LOG_PREFIX, f"Style '{style}' not found")

        # If apply_to_positive is disabled, return original positive prompt
        if not apply_to_positive:
            text_positive_styled = text_positive
            if log_prompt:
                log.debug(_LOG_PREFIX, "apply_to_positive: disabled")

        # If apply_to_negative is disabled, return original negative prompt
        if not apply_to_negative:
            text_negative_styled = text_negative
            if log_prompt:
                log.debug(_LOG_PREFIX, "apply_to_negative: disabled")

        # Apply spaces to underscores conversion if enabled
        if spaces_to_underscores:
            if apply_to_positive:
                text_positive_styled = self._convert_spaces_to_underscores(text_positive_styled, max_words_to_combine)
            if apply_to_negative:
                text_negative_styled = self._convert_spaces_to_underscores(text_negative_styled, max_words_to_combine)
            if log_prompt:
                log.debug(_LOG_PREFIX, f"Applied spaces_to_underscores (max_words: {max_words_to_combine})")

        # Log the styled prompts if logging is enabled
        if log_prompt:
            log.msg(_LOG_PREFIX, f"style: {style}")
            log.msg(_LOG_PREFIX, f"text_positive: {text_positive}")
            log.msg(_LOG_PREFIX, f"text_negative: {text_negative}")
            log.msg(_LOG_PREFIX, f"text_positive_styled: {text_positive_styled}")
            log.msg(_LOG_PREFIX, f"text_negative_styled: {text_negative_styled}")

        return text_positive_styled, text_negative_styled


NODE_NAME = 'Prompt Styler [Eclipse]'
NODE_DESC = 'Prompt Styler'

NODE_CLASS_MAPPINGS = {
   NODE_NAME: RvText_PromptStyler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

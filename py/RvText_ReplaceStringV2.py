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
# For advanced options (shot_style, age, remove_nsfw, watermark, sense_preservation), use V3.

import re
import os
import json
from ..core import CATEGORY

# Import processor lazily inside execute to reduce import-time overhead
from ..core.logger import log

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
        
        # Apply custom regex replacement if provided
        if regex and s:
            try:
                pattern = re.compile(regex, re.IGNORECASE)
                s = pattern.sub(replace_with, s)
            except re.error as e:
                # Log error but continue processing
                log.warning("ReplaceStringV2", f"Regex error: {e}")

        # Use SmartTextProcessor for category detection & edits
        try:
            from ..core.smart_text_processor import get_default_processor
            processor = get_default_processor()

            matches_all = []

            # Category flags mapping
            flag_to_cat = {
                'remove_image': 'image_styles',
                'remove_subject': 'subjects',
                'remove_background': 'backgrounds',
                'remove_mood': 'atmosphere_moods',  # Only remove image atmosphere, keep subject expressions
            }

            to_remove = []
            # Explicit flags mapping to avoid relying on locals()
            flags = {
                'remove_image': remove_image,
                'remove_subject': remove_subject,
                'remove_background': remove_background,
                'remove_mood': remove_mood,
            }
            
            # Log which removal options are enabled
            enabled_flags = [flag for flag, value in flags.items() if value]
            if enabled_flags:
                log.debug("ReplaceStringV2", f"Removal options enabled: {', '.join(enabled_flags)}")
            
            for flag, cat in flag_to_cat.items():
                if flags.get(flag):
                    ms = processor.detect(s, categories=[cat])
                    matches_all.extend(ms)
                    to_remove.extend(ms)

            # Remove instruction prefixes if requested
            if remove_instructions:
                ip_pat = processor.compiled.get('instruction_prefixes')
                if ip_pat:
                    m = ip_pat.search(s)
                    if m:
                        s = s[m.end():].lstrip()

            # Handle LLM lists: either select first item or convert whole list to a single-line string
            # Priority: if list_select_first is True, it takes precedence over list_to_string
            if list_select_first:
                # capture numbered/bulleted list items (per-line)
                items = re.findall(r"^\s*(?:\d+[\.)]|\d+\s*-|[-\*]+)\s*(.+)$", s, flags=re.M)
                # fallback: inline numeric items like '1. first; 2. second'
                if not items:
                    items = re.findall(r"\d+[\.)]\s*([^;\n]+)", s)
                if items:
                    s = items[0].strip()

            elif list_to_string:
                items = re.findall(r"^\s*(?:\d+[\.)]|\d+\s*-|[-\*]+)\s*(.+)$", s, flags=re.M)
                if not items:
                    items = re.findall(r"\d+[\.)]\s*([^;\n]+)", s)
                if items:
                    s = ", ".join(i.strip() for i in items)

            if to_remove:
                # Build list of categories to preserve (those with flags set to False)
                preserve_categories = []
                for flag, cat in flag_to_cat.items():
                    if not flags.get(flag):
                        preserve_categories.append(cat)
                
                # Log before and after removal
                before_len = len(s)
                before_text = s[:100] + "..." if len(s) > 100 else s
                log.debug("ReplaceStringV2", f"Text before removal (len={before_len}): {before_text}")
                
                s = processor.remove_matches(s, to_remove, preserve_categories=preserve_categories if preserve_categories else None)
                
                after_len = len(s)
                after_text = s[:100] + "..." if len(s) > 100 else s
                log.debug("ReplaceStringV2", f"Text after removal (len={after_len}): {after_text}")
                
                if before_len == after_len:
                    log.warning("ReplaceStringV2", "Text length unchanged after removal - no actual removal occurred!")

            # cleanup: remove surrounding quotes and trim
            if cleanup:
                s = s.strip()
                if len(s) >= 2 and ((s[0] == s[-1]) and s[0] in ('"', "'")):
                    s = s[1:-1].strip()

        except Exception as e:
            log.warning('ReplaceStringV2', f'Processor integration failed: {e}')

        # Log final return value
        final_text = s[:100] + "..." if len(s) > 100 else s
        log.debug("ReplaceStringV2", f"Returning final text (len={len(s)}): {final_text}")
        
        return (s,)


NODE_NAME = 'Replace String v2 [Eclipse]'
NODE_DESC = 'Replace String v2'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvText_ReplaceStringV2
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

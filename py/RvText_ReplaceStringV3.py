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
import os
import json
from datetime import datetime
from ..core import CATEGORY
from ..core.logger import log

# Lazy import SmartTextProcessor inside execute to avoid heavy imports during node registration

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
                "remove_image": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove image description matches."}),
                "remove_shot_style": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove camera angles and shot types (close-up, portrait, from above, cowboy shot, looking at viewer, etc.)."}),
                "remove_subject": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove subject description matches."}),
                "remove_background": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove background description matches."}),
                "remove_mood": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Whether to remove mood description matches."}),
                "adjust_age": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Replace age references with the specified target age."}),
                "age": ("INT", {"default": 25, "min": 18, "max": 99, "step": 1, "tooltip": "Target age to use when adjust_age is enabled."}),
                "nsfw_handling": (["none", "soften", "remove"], {"default": "none", "tooltip": "How to handle NSFW content: 'none' (keep as-is), 'soften' ('nude woman' → 'woman', preserves structure), 'remove' (delete NSFW content entirely)."}),
                "remove_watermark": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "Remove phrases containing 'watermark' (e.g., 'has a watermark in the top left corner')."}),
                "cleanup": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, trim whitespace and remove surrounding quotes from the final output."}),
                #"debug_mode": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "When enabled, save before/after comparisons to debug JSON file for batch analysis."}),
            }
        }

    def execute(
        self,
        string: str,
        regex: str = "",
        replace_with: str = "",
        nsfw_handling: str = "none",
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
        remove_watermark: bool = False,
        cleanup: bool = False,
        #debug_mode: bool = False,
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
                log.warning("ReplaceStringV3", f"Regex error: {e}")

        # Age adjustment - normalize age references early (before other processing)
        if adjust_age and s:
            from ..core.regex_helper import adjust_age as adjust_age_func
            s = adjust_age_func(s, age)

        # Integrate with SmartTextProcessor
        try:
            from ..core.smart_text_processor import get_default_processor
            processor = get_default_processor()

            # Load soften map if nsfw_handling is 'soften'
            soften_map = {}
            if nsfw_handling == 'soften':
                try:
                    # Load from subjects.json soften_map
                    subjects_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'patterns', 'subjects.json')
                    with open(subjects_path, 'r', encoding='utf-8') as fh:
                        subjects_data = json.load(fh)
                        soften_map_data = subjects_data.get('soften_map', {})
                        # Extract map (skip description key)
                        soften_map = {k: v for k, v in soften_map_data.items() if k != 'description'}
                except Exception:
                    soften_map = {}

            matches_all = []

            # Remove/soften categories depending on options
            flag_to_cat = {
                'nsfw_handling': 'subjects',
                'remove_watermark': 'watermarks',
                'remove_image': 'image_styles',
                'remove_shot_style': 'shot_styles',
                'remove_subject': 'subjects',
                'remove_background': 'backgrounds',
                'remove_mood': 'atmosphere_moods',  # Only remove image atmosphere, keep subject expressions
            }

            to_remove = []
            to_soften = []
            # Explicit flags mapping to avoid relying on locals()
            flags = {
                'nsfw_handling': nsfw_handling != 'none',
                'remove_watermark': remove_watermark,
                'remove_image': remove_image,
                'remove_shot_style': remove_shot_style,
                'remove_subject': remove_subject,
                'remove_background': remove_background,
                'remove_mood': remove_mood,
            }
            
            # Log which removal options are enabled
            enabled_flags = [flag for flag, value in flags.items() if value]
            if enabled_flags:
                log.debug("ReplaceStringV3", f"Removal options enabled: {', '.join(enabled_flags)}")
            
            for flag, cat in flag_to_cat.items():
                if flags.get(flag):
                    ms = processor.detect(s, categories=[cat])
                    matches_all.extend(ms)
                    if flag == 'nsfw_handling' and nsfw_handling == 'soften':
                        # Soften mode: use full subject context, soften_map filters what gets replaced
                        to_soften.extend(ms)
                    elif flag == 'nsfw_handling' and nsfw_handling == 'remove':
                        # Remove mode: only remove NSFW terms, keep innocent subjects
                        nsfw_only = [m for m in ms if m['text'].lower().strip() in soften_map]
                        to_remove.extend(nsfw_only)
                    else:
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

            if to_soften:
                s = processor.soften_matches(s, to_soften, soften_map)

            if to_remove:
                # Build list of categories to preserve (those with flags set to False)
                # This enables smart overlap handling: if "shoot" appears in both image_styles
                # and shot_styles, and only image is being removed, "shoot from above" is preserved.
                preserve_categories = []
                for flag, cat in flag_to_cat.items():
                    if not flags.get(flag):
                        preserve_categories.append(cat)
                
                # Log before and after removal
                before_len = len(s)
                before_text = s[:100] + "..." if len(s) > 100 else s
                log.debug("ReplaceStringV3", f"Text before removal (len={before_len}): {before_text}")
                
                s = processor.remove_matches(s, to_remove, preserve_categories=preserve_categories if preserve_categories else None)
                
                after_len = len(s)
                after_text = s[:100] + "..." if len(s) > 100 else s
                log.debug("ReplaceStringV3", f"Text after removal (len={after_len}): {after_text}")
                
                if before_len == after_len:
                    log.warning("ReplaceStringV3", "Text length unchanged after removal - no actual removal occurred!")

            # cleanup: remove surrounding quotes and trim
            if cleanup:
                s = s.strip()
                if len(s) >= 2 and ((s[0] == s[-1]) and s[0] in ('"', "'")):
                    s = s[1:-1].strip()

        except Exception as e:
            log.warning('ReplaceStringV3', f'Processor integration failed: {e}')

        # Log final output
        final_text = s[:100] + "..." if len(s) > 100 else s
        log.debug("ReplaceStringV3", f"Returning final text (len={len(s)}): {final_text}")
        
        # Debug mode: save before/after to JSON for batch analysis
        try:
            if debug_mode:
                try:
                    # Create debug folder if it doesn't exist
                    debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug")
                    os.makedirs(debug_dir, exist_ok=True)
                    
                    # Use date in filename to keep existing files
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    debug_file = os.path.join(debug_dir, f"debug_replacements_{date_str}.json")
                    
                    debug_entry = {
                        "before": string,
                        "after": s
                    }
                    
                    # Load existing entries or create new array
                    if os.path.exists(debug_file):
                        with open(debug_file, 'r', encoding='utf-8') as f:
                            debug_data = json.load(f)
                    else:
                        debug_data = []
                    
                    # Append new entry
                    debug_data.append(debug_entry)
                    
                    # Save back to file
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump(debug_data, f, ensure_ascii=False, indent=2)
                        
                except Exception as e:
                    log.warning("ReplaceStringV3", f"Failed to save debug data: {e}")
        except NameError:
            pass  # debug_mode not defined, skip debug output
        
        return (s,)       

NODE_NAME = 'Replace String v3 [Eclipse]'
NODE_DESC = 'Replace String v3'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvText_ReplaceStringV3
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

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

import csv
import json
import os
import re

from typing import Any, Dict, List, Optional, Tuple
from ..core import CATEGORY
from ..core.logger import log


def warning_log(message):
    log.warning("Style Loader", message)


def msg_log(message):
    log.msg("Style Loader", message)


def error_log(message):
    log.error("Style Loader", message)


def debug_log(message):
    log.debug("Style Loader", message)


def read_json_file(file_path: str) -> Optional[List[Dict]]:
    """
    Reads a JSON file's content and returns it.
    Ensures content matches the expected format.
    """
    if not os.access(file_path, os.R_OK):
        warning_log(f"No read permissions for file {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = json.load(file)
            # Check if the content matches the expected format.
            if not all(['name' in item and 'prompt' in item and 'negative_prompt' in item for item in content]):
                warning_log(f"Invalid content in file {file_path}")
                return None
            return content
    except Exception as e:
        error_log(f"An error occurred while reading {file_path}: {str(e)}")
        return None


def read_csv_file(file_path: str) -> Optional[List[Dict]]:
    """
    Reads a CSV file's content and returns it as a list of dicts.
    Expected format: name,prompt,negative_prompt
    """
    if not os.access(file_path, os.R_OK):
        warning_log(f"No read permissions for file {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            content = []
            for row in reader:
                # Ensure required fields exist
                if 'name' in row and 'prompt' in row:
                    content.append({
                        'name': row['name'].strip('"').strip(),
                        'prompt': row['prompt'].strip('"').strip() if row.get('prompt') else '{prompt}',
                        'negative_prompt': row.get('negative_prompt', '').strip('"').strip()
                    })
            return content if content else None
    except Exception as e:
        error_log(f"An error occurred while reading CSV {file_path}: {str(e)}")
        return None


def read_style_file(file_path: str) -> Optional[List[Dict]]:
    """
    Reads a style file (JSON, CSV, or TXT) and returns the content.
    TXT files are expected to have CSV format (name,prompt,negative_prompt).
    """
    if file_path.endswith('.json'):
        return read_json_file(file_path)
    elif file_path.endswith('.csv') or file_path.endswith('.txt'):
        return read_csv_file(file_path)
    else:
        warning_log(f"Unsupported file format: {file_path}")
        return None


def get_all_style_files(directory: str) -> List[str]:
    """
    Returns all style files (JSON, CSV, TXT) from the specified directory.
    """
    return [os.path.join(directory, file) for file in os.listdir(directory) 
            if (file.endswith('.json') or file.endswith('.csv') or file.endswith('.txt')) 
            and os.path.isfile(os.path.join(directory, file))]


def detect_style_type(prompt: str) -> Optional[str]:
    """Suffix-first detection (inspect only the part AFTER {prompt} when present).

    Returns:
      - 'tag_based' or 'natural_language' when a decision can be made
      - None when the template is explicitly the base placeholder ('{prompt}')
        which should be ignored by auto-detection.

    Rules:
    - If there's no suffix (nothing after {prompt}) -> 'tag_based'.
    - If suffix contains punctuation (.,!?), return 'natural_language'.
    - If suffix contains strong markers ('with', 'featuring', 'depicting', 'showing'), return 'natural_language'.
    - Otherwise split suffix on commas and count "short" segments (1-4 tokens). If >=50% short -> 'tag_based'.
    - Fallback: classify by token count threshold (<=4 tokens -> tag_based).
    """
    if not prompt:
        return 'tag_based'

    # If the template is exactly the placeholder, don't attempt to classify it here
    if prompt.strip() == '{prompt}':
        return None

    # Extract suffix only (ignore prefix)
    if '{prompt}' in prompt:
        suffix = prompt.split('{prompt}', 1)[1].strip() if len(prompt.split('{prompt}', 1)) > 1 else ''
    else:
        suffix = ''

    # If no suffix, nothing to classify -> default to tag_based
    if not suffix:
        return 'tag_based'

    s = suffix
    # punctuation is a strong NL signal
    if any(p in s for p in ('.', '!', '?')):
        return 'natural_language'

    s_low = s.lower()
    strong_markers = (' with ', ' featuring ', ' depicting ', ' showing ')
    if any(m in s_low for m in strong_markers):
        return 'natural_language'

    token_re = re.compile(r'"[^\"]+"|\'[^\']+\'|[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*')

    segments = [seg.strip() for seg in s.split(',') if seg.strip()]
    if segments:
        short = 0
        weak_markers = (' and ', ' in ', ' by ', ' for ')
        for seg in segments:
            seg_low = f" {seg.lower()} "
            toks = token_re.findall(seg)
            # treat segments with weak markers as NL only when long
            if any(marker in seg_low for marker in weak_markers) and len(toks) > 2:
                continue
            if seg_low.startswith(' and ') and len(toks) > 1:
                continue
            if 1 <= len(toks) <= 4:
                short += 1
        return 'tag_based' if (short / len(segments)) >= 0.5 else 'natural_language'

    # No comma segments: fallback by token count
    toks = token_re.findall(s)
    return 'tag_based' if len(toks) <= 4 else 'natural_language'


def load_styles_from_directory(directory: str) -> Tuple[Dict[str, List[Dict]], Dict[str, List[str]]]:
    """
    Loads styles from style files in the directory, organized by mode.
    Files starting with 'tag_based' go to 'tag_based' mode.
    Files starting with 'natural_lang' go to 'natural_language' mode.
    Custom files are auto-detected and added to appropriate mode + 'custom' mode.
    Duplicates are filtered out (existing styles in a mode are not overwritten).
    """
    styles_by_mode = {'tag_based': [], 'natural_language': [], 'custom': []}
    names_by_mode = {'tag_based': [], 'natural_language': [], 'custom': []}
    
    all_files = get_all_style_files(directory)
    custom_styles = []  # Collect custom styles for processing after main files
    
    # First pass: load tag_based and natural_lang files
    for style_file in all_files:
        filename = os.path.basename(style_file)
        style_data = read_style_file(style_file)
        
        if not style_data:
            continue
            
        # Determine which mode this file belongs to
        if filename.startswith('tag_based'):
            mode = 'tag_based'
        elif filename.startswith('natural_lang'):
            mode = 'natural_language'
        else:
            # Custom file - save for later processing
            custom_styles.extend(style_data)
            continue
        
        # Add styles to the appropriate mode. Special-case 'base' entries so they
        # are stored in 'custom' only once and not duplicated across modes.
        seen = set(names_by_mode[mode])
        for item in style_data:
            style_name = item['name']
            prompt = item.get('prompt', '')
            # If this is an explicit base/placeholder entry, move it to custom (once)
            if style_name.strip().lower() == 'base' and (prompt or '').strip() == '{prompt}':
                if 'base' not in names_by_mode['custom']:
                    styles_by_mode['custom'].append(item)
                    names_by_mode['custom'].append('base')
                continue
            if style_name not in seen:
                seen.add(style_name)
                styles_by_mode[mode].append(item)
                names_by_mode[mode].append(style_name)
    
    # Second pass: process custom styles
    # 1. Add all to 'custom' mode
    # 2. Auto-detect type and add to tag_based/natural_language if not duplicate
    custom_seen = set()
    for item in custom_styles:
        style_name = item['name']
        prompt = item.get('prompt', '')
        
        # Add to custom mode (filter duplicates within custom)
        if style_name not in custom_seen:
            custom_seen.add(style_name)
            styles_by_mode['custom'].append(item)
            names_by_mode['custom'].append(style_name)
        
        # Ignore explicit 'base' entries or empty placeholder prompts when auto-detecting
        # These are commonly used to disable a style and should not be auto-categorized
        if (prompt or '').strip() == '{prompt}' or style_name.strip().lower() == 'base':
            continue

        # Auto-detect style type and add to appropriate mode if not duplicate
        detected_mode = detect_style_type(prompt)
        if detected_mode not in ('tag_based', 'natural_language'):
            continue
        if style_name not in names_by_mode[detected_mode]:
            styles_by_mode[detected_mode].append(item.copy())
            names_by_mode[detected_mode].append(style_name)
    
    # Ensure 'base' style exists in ALL modes (pass-through for original prompt)
    # This allows users to select 'base' regardless of which style_mode is active
    base_style = {'name': 'base', 'prompt': '{prompt}', 'negative_prompt': ''}
    for mode in ('tag_based', 'natural_language', 'custom'):
        if 'base' not in names_by_mode[mode]:
            styles_by_mode[mode].insert(0, base_style.copy())
            names_by_mode[mode].insert(0, 'base')
    
    return styles_by_mode, names_by_mode


def validate_json_data(json_data: List[Dict]) -> bool:
    """
    Validates the structure of the JSON data.
    """
    if not isinstance(json_data, list):
        return False
    for template in json_data:
        if 'name' not in template or 'prompt' not in template:
            return False
    return True


def find_template_by_name(json_data: List[Dict], template_name: str) -> Optional[Dict]:
    """
    Returns a template from the JSON data by name or None if not found.
    """
    for template in json_data:
        if template['name'] == template_name:
            return template
    return None


def get_styles_directory() -> str:
    """
    Get the styles directory path.
    First looks for 'models/Eclipse/styles' folder (user folder, persists across updates).
    Falls back to 'templates/styles' folder in ComfyUI_Eclipse if not found.
    """
    # Try Eclipse user folder first (models/Eclipse/styles)
    current_directory = os.path.dirname(os.path.realpath(__file__))
    parent_directory = os.path.dirname(current_directory)
    comfyui_root = os.path.abspath(os.path.join(parent_directory, '..', '..'))
    eclipse_styles_dir = os.path.join(comfyui_root, 'models', 'Eclipse', 'styles')
    
    if os.path.exists(eclipse_styles_dir):
        return eclipse_styles_dir
    
    # Fallback to repo templates folder
    repo_styles_dir = os.path.join(parent_directory, "templates", "styles")
    return repo_styles_dir


class RvText_PromptStyler:
    """
    Load and apply prompt styles from JSON or CSV files.
    Replaces {prompt} placeholder with your positive prompt and combines negative prompts.
    Style files should be placed in the 'templates/styles' folder of ComfyUI_Eclipse.
    """
    
    # Class-level storage for styles by mode
    styles_by_mode = {}
    names_by_mode = {}

    def __init__(self):
        pass

    @classmethod
    def reload_styles(cls):
        """Reload styles from disk. Call this when style files are modified."""
        styles_directory = get_styles_directory()
        cls.styles_by_mode, cls.names_by_mode = load_styles_from_directory(styles_directory)
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
        styles_directory = get_styles_directory()
        
        # Load all styles organized by mode
        cls.styles_by_mode, cls.names_by_mode = load_styles_from_directory(styles_directory)
        
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
                "index": ("INT", {"default": 0, "min": 0, "max": 999999, "step": 1, "tooltip": "Style index for batch processing. Controlled by index_control setting."}),
                "index_control": (["fixed", "increment", "decrement", "random"], {"default": "fixed", "tooltip": "How to update index: fixed (use widget value), increment/decrement (cycle through styles), random (pick randomly)."}),
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
        """
        Convert spaces to underscores in comma-separated segments that have
        at most max_words words. Segments with more words are left unchanged
        (assumed to be natural language).
        """
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
        index_control: str,
        spaces_to_underscores: bool,
        max_words_to_combine: int,
        text_positive: str, 
        apply_to_positive: bool,
        apply_to_negative: bool,
        log_prompt: bool,
        text_negative: str = ""
    ) -> Tuple[str, str]:
        """
        Process and combine prompts in templates.
        The function replaces the positive prompt placeholder in the template,
        and combines the negative prompt with the template's negative prompt, if they exist.
        """
        # Get styles for the selected mode
        mode_styles = self.styles_by_mode.get(style_mode, [])
        
        # If index >= 0, use index to select style (with wrapping)
        if index >= 0 and mode_styles:
            actual_index = index % len(mode_styles)
            template = mode_styles[actual_index]
            style = template.get('name', style)
            if log_prompt:
                debug_log(f"Using index {index} (wrapped to {actual_index}) - style: {style} (mode: {style_mode})")
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
                warning_log(f"Style '{style}' not found")

        # If apply_to_positive is disabled, return original positive prompt
        if not apply_to_positive:
            text_positive_styled = text_positive
            if log_prompt:
                debug_log("apply_to_positive: disabled")

        # If apply_to_negative is disabled, return original negative prompt
        if not apply_to_negative:
            text_negative_styled = text_negative
            if log_prompt:
                debug_log("apply_to_negative: disabled")

        # Apply spaces to underscores conversion if enabled
        if spaces_to_underscores:
            if apply_to_positive:
                text_positive_styled = self._convert_spaces_to_underscores(text_positive_styled, max_words_to_combine)
            if apply_to_negative:
                text_negative_styled = self._convert_spaces_to_underscores(text_negative_styled, max_words_to_combine)
            if log_prompt:
                debug_log(f"Applied spaces_to_underscores (max_words: {max_words_to_combine})")

        # Log the styled prompts if logging is enabled
        if log_prompt:
            msg_log(f"style: {style}")
            msg_log(f"text_positive: {text_positive}")
            msg_log(f"text_negative: {text_negative}")
            msg_log(f"text_positive_styled: {text_positive_styled}")
            msg_log(f"text_negative_styled: {text_negative_styled}")

        return text_positive_styled, text_negative_styled


NODE_NAME = 'Prompt Styler [Eclipse]'
NODE_DESC = 'Prompt Styler'

NODE_CLASS_MAPPINGS = {
   NODE_NAME: RvText_PromptStyler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}
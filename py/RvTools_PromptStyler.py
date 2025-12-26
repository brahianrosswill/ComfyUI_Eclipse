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


def detect_style_type(prompt: str) -> str:
    """
    Detect if a style prompt is tag-based or natural language.
    
    Tag-based indicators:
    - Has '. ' separator after {prompt}
    - Many comma-separated short phrases
    - Starts with lowercase descriptive words
    
    Natural language indicators:
    - Starts with articles (A, An, The)
    - Has flowing sentence structure
    - Uses prepositions like 'of', 'with', 'in'
    """
    if not prompt or '{prompt}' not in prompt:
        return 'tag_based'  # Default
    
    # Get the part after {prompt}
    parts = prompt.split('{prompt}')
    prefix = parts[0].strip() if parts else ""
    suffix = parts[1].strip() if len(parts) > 1 else ""
    
    # Check for tag-based indicators
    # 1. Suffix starts with '. ' (common in tag-based styles)
    if suffix.startswith('.') or suffix.startswith(','):
        return 'tag_based'
    
    # 2. Prefix starts with lowercase word (tag-based often do this)
    if prefix and prefix[0].islower():
        return 'tag_based'
    
    # Check for natural language indicators
    # 1. Prefix starts with article
    natural_starters = ('A ', 'An ', 'The ', 'This ')
    if any(prefix.startswith(s) for s in natural_starters):
        return 'natural_language'
    
    # 2. Contains natural language patterns
    natural_patterns = [' of ', ' with ', ' featuring ', ' depicting ', ' showing ']
    if any(p in prompt.lower() for p in natural_patterns):
        return 'natural_language'
    
    # Default to tag_based
    return 'tag_based'


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
        
        # Add styles to the appropriate mode
        seen = set(names_by_mode[mode])
        for item in style_data:
            style_name = item['name']
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
        
        # Auto-detect style type and add to appropriate mode if not duplicate
        detected_mode = detect_style_type(prompt)
        if style_name not in names_by_mode[detected_mode]:
            styles_by_mode[detected_mode].append(item.copy())
            names_by_mode[detected_mode].append(style_name)
    
    # Ensure 'base' style exists in custom mode (pass-through for original prompt)
    if 'base' not in custom_seen:
        base_style = {'name': 'base', 'prompt': '{prompt}', 'negative_prompt': ''}
        styles_by_mode['custom'].insert(0, base_style)
        names_by_mode['custom'].insert(0, 'base')
    
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


class RvTools_PromptStyler:
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
                "index": ("INT", {"default": 0, "min": 0, "max": 999999, "step": 1, "control_after_generate": True, "tooltip": "Style index for batch processing. Use control_after_generate to randomize or increment through styles."}),
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
    CATEGORY = CATEGORY.MAIN.value + CATEGORY.TOOLS.value

    def prompt_styler(
        self, 
        style_mode: str,
        style: str,
        index: int,
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
                
                # Build final prompt: prefix, user prompt, comma, suffix
                if prefix and suffix:
                    text_positive_styled = f"{prefix} {text_positive_clean}, {suffix}"
                elif prefix:
                    text_positive_styled = f"{prefix} {text_positive_clean}"
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

        # Log the styled prompts if logging is enabled
        if log_prompt:
            msg_log(f"style: {style}")
            debug_log(f"text_positive: {text_positive}")
            debug_log(f"text_negative: {text_negative}")
            debug_log(f"text_positive_styled: {text_positive_styled}")
            debug_log(f"text_negative_styled: {text_negative_styled}")

        return text_positive_styled, text_negative_styled


NODE_NAME = 'Prompt Styler [Eclipse]'
NODE_DESC = 'Prompt Styler'

NODE_CLASS_MAPPINGS = {
   NODE_NAME: RvTools_PromptStyler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}
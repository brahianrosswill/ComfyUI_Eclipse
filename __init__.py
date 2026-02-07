# Comfyui_Eclipse Extension Loader
#
# Initializes and loads all custom nodes for Comfyui_Eclipse, providing NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS for the extension.
#
# Author: r-vage
#
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
WEB_DIRECTORY = "./js"

import importlib.util
import os
import json
import __main__
from .core import version
from .core.logger import log, cstr
from aiohttp import web 
import server
import folder_paths

from typing import Any, Dict, Type

NODE_CLASS_MAPPINGS: Dict[str, Type[Any]] = {}
NODE_DISPLAY_NAME_MAPPINGS: Dict[str, str] = {}

log.msg("Eclipse", f"Version: {version}")

# Early check of wrappers (for consistent startup logging)
try:
    from .core import gguf_wrapper
except Exception as e:
    log.warning("GGUF Wrapper", f"Failed to load: {e}")

try:
    from .core import nunchaku_wrapper
except Exception as e:
    log.warning("Nunchaku Wrapper", f"Failed to load: {e}")

def get_ext_dir(subpath=None, mkdir=False):
    dir = os.path.dirname(__file__)
    if subpath is not None:
        dir = os.path.join(dir, subpath)
    dir = os.path.abspath(dir)
    if mkdir and not os.path.exists(dir):
        os.makedirs(dir)
    return dir

# Initialize Eclipse folder structure with templates (one-time copy on first run)
from .core.common import copy_prompt_files_once, create_junction, migrate_old_folders
import sys

comfyui_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
eclipse_dir = os.path.join(comfyui_root, 'models', 'Eclipse')

# Migrate user files from old locations (one-time migration)
migrate_old_folders(comfyui_root)

# Copy templates to models/Eclipse/ structure
repo_templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
repo_prompt_dir = os.path.join(repo_templates_dir, 'prompt')
repo_loader_dir = os.path.join(repo_templates_dir, 'loader_templates')
repo_styles_dir = os.path.join(repo_templates_dir, 'styles')
repo_patterns_dir = os.path.join(repo_templates_dir, 'patterns')

eclipse_prompt_dir = os.path.join(eclipse_dir, 'smart_prompt')
eclipse_loader_dir = os.path.join(eclipse_dir, 'loader_templates')
eclipse_styles_dir = os.path.join(eclipse_dir, 'styles')
eclipse_patterns_dir = os.path.join(eclipse_dir, 'patterns')

# Check if force_update or dev_mode is enabled in config
force_update = False
dev_mode = False
config_file = os.path.join(os.path.dirname(__file__), 'eclipse_config.json')
if os.path.exists(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            force_update = config_data.get('_force_update', False)
            dev_mode = config_data.get('dev_mode', False)
    except Exception:
        pass

def is_folder_empty_or_missing(folder_path):
    if not os.path.exists(folder_path):
        return True
    try:
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json') and os.path.isfile(os.path.join(folder_path, f))]
        return len(json_files) == 0
    except Exception:
        return True

# Dev mode: skip all template copying (work directly with repo templates)
if dev_mode:
    log.msg("Eclipse", "Dev mode enabled - using repo templates directly")
else:
    # One-time copy of templates to Eclipse folder
    if not os.path.exists(eclipse_prompt_dir) and os.path.exists(repo_prompt_dir):
        copy_prompt_files_once(repo_prompt_dir, eclipse_prompt_dir)

    if not os.path.exists(eclipse_loader_dir) and os.path.exists(repo_loader_dir):
        copy_prompt_files_once(repo_loader_dir, eclipse_loader_dir)

    # Styles folder: copy on first run (user can add custom styles that persist across updates)
    if not os.path.exists(eclipse_styles_dir) and os.path.exists(repo_styles_dir):
        copy_prompt_files_once(repo_styles_dir, eclipse_styles_dir)
        log.msg("Eclipse", "Style files copied to models/Eclipse/styles/")

    # Patterns folder: copy if missing/empty OR force_update
    patterns_folder_empty = is_folder_empty_or_missing(eclipse_patterns_dir)
    if patterns_folder_empty and os.path.exists(repo_patterns_dir):
        copy_prompt_files_once(repo_patterns_dir, eclipse_patterns_dir, force=True)
        log.msg("Eclipse", "Pattern files copied to models/Eclipse/patterns/")
    elif force_update and os.path.exists(repo_patterns_dir):
        import shutil
        repo_pattern_files = {f for f in os.listdir(repo_patterns_dir) 
                             if os.path.isfile(os.path.join(repo_patterns_dir, f)) and f.endswith('.json')}
        os.makedirs(eclipse_patterns_dir, exist_ok=True)
        for item in repo_pattern_files:
            src = os.path.join(repo_patterns_dir, item)
            dst = os.path.join(eclipse_patterns_dir, item)
            shutil.copy2(src, dst)
        log.msg("Eclipse", f"Force updated {len(repo_pattern_files)} pattern file(s)")

    # Reset force_update flag after updates are complete
    if force_update:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            config_data['_force_update'] = False
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            log.warning("Eclipse", f"Could not reset _force_update flag: {e}")

# Create junction for wildcards/smart_prompt → Eclipse/smart_prompt (no duplication)
wildcards_smartprompt_dir = os.path.join(comfyui_root, 'models', 'wildcards', 'smart_prompt')
if not os.path.exists(wildcards_smartprompt_dir) and os.path.exists(eclipse_prompt_dir):
    create_junction(eclipse_prompt_dir, wildcards_smartprompt_dir)

# Update references to use Eclipse folder
models_smartprompt_dir = eclipse_prompt_dir
models_loader_dir = eclipse_loader_dir
repo_prompt_dir = eclipse_prompt_dir

# Load all node modules from py/ directory
py = get_ext_dir("py")
files = os.listdir(py)
for file in files:
    if not file.endswith(".py"):
        continue
    name = os.path.splitext(file)[0]
    imported_module = importlib.import_module(f".py.{name}", __name__)
    try:
        NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **imported_module.NODE_CLASS_MAPPINGS}
        NODE_DISPLAY_NAME_MAPPINGS = {**NODE_DISPLAY_NAME_MAPPINGS, **imported_module.NODE_DISPLAY_NAME_MAPPINGS}
    except Exception:
        pass

# Initialize server endpoints
try:
    from .core.server_endpoints import initialize_endpoints
    initialize_endpoints()
except Exception as e:
    log.warning("Eclipse", f"Failed to initialize server endpoints: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
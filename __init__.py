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
import re
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

# Message templates are now defined in logger.py
log.msg("Eclipse", f"Version: {version}")

# Initialize LLM paths early (before any SmartLM operations)
# This ensures config exists and detects the correct LLM folder for the user's ComfyUI installation
try:
    from .core.smartlm_templates import ensure_eclipse_config_exists, initialize_llm_paths
    ensure_eclipse_config_exists()  # Create config with defaults if missing
    initialize_llm_paths()  # Auto-detect and update LLM paths
except Exception as e:
    log.warning("Eclipse", f"Could not initialize LLM paths: {e}")

# Early check of wrappers (for consistent startup logging)
try:
    from .core import gguf_wrapper
except Exception as e:
    log.warning("GGUF Wrapper", f"Failed to load: {e}")

try:
    from .core import nunchaku_wrapper
except Exception as e:
    log.warning("Nunchaku Wrapper", f"Failed to load: {e}")

try:
    from .core import florence2_wrapper
    # Show tip if using fallback (only for v4 - comfyui-florence2 doesn't help on v5)
    if not florence2_wrapper.FLORENCE2_CUSTOM_AVAILABLE and florence2_wrapper.transformers_version < (5, 0):
        log.msg("Florence-2", "Tip: Install comfyui-florence2 extension for better compatibility")
except Exception as e:
    log.warning("Florence-2 Wrapper", f"Failed to load: {e}")

# Quick Docker check (without loading full vllm_docker module)
try:
    import subprocess
    result = subprocess.run(
        ["docker", "--version"],
        capture_output=True,
        timeout=2,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    )
    if result.returncode == 0:
        version = result.stdout.strip()
        log.msg("Docker", f"✓ {version}")
except FileNotFoundError:
    pass  # Docker not installed - silent (not everyone needs it)
except Exception:
    pass  # Any other error - silent

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
repo_smartlm_dir = os.path.join(repo_templates_dir, 'smartlm_templates')
repo_config_dir = os.path.join(repo_templates_dir, 'config')

eclipse_prompt_dir = os.path.join(eclipse_dir, 'smart_prompt')
eclipse_loader_dir = os.path.join(eclipse_dir, 'loader_templates')
eclipse_smartlm_dir = os.path.join(eclipse_dir, 'smartlm_templates')
eclipse_config_dir = os.path.join(eclipse_dir, 'config')

# Check if force_update or dev_mode is enabled in config
import json
force_update = False
dev_mode = False
config_file = os.path.join(os.path.dirname(__file__), 'eclipse_config.json')
if os.path.exists(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            force_update = config_data.get('_force_update', False)
            dev_mode = config_data.get('dev_mode', False)
    except:
        pass

# Dev mode: skip all template copying (work directly with repo templates)
if dev_mode:
    log.msg("Eclipse", "Dev mode enabled - using repo templates directly")
else:
    # One-time copy of templates to Eclipse folder (smart_prompt and loader - normal behavior)
    if not os.path.exists(eclipse_prompt_dir) and os.path.exists(repo_prompt_dir):
        copy_prompt_files_once(repo_prompt_dir, eclipse_prompt_dir)

    if not os.path.exists(eclipse_loader_dir) and os.path.exists(repo_loader_dir):
        copy_prompt_files_once(repo_loader_dir, eclipse_loader_dir)

    # smartlm_templates: copy on first run (folder doesn't exist) OR force update (overwrite existing)
    if not os.path.exists(eclipse_smartlm_dir):
        # First run: copy templates from repo
        if os.path.exists(repo_smartlm_dir):
            copy_prompt_files_once(repo_smartlm_dir, eclipse_smartlm_dir)
    elif force_update:
        # Force update: only update templates that exist in repo (preserve user templates)
        import shutil
        try:
            # Get list of template files in repo
            repo_templates = set()
            if os.path.exists(repo_smartlm_dir):
                repo_templates = {item for item in os.listdir(repo_smartlm_dir) 
                                if os.path.isfile(os.path.join(repo_smartlm_dir, item)) and item.endswith('.json')}
            
            # Only delete templates that exist in repo (user templates are preserved)
            deleted_count = 0
            for item in os.listdir(eclipse_smartlm_dir):
                if item in repo_templates:
                    item_path = os.path.join(eclipse_smartlm_dir, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        deleted_count += 1
            
            # Copy all templates from repo
            copied_count = 0
            for item in repo_templates:
                src = os.path.join(repo_smartlm_dir, item)
                dst = os.path.join(eclipse_smartlm_dir, item)
                shutil.copy2(src, dst)
                copied_count += 1
            
            log.msg("Eclipse", f"Force updated {copied_count} repo template(s), preserved user templates")
        except Exception as e:
            log.warning("Eclipse", f"Could not fully update templates: {e}")

    # Note: smartlm_prompt_defaults.json and llm_few_shot_training.json are always loaded from repo folder
    # Other config files: copy on first run OR force update if flag is set
    if force_update or not os.path.exists(eclipse_config_dir):
        os.makedirs(eclipse_config_dir, exist_ok=True)
        if force_update and os.path.exists(repo_config_dir):
            # Force update: overwrite config files (except files always loaded from repo)
            import shutil
            skip_files = {'smartlm_prompt_defaults.json', 'llm_few_shot_training.json'}
            for item in os.listdir(repo_config_dir):
                if item not in skip_files:  # Skip files that are always loaded from repo
                    src = os.path.join(repo_config_dir, item)
                    dst = os.path.join(eclipse_config_dir, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
            log.msg("Eclipse", "Force updated config files")

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
models_smartprompt_dir = eclipse_prompt_dir  # For API compatibility
models_loader_dir = eclipse_loader_dir
repo_prompt_dir = eclipse_prompt_dir  # Fallback uses Eclipse copy

# Server endpoints are now consolidated in core/server_endpoints.py

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

# Initialize wildcard processor server endpoints after loading nodes
# This ensures wildcards are loaded when the endpoints are registered
try:
    from .core.server_endpoints import initialize_endpoints
    initialize_endpoints()
except Exception as e:
    log.warning("Eclipse", f"Failed to initialize wildcard processor endpoints: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
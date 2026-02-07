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

# Centralized loader template management for Smart Loader nodes.
#
# This module provides shared template functions for:
# - RvLoader_SmartLoader.py
# - RvLoader_SmartLoader_Plus.py
#
# Templates are stored in models/Eclipse/loader_templates/ (production)
# or templates/loader_templates/ (dev mode).

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

from .logger import log
from .common import get_config_value

# Module log prefix - change here to update all log messages
_LOG_PREFIX = "LoaderTemplates"


# Centralized filename validation (same logic as server_endpoints.is_safe_filename)
def is_safe_template_name(name: str) -> bool:
    # Validate template name to prevent path traversal attacks.
    # Returns True if name is safe (no path separators or traversal).
    if not name or name == "None":
        return False
    # Block path traversal attempts
    if '..' in name or '/' in name or '\\' in name:
        log.warning(_LOG_PREFIX, f"Blocked path traversal attempt: {name}")
        return False
    # Block null bytes
    if '\x00' in name:
        log.warning(_LOG_PREFIX, f"Blocked null byte in name: {repr(name)}")
        return False
    return True

# Try to import folder_paths from ComfyUI
try:
    import folder_paths
    MODELS_DIR = folder_paths.models_dir
except ImportError:
    # Fallback for testing outside ComfyUI
    MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")


def get_template_dir() -> str:
    # Get current template directory (controlled by dev_mode flag).
    #
    # Returns:
    #     Path to loader templates directory
    if get_config_value('dev_mode', False):
        # Dev mode: use repo templates
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'loader_templates')
    # Production mode: use Eclipse folder
    eclipse_dir = os.path.join(MODELS_DIR, "Eclipse", "loader_templates")
    if os.path.exists(eclipse_dir):
        return eclipse_dir
    # Fallback to repo if Eclipse doesn't exist
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'loader_templates')


# Module-level template directory (evaluated at import time)
TEMPLATE_DIR = get_template_dir()


def ensure_template_dir() -> None:
    # Ensure template directory exists.
    os.makedirs(TEMPLATE_DIR, exist_ok=True)


def get_template_list() -> List[str]:
    # Get list of available templates.
    #
    # Returns:
    #     List of template names (without .json extension), with "None" as first item
    ensure_template_dir()
    templates = ["None"]
    try:
        for f in os.listdir(TEMPLATE_DIR):
            if f.endswith('.json'):
                templates.append(f[:-5])
    except Exception:
        pass
    return templates


def save_template(name: str, config: Dict) -> bool:
    # Save a configuration template.
    #
    # Args:
    #     name: Template name (without .json extension)
    #     config: Dictionary of configuration values to save
    #
    # Returns:
    #     True if saved successfully, False otherwise
    
    # Security: validate name to prevent path traversal
    if not is_safe_template_name(name):
        return False
    
    ensure_template_dir()
    template_path = os.path.join(TEMPLATE_DIR, f"{name}.json")
    
    # Security: verify resolved path stays within template directory
    if not os.path.abspath(template_path).startswith(os.path.abspath(TEMPLATE_DIR)):
        log.warning(_LOG_PREFIX, f"Blocked path traversal in save: {name}")
        return False
    
    try:
        with open(template_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        log.error(_LOG_PREFIX, f"Error saving template: {e}")
        return False


def load_template(name: str) -> Dict:
    # Load a configuration template.
    #
    # Args:
    #     name: Template name (without .json extension)
    #
    # Returns:
    #     Dictionary of configuration values, or empty dict if not found
    if name == "None" or not name:
        return {}
    
    # Security: validate name to prevent path traversal
    if not is_safe_template_name(name):
        return {}
    
    template_path = os.path.join(TEMPLATE_DIR, f"{name}.json")
    
    # Security: verify resolved path stays within template directory
    if not os.path.abspath(template_path).startswith(os.path.abspath(TEMPLATE_DIR)):
        log.warning(_LOG_PREFIX, f"Blocked path traversal in load: {name}")
        return {}
    
    try:
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        log.error(_LOG_PREFIX, f"Error loading template: {e}")
    return {}


def delete_template(name: str) -> bool:
    # Delete a configuration template.
    #
    # Args:
    #     name: Template name (without .json extension)
    #
    # Returns:
    #     True if deleted successfully, False otherwise
    if name == "None" or not name:
        return False
    
    # Security: validate name to prevent path traversal
    if not is_safe_template_name(name):
        return False
    
    template_path = os.path.join(TEMPLATE_DIR, f"{name}.json")
    
    # Security: verify resolved path stays within template directory
    if not os.path.abspath(template_path).startswith(os.path.abspath(TEMPLATE_DIR)):
        log.warning(_LOG_PREFIX, f"Blocked path traversal in delete: {name}")
        return False
    
    try:
        if os.path.exists(template_path):
            os.remove(template_path)
            return True
    except Exception as e:
        log.error(_LOG_PREFIX, f"Error deleting template: {e}")
    return False


def get_template_mtime() -> Optional[float]:
    # Get the maximum modification time of all templates.
    #
    # Used by IS_CHANGED to detect template file changes.
    #
    # Returns:
    #     Maximum mtime of template files, or None if directory doesn't exist
    if os.path.exists(TEMPLATE_DIR):
        try:
            json_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.json')]
            if json_files:
                return max(os.path.getmtime(os.path.join(TEMPLATE_DIR, f)) for f in json_files)
        except Exception:
            pass
    return None

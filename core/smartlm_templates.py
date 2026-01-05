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

# SmartLM Templates - Template Loading, Saving, and Configuration
#
# Handles all template-related operations:
# - Loading/saving template JSON files
# - Template directory management
# - Prompt configuration loading
# - Template field updates (local_path, vram_requirement, mmproj_path)
#
# Used by both smartlm_base.py (v1) and smartlm_base_v2.py.

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from .smartlm_types import is_model_architecture_supported
from .logger import log

_LOG_PREFIX = "SmartLM"


# ============================================================================
# Template Context Class
# ============================================================================

class TemplateContext:
    # Context object for template-related operations.
    #
    # Holds all template/widget values in one place, avoiding the need to
    # pass many individual parameters through call chains.
    #
    # Thread-safe: Each execution creates its own context instance.
    #
    # Usage:
    #     # From template dict
    #     ctx = TemplateContext.from_template_info(template_info)
    #     
    #     # From widget values
    #     ctx = TemplateContext.from_widgets(
    #         model_family="LLaVA",
    #         model_type="llava",
    #         loading_method="Ollama (Docker)",
    #     )
    #     
    #     # Update values
    #     ctx.update(has_vision=True, ollama_model="local_llava:latest")
    
    def __init__(self):
        # Core template fields
        self.model_family: str = ""
        self.model_type: str = ""
        self.loading_method: str = ""
        
        # Model source
        self.repo_id: str = ""
        self.local_path: str = ""
        self.ollama_model: str = ""
        self.model_source: str = ""  # "huggingface", "local", "ollama"
        
        # Vision support
        self.mmproj_path: str = ""
        self.mmproj_url: str = ""
        self.has_vision: bool = False
        
        # Configuration
        self.quantization: str = "auto"
        self.attention_mode: str = "auto"
        self.context_size: int = 8192
        self.max_tokens: int = 1024
        
        # Metadata
        self.template_name: str = ""
        self.original_filename: str = ""
        self.quantized: bool = False
        self.default_task: str = ""
        self.default_text_input: str = ""
        
    @classmethod
    def from_template_info(cls, template_info: Dict[str, Any]) -> "TemplateContext":
        # Create context from a template_info dictionary
        ctx = cls()
        if not template_info:
            return ctx
        
        # Map dict keys to context attributes
        ctx.model_family = template_info.get("model_family", "")
        ctx.model_type = template_info.get("model_type", "")
        ctx.loading_method = template_info.get("loading_method", "")
        ctx.repo_id = template_info.get("repo_id", "")
        ctx.local_path = template_info.get("local_path", "")
        ctx.ollama_model = template_info.get("ollama_model", "")
        ctx.model_source = template_info.get("model_source", "")
        ctx.mmproj_path = template_info.get("mmproj_path", "")
        ctx.mmproj_url = template_info.get("mmproj_url", "")
        ctx.quantization = template_info.get("quantization", "auto")
        ctx.attention_mode = template_info.get("attention_mode", "auto")
        ctx.context_size = template_info.get("context_size", 8192)
        ctx.max_tokens = template_info.get("max_tokens", 1024)
        ctx.template_name = template_info.get("template_name", "")
        ctx.quantized = template_info.get("quantized", False)
        ctx.default_task = template_info.get("default_task", "")
        ctx.default_text_input = template_info.get("default_text_input", "")
        ctx.has_vision = template_info.get("has_vision", False)
        
        return ctx
    
    @classmethod
    def from_template_name(cls, template_name: str) -> "TemplateContext":
        # Create context by loading a template by name.
        #
        # Args:
        #     template_name: Name of the template to load
        #
        # Returns:
        #     TemplateContext populated with template values
        template_info = load_template(template_name)
        ctx = cls.from_template_info(template_info)
        ctx.template_name = template_name  # Ensure template_name is set
        return ctx
    
    def update_from_template(self, template_name: str) -> "TemplateContext":
        # Update context with values from a template.
        #
        # Loads the template and updates this context's values.
        # Returns self for chaining.
        #
        # Args:
        #     template_name: Name of the template to load
        if not template_name or template_name == "None":
            return self
            
        template_info = load_template(template_name)
        if not template_info:
            return self
        
        # Update all fields from template
        self.model_family = template_info.get("model_family", self.model_family)
        self.model_type = template_info.get("model_type", self.model_type)
        self.loading_method = template_info.get("loading_method", self.loading_method)
        self.repo_id = template_info.get("repo_id", self.repo_id)
        self.local_path = template_info.get("local_path", self.local_path)
        self.ollama_model = template_info.get("ollama_model", self.ollama_model)
        self.model_source = template_info.get("model_source", self.model_source)
        self.mmproj_path = template_info.get("mmproj_path", self.mmproj_path)
        self.mmproj_url = template_info.get("mmproj_url", self.mmproj_url)
        self.quantization = template_info.get("quantization", self.quantization)
        self.attention_mode = template_info.get("attention_mode", self.attention_mode)
        self.context_size = template_info.get("context_size", self.context_size)
        self.max_tokens = template_info.get("max_tokens", self.max_tokens)
        self.quantized = template_info.get("quantized", self.quantized)
        self.default_task = template_info.get("default_task", self.default_task)
        self.has_vision = template_info.get("has_vision", self.has_vision)
        self.template_name = template_name
        
        return self
    
    @classmethod
    def from_widgets(
        cls,
        model_family: str = "",
        model_type: str = "",
        loading_method: str = "",
        **kwargs,
    ) -> "TemplateContext":
        # Create context from widget values
        ctx = cls()
        ctx.model_family = model_family
        ctx.model_type = model_type
        ctx.loading_method = loading_method
        
        # Apply any additional kwargs
        for key, value in kwargs.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
        
        return ctx
    
    def update(self, **kwargs) -> "TemplateContext":
        # Update context values. Returns self for chaining
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        # Convert context to dictionary (for compatibility)
        return {
            "model_family": self.model_family,
            "model_type": self.model_type,
            "loading_method": self.loading_method,
            "repo_id": self.repo_id,
            "local_path": self.local_path,
            "ollama_model": self.ollama_model,
            "model_source": self.model_source,
            "mmproj_path": self.mmproj_path,
            "mmproj_url": self.mmproj_url,
            "quantization": self.quantization,
            "attention_mode": self.attention_mode,
            "context_size": self.context_size,
            "max_tokens": self.max_tokens,
            "template_name": self.template_name,
            "quantized": self.quantized,
            "default_task": self.default_task,
            "has_vision": self.has_vision,
        }
    
    def save_to_template(self, auto_save: bool = True) -> bool:
        # Save context values to the template file.
        #
        # Only saves certain fields that should be auto-updated:
        # - model_family, loading_method, quantization, attention_mode
        # - max_tokens, default_task, context_size
        #
        # Args:
        #     auto_save: Whether auto-save is enabled (user preference)
        #
        # Returns:
        #     True if saved successfully, False otherwise
        if not auto_save or not self.template_name or self.template_name == "None":
            return False
        
        # Don't modify repo templates in dev_mode
        if get_dev_mode():
            return False
        
        template_path = get_template_dir() / f"{self.template_name}.json"
        try:
            if not template_path.exists():
                return False
                
            with open(template_path, 'r') as f:
                template_data = json.load(f)
            
            # Fields to potentially update (only if value is set and different from stored)
            fields_to_save = {
                "model_family": self.model_family,
                "loading_method": self.loading_method,
                "quantization": self.quantization,
                "attention_mode": self.attention_mode,
                "max_tokens": self.max_tokens,
                "default_task": self.default_task,
            }
            
            # Add context_size only for methods that use it
            if self.loading_method in ("GGUF (llama-cpp-python)", "vLLM (Docker)", "vLLM (Native)", "SGLang (Docker)", "Ollama (Docker)", "llama.cpp (Docker)"):
                fields_to_save["context_size"] = self.context_size
            
            # Track what changed (only save if value exists AND is different from stored)
            changes = []
            for key, value in fields_to_save.items():
                stored_value = template_data.get(key)
                # Only update if: value is set (not empty/None) AND different from stored
                if value and stored_value != value:
                    template_data[key] = value
                    changes.append(f"{key}={value}")
            
            # Save if anything changed
            if changes:
                with open(template_path, 'w') as f:
                    json.dump(template_data, f, indent=2)
                log.msg(_LOG_PREFIX, f"✓ Auto-saved template '{self.template_name}': {', '.join(changes)}")
                return True
                
        except Exception as e:
            log.warning(_LOG_PREFIX, f"Could not auto-save template {self.template_name}: {e}")
        
        return False


# ============================================================================
# Directory Constants and Paths
# ============================================================================

NODE_DIR = Path(__file__).parent.parent
REPO_TEMPLATE_DIR = NODE_DIR / "templates" / "smartlm_templates"

# Config directories
REPO_CONFIG_DIR = NODE_DIR / "templates" / "config"

# Lazy-load folder_paths to avoid import issues
_ECLIPSE_TEMPLATE_DIR = None
_ECLIPSE_CONFIG_DIR = None


def _get_folder_paths():
    # Lazy import folder_paths to avoid circular imports
    import folder_paths
    return folder_paths


def _get_eclipse_template_dir() -> Path:
    # Get Eclipse template directory (user-editable location)
    global _ECLIPSE_TEMPLATE_DIR
    if _ECLIPSE_TEMPLATE_DIR is None:
        folder_paths = _get_folder_paths()
        
        # Ensure we have the correct ComfyUI models directory
        models_dir = folder_paths.models_dir
        if not models_dir or not os.path.isabs(models_dir):
            # Fallback: compute ComfyUI models dir relative to this extension
            comfyui_root = Path(__file__).parent.parent.parent.parent  # Go up to ComfyUI root
            models_dir = str(comfyui_root / "models")
            log.warning(_LOG_PREFIX, f"folder_paths.models_dir not set correctly, using fallback: {models_dir}")
        
        _ECLIPSE_TEMPLATE_DIR = Path(models_dir) / "Eclipse" / "smartlm_templates"
        _ECLIPSE_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        log.debug(_LOG_PREFIX, f"Eclipse template directory: {_ECLIPSE_TEMPLATE_DIR}")
    return _ECLIPSE_TEMPLATE_DIR


def _get_eclipse_config_dir() -> Path:
    # Get Eclipse config directory
    global _ECLIPSE_CONFIG_DIR
    if _ECLIPSE_CONFIG_DIR is None:
        folder_paths = _get_folder_paths()
        _ECLIPSE_CONFIG_DIR = Path(folder_paths.models_dir) / "Eclipse" / "config"
    return _ECLIPSE_CONFIG_DIR


# ============================================================================
# Config File Helpers
# ============================================================================

# Config cache for get_config_value (avoids repeated file I/O)
_config_cache: Dict[str, Any] = {}
_config_cache_time: float = 0.0
_CONFIG_CACHE_TTL: float = 5.0  # Cache for 5 seconds

def get_config_value(key: str, default=None):
    # Get a configuration value from eclipse_config.json (cached)
    import time
    global _config_cache, _config_cache_time
    
    current_time = time.time()
    
    # Check if cache is valid
    if current_time - _config_cache_time < _CONFIG_CACHE_TTL and _config_cache:
        return _config_cache.get(key, default)
    
    # Reload config from file
    config_path = NODE_DIR / "eclipse_config.json"
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                _config_cache = json.load(f)
                _config_cache_time = current_time
                return _config_cache.get(key, default)
    except Exception:
        pass
    return default


def invalidate_config_cache():
    # Invalidate config cache (call after updating config)
    global _config_cache_time
    _config_cache_time = 0.0


def update_config_value(key: str, value, nested_key: str = None) -> bool:
    # Update a configuration value in eclipse_config.json.
    #
    # Args:
    #     key: Top-level key in config
    #     value: Value to set (or dict to merge if nested_key is None)
    #     nested_key: Optional nested key within the top-level dict
    #
    # Returns:
    #     bool: True if successful
    invalidate_config_cache()  # Clear cache before update
    config_path = NODE_DIR / "eclipse_config.json"
    try:
        # Load existing config
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # Update value
        if nested_key:
            if key not in config:
                config[key] = {}
            if not isinstance(config[key], dict):
                config[key] = {}
            config[key][nested_key] = value
        else:
            config[key] = value
        
        # Save config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        log.error(_LOG_PREFIX, f"Config failed to update {key}: {e}")
        return False


def ensure_eclipse_config_exists() -> bool:
    # Ensure eclipse_config.json exists with default values if missing.
    #
    # Creates the config file with safe defaults:
    #   - llm_models_path: "LLM"
    #   - llm_models_absolute_path: "" (empty, will be auto-detected)
    #   - dev_mode: False
    #   - log_level: "warning"
    #
    # Returns:
    #     bool: True if file was created, False if it already existed
    config_path = NODE_DIR / "eclipse_config.json"
    if not config_path.exists():
        default_config = {
            "_comments": {
                "description": "Eclipse ComfyUI Node Configuration",
                "log_level_options": "error | warning | info | debug",
                "llm_models_path": "Relative path from ComfyUI models folder (e.g., 'LLM'). Used for Python file scanning.",
                "llm_models_absolute_path": "REQUIRED FOR DOCKER: Full absolute path to LLM models folder. Docker containers need the complete path for volume mounts.",
                "retry_download_attempts": "Number of times to retry download if hash verification fails (0 to disable auto-retry)"
            },
            "_force_update": False,
            "dev_mode": False,
            "log_level": "warning",
            "llm_models_path": "LLM",
            "llm_models_absolute_path": "",
            "retry_download_attempts": 2
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
            log.msg(_LOG_PREFIX, f"Created default eclipse_config.json")
            return True
        except Exception as e:
            log.error(_LOG_PREFIX, f"Failed to create eclipse_config.json: {e}")
            return False
    return False


def get_dev_mode() -> bool:
    # Check if we should use repo templates directly (dev mode)
    return get_config_value("dev_mode", False)


def get_llm_models_path() -> Path:
    # Get the LLM models directory path from config (for Python file scanning).
    #
    # The path can be:
    # - Relative: Will be joined with ComfyUI's models_dir (e.g., "LLM" -> models/LLM)
    # - Absolute: Will be used directly (e.g., "D:/MyModels/LLM")
    #
    # Returns:
    #     Path to LLM models directory
    import folder_paths
    
    llm_path = get_config_value("llm_models_path", "LLM")
    path = Path(llm_path)
    
    # If absolute path, use directly
    if path.is_absolute():
        return path
    
    # Otherwise, join with ComfyUI models directory
    return Path(folder_paths.models_dir) / llm_path


def get_llm_models_absolute_path() -> str:
    # Get the absolute path to LLM models directory (required for Docker).
    #
    # Docker containers need the complete absolute path for volume mounts.
    # This value MUST be configured in eclipse_config.json for Docker backends to work.
    #
    # Returns:
    #     Absolute path string to LLM models directory
    #
    # Raises:
    #     ValueError: If path is not configured or is empty
    abs_path = get_config_value("llm_models_absolute_path", "")
    
    if not abs_path:
        # Try to derive from relative path as fallback
        derived = get_llm_models_path()
        if derived.exists():
            return str(derived.resolve())
        raise ValueError(
            "llm_models_absolute_path not configured in eclipse_config.json.\n"
            "Docker backends require the full absolute path to your LLM models folder.\n"
            "Example: \"D:/AI/ComfyUI/models/LLM\" or \"/home/user/models/LLM\""
        )
    
    return abs_path


def initialize_llm_paths() -> bool:
    # Initialize LLM model paths in eclipse_config.json at startup.
    #
    # This function:
    # 1. Detects the correct LLM models folder based on llm_models_path config
    # 2. Creates the folder if it doesn't exist (for model downloads)
    # 3. Updates llm_models_absolute_path to always match the derived path
    #
    # The absolute path is ALWAYS derived from llm_models_path + ComfyUI models dir.
    # If user changes llm_models_path (e.g., "LLM" -> "Eclipse"), the absolute path
    # will be updated accordingly on next startup.
    #
    # Called early in __init__.py before any other SmartLM operations.
    #
    # Returns:
    #     bool: True if paths were updated, False if no update was needed
    import folder_paths
    
    # Get current values from config (fallback to "LLM" if empty or not set)
    current_relative = get_config_value("llm_models_path", "LLM")
    if not current_relative or not current_relative.strip():
        current_relative = "LLM"
        # Also update the config to have the default value
        update_config_value("llm_models_path", "LLM")
        log.debug(_LOG_PREFIX, "llm_models_path was empty, using default 'LLM'")
    
    current_absolute = get_config_value("llm_models_absolute_path", "")
    
    # Derive the expected absolute path from ComfyUI's models directory
    relative_path = Path(current_relative)
    if relative_path.is_absolute():
        # User has set an absolute path as llm_models_path, use it directly
        expected_path = relative_path
    else:
        # Normal case: relative path from models folder (e.g., "LLM" or "Eclipse")
        expected_path = Path(folder_paths.models_dir) / current_relative
    
    expected_absolute = str(expected_path.resolve())
    
    # Create the directory if it doesn't exist (needed for model downloads)
    if not expected_path.exists():
        try:
            expected_path.mkdir(parents=True, exist_ok=True)
            log.msg(_LOG_PREFIX, f"Created LLM models folder: {expected_absolute}")
        except Exception as e:
            log.warning(_LOG_PREFIX, f"Could not create LLM models folder '{expected_absolute}': {e}")
    
    # Normalize paths for comparison (handle different separators)
    def normalize_path(p: str) -> str:
        return str(Path(p).resolve()) if p else ""
    
    current_absolute_normalized = normalize_path(current_absolute)
    expected_absolute_normalized = normalize_path(expected_absolute)
    
    # Check if update is needed
    if current_absolute_normalized == expected_absolute_normalized:
        log.debug(_LOG_PREFIX, f"LLM paths already configured correctly: {expected_absolute}")
        return False
    
    # Update the absolute path in config (always sync with derived path)
    success = update_config_value("llm_models_absolute_path", expected_absolute)
    
    if success:
        log.msg(_LOG_PREFIX, f"Updated LLM models path: {expected_absolute}")
    else:
        log.warning(_LOG_PREFIX, f"Failed to update LLM models path in config")
    
    return success


# ============================================================================
# Template Directory Functions
# ============================================================================

def get_template_dir() -> Path:
    # Get current template directory (dynamic - controlled by dev_mode flag).
    #
    # Returns:
    #     Path to template directory (Eclipse models folder or repo templates)
    if get_dev_mode():
        return REPO_TEMPLATE_DIR
    return _get_eclipse_template_dir()


# ============================================================================
# Template Loading Functions
# ============================================================================

def get_template_list(filter_unsupported: bool = True) -> List[str]:
    # Get list of available SmartLM templates.
    #
    # Args:
    #     filter_unsupported: If True, filter out templates that require newer transformers
    #
    # Returns:
    #     List of template names (sorted, with "None" at top)
    templates = []
    filtered_templates = []
    template_dir = get_template_dir()
    
    if template_dir.exists():
        for f in template_dir.iterdir():
            if f.suffix == '.json' and not f.name.startswith('_'):
                if filter_unsupported:
                    # Check if template's model architecture is supported
                    try:
                        with open(f, 'r') as file:
                            template_data = json.load(file)
                            repo_id = template_data.get('repo_id', '')
                            
                            if is_model_architecture_supported(repo_id):
                                templates.append(f.stem)
                            else:
                                filtered_templates.append(f.stem)
                    except Exception:
                        templates.append(f.stem)
                else:
                    templates.append(f.stem)
    
    # Log filtered templates summary (only once per session)
    if filtered_templates and not hasattr(get_template_list, '_logged'):
        get_template_list._logged = True
        
        # Group templates by base model
        base_models = set()
        for template in filtered_templates:
            template_lower = template.lower()
            if 'qwen3-vl' in template_lower or 'qwen3_vl' in template_lower:
                base_models.add('Qwen3-VL')
        
        if base_models:
            models_str = ', '.join(sorted(base_models))
            log.warning(_LOG_PREFIX, f"{len(filtered_templates)} template(s) hidden (require transformers >= 4.57.1): {models_str} variants")
        else:
            log.warning(_LOG_PREFIX, f"{len(filtered_templates)} template(s) hidden (require newer transformers): {', '.join(filtered_templates)}")
    
    sorted_templates = sorted(templates) if templates else []
    return ["None"] + sorted_templates


# Template cache for load_template (avoids repeated file I/O)
_template_cache: Dict[str, dict] = {}
_template_cache_times: Dict[str, float] = {}
_TEMPLATE_CACHE_TTL: float = 30.0  # Cache for 30 seconds

def load_template(name: str) -> dict:
    # Load a SmartLM template configuration (cached).
    #
    # Args:
    #     name: Template name (without .json extension)
    #
    # Returns:
    #     Template dictionary or empty dict if not found
    import time
    global _template_cache, _template_cache_times
    
    if not name or name == "None": 
        return {}
    
    current_time = time.time()
    
    # Check if cached and still valid
    if name in _template_cache:
        if current_time - _template_cache_times.get(name, 0) < _TEMPLATE_CACHE_TTL:
            return _template_cache[name].copy()  # Return copy to prevent mutation
    
    template_path = get_template_dir() / f"{name}.json"
    try:
        if template_path.exists():
            with open(template_path, 'r') as f:
                template = json.load(f)
                _template_cache[name] = template
                _template_cache_times[name] = current_time
                return template.copy()
    except Exception as e:
        log.error(_LOG_PREFIX, f"Error loading template {name}: {e}")
    return {}


def invalidate_template_cache(name: str = None):
    # Invalidate template cache (call after updating/deleting templates).
    #
    # Args:
    #     name: Template name to invalidate, or None to clear all
    global _template_cache, _template_cache_times
    if name is None:
        _template_cache.clear()
        _template_cache_times.clear()
    elif name in _template_cache:
        del _template_cache[name]
        _template_cache_times.pop(name, None)


# ============================================================================
# Template Update Functions
# ============================================================================

def update_template_settings(name: str, settings: dict, auto_save: bool = True) -> bool:
    # Update template with changed settings.
    #
    # This is the unified function for updating any template fields including:
    # - Widget settings (max_tokens, quantization, attention_mode, etc.)
    # - Path fields (local_path, mmproj_path)
    # - Model configuration (loading_method, context_size, etc.)
    #
    # Args:
    #     name: Template name
    #     settings: Dict of settings to update (e.g., {"max_tokens": 1024, "local_path": "model/file.gguf"})
    #     auto_save: Whether to save changes (user preference, default True)
    #
    # Returns:
    #     True if template was updated, False otherwise
    # Don't modify repo templates in dev_mode
    if get_dev_mode():
        return False
    
    # Skip invalid or temporary templates
    if not name or name == "None" or name.startswith("_temp") or name == "__temp_manual_config__":
        return False
        
    if not auto_save or not settings:
        return False
    
    template_path = get_template_dir() / f"{name}.json"
    try:
        if template_path.exists():
            with open(template_path, 'r') as f:
                template_data = json.load(f)
            
            # Track what changed
            changes = []
            for key, value in settings.items():
                if template_data.get(key) != value:
                    template_data[key] = value
                    changes.append(f"{key}={value}")
            
            # Save if anything changed
            if changes:
                with open(template_path, 'w') as f:
                    json.dump(template_data, f, indent=2)
                invalidate_template_cache(name)  # Clear cache for this template
                log.msg(_LOG_PREFIX, f"✓ Auto-saved template '{name}': {', '.join(changes)}")
                return True
    except Exception as e:
        log.warning(_LOG_PREFIX, f"Could not auto-save template {name}: {e}")
    return False


# ============================================================================
# Auto Template Generation (for imported models)
# ============================================================================

def infer_model_family_from_name(model_name: str) -> str:
    # Infer model family from model name for template generation.
    #
    # Used when auto-generating templates for locally imported models
    # (e.g., GGUF files imported into Ollama).
    #
    # Args:
    #     model_name: The model name or filename
    #
    # Returns:
    #     Model family string for template display
    name_lower = model_name.lower()
    
    if "mistral" in name_lower or "ministral" in name_lower:
        return "Mistral"
    elif "qwen" in name_lower:
        return "Qwen"
    elif "llava" in name_lower or "llama" in name_lower:
        return "LLaVA"
    elif "florence" in name_lower:
        return "Florence"
    elif "phi" in name_lower:
        return "Phi"
    elif "gemma" in name_lower:
        return "Gemma"
    elif "deepseek" in name_lower:
        return "DeepSeek"
    else:
        return "LLM (Text-Only)"


def infer_model_type_from_name(model_name: str, model_path: str = None) -> str:
    # Infer model type from model name and optionally from config.json.
    #
    # This determines the prompt format/chat template to use.
    # When model_path is provided and contains config.json, that takes priority.
    #
    # Args:
    #     model_name: The model name or filename
    #     model_path: Optional path to model directory (for config.json detection)
    #
    # Returns:
    #     Model type string for internal processing
    import json
    from pathlib import Path
    
    # Try config.json detection first if model_path provided
    if model_path:
        model_dir = Path(model_path)
        config_file = model_dir / "config.json" if model_dir.is_dir() else None
        
        if config_file and config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
                
                # Get model_type and architectures from config
                cfg_model_type = config.get("model_type", "").lower()
                architectures = [a.lower() for a in config.get("architectures", [])]
                
                # Mllama detection (Llama 3.2 Vision)
                if "mllama" in cfg_model_type or any("mllama" in a for a in architectures):
                    return "mllama"
                
                # LLaVA detection
                if "llava" in cfg_model_type or any("llava" in a for a in architectures):
                    return "llava"
                
                # Florence-2 detection
                if "florence" in cfg_model_type or any("florence" in a for a in architectures):
                    return "florence2"
                
                # Qwen detection
                if "qwen" in cfg_model_type or any("qwen" in a for a in architectures):
                    has_vision = "vl" in cfg_model_type or "vision_config" in config
                    return "qwenvl" if has_vision else "qwen"
                
                # Mistral/Pixtral detection
                if "mistral" in cfg_model_type or "pixtral" in cfg_model_type or any("mistral" in a or "pixtral" in a for a in architectures):
                    has_vision = "pixtral" in cfg_model_type or "vision_config" in config
                    return "mistral3" if has_vision else "mistral"
                
                # Phi detection
                if "phi" in cfg_model_type or any("phi" in a for a in architectures):
                    return "phi"
                
                # Gemma detection
                if "gemma" in cfg_model_type or any("gemma" in a for a in architectures):
                    return "gemma"
                
                # DeepSeek detection
                if "deepseek" in cfg_model_type or any("deepseek" in a for a in architectures):
                    return "deepseek"
                
            except Exception:
                pass  # Fall through to name-based detection
    
    # Fallback: Name-based detection
    name_lower = model_name.lower()
    
    if "ministral-3" in name_lower or "ministral3" in name_lower or "pixtral" in name_lower:
        return "mistral3"
    elif "mistral" in name_lower:
        return "mistral"
    elif "florence" in name_lower:
        return "florence2"
    elif "qwen" in name_lower and ("vl" in name_lower or "vision" in name_lower):
        return "qwenvl"
    elif "qwen" in name_lower:
        return "qwen"
    # Check for Llama 3.2 Vision (Mllama) BEFORE generic llava check
    elif ("llama-3.2" in name_lower or "llama3.2" in name_lower or "llama-3-2" in name_lower) and "vision" in name_lower:
        return "mllama"
    elif "mllama" in name_lower:
        return "mllama"
    elif "llava" in name_lower:
        return "llava"
    elif "phi" in name_lower:
        return "phi"
    elif "gemma" in name_lower:
        return "gemma"
    elif "deepseek" in name_lower:
        return "deepseek"
    else:
        return "llm"


def create_auto_template(
    model_name: str = None,
    loading_method: str = None,
    original_filename: str = None,
    has_vision: bool = False,
    ollama_model: str = None,
    local_path: str = None,
    repo_id: str = None,
    force_overwrite: bool = False,
    prefix: str = None,
    widget_model_family: str = None,
    widget_model_type: str = None,
    ctx: TemplateContext = None,
) -> Optional[str]:
    # Create a SmartLM template file for an imported/loaded model.
    #
    # This is a generic function that can create templates for any backend:
    # - Ollama Docker (local GGUF imports)
    # - llama.cpp Docker
    # - vLLM Docker
    # - Local GGUF files
    #
    # Args:
    #     model_name: Model identifier (used for inference and display)
    #     loading_method: Backend used ("Ollama (Docker)", "llama.cpp (Docker)", etc.)
    #     original_filename: Original filename for naming (e.g., GGUF filename)
    #     has_vision: Whether model supports vision
    #     ollama_model: Ollama model name (for Ollama backend)
    #     local_path: Local path to model file (for GGUF backend)
    #     repo_id: HuggingFace repo ID (if applicable)
    #     force_overwrite: If True, overwrite existing template
    #     prefix: Custom prefix for template name (e.g., "ollama--local--")
    #     widget_model_family: Model family from widget (overrides inference from name)
    #     widget_model_type: Model type from widget (overrides inference from name)
    #     ctx: TemplateContext object (if provided, overrides individual params)
    #
    # Returns:
    #     str: Path to created template, or None on error
    # If context provided, extract values from it (context takes priority)
    if ctx is not None:
        model_name = model_name or ctx.ollama_model or ""
        loading_method = loading_method or ctx.loading_method
        original_filename = original_filename or ctx.original_filename
        has_vision = ctx.has_vision if ctx.has_vision else has_vision
        ollama_model = ollama_model or ctx.ollama_model
        local_path = local_path or ctx.local_path
        repo_id = repo_id or ctx.repo_id
        widget_model_family = widget_model_family or ctx.model_family
        widget_model_type = widget_model_type or ctx.model_type
    
    # Determine template filename
    if prefix:
        template_name = prefix
        if original_filename:
            template_name += Path(original_filename).stem
        else:
            template_name += model_name.replace(':', '-').replace('/', '-')
    elif original_filename:
        # Use original filename but clean it up
        clean_name = Path(original_filename).stem
        template_name = f"local--{clean_name}"
    else:
        # Use model name
        template_name = model_name.replace(':', '-').replace('/', '-')
    
    # Get templates directory
    templates_dir = get_template_dir()
    template_path = templates_dir / f"{template_name}.json"
    
    if template_path.exists() and not force_overwrite:
        # Return None to indicate no new template was created
        return None
    
    # Determine model_path for config.json detection
    # Priority: local_path (if directory) > repo_id path (if exists locally)
    config_detection_path = None
    if local_path:
        local_path_obj = Path(local_path)
        if local_path_obj.is_dir():
            config_detection_path = str(local_path_obj)
        elif local_path_obj.is_file():
            config_detection_path = str(local_path_obj.parent)
    
    # Use widget values if provided, otherwise infer from name (and config if available)
    if widget_model_family:
        model_family = widget_model_family
    else:
        name_for_inference = original_filename or model_name
        model_family = infer_model_family_from_name(name_for_inference)
    
    if widget_model_type:
        model_type = widget_model_type
    else:
        name_for_inference = original_filename or model_name
        model_type = infer_model_type_from_name(name_for_inference, config_detection_path)
    
    # Adjust model family for text-only when vision not supported
    # Only apply this adjustment if we inferred the family (not from widget)
    if not has_vision and not widget_model_family and model_family in ("Mistral", "LLaVA"):
        model_family = "LLM (Text-Only)"
    
    # Get values from context if available, otherwise use defaults
    ctx_quantization = ctx.quantization if ctx and ctx.quantization else "auto"
    ctx_attention_mode = ctx.attention_mode if ctx and ctx.attention_mode else "auto"
    ctx_context_size = ctx.context_size if ctx and ctx.context_size else 8192
    ctx_max_tokens = ctx.max_tokens if ctx and ctx.max_tokens else 1024
    ctx_default_task = ctx.default_task if ctx and ctx.default_task else ("Detailed Description" if has_vision else "Tags to Natural Language")
    ctx_default_text_input = ctx.default_text_input if ctx and ctx.default_text_input else ""
    
    # mmproj_path should ONLY contain local paths, never URLs
    # It will be populated after download when the file is resolved
    ctx_mmproj_path = ""
    if ctx and ctx.mmproj_path and not ctx.mmproj_path.startswith("http"):
        ctx_mmproj_path = ctx.mmproj_path
    
    # mmproj_url applies to GGUF-based backends (GGUF, llama.cpp Docker)
    # Transformers handle vision natively without mmproj
    # Ollama doesn't support mmproj - it uses its own vision handling
    ctx_mmproj_url = ""
    if loading_method and ("GGUF" in loading_method or "llama.cpp" in loading_method):
        ctx_mmproj_url = ctx.mmproj_url if ctx and ctx.mmproj_url else ""
    
    # Detect if GGUF model is quantized from filename
    is_quantized = False
    if loading_method and ("GGUF" in loading_method or "llama.cpp" in loading_method or "Ollama" in loading_method):
        # Check filename for GGUF quantization patterns
        name_to_check = (original_filename or local_path or repo_id or model_name or "").upper()
        # Common GGUF quantization patterns: Q2_K, Q3_K_S, Q4_0, Q4_K_M, Q5_K_S, Q6_K, Q8_0, IQ2_XS, etc.
        gguf_quant_patterns = [
            "Q2_K", "Q3_K", "Q4_K", "Q5_K", "Q6_K", "Q8_0", "Q8_1",
            "Q4_0", "Q4_1", "Q5_0", "Q5_1", "Q3_K_S", "Q3_K_M", "Q3_K_L",
            "Q4_K_S", "Q4_K_M", "Q5_K_S", "Q5_K_M", "Q6_K",
            "IQ1_", "IQ2_", "IQ3_", "IQ4_",  # imatrix quants
        ]
        for pattern in gguf_quant_patterns:
            if pattern in name_to_check:
                is_quantized = True
                break
    
    # Ensure local_path is never a URL (it will be populated after download)
    safe_local_path = local_path or ""
    if safe_local_path.startswith("http"):
        safe_local_path = ""
    
    # Build template with all standard fields
    template = {
        "model_family": model_family,
        "model_type": model_type,
        "loading_method": loading_method,
        "repo_id": repo_id or "",
        "local_path": safe_local_path,
        "ollama_model": ollama_model or "",
        "model_source": "ollama" if ollama_model else "",
        "mmproj_path": ctx_mmproj_path,
        "mmproj_url": ctx_mmproj_url,
        "quantization": ctx_quantization,
        "attention_mode": ctx_attention_mode,
        "context_size": ctx_context_size,
        "max_tokens": ctx_max_tokens,
        "quantized": is_quantized,
        "default_task": ctx_default_task,
        "default_text_input": ctx_default_text_input,
        "has_vision": has_vision,
    }
    
    # Write template
    try:
        templates_dir.mkdir(parents=True, exist_ok=True)
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)
        
        return str(template_path)
    except Exception as e:
        log.error(_LOG_PREFIX, f"Failed to create template: {e}")
        return None


def update_template_quantization(
    template_name: str,
    detected_quantization: str,
    is_quantized: bool = True,
) -> bool:
    # Update an existing template with detected quantization type.
    #
    # This should be called after model loading when we detect the actual
    # quantization format (FP8, AWQ, GPTQ, etc.) from the model files.
    #
    # Args:
    #     template_name: Name of the template (without .json extension)
    #     detected_quantization: Detected quantization type ("fp8", "awq", "gptq", "bf16", etc.)
    #     is_quantized: Whether the model is pre-quantized
    #
    # Returns:
    #     bool: True if template was updated, False otherwise
    import json
    
    templates_dir = get_template_dir()
    template_path = templates_dir / f"{template_name}.json"
    
    if not template_path.exists():
        log.debug(_LOG_PREFIX, f"Template not found for update: {template_name}")
        return False
    
    try:
        # Read existing template
        template = json.loads(template_path.read_text(encoding='utf-8'))
        
        # Check if update is needed
        old_quant = template.get("quantization", "auto")
        old_quantized = template.get("quantized", False)
        
        # Only update if we have new info and it differs
        if detected_quantization and (old_quant == "auto" or old_quant != detected_quantization):
            template["quantization"] = detected_quantization
            template["quantized"] = is_quantized
            
            # Write updated template
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2)
            
            log.msg(_LOG_PREFIX, f"✓ Updated template '{template_name}' quantization: {old_quant} → {detected_quantization}")
            return True
        
        return False
        
    except Exception as e:
        log.error(_LOG_PREFIX, f"Failed to update template quantization: {e}")
        return False


# ============================================================================
# Prompt Configuration Loading
# ============================================================================

# Global configuration storage
MODEL_CONFIGS: Dict[str, Any] = {}
SYSTEM_PROMPTS: Dict[str, str] = {}
LLM_FEW_SHOT_EXAMPLES: Dict[str, Any] = {}


def get_prompt_config_path() -> Path:
    # Get path to prompt defaults config file
    return REPO_CONFIG_DIR / "smartlm_prompt_defaults.json"


def get_llm_few_shot_config_path() -> Path:
    # Get path to LLM few-shot config file (always from repo config folder)
    return REPO_CONFIG_DIR / "llm_few_shot_training.json"


def load_prompt_configs():
    # Load prompt configurations for all model types.
    #
    # Loads:
    # - QwenVL system prompts
    # - Preset prompts
    # - Florence-2 tasks (deferred to avoid circular import)
    # - LLM few-shot examples
    global MODEL_CONFIGS, SYSTEM_PROMPTS, LLM_FEW_SHOT_EXAMPLES
    
    prompt_config_path = get_prompt_config_path()
    
    log.debug(_LOG_PREFIX, f"Loading config from: {prompt_config_path}")
    
    # Store florence tasks config for later loading (avoid circular import)
    florence_tasks_config = None
    
    try:
        with open(prompt_config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
            # System prompts are now embedded in each task object's "system_prompt" field
            # SYSTEM_PROMPTS will be populated after build_task_dict() extracts them

            # New split format: _custom_tasks, _vision_tasks, _detection_tasks, _text_tasks
            custom = config_data.get("_custom_tasks", None)
            vision = config_data.get("_vision_tasks", None)
            detection = config_data.get("_detection_tasks", None)
            text = config_data.get("_text_tasks", None)

            if custom is not None or vision is not None or detection is not None or text is not None:
                MODEL_CONFIGS["_custom_tasks"] = custom or []
                MODEL_CONFIGS["_vision_tasks"] = vision or []
                MODEL_CONFIGS["_detection_tasks"] = detection or []
                MODEL_CONFIGS["_text_tasks"] = text or []

                # Maintain preset dict with new key names that match JSON: custom, vision, detection, text
                # Keep legacy aliases available when reading to stay backwards-compatible at runtime
                MODEL_CONFIGS["_preset_prompts"] = {
                    "custom": MODEL_CONFIGS["_custom_tasks"],
                    "vision": MODEL_CONFIGS["_vision_tasks"],
                    "detection": MODEL_CONFIGS["_detection_tasks"],
                    "text": MODEL_CONFIGS["_text_tasks"]
                }

                # Use local variables to avoid nested quote issues in f-strings
                c_n = len(MODEL_CONFIGS["_custom_tasks"])
                v_n = len(MODEL_CONFIGS["_vision_tasks"])
                d_n = len(MODEL_CONFIGS["_detection_tasks"])
                t_n = len(MODEL_CONFIGS["_text_tasks"])
                log.debug(_LOG_PREFIX, f"Loaded task lists: custom={c_n}, vision={v_n}, detection={d_n}, text={t_n}")
            else:
                preset_data = config_data.get("_preset_prompts", {})
                log.debug(_LOG_PREFIX, f"_preset_prompts type: {type(preset_data).__name__}")
                # Enforce canonical preset keys: custom, vision, detection, text
                if isinstance(preset_data, dict):
                    # Fail loudly if legacy keys are present - hard rename policy
                    legacy_keys = [k for k in ("common", "qwen_extra", "llm") if k in preset_data]
                    if legacy_keys:
                        raise RuntimeError(
                            f"Deprecated preset keys found in _preset_prompts: {legacy_keys}.\n"
                            "Please migrate to canonical keys: 'vision', 'detection', 'text' and remove legacy keys."
                        )
                    # Only accept canonical keys (missing keys default to empty lists)
                    canonical = {
                        "custom": preset_data.get("custom", []) or [],
                        "vision": preset_data.get("vision", []) or [],
                        "detection": preset_data.get("detection", []) or [],
                        "text": preset_data.get("text", []) or [],
                    }
                    MODEL_CONFIGS["_preset_prompts"] = canonical
                else:
                    MODEL_CONFIGS["_preset_prompts"] = preset_data

        # Check for deprecated Florence-specific config section and fail loudly if present
            if "_florence_tasks" in config_data:
                raise RuntimeError("Deprecated '_florence_tasks' section found in prompt defaults. Please migrate Florence tasks into the new split sections (_vision_tasks, _detection_tasks, _text_tasks) and remove '_florence_tasks'.")

        # Debug: Show loaded task counts (only in dev mode)
        preset = MODEL_CONFIGS.get("_preset_prompts", {})
        if isinstance(preset, dict):
            vision_count = len(preset.get("vision", []))
            detection_count = len(preset.get("detection", []))
            text_count = len(preset.get("text", []))
            log.debug(_LOG_PREFIX, f"Loaded tasks - Vision: {vision_count}, Detection: {detection_count}, Text: {text_count}")

        # Build authoritative task dict (fail loudly on invalid config)
        build_task_dict()
        
        # Build SYSTEM_PROMPTS from task_dict metadata (replaces old _system_prompts section)
        # This provides backwards compatibility for code that uses SYSTEM_PROMPTS directly
        task_dict = MODEL_CONFIGS.get("_task_dict", {})
        for display_name, meta in task_dict.items():
            sp = meta.get("system_prompt")
            if sp:
                SYSTEM_PROMPTS[display_name] = sp
        log.debug(_LOG_PREFIX, f"Built {len(SYSTEM_PROMPTS)} system prompts from task metadata")
            
    except Exception as exc:
        # Fail loudly: configuration must be present and valid at startup.
        log.error(_LOG_PREFIX, f"Config load failed: {exc}")
        import traceback
        traceback.print_exc()
        # Re-raise to surface failure (no silent fallback)
        raise

    llm_config_path = get_llm_few_shot_config_path()
    try:
        with open(llm_config_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        LLM_FEW_SHOT_EXAMPLES.clear()
        LLM_FEW_SHOT_EXAMPLES.update(loaded_data)
        log.msg(_LOG_PREFIX, f"Loaded LLM few-shot training examples ({len(loaded_data)} modes)")
    except Exception as exc:
        log.warning(_LOG_PREFIX, f"LLM few-shot config load failed: {exc}")
        LLM_FEW_SHOT_EXAMPLES.clear()
        LLM_FEW_SHOT_EXAMPLES.update({
            "prompt_generation": {
                "system_prompt": "You are a helpful assistant.",
                "examples": []
            },
            "direct_chat": {
                "system_prompt": "You are a helpful assistant. Try your best to give the best response possible to the user.",
                "examples": []
            }
        })
    
    # Count templates (best-effort, don't fail init if templates can't be enumerated)
    try:
        template_count = len(get_template_list())
        log.msg(_LOG_PREFIX, f"Found {template_count} model templates")
    except Exception:
        log.debug(_LOG_PREFIX, "Could not list templates at startup (non-fatal)")
    
    # Show transformers version
    try:
        import transformers
        log.msg(_LOG_PREFIX, f"Transformers version: {transformers.__version__}")
    except Exception:
        log.warning(_LOG_PREFIX, "Transformers not found")


def get_system_prompts() -> Dict[str, str]:
    # Get loaded system prompts
    return SYSTEM_PROMPTS


def get_preset_prompts() -> List[str]:
    # Get loaded preset prompts
    return MODEL_CONFIGS.get("_preset_prompts", [])


def get_llm_few_shot_examples() -> Dict[str, Any]:
    # Get loaded LLM few-shot examples
    return LLM_FEW_SHOT_EXAMPLES


def reload_prompt_configs() -> Dict[str, Any]:
    # Reload prompt configs and few-shot examples from disk.
    #
    # Call this when user edits config files and wants to pick up changes
    # without restarting ComfyUI.
    #
    # Returns:
    #     Dict with reload status and counts
    global MODEL_CONFIGS, SYSTEM_PROMPTS, LLM_FEW_SHOT_EXAMPLES
    
    try:
        # Clear existing data
        MODEL_CONFIGS.clear()
        SYSTEM_PROMPTS.clear()
        LLM_FEW_SHOT_EXAMPLES.clear()
        
        # Reload from disk
        load_prompt_configs()
        
        # Get counts for status
        task_dict = MODEL_CONFIGS.get("_task_dict", {})
        
        log.msg(_LOG_PREFIX, f"Reloaded configs: {len(task_dict)} tasks, {len(SYSTEM_PROMPTS)} system prompts, {len(LLM_FEW_SHOT_EXAMPLES)} few-shot modes")
        
        return {
            "success": True,
            "tasks": len(task_dict),
            "system_prompts": len(SYSTEM_PROMPTS),
            "few_shot_modes": len(LLM_FEW_SHOT_EXAMPLES)
        }
    except Exception as e:
        log.error(_LOG_PREFIX, f"Failed to reload configs: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_system_prompt(name: str) -> str:
    # Return the system prompt for a task name.
    #
    # Tries exact match first, then falls back to case-insensitive match.
    # If the `_system_prompts` mapping is empty or missing the key, consult the
    # authoritative `MODEL_CONFIGS["_task_dict"]` metadata for an embedded
    # `system_prompt` value (case-insensitive). Returns empty string if nothing found.
    if not name:
        return ""
    # 1) Exact match in explicit system prompts
    if name in SYSTEM_PROMPTS:
        return SYSTEM_PROMPTS.get(name, "")
    # 2) Case-insensitive match in explicit system prompts
    name_l = name.lower()
    for k, v in SYSTEM_PROMPTS.items():
        if k.lower() == name_l:
            return v

    # 3) Fallback: consult TASK_DICT meta (case-insensitive display name match)
    task_dict = MODEL_CONFIGS.get("_task_dict", {}) if "MODEL_CONFIGS" in globals() else {}
    if task_dict:
        for disp, meta in task_dict.items():
            if disp and disp.lower() == name_l:
                sp = meta.get("system_prompt")
                if sp:
                    return sp
    return ""


# --------------------------------------------------------------------------
# TASK_DICT builder (authoritative, fail-loud on invalid config)
# --------------------------------------------------------------------------

def build_task_dict() -> None:
    # Build a single authoritative task dict from the loaded MODEL_CONFIGS.
    #
    # - Keys: display name (user-facing)
    # - Values: metadata dict with fields: id, prompt, families, system_prompt, description
    #
    # This function validates the input and *raises* RuntimeError on any
    # malformed or duplicate entries (no silent fallbacks).
    task_dict = {}
    id_to_display = {}

    sections = ["_custom_tasks", "_vision_tasks", "_detection_tasks", "_text_tasks"]

    for section in sections:
        entries = MODEL_CONFIGS.get(section, []) or []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise RuntimeError(f"Invalid prompt entry in {section}[{idx}]: expected object, got {type(entry).__name__}")
            name = entry.get("name")
            if not name or not isinstance(name, str):
                raise RuntimeError(f"Prompt entry missing or invalid 'name' in {section}[{idx}]")
            if name in task_dict:
                raise RuntimeError(f"Duplicate prompt display name '{name}' found in {section}[{idx}]")

            families = entry.get("families", [])
            if families is None:
                raise RuntimeError(f"Prompt '{name}' has null 'families' in {section}[{idx}]")
            if not isinstance(families, list):
                raise RuntimeError(f"Prompt '{name}' has invalid 'families' type (expected list) in {section}[{idx}]")

            meta = {
                "name": name,
                "id": entry.get("id"),
                "prompt": entry.get("prompt"),
                "families": families,
                "system_prompt": entry.get("system_prompt"),
                "description": entry.get("description", ""),
            }

            # Validate Florence tasks require an 'id'
            if "Florence" in families:
                if not meta["id"] or not isinstance(meta["id"], str):
                    raise RuntimeError(f"Florence task '{name}' is missing required 'id' field in {section}[{idx}]")
                if meta["id"] in id_to_display:
                    raise RuntimeError(f"Duplicate Florence task id '{meta['id']}' found for '{name}' and '{id_to_display[meta['id']]}'")
                id_to_display[meta["id"]] = name

            task_dict[name] = meta

    MODEL_CONFIGS["_task_dict"] = task_dict
    MODEL_CONFIGS["_id_to_display"] = id_to_display


def resolve_florence_machine_key(value: str) -> str:
    # Resolve a Florence machine key from a display name or id.
    #
    # Raises RuntimeError if resolution fails (no silent fallbacks).
    if not isinstance(value, str) or not value:
        raise RuntimeError("Invalid Florence task value")

    id_to_display = MODEL_CONFIGS.get("_id_to_display", {})
    task_dict = MODEL_CONFIGS.get("_task_dict", {})

    # Direct id match
    if value in id_to_display:
        return value

    # Exact display match
    meta = task_dict.get(value)
    if meta and meta.get("id"):
        return meta.get("id")

    # Case-insensitive display match
    v_l = value.lower()
    for disp, m in task_dict.items():
        if disp.lower() == v_l and m.get("id"):
            return m.get("id")

    raise RuntimeError(f"Could not resolve Florence machine key for task value: '{value}'")


def resolve_florence_display_from_id(mk: str) -> str:
    # Resolve a Florence display name from a machine key (id).
    #
    # Raises RuntimeError if resolution fails (no silent fallbacks).
    if not isinstance(mk, str) or not mk:
        raise RuntimeError("Invalid Florence machine key")

    id_to_display = MODEL_CONFIGS.get("_id_to_display", {})
    # Direct lookup
    if mk in id_to_display:
        return id_to_display[mk]
    # Case-insensitive
    mk_l = mk.lower()
    if mk_l in id_to_display:
        return id_to_display[mk_l]

    raise RuntimeError(f"Could not resolve Florence display name for id: '{mk}'")




# ============================================================================
# Auto-load configs on import
# ============================================================================
# This ensures MODEL_CONFIGS is populated BEFORE any other module imports it
load_prompt_configs()

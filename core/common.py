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

import hashlib
import json
import os
import re
import time
import comfy
import ipaddress
import socket
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Import log from logger (centralized location)
from .logger import log

# ============================================================================
# Eclipse config utilities (read/write eclipse_config.json)
# ============================================================================

# Path to the extension root (one level up from core/)
_NODE_DIR = Path(__file__).resolve().parent.parent

# Config cache for get_config_value (avoids repeated file I/O)
_config_cache: Dict[str, Any] = {}
_config_cache_time: float = 0.0
_CONFIG_CACHE_TTL: float = 5.0  # Cache for 5 seconds


def get_config_value(key: str, default=None):
    # Get a configuration value from eclipse_config.json (cached)
    global _config_cache, _config_cache_time

    current_time = time.time()

    # Check if cache is valid
    if current_time - _config_cache_time < _CONFIG_CACHE_TTL and _config_cache:
        return _config_cache.get(key, default)

    # Reload config from file
    config_path = _NODE_DIR / "eclipse_config.json"
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
    invalidate_config_cache()
    config_path = _NODE_DIR / "eclipse_config.json"
    try:
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

        if nested_key:
            if key not in config:
                config[key] = {}
            if not isinstance(config[key], dict):
                config[key] = {}
            config[key][nested_key] = value
        else:
            config[key] = value

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        return True
    except Exception as e:
        log.error("Config", f"Failed to update {key}: {e}")
        return False


def calculate_file_hash(file_path: Path, show_progress: bool = True) -> str:
    # Calculate SHA256 hash of a file with optional progress display.
    import sys

    sha256_hash = hashlib.sha256()
    file_size = file_path.stat().st_size
    bytes_processed = 0
    last_progress = -1

    size_mb = file_size / (1024 * 1024)
    if show_progress and file_size > 100 * 1024 * 1024:
        log.msg("FileHash", f"Calculating hash for {file_path.name} ({size_mb:.1f} MB)...")
    elif show_progress:
        log.msg("FileHash", f"Calculating hash for {file_path.name}...")

    with open(file_path, "rb") as f:
        while chunk := f.read(8192 * 1024):  # 8MB chunks
            sha256_hash.update(chunk)
            bytes_processed += len(chunk)
            if show_progress and file_size > 100 * 1024 * 1024:
                progress = int((bytes_processed / file_size) * 100)
                if progress != last_progress:
                    sys.stdout.write(f"\rEclipse: [FileHash]   Hashing: {progress}% ({bytes_processed / (1024*1024):.0f}/{size_mb:.0f} MB)")
                    sys.stdout.flush()
                    last_progress = progress

    if show_progress and file_size > 100 * 1024 * 1024:
        print()

    return sha256_hash.hexdigest()


# ============================================================================
# Pre-compiled regex patterns for strip_thinking_tags()
# These patterns are used during LLM inference - compiling once saves ~10ms per call
# ============================================================================

# Wrapper tags that should have their entire content removed
_THINKING_WRAPPER_TAGS = ['think', 'thinking', 'reasoning', 'summary']

# Pre-compiled patterns for each wrapper tag (XML and bracket styles)
_RE_THINKING_XML_BLOCK = {
    tag: re.compile(rf'<{tag}>.*?</{tag}>\s*', re.DOTALL | re.IGNORECASE)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_BRACKET_BLOCK = {
    tag: re.compile(rf'\[{tag.upper()}\].*?\[/{tag.upper()}\]\s*', re.DOTALL)
    for tag in _THINKING_WRAPPER_TAGS
}

# Orphan tag patterns (opening without closing, or closing without opening)
_RE_THINKING_XML_OPEN = {
    tag: re.compile(rf'<{tag}>', re.IGNORECASE)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_XML_CLOSE = {
    tag: re.compile(rf'</{tag}>', re.IGNORECASE)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_XML_ORPHAN_CLOSE = {
    tag: re.compile(rf'^.*?</{tag}>\s*', re.DOTALL | re.IGNORECASE)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_XML_ORPHAN_OPEN = {
    tag: re.compile(rf'<{tag}>.*$', re.DOTALL | re.IGNORECASE)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_BRACKET_OPEN = {
    tag: re.compile(rf'\[{tag.upper()}\]')
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_BRACKET_CLOSE = {
    tag: re.compile(rf'\[/{tag.upper()}\]')
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_BRACKET_ORPHAN_CLOSE = {
    tag: re.compile(rf'^.*?\[/{tag.upper()}\]\s*', re.DOTALL)
    for tag in _THINKING_WRAPPER_TAGS
}
_RE_THINKING_BRACKET_ORPHAN_OPEN = {
    tag: re.compile(rf'\[{tag.upper()}\].*$', re.DOTALL)
    for tag in _THINKING_WRAPPER_TAGS
}

# Generic tag cleanup patterns
_RE_XML_ANY_TAG = re.compile(r'</?[a-zA-Z_][a-zA-Z0-9_]*\s*/?>')
_RE_BRACKET_ANY_TAG = re.compile(r'\[/?[A-Z_][A-Z0-9_]*\]')
_RE_CODE_FENCE_OPEN = re.compile(r'^```[a-zA-Z]*\n?')
_RE_CODE_FENCE_CLOSE = re.compile(r'\n?```\s*$')


class AnyType(str):
    # A special class that is always equal in not-equal comparisons. Credit to pythongosssss

    def __eq__(self, _) -> bool:
        return True

    def __ne__(self, __value: object) -> bool:
        return False


def is_safe_url(url: str) -> bool:
    # Validate URL to prevent SSRF attacks.
    # Blocks private IP ranges and localhost to prevent internal network access.
    #
    # Returns:
    #     True if URL is safe to fetch, False otherwise.
    if not url:
        log.warning("Security", "Blocked empty URL")
        return False
    
    try:
        parsed = urlparse(url)
        
        # Only allow http/https
        if parsed.scheme not in ('http', 'https'):
            log.warning("Security", f"Blocked non-http(s) URL scheme: {parsed.scheme}")
            return False
        
        hostname = parsed.hostname
        if not hostname:
            log.warning("Security", f"Blocked URL with no hostname: {url}")
            return False
        
        # Block localhost variants
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            log.warning("Security", f"Blocked localhost URL: {url}")
            return False
        
        # Try to resolve hostname and check if it's a private IP
        try:
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            
            # Block private, loopback, link-local, and reserved ranges
            if (ip_obj.is_private or ip_obj.is_loopback or 
                ip_obj.is_link_local or ip_obj.is_reserved):
                log.warning("Security", f"Blocked private/reserved IP URL: {url} (resolved to {ip})")
                return False
        except (socket.gaierror, ValueError):
            # Could not resolve - allow (might be valid external domain)
            pass
        
        return True
    except Exception as e:
        log.warning("Security", f"Blocked URL due to parse error: {url} ({e})")
        return False


def purge_vram() -> None:
    # Central helper to purge VRAM and unload models safely.
    #
    # Use this from nodes instead of duplicating the try/except import and
    # GC/CUDA/model unload sequence. Any exception is reported via the
    # project's cstr warning helper so callers don't need to duplicate
    # error handling.
    #
    # This function unloads all models and clears allocator caches to free
    # maximum VRAM. This will require models to be reloaded on next use.
    # Based on comfyui-multigpu's soft_empty_cache_multigpu approach.
    try:
        import gc
        torch: Optional[ModuleType]
        comfy_mod: Optional[ModuleType]
        try:
            import torch  # type: ignore
        except Exception:
            torch = None

        try:
            import comfy.model_management  # type: ignore
            comfy_mod = comfy
        except Exception:
            comfy_mod = None

        # Step 1: Python garbage collection
        gc.collect()
        
        # Step 2: Clear device caches (multi-device support)
        if torch is not None:
            try:
                # CUDA devices
                if torch.cuda.is_available():
                    device_count = torch.cuda.device_count()
                    for i in range(device_count):
                        with torch.cuda.device(i):
                            torch.cuda.empty_cache()
                            if hasattr(torch.cuda, 'ipc_collect'):
                                torch.cuda.ipc_collect()
                
                # MPS (Apple Silicon)
                if hasattr(torch, 'mps') and hasattr(torch.mps, 'empty_cache'):
                    torch.mps.empty_cache()
                
                # XPU (Intel)
                if hasattr(torch, 'xpu') and hasattr(torch.xpu, 'empty_cache'):
                    torch.xpu.empty_cache()
                
                # NPU (Huawei/Ascend)
                if hasattr(torch, 'npu') and hasattr(torch.npu, 'empty_cache'):
                    torch.npu.empty_cache()
                
                # MLU (Cambricon)
                if hasattr(torch, 'mlu') and hasattr(torch.mlu, 'empty_cache'):
                    torch.mlu.empty_cache()
                
            except Exception:
                # Ignore device-specific failures
                pass

        # Step 3: ComfyUI model unloading and cache clearing
        if comfy_mod is not None:
            try:
                # Unload all models first, then clear caches
                if hasattr(comfy_mod.model_management, 'unload_all_models'):
                    comfy_mod.model_management.unload_all_models()
                if hasattr(comfy_mod.model_management, 'soft_empty_cache'):
                    comfy_mod.model_management.soft_empty_cache()
            except Exception:
                # Ignore model-management failures
                pass
    except Exception as e:
        try:
            log.warning("VRAM", f"Purge failed: {e}")
        except Exception:
            try:
                print(f"VRAM purge failed: {e}")
            except Exception:
                pass


# Pre-instantiated AnyType for use across nodes
# Import as: from ..core.common import any_type
any_type = AnyType("*")


def cleanup_memory_before_load(aggressive: bool = True) -> None:
    # Clean up memory before loading a new model.
    #
    # Parameters:
    #     aggressive: If True (default), performs full multi-device CUDA cleanup with
    #                 ipc_collect and verbose logging. Used by Smart Loaders.
    #                 If False, performs gentle cleanup that only clears unused cache
    #                 without disrupting loaded models.
    #
    # Note: Neither mode unloads models - use purge_vram() for that.
    import gc
    torch_mod: Optional[ModuleType]
    try:
        import torch as torch_mod
    except ImportError:
        torch_mod = None
    
    if aggressive:
        log.msg("Memory Cleanup", "Starting pre-load memory cleanup...")
    
    gc.collect()
    
    if torch_mod is not None and torch_mod.cuda.is_available():
        if aggressive:
            # Full multi-device cleanup with ipc_collect
            device_count = torch_mod.cuda.device_count()
            log.msg("Memory Cleanup", f"Clearing CUDA cache on {device_count} device(s)")
            for i in range(device_count):
                with torch_mod.cuda.device(i):
                    torch_mod.cuda.empty_cache()
                    if hasattr(torch_mod.cuda, 'ipc_collect'):
                        torch_mod.cuda.ipc_collect()
        else:
            # Gentle cleanup - just clear cache on current device
            torch_mod.cuda.empty_cache()
    
    if aggressive and torch_mod is not None and hasattr(torch_mod, 'mps') and hasattr(torch_mod.mps, 'empty_cache'):
        try:
            torch_mod.mps.empty_cache()
            log.msg("Memory Cleanup", "Cleared MPS cache")
        except Exception:
            pass
    
    try:
        import comfy.model_management as mm
        if hasattr(mm, 'soft_empty_cache'):
            mm.soft_empty_cache()
    except Exception:
        pass
    
    if aggressive:
        log.msg("Memory Cleanup", "✓ Memory cleanup complete")


# Resolution presets and mappings for image generation
RESOLUTION_PRESETS = [
    "Custom",
    "512x512 (1:1)",
    "512x682 (3:4)",
    "512x768 (2:3)",
    "512x910 (9:16)",
    "512x952 (1:1.85)",
    "512x1024 (1:2)",
    "512x1224 (1:2.39)",
    "640x1536 (9:21)",
    "768x1280 (3:5 Flux)",
    "768x1344 (9:16 HiDream)",
    "832x1216 (2:3 Flux, SDXL)",
    "832x1408 (1:1.692 HiDream)",
    "896x1152 (3:4)",
    "896x1536 (7:12 HiDream)",
    "1024x1024 (1:1)",
    "1024x1536 (2:3 Flux, Qwen)",
    "1024x2048 (1:2 Qwen)",
    "1152x896 (4:3)",
    "682x512 (4:3)",
    "768x512 (3:2)",
    "910x512 (16:9)",
    "952x512 (1.85:1)",
    "1024x512 (2:1)",
    "1224x512 (2.39:1)",
    "1536x640 (21:9)",
    "1280x768 (5:3 Flux)",
    "1344x768 (16:9 HiDream)",
    "1216x832 (3:2 Flux, SDXL)",
    "1408x832 (1.692:1 HiDream)",
    "1536x896 (12:7 HiDream)",
    "1536x1024 (3:2 Flux, Qwen)",
    "2048x1024 (2:1 Qwen)",
]

RESOLUTION_MAP = {
    "512x512 (1:1)": (512, 512),
    "512x682 (3:4)": (512, 682),
    "512x768 (2:3)": (512, 768),
    "512x910 (9:16)": (512, 910),
    "512x952 (1:1.85)": (512, 952),
    "512x1024 (1:2)": (512, 1024),
    "512x1224 (1:2.39)": (512, 1224),
    "640x1536 (9:21)": (640, 1536),
    "768x1280 (3:5 Flux)": (768, 1280),
    "768x1344 (9:16 HiDream)": (768, 1344),
    "832x1216 (2:3 Flux, SDXL)": (832, 1216),
    "832x1408 (1:1.692 HiDream)": (832, 1408),
    "896x1152 (3:4)": (896, 1152),
    "896x1536 (7:12 HiDream)": (896, 1536),
    "1024x1024 (1:1)": (1024, 1024),
    "1024x1536 (2:3 Flux, Qwen)": (1024, 1536),
    "1024x2048 (1:2 Qwen)": (1024, 2048),
    "1152x896 (4:3)": (1152, 896),
    "682x512 (4:3)": (682, 512),
    "768x512 (3:2)": (768, 512),
    "910x512 (16:9)": (910, 512),
    "952x512 (1.85:1)": (952, 512),
    "1024x512 (2:1)": (1024, 512),
    "1224x512 (2.39:1)": (1224, 512),
    "1536x640 (21:9)": (1536, 640),
    "1280x768 (5:3 Flux)": (1280, 768),
    "1344x768 (16:9 HiDream)": (1344, 768),
    "1216x832 (3:2 Flux, SDXL)": (1216, 832),
    "1408x832 (1.692:1 HiDream)": (1408, 832),
    "1536x896 (12:7 HiDream)": (1536, 896),
    "1536x1024 (3:2 Flux, Qwen)": (1536, 1024),
    "2048x1024 (2:1 Qwen)": (2048, 1024),
}

# Sampler and scheduler lists for ComfyUI (lazy-loaded to avoid import errors in standalone tests)
_SAMPLERS_COMFY = None
_SCHEDULERS_ANY = None

def get_samplers_comfy():
    """Get ComfyUI sampler list (lazy-loaded)."""
    global _SAMPLERS_COMFY
    if _SAMPLERS_COMFY is None:
        _SAMPLERS_COMFY = comfy.samplers.KSampler.SAMPLERS
    return _SAMPLERS_COMFY

def get_schedulers_any():
    """Get ComfyUI scheduler list (lazy-loaded)."""
    global _SCHEDULERS_ANY
    if _SCHEDULERS_ANY is None:
        _SCHEDULERS_ANY = comfy.samplers.KSampler.SCHEDULERS
    return _SCHEDULERS_ANY

# Backward compatibility - these will fail if accessed before ComfyUI is loaded
# Use get_samplers_comfy() and get_schedulers_any() instead for safe access
try:
    SAMPLERS_COMFY = comfy.samplers.KSampler.SAMPLERS
    SCHEDULERS_ANY = comfy.samplers.KSampler.SCHEDULERS
except AttributeError:
    # ComfyUI not fully loaded yet (standalone test mode)
    SAMPLERS_COMFY = []
    SCHEDULERS_ANY = []


def copy_prompt_files_once(source_dir: str, target_dir: str, force: bool = False) -> bool:
    # Copy Smart Prompt files from source to target directory if target doesn't exist.
    # This is a one-time operation to enable wildcard integration.
    #
    # Args:
    #     source_dir: Source directory path (ComfyUI_Eclipse/templates/prompt/)
    #     target_dir: Target directory path (ComfyUI/models/wildcards/smartprompt/)
    #     force: If True, copy files even if target directory exists (for empty folders)
    #
    # Returns:
    #     True if copy was successful or target already exists, False on error
    import os
    import shutil
    
    # If target already exists and not forcing, skip copy
    if os.path.exists(target_dir) and not force:
        return True
    
    # If source doesn't exist, nothing to copy
    if not os.path.exists(source_dir):
        log.warning("Setup", f"Smart Prompt source directory not found: {source_dir}")
        return False
    
    try:
        # Create target directory and copy all contents
        os.makedirs(target_dir, exist_ok=True)
        
        # Copy directory tree
        for item in os.listdir(source_dir):
            source_item = os.path.join(source_dir, item)
            target_item = os.path.join(target_dir, item)
            
            if os.path.isdir(source_item):
                shutil.copytree(source_item, target_item, dirs_exist_ok=True)
            else:
                shutil.copy2(source_item, target_item)
        
        log.msg("Setup", "Smart Prompt files copied to wildcards folder for wildcard integration")
        return True
        
    except Exception as e:
        log.warning("Setup", f"Failed to copy Smart Prompt files to wildcards: {e}")
        return False


def copy_config_file(source_file: str, target_file: str, force: bool = False) -> bool:
    # Copy a single config file from source to target if target doesn't exist.
    # Use this for individual config files like llm_few_shot_training.json.
    #
    # Args:
    #     source_file: Source file path (full path to the template file)
    #     target_file: Target file path (full path to the destination)
    #     force: If True, overwrite existing file
    #
    # Returns:
    #     True if copy was successful or target already exists, False on error
    import os
    import shutil
    
    # If target already exists and not forcing, skip copy
    if os.path.isfile(target_file) and not force:
        return True
    
    # If source doesn't exist, nothing to copy
    if not os.path.isfile(source_file):
        log.warning("Setup", f"Config source file not found: {source_file}")
        return False
    
    try:
        # Create target directory if needed
        target_dir = os.path.dirname(target_file)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_file, target_file)
        
        filename = os.path.basename(target_file)
        if force:
            log.msg("Setup", f"Config file updated: {filename}")
        else:
            log.msg("Setup", f"Config file copied: {filename}")
        return True
        
    except Exception as e:
        log.warning("Setup", f"Failed to copy config file {os.path.basename(source_file)}: {e}")
        return False


def ensure_config_files(source_dir: str, target_dir: str, files: list, force: bool = False) -> dict:
    # Ensure multiple config files exist in target directory.
    # Copies missing files from source directory, optionally force-updates all.
    #
    # Args:
    #     source_dir: Source directory containing template config files
    #     target_dir: Target directory for user config files
    #     files: List of filenames to check and copy
    #     force: If True, overwrite all existing files with source versions
    #
    # Returns:
    #     Dict with 'copied', 'skipped', 'failed' lists of filenames
    import os
    
    results = {'copied': [], 'updated': [], 'skipped': [], 'failed': []}
    
    for filename in files:
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(target_dir, filename)
        
        # Check if target already exists
        target_exists = os.path.isfile(target_file)
        
        if target_exists and not force:
            results['skipped'].append(filename)
            continue
        
        # Try to copy
        if copy_config_file(source_file, target_file, force=force):
            if target_exists and force:
                results['updated'].append(filename)
            else:
                results['copied'].append(filename)
        else:
            results['failed'].append(filename)
    
    return results


def create_junction(source_dir: str, link_dir: str) -> bool:
    # Create a junction (Windows) or symlink (Linux/macOS) from link_dir to source_dir.
    # This enables wildcards integration without file duplication.
    #
    # Args:
    #     source_dir: Target directory path (models/Eclipse/smart_prompt/)
    #     link_dir: Junction/symlink path (models/wildcards/smart_prompt/)
    #
    # Returns:
    #     True if junction created successfully or already exists, False on error
    import os
    import platform
    import subprocess
    
    # If link already exists, skip creation
    if os.path.exists(link_dir):
        return True
    
    # If source doesn't exist, can't create junction
    if not os.path.exists(source_dir):
        log.warning("Setup", f"Junction source directory not found: {source_dir}")
        return False
    
    try:
        # Create parent directory if needed
        parent_dir = os.path.dirname(link_dir)
        os.makedirs(parent_dir, exist_ok=True)
        
        system = platform.system()
        
        if system == "Windows":
            # Use mklink /J for directory junction on Windows
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", link_dir, source_dir],
                check=True,
                capture_output=True
            )
            log.msg("Setup", "Created junction: wildcards/smart_prompt → Eclipse/smart_prompt")
        else:
            # Use ln -s for symbolic link on Linux/macOS
            os.symlink(source_dir, link_dir, target_is_directory=True)
            log.msg("Setup", "Created symlink: wildcards/smart_prompt → Eclipse/smart_prompt")
        
        return True
        
    except Exception as e:
        # Silent failure - junction is optional for wildcards integration
        log.warning("Setup", f"Could not create junction for wildcards integration (optional): {e}")
        return False


def migrate_old_folders(comfyui_root: str) -> None:
    # Migrate user files from old folder structure to new Eclipse structure.
    # This is a one-time migration to preserve user customizations.
    #
    # Old locations:
    #   - models/smart_loader_templates → models/Eclipse/loader_templates
    #   - models/wildcards/smartprompt → models/Eclipse/smart_prompt
    #
    # Args:
    #     comfyui_root: ComfyUI root directory path
    import os
    import shutil
    
    migrations = [
        {
            'old': os.path.join(comfyui_root, 'models', 'smart_loader_templates'),
            'new': os.path.join(comfyui_root, 'models', 'Eclipse', 'loader_templates'),
            'name': 'Smart Loader templates'
        },
        {
            'old': os.path.join(comfyui_root, 'models', 'wildcards', 'smartprompt'),
            'new': os.path.join(comfyui_root, 'models', 'Eclipse', 'smart_prompt'),
            'name': 'Smart Prompt files'
        }
    ]
    
    for migration in migrations:
        old_path = migration['old']
        new_path = migration['new']
        name = migration['name']
        
        # Skip if old location doesn't exist
        if not os.path.exists(old_path):
            continue
        
        # Skip if new location already has content (already migrated or fresh install)
        if os.path.exists(new_path) and os.listdir(new_path):
            try:
                # Clean up old location if new location exists
                shutil.rmtree(old_path)
                log.msg("Migration", f"Removed old {name} folder (migrated previously)")
            except Exception as e:
                log.warning("Migration", f"Could not remove old {name} folder: {e}")
            continue
        
        try:
            # Create parent directory if needed
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            
            # Move the entire directory to new location
            if os.path.exists(new_path):
                # New path exists but is empty, remove it first
                shutil.rmtree(new_path)
            
            shutil.move(old_path, new_path)
            log.msg("Migration", f"Migrated {name} to Eclipse folder")
            
        except Exception as e:
            # If move fails, try copy and delete
            try:
                os.makedirs(new_path, exist_ok=True)
                
                # Copy directory tree
                for item in os.listdir(old_path):
                    source_item = os.path.join(old_path, item)
                    target_item = os.path.join(new_path, item)
                    
                    if os.path.isdir(source_item):
                        shutil.copytree(source_item, target_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_item, target_item)
                
                # Remove old directory after successful copy
                shutil.rmtree(old_path)
                log.msg("Migration", f"Migrated {name} to Eclipse folder (via copy)")
                
            except Exception as copy_error:
                log.warning("Migration", f"Failed to migrate {name}: {copy_error}")


def strip_thinking_tags(text: str) -> tuple[str, str]:
    # Strip XML-style and bracket-style tags from model output.
    #
    # Models like Qwen3-VL-Thinking, DeepSeek-R1, MiroThinker output
    # various tags like <think>, <summary>, <output>, [THINK], [/THINK], etc.
    # These wrap reasoning/planning that should be removed from final output.
    #
    # If stripping would result in empty output, return original text unchanged.
    #
    # Uses pre-compiled regex patterns defined at module level for performance.
    #
    # Args:
    #     text: Raw model output text
    #
    # Returns:
    #     Tuple of (cleaned_text, raw_text) where cleaned_text has all tags removed
    raw_text = text.strip() if text else ""
    if not raw_text:
        return "", ""
    
    cleaned_text = raw_text
    
    # Remove all wrapper tag blocks and handle orphan tags
    for tag in _THINKING_WRAPPER_TAGS:
        # Remove complete <tag>...</tag> blocks (XML-style)
        cleaned_text = _RE_THINKING_XML_BLOCK[tag].sub('', cleaned_text).strip()
        
        # Remove complete [TAG]...[/TAG] blocks (bracket-style)
        cleaned_text = _RE_THINKING_BRACKET_BLOCK[tag].sub('', cleaned_text).strip()
        
        # Handle orphan XML tags (closing without opening)
        if _RE_THINKING_XML_CLOSE[tag].search(cleaned_text) and not _RE_THINKING_XML_OPEN[tag].search(cleaned_text):
            cleaned_text = _RE_THINKING_XML_ORPHAN_CLOSE[tag].sub('', cleaned_text).strip()
        # Handle orphan XML tags (opening without closing)
        if _RE_THINKING_XML_OPEN[tag].search(cleaned_text) and not _RE_THINKING_XML_CLOSE[tag].search(cleaned_text):
            cleaned_text = _RE_THINKING_XML_ORPHAN_OPEN[tag].sub('', cleaned_text).strip()
        
        # Handle orphan bracket tags (closing without opening)
        if _RE_THINKING_BRACKET_CLOSE[tag].search(cleaned_text) and not _RE_THINKING_BRACKET_OPEN[tag].search(cleaned_text):
            cleaned_text = _RE_THINKING_BRACKET_ORPHAN_CLOSE[tag].sub('', cleaned_text).strip()
        # Handle orphan bracket tags (opening without closing)
        if _RE_THINKING_BRACKET_OPEN[tag].search(cleaned_text) and not _RE_THINKING_BRACKET_CLOSE[tag].search(cleaned_text):
            cleaned_text = _RE_THINKING_BRACKET_ORPHAN_OPEN[tag].sub('', cleaned_text).strip()
    
    # Safety check: if stripping left us with nothing, return original
    if not cleaned_text:
        return raw_text, raw_text
    
    # Remove any remaining XML-style tags (but keep their content)
    cleaned_text = _RE_XML_ANY_TAG.sub('', cleaned_text).strip()
    
    # Remove any remaining bracket-style tags (but keep their content)
    cleaned_text = _RE_BRACKET_ANY_TAG.sub('', cleaned_text).strip()
    
    # Remove markdown code fences that some models add
    cleaned_text = _RE_CODE_FENCE_OPEN.sub('', cleaned_text).strip()
    cleaned_text = _RE_CODE_FENCE_CLOSE.sub('', cleaned_text).strip()
    
    return cleaned_text, raw_text


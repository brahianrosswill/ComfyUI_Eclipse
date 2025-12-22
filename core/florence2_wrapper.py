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

# Florence-2 Wrapper for Smart LML
#
# This module provides graceful loading support for Florence-2 models with fallback.
# Handles import from comfyui-florence2 extension if available.
#
# Key Features:
# - Automatic detection of comfyui-florence2 extension
# - Graceful fallback to transformers AutoModel
# - Proper package path management
# - Support for custom model implementations

import sys
from typing import Optional, Any
from pathlib import Path
import torch

from .smartlm_templates import get_dev_mode
from .logger import log


# Local logging helpers with "Florence-2" prefix
def debug_log(message: str):
    # Print debug message only when log_level is 'debug'.
    log.debug("Florence-2", message)


def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning("Florence-2", message)


def msg_log(message: str):
    # Print regular message (always shown).
    log.msg("Florence-2", message)


def error_log(message: str):
    # Print error message (always shown).
    log.error("Florence-2", message)


# Transformers version detection
import transformers
transformers_version = tuple(map(int, transformers.__version__.split('.')[:2])) if transformers.__version__[0].isdigit() else (4, 0)
if 'rc' in transformers.__version__.lower():
    transformers_version = (5, 0)

# Florence-2 availability flags
FLORENCE2_CUSTOM_AVAILABLE = False
Florence2ForConditionalGeneration: Optional[Any] = None
Florence2Config: Optional[Any] = None
Florence2Processor: Optional[Any] = None

# Try to import custom Florence-2 implementation
try:
    # Path: core/florence2_wrapper.py -> ComfyUI_Eclipse -> custom_nodes
    custom_nodes_path = Path(__file__).parent.parent.parent
    florence_path = custom_nodes_path / "comfyui-florence2"
    
    if florence_path.exists():
        debug_log("Attempting to import custom Florence-2 classes...")
        
        import importlib.util
        import types
        
        # Create a fake package to support relative imports
        fake_package_name = "comfyui_florence2_custom"
        fake_package = types.ModuleType(fake_package_name)
        fake_package.__path__ = [str(florence_path)]
        fake_package.__file__ = str(florence_path / "__init__.py")
        sys.modules[fake_package_name] = fake_package
        
        # For v5: Skip custom implementation - comfyui-florence2 is incompatible with v5
        # Florence-2 uses custom modeling code that doesn't work with transformers v5
        if transformers_version >= (5, 0):
            warning_log("Incompatible with transformers v5 - use Qwen-VL or Mistral instead")
            # Don't set FLORENCE2_CUSTOM_AVAILABLE, and don't attempt further loading
            FLORENCE2_V5_SKIPPED = True
            raise ImportError("Florence-2 incompatible with transformers v5")
        
        # v4: Import configuration from comfyui-florence2
        config_spec = importlib.util.spec_from_file_location(
            f"{fake_package_name}.configuration_florence2",
            florence_path / "configuration_florence2.py"
        )
        if config_spec and config_spec.loader:
            config_module = importlib.util.module_from_spec(config_spec)
            config_module.__package__ = fake_package_name
            sys.modules[f"{fake_package_name}.configuration_florence2"] = config_module
            config_spec.loader.exec_module(config_module)
            Florence2Config = config_module.Florence2Config
        
        # Import modeling (contains Florence2ForConditionalGeneration)
        modeling_spec = importlib.util.spec_from_file_location(
            f"{fake_package_name}.modeling_florence2",
            florence_path / "modeling_florence2.py"
        )
        if modeling_spec and modeling_spec.loader:
            modeling_module = importlib.util.module_from_spec(modeling_spec)
            modeling_module.__package__ = fake_package_name
            sys.modules[f"{fake_package_name}.modeling_florence2"] = modeling_module
            
            # Inject the config module reference for relative imports
            modeling_module.configuration_florence2 = config_module
            
            modeling_spec.loader.exec_module(modeling_module)
            Florence2ForConditionalGeneration = modeling_module.Florence2ForConditionalGeneration
        
        # Import processing (if it exists - comfyui-florence2 uses AutoProcessor, not custom)
        processing_file = florence_path / "processing_florence2.py"
        if processing_file.exists():
            processing_spec = importlib.util.spec_from_file_location(
                f"{fake_package_name}.processing_florence2",
                processing_file
            )
            if processing_spec and processing_spec.loader:
                processing_module = importlib.util.module_from_spec(processing_spec)
                processing_module.__package__ = fake_package_name
                sys.modules[f"{fake_package_name}.processing_florence2"] = processing_module
                processing_spec.loader.exec_module(processing_module)
                Florence2Processor = processing_module.Florence2Processor
        
        # Check if we got the essential classes
        if Florence2ForConditionalGeneration and Florence2Config:
            msg_log("✓ Custom Florence-2 classes imported successfully")
            FLORENCE2_CUSTOM_AVAILABLE = True
        else:
            warning_log("Custom Florence-2 classes incomplete, will use AutoModel")
    else:
        warning_log("comfyui-florence2 extension not found, will use AutoModel")
        
except Exception as e:
    error_msg = str(e)
    # Suppress expected errors (v5 skip, relative import when extension not installed)
    expected_errors = ["incompatible with transformers v5", "attempted relative import"]
    if not any(exp in error_msg for exp in expected_errors):
        import traceback
        warning_log(f"Could not import custom Florence-2: {e}")
        traceback.print_exc()
        warning_log("Will fall back to transformers AutoModel")


def load_florence2_model(model_path: str, **load_kwargs) -> Any:
    # Load Florence-2 model with custom implementation if available, fallback to AutoModel.
    # Supports both local model paths and HuggingFace repo IDs.
    #
    # Args:
    #     model_path: Path to local model directory or HuggingFace repo ID
    #     **load_kwargs: Additional arguments for from_pretrained (dtype, device_map, etc.)
    #
    # Returns:
    #     Loaded Florence-2 model
    
    # Check for transformers v5 incompatibility BEFORE attempting to load
    if transformers_version >= (5, 0):
        # Try to load config to check for v5-incompatible attributes
        try:
            from transformers import AutoConfig
            config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
            
            # Check for known v5-incompatible attributes
            incompatible_attrs = []
            if hasattr(config, '_tied_weights_keys'):
                # v5 changed _tied_weights_keys from list to dict
                if isinstance(config._tied_weights_keys, list):
                    incompatible_attrs.append('_tied_weights_keys (list type)')
            
            if incompatible_attrs:
                error_msg = (
                    f"Florence-2 model is incompatible with transformers {transformers.__version__}.\n"
                    f"Detected incompatible attributes: {', '.join(incompatible_attrs)}\n\n"
                    f"Solutions:\n"
                    f"  1. Downgrade to transformers 4.46.3: pip install transformers==4.46.3\n"
                    f"  2. Use Qwen2.5-VL-3B-Instruct for detection tasks (7 GB VRAM, supports v5)\n\n"
                    f"Florence-2 requires updated model files from Microsoft for v5 compatibility."
                )
                error_log(error_msg)
                raise RuntimeError(error_msg)
        except Exception as e:
            if "incompatible" in str(e):
                raise
            # If config check fails for other reasons, continue with attempt
            warning_log(f"Could not validate v5 compatibility: {e}")
    
    # Determine if loading from local path or remote
    is_local = Path(model_path).exists()
    source = "local" if is_local else "remote"
    
    # Verify model integrity if loading from local cache
    if is_local:
        from .smartlm_files import verify_model_integrity
        # Try to get repo_id from load_kwargs if available (for hash lookup from HuggingFace)
        repo_id = load_kwargs.pop('repo_id', '') if isinstance(load_kwargs, dict) else ''
        if not verify_model_integrity(Path(model_path), repo_id):
            raise RuntimeError(f"Florence-2 model integrity check failed for {model_path}. The model may be corrupted. Please delete and re-download.")
    
    # CRITICAL: Resolve "auto" attention mode BEFORE trying any loading
    # Florence-2 doesn't support "auto" - must be resolved to specific mode
    requested_attn = load_kwargs.get('attn_implementation', 'auto')
    
    if requested_attn == 'auto':
        # Check if flash-attn is available
        try:
            import flash_attn
            load_kwargs['attn_implementation'] = 'flash_attention_2'
            requested_attn = 'flash_attention_2'
            msg_log("Auto mode: Selected flash_attention_2 (flash-attn available)")
        except ImportError:
            # Fall back to sdpa (PyTorch built-in, good performance)
            load_kwargs['attn_implementation'] = 'sdpa'
            requested_attn = 'sdpa'
            msg_log("Auto mode: Selected sdpa (flash-attn not available)")
    
    # Try custom implementation first
    if FLORENCE2_CUSTOM_AVAILABLE and Florence2ForConditionalGeneration:
        try:
            debug_log(f"Loading from {source} with custom implementation: {model_path}")
            model = Florence2ForConditionalGeneration.from_pretrained(
                model_path,
                local_files_only=is_local,  # Prevent online lookup for local models
                **load_kwargs
            )
            debug_log("Loaded with custom implementation")
            return model
        except Exception as e:
            warning_log(f"Custom implementation failed: {e}")
            warning_log("Falling back to AutoModel...")
    
    # Fallback to AutoModel (v4 compatible)
    # Note: v5 incompatibility already checked above, should not reach here with v5
    from transformers import AutoModelForCausalLM
    msg_log(f"Loading from {source} with AutoModelForCausalLM: {model_path}")
    
    # For transformers < 4.51.0, apply flash_attn workaround (matching comfyui-florence2)
    if transformers.__version__ < '4.51.0':
        from unittest.mock import patch
        from transformers.dynamic_module_utils import get_imports
        
        def fixed_get_imports(filename):
            # Workaround for unnecessary flash_attn requirement
            try:
                if not str(filename).endswith("modeling_florence2.py"):
                    return get_imports(filename)
                imports = get_imports(filename)
                if "flash_attn" in imports:
                    imports.remove("flash_attn")
            except:
                pass
            return imports
        
        msg_log(f"Applying flash_attn workaround for transformers {transformers.__version__}")
    
    # Handle flash_attention_2 gracefully with fallback to sdpa
    # Some cached Florence-2 model code may not declare Flash Attention 2 support
    
    # Apply workaround context manager if needed
    if transformers.__version__ < '4.51.0':
        load_context = patch("transformers.dynamic_module_utils.get_imports", fixed_get_imports)
    else:
        from contextlib import nullcontext
        load_context = nullcontext()
    
    with load_context:
        if requested_attn == 'flash_attention_2':
            try:
                msg_log("Attempting Flash Attention 2...")
                model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    trust_remote_code=True,
                    local_files_only=is_local,
                    **load_kwargs
                )
                msg_log("✓ Loaded with Flash Attention 2")
                return model
            except (ValueError, ImportError) as e:
                if "does not support Flash Attention 2.0" in str(e) or "flash_attn" in str(e):
                    warning_log("Flash Attention 2 not supported by cached model code")
                    error_log("Your Florence-2 model uses outdated cached code from HuggingFace")
                    
                    # Extract cache path from model_path for user guidance
                    import os
                    cache_hint = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "modules", "transformers_modules")
                    model_name = Path(model_path).name if is_local else model_path.split('/')[-1]
                    
                    error_log("To update: Delete cached folder and restart ComfyUI:")
                    error_log(f"  Location: {cache_hint}\\{model_name.replace('/', '_').replace('-', '_hyphen_')}")
                    error_log(f"  Or run: Remove-Item '{cache_hint}\\{model_name.replace('/', '_').replace('-', '_hyphen_')}' -Recurse -Force")
                    warning_log("Falling back to SDPA (still faster than eager mode)")
                    
                    load_kwargs['attn_implementation'] = 'sdpa'
                else:
                    raise
        
        # Load with requested attention mode (or fallback to sdpa)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            local_files_only=is_local,  # Prevent online lookup for local models
            **load_kwargs
        )
    
    # Add _supports_sdpa to model class if not present (custom models from HF may lack it)
    if not hasattr(type(model), '_supports_sdpa'):
        warning_log(f"Adding _supports_sdpa=True to {type(model).__name__}")
        type(model)._supports_sdpa = True
    
    # Also patch language_model subcomponent if it exists (for Florence2ForConditionalGeneration)
    if hasattr(model, 'language_model') and not hasattr(type(model.language_model), '_supports_sdpa'):
        warning_log(f"Adding _supports_sdpa=True to {type(model.language_model).__name__}")
        type(model.language_model)._supports_sdpa = True
    
    attn_used = load_kwargs.get('attn_implementation', 'auto')
    msg_log(f"✓ Loaded with AutoModel from {source}, attention={attn_used}")
    return model


def load_florence2_processor(model_path: str, **kwargs) -> Any:
    # Load Florence-2 processor with custom implementation if available, fallback to AutoProcessor.
    # Supports both local model paths and HuggingFace repo IDs.
    #
    # Args:
    #     model_path: Path to local model directory or HuggingFace repo ID
    #     **kwargs: Additional arguments for from_pretrained
    #
    # Returns:
    #     Loaded Florence-2 processor
    # Determine if loading from local path or remote
    model_path_obj = Path(model_path)
    is_local = model_path_obj.exists()
    
    # Check if the local folder has the required dynamic module file for the processor
    # If not (e.g., models from comfyui-florence2 node), we need to allow online lookup
    has_processor_module = is_local and (model_path_obj / "processing_florence2.py").exists()
    local_files_only = has_processor_module  # Only force local if we have all required files
    
    # Try custom processor first
    if FLORENCE2_CUSTOM_AVAILABLE and Florence2Processor:
        try:
            processor = Florence2Processor.from_pretrained(
                model_path,
                local_files_only=local_files_only,
                **kwargs
            )
            return processor
        except Exception as e:
            warning_log(f"Custom processor failed: {e}, using AutoProcessor")
    
    # Fallback to AutoProcessor or native Florence2Processor
    # v5: Try native Florence2Processor for better compatibility
    if transformers_version >= (5, 0):
        try:
            from transformers import Florence2Processor as NativeFlorenceProcessor
            try:
                processor = NativeFlorenceProcessor.from_pretrained(
                    model_path,
                    local_files_only=local_files_only,
                    **kwargs
                )
                msg_log("✓ Loaded processor with native Florence2Processor (v5)")
                return processor
            except TypeError as e:
                if "extra_special_tokens" in str(e):
                    error_log("✗ Florence-2 processor incompatible with transformers v5")
                    raise RuntimeError(f"Florence-2 processor incompatible with transformers v5. Please use transformers v4.") from e
                raise
        except ImportError:
            warning_log("Native Florence2Processor not available, using AutoProcessor")
    
    # v4 or fallback: Use AutoProcessor
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(
        model_path,
        trust_remote_code=True,
        local_files_only=local_files_only,  # Allow online lookup if processor module is missing
        **kwargs
    )
    return processor


# Export public API
__all__ = [
    'FLORENCE2_CUSTOM_AVAILABLE',
    'Florence2ForConditionalGeneration',
    'Florence2Config',
    'Florence2Processor',
    'load_florence2_model',
    'load_florence2_processor',
]




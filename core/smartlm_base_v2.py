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

# SmartLM Base v2 - Method-First Workflow Functions
#
# Contains v2-specific functionality:
# - Method-first support matrix (reversed from v1)
# - Model auto-discovery
# - Backend routing (load_model_with_backend)
# - Dynamic model filtering
#
# Uses shared modules for common functionality:
# - smartlm_types.py: Enums and type detection
# - smartlm_templates.py: Template loading/saving
# - smartlm_device.py: VRAM/GPU management
# - smartlm_files.py: File operations and downloads
import os
import gc
import re
import torch
from pathlib import Path
from typing import Dict, List, Any, Optional

# ============================================================================
# Import from shared modular files
# ============================================================================

# Types and enums (single source of truth)
from .smartlm_types import (
    ModelType, ModelFamily, LoadingMethod,
    METHOD_SUPPORT_V2,
    get_model_family_list, get_loading_method_list,
    get_supported_families, get_supported_families_by_name,
    get_model_family_from_name, detect_model_type,
    is_mistral3_vision_model, detect_llava_or_mllama,
)

# Template functions
from .smartlm_templates import (
    get_template_dir, get_template_list, load_template,
    update_template_settings,
    load_prompt_configs, MODEL_CONFIGS,
    get_llm_models_path,
    TemplateContext,
)

# Centralized logger
from .logger import log


_LOG_PREFIX = "SmartLM"


def get_dtype_kwarg_name() -> str:
    # Get the correct dtype parameter name for from_pretrained.
    #
    # In transformers v5, 'torch_dtype' is deprecated in favor of 'dtype'.
    # This helper returns the appropriate parameter name based on version.
    #
    # Returns:
    #     'dtype' for transformers >= 5.0, 'torch_dtype' otherwise
    try:
        import transformers
        version_str = transformers.__version__
        # Handle dev versions like "5.0.0.dev0"
        version_parts = version_str.split('.')[:2]
        major = int(version_parts[0])
        if major >= 5:
            return "dtype"
    except Exception:
        pass
    return "torch_dtype"


# Cached version for performance
_DTYPE_KWARG_NAME = None

def dtype_kwarg() -> str:
    # Cached version of get_dtype_kwarg_name.
    global _DTYPE_KWARG_NAME
    if _DTYPE_KWARG_NAME is None:
        _DTYPE_KWARG_NAME = get_dtype_kwarg_name()
    return _DTYPE_KWARG_NAME


# Device and memory functions
from .smartlm_device import (
    get_device_info, cleanup_memory_before_load,
    is_llama_cpp_available, get_llama_cpp_module,
    auto_select_attention, auto_select_quantization,
    LLAMA_CPP_AVAILABLE, LLAMA_CPP_MODULE,
)


# ============================================================================
# Transformers Model Cache
# ============================================================================
# Cache for loaded Transformers models to avoid reloading on each queue
# Key: "{model_path}:{quantization}:{attention}" 
# Value: (model, processor, model_type)

_transformers_model_cache: Dict[str, tuple] = {}


def get_transformers_cache_key(model_path: str, quantization: str, attention: str) -> str:
    # Build cache key for Transformers models.
    return f"{model_path}:{quantization or 'none'}:{attention or 'auto'}"


def get_cached_transformers_model(cache_key: str) -> Optional[tuple]:
    # Get cached Transformers model if available.
    #
    # Returns:
    #     Tuple of (model, processor, model_type) or None if not cached
    if cache_key in _transformers_model_cache:
        log.debug(_LOG_PREFIX, f"Using cached Transformers model: {cache_key.split(':')[0].split('/')[-1]}")
        return _transformers_model_cache[cache_key]
    return None


def set_cached_transformers_model(cache_key: str, model: Any, processor: Any, model_type: ModelType):
    # Store Transformers model in cache.
    #
    # Also clears any other cached models to avoid VRAM accumulation.
    global _transformers_model_cache
    
    # Clear existing cache if loading a different model
    if _transformers_model_cache and cache_key not in _transformers_model_cache:
        log.debug(_LOG_PREFIX, "Clearing previous Transformers model from cache (different model requested)")
        clear_transformers_cache()
    
    _transformers_model_cache[cache_key] = (model, processor, model_type)
    log.msg(_LOG_PREFIX, f"Cached Transformers model for reuse")


def clear_transformers_cache():
    # Clear all cached Transformers models and free VRAM.
    global _transformers_model_cache
    
    if not _transformers_model_cache:
        return
    
    log.debug(_LOG_PREFIX, "Clearing Transformers model cache...")
    
    for key, (model, processor, _) in list(_transformers_model_cache.items()):
        try:
            # Clear any cached states/gradients to help free memory
            if hasattr(model, 'eval'):
                model.eval()
            if hasattr(model, 'zero_grad'):
                try:
                    model.zero_grad(set_to_none=True)
                except Exception:
                    pass
            # NOTE: Don't call model.to('cpu') - it's very slow for large models
            # (can take 10-30+ seconds for 7B+ models) and requires that much free RAM.
            # Instead, just delete references and let CUDA free memory via empty_cache().
            del model
            del processor
        except Exception as e:
            log.debug(_LOG_PREFIX, f"  Error clearing model {key}: {e}")
    
    _transformers_model_cache.clear()
    
    # Force garbage collection multiple passes and VRAM cleanup
    for _ in range(3):
        gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    
    log.debug(_LOG_PREFIX, "Transformers cache cleared")


def get_cached_model_key() -> Optional[str]:
    # Get the key of the currently cached Transformers model, if any.
    #
    # Used to check if a different model needs to evict the current one.
    if _transformers_model_cache:
        return next(iter(_transformers_model_cache.keys()))
    return None


def is_transformers_cache_empty() -> bool:
    # Check if the Transformers model cache is empty.
    return not bool(_transformers_model_cache)


# ============================================================================
# GGUF Model Cache (Native llama-cpp-python ONLY)
# ============================================================================
# Cache for loaded GGUF models using native llama-cpp-python to avoid reloading.
# This cache is NOT used by Docker backends (llama.cpp Docker, Ollama Docker).
# Docker backends manage their own model lifecycle via container lifecycle.
#
# Key: "{model_path}:{context_size}"
# Value: (model, chat_handler, model_type)
# 
# IMPORTANT: With proper KV cache clearing between calls, GGUF models
# can now be safely reused. The chat_handler's mtmd_ctx is lazily
# initialized once and reusable across calls.
# ============================================================================

_gguf_model_cache: Dict[str, tuple] = {}


def get_gguf_cache_key(model_path: str, context_size: int) -> str:
    # Build cache key for GGUF models.
    return f"{model_path}:{context_size}"


def get_cached_gguf_model(cache_key: str) -> Optional[tuple]:
    # Get cached GGUF model if available.
    #
    # Returns:
    #     Tuple of (model, chat_handler, model_type) or None if not cached
    if cache_key in _gguf_model_cache:
        log.debug(_LOG_PREFIX, f"Using cached GGUF model: {cache_key.split(':')[0].split('/')[-1]}")
        return _gguf_model_cache[cache_key]
    return None


def set_cached_gguf_model(cache_key: str, model: Any, chat_handler: Any, model_type: 'ModelType'):
    # Store GGUF model in cache.
    #
    # Also clears any other cached models to avoid VRAM accumulation.
    global _gguf_model_cache
    
    # Clear existing cache if loading a different model
    if _gguf_model_cache and cache_key not in _gguf_model_cache:
        log.debug(_LOG_PREFIX, "Clearing previous GGUF model from cache (different model requested)")
        clear_gguf_cache()
    
    _gguf_model_cache[cache_key] = (model, chat_handler, model_type)
    log.msg(_LOG_PREFIX, f"Cached GGUF model for reuse")


def clear_gguf_cache():
    # Clear all cached GGUF models and free VRAM.
    global _gguf_model_cache
    
    if not _gguf_model_cache:
        return
    
    log.debug(_LOG_PREFIX, "Clearing GGUF model cache...")
    
    # Import the proper cleanup function that handles vision handlers
    from .smartlm_gguf import cleanup_chat_handler_vision
    
    for key, (model, chat_handler, _) in list(_gguf_model_cache.items()):
        try:
            # Cleanup chat_handler FIRST (holds CLIP/mtmd vision model - 1-2GB VRAM)
            # Must use proper cleanup that calls clip_free/mtmd_free
            if chat_handler is not None:
                log.debug(_LOG_PREFIX, f"  Cleaning up chat_handler for {key}")
                cleanup_chat_handler_vision(chat_handler)
            
            # Then close the model (calls llama_free in C)
            if model is not None:
                # Reset KV cache first (may not be available in all versions)
                try:
                    if hasattr(model, 'reset'):
                        model.reset()
                except Exception:
                    pass
                # Close the model - this is the safe way to free resources
                if hasattr(model, 'close') and callable(model.close):
                    model.close()
            
            del model
            del chat_handler
        except Exception as e:
            log.debug(_LOG_PREFIX, f"  Error clearing GGUF model {key}: {e}")
    
    _gguf_model_cache.clear()
    
    # Force garbage collection and VRAM cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    
    log.debug(_LOG_PREFIX, "GGUF cache cleared")


def get_cached_gguf_model_key() -> Optional[str]:
    # Get the key of the currently cached GGUF model, if any.
    if _gguf_model_cache:
        return next(iter(_gguf_model_cache.keys()))
    return None


def is_gguf_cache_empty() -> bool:
    # Check if the GGUF model cache is empty.
    return not bool(_gguf_model_cache)


def clear_all_model_caches():
    # Clear ALL model caches across all backends to free VRAM.
    #
    # This is called when loading a different model to ensure VRAM is freed
    # BEFORE the new model is loaded, preventing OOM in multi-node workflows.
    #
    # Clears:
    # - Transformers cache (_transformers_model_cache)
    # - GGUF cache (_gguf_model_cache)
    # - vLLM Native cache (if available)
    log.debug(_LOG_PREFIX, "Clearing all model caches for multi-node workflow...")
    
    # Clear Transformers cache
    clear_transformers_cache()
    
    # Clear GGUF cache
    clear_gguf_cache()
    
    # Clear vLLM Native cache if module is loaded
    try:
        from . import smartlm_vllm_native
        if hasattr(smartlm_vllm_native, '_vllm_model_cache'):
            smartlm_vllm_native.unload_vllm()  # Unloads all models
            log.debug(_LOG_PREFIX, "  Cleared vLLM Native cache")
    except ImportError:
        pass  # vLLM native not available
    
    # Force final cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    
    log.debug(_LOG_PREFIX, "All model caches cleared")


def stop_all_docker_containers():
    # Stop all running Docker containers for LLM backends.
    #
    # This is called when switching between backends to free GPU VRAM.
    # Each Docker container holds its model in GPU memory, so we need to
    # stop them when switching to a different backend.
    #
    # Stops:
    # - vLLM Docker containers
    # - SGLang Docker containers
    # - Ollama Docker container
    # - llama.cpp Docker containers
    log.debug(_LOG_PREFIX, "Stopping all Docker containers for backend switch...")
    
    # Stop vLLM Docker containers
    try:
        from . import smartlm_vllm_docker
        if smartlm_vllm_docker.get_running_vllm_containers():
            log.msg(_LOG_PREFIX, "Stopping vLLM Docker container(s)...")
            smartlm_vllm_docker.stop_vllm_container()
    except ImportError:
        pass
    except Exception as e:
        log.debug(_LOG_PREFIX, f"  Error stopping vLLM containers: {e}")
    
    # Stop SGLang Docker containers
    try:
        from . import smartlm_sglang_docker
        if smartlm_sglang_docker.get_running_sglang_containers():
            log.msg(_LOG_PREFIX, "Stopping SGLang Docker container(s)...")
            smartlm_sglang_docker.stop_sglang_container()
    except ImportError:
        pass
    except Exception as e:
        log.debug(_LOG_PREFIX, f"  Error stopping SGLang containers: {e}")
    
    # Stop Ollama Docker container
    try:
        from . import smartlm_ollama_docker
        if smartlm_ollama_docker.is_ollama_container_running():
            log.msg(_LOG_PREFIX, "Stopping Ollama Docker container...")
            smartlm_ollama_docker.stop_ollama_container()
    except ImportError:
        pass
    except Exception as e:
        log.debug(_LOG_PREFIX, f"  Error stopping Ollama container: {e}")
    
    # Stop llama.cpp Docker containers
    try:
        from . import smartlm_llamacpp_docker
        if smartlm_llamacpp_docker.get_running_llamacpp_containers():
            log.msg(_LOG_PREFIX, "Stopping llama.cpp Docker container(s)...")
            smartlm_llamacpp_docker.stop_llamacpp_container()
    except ImportError:
        pass
    except Exception as e:
        log.debug(_LOG_PREFIX, f"  Error stopping llama.cpp containers: {e}")
    
    log.debug(_LOG_PREFIX, "Docker containers stopped")


# ============================================================================
# FP8 Dequantization Support
# ============================================================================

def dequantize_fp8_model(model_path: str, target_dtype: torch.dtype = torch.bfloat16) -> dict:
    # Manually dequantize FP8 weights to target dtype (bf16 by default).
    #
    # FP8 weights use:
    # - weight: float8_e4m3fn (the quantized weight)
    # - weight_scale_inv: bf16 (inverse scale for dequantization)
    #
    # Dequantization formula: dequant_weight = fp8_weight.to(dtype) * weight_scale_inv
    #
    # Args:
    #     model_path: Path to model folder containing safetensors files
    #     target_dtype: Target dtype for dequantized weights (default: bf16)
    #
    # Returns:
    #     Dictionary of dequantized state_dict
    import safetensors
    from pathlib import Path
    
    model_dir = Path(model_path)
    state_dict = {}
    
    # Find all safetensors files
    safetensor_files = list(model_dir.glob("*.safetensors"))
    if not safetensor_files:
        raise FileNotFoundError(f"No safetensors files found in {model_path}")
    
    log.msg(_LOG_PREFIX, f"Dequantizing FP8 weights to {target_dtype}...")
    
    fp8_count = 0
    total_count = 0
    
    for sf_file in safetensor_files:
        log.debug(_LOG_PREFIX, f"  Processing {sf_file.name}")
        
        with safetensors.safe_open(str(sf_file), framework="pt") as f:
            keys = list(f.keys())
            
            # First pass: identify FP8 weights and their scales
            fp8_weights = {}
            scale_tensors = {}
            normal_tensors = {}
            
            for key in keys:
                tensor = f.get_tensor(key)
                total_count += 1
                
                if tensor.dtype == torch.float8_e4m3fn:
                    fp8_weights[key] = tensor
                    fp8_count += 1
                elif key.endswith(".weight_scale_inv"):
                    # This is a scale tensor for dequantization
                    base_key = key.replace(".weight_scale_inv", ".weight")
                    scale_tensors[base_key] = tensor
                elif key.endswith(".activation_scale"):
                    # Activation scales are not needed for weight dequantization
                    # but we still keep them for potential dynamic quant
                    pass
                else:
                    normal_tensors[key] = tensor
            
            # Dequantize FP8 weights
            for key, fp8_tensor in fp8_weights.items():
                scale_key = key.replace(".weight", ".weight_scale_inv")
                if scale_key in scale_tensors:
                    scale = scale_tensors[scale_key]
                    # Dequantize: convert FP8 to target dtype, then multiply by scale
                    dequant = fp8_tensor.to(target_dtype) * scale
                    state_dict[key] = dequant
                    log.debug(_LOG_PREFIX, f"    Dequantized {key}: {fp8_tensor.dtype} -> {dequant.dtype}")
                else:
                    # No scale found, just convert dtype
                    state_dict[key] = fp8_tensor.to(target_dtype)
                    log.debug(_LOG_PREFIX, f"    Converted {key}: {fp8_tensor.dtype} -> {target_dtype} (no scale)")
            
            # Copy normal tensors
            for key, tensor in normal_tensors.items():
                # Skip scale tensors - they're not needed after dequantization
                if not key.endswith(".weight_scale_inv") and not key.endswith(".activation_scale"):
                    state_dict[key] = tensor if tensor.dtype == target_dtype else tensor.to(target_dtype)
    
    log.msg(_LOG_PREFIX, f"Dequantized {fp8_count}/{total_count} FP8 tensors")
    return state_dict


def load_mistral_with_fp8_dequant(model_path: str, **kwargs) -> tuple:
    # Load Mistral model with FP8 dequantization.
    #
    # This creates the model architecture first, then loads dequantized weights.
    #
    # Args:
    #     model_path: Path to model folder
    #     **kwargs: Additional load kwargs (attn_implementation, etc.)
    #
    # Returns:
    #     Tuple of (model, processor, model_type)
    from transformers import AutoProcessor, AutoConfig, AutoModelForVision2Seq
    import json
    
    log.msg(_LOG_PREFIX, "Loading Mistral FP8 with manual dequantization...")
    log.warning(_LOG_PREFIX, "This may take a few minutes for initial dequantization.")
    
    # Patch config if needed - fix model_type and tie_word_embeddings
    config_path = Path(model_path) / "config.json"
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text())
            needs_patch = False
            
            # Remove quantization_config - we're dequantizing
            if "quantization_config" in config_data:
                del config_data["quantization_config"]
                needs_patch = True
                log.debug(_LOG_PREFIX, "  Removed quantization_config from config")
            
            # Fix text_config.model_type: mistral3/ministral3 -> mistral
            # This makes transformers create MistralModel (text-only) for the language backbone
            if "text_config" in config_data:
                text_model_type = config_data["text_config"].get("model_type", "")
                if text_model_type in ("mistral3", "ministral3"):
                    config_data["text_config"]["model_type"] = "mistral"
                    needs_patch = True
                    log.debug(_LOG_PREFIX, f"  Patched text_config.model_type: {text_model_type} -> mistral")
                
                # Disable tie_word_embeddings in text_config
                if config_data["text_config"].get("tie_word_embeddings", True):
                    config_data["text_config"]["tie_word_embeddings"] = False
                    needs_patch = True
                    log.debug(_LOG_PREFIX, "  Patched text_config.tie_word_embeddings: False")
            
            # Also disable tie_word_embeddings at top level
            if config_data.get("tie_word_embeddings", True):
                config_data["tie_word_embeddings"] = False
                needs_patch = True
                log.debug(_LOG_PREFIX, "  Patched tie_word_embeddings: False")
            
            if needs_patch:
                config_path.write_text(json.dumps(config_data, indent=2))
        except Exception as e:
            log.debug(_LOG_PREFIX, f"  Config patch error: {e}")
    
    # Patch tokenizer_config.json
    tokenizer_config_path = Path(model_path) / "tokenizer_config.json"
    if tokenizer_config_path.exists():
        try:
            tokenizer_data = json.loads(tokenizer_config_path.read_text())
            if tokenizer_data.get("tokenizer_class") == "TokenizersBackend":
                tokenizer_data["tokenizer_class"] = "PreTrainedTokenizerFast"
                tokenizer_config_path.write_text(json.dumps(tokenizer_data, indent=2))
                log.debug(_LOG_PREFIX, "  Patched tokenizer_class: TokenizersBackend -> PreTrainedTokenizerFast")
        except Exception as e:
            log.debug(_LOG_PREFIX, f"  Tokenizer config patch error: {e}")
    
    # Dequantize weights
    state_dict = dequantize_fp8_model(model_path, target_dtype=torch.bfloat16)
    
    # Load config and create model skeleton
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    
    attn_impl = kwargs.get("attn_implementation")
    
    log.msg(_LOG_PREFIX, "Creating model architecture...")
    
    # Create empty model on meta device
    from_config_kwargs = {dtype_kwarg(): torch.bfloat16}
    if attn_impl:
        from_config_kwargs["attn_implementation"] = attn_impl
    
    with torch.device("meta"):
        model = AutoModelForVision2Seq.from_config(config, **from_config_kwargs)
    
    log.msg(_LOG_PREFIX, "Moving to CPU and loading weights...")
    
    # Use to_empty() to move from meta to CPU with empty tensors
    model = model.to_empty(device="cpu")
    
    # Now load the state dict
    missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=False)
    
    if missing_keys:
        log.debug(_LOG_PREFIX, f"  Missing keys: {len(missing_keys)} (some may be tied weights)")
    if unexpected_keys:
        log.debug(_LOG_PREFIX, f"  Unexpected keys: {len(unexpected_keys)}")
    
    # Clear state_dict reference to free memory
    del state_dict
    gc.collect()
    
    log.msg(_LOG_PREFIX, "Moving model to GPU...")
    
    # Move to GPU
    model = model.to("cuda")
    model.eval()
    
    # Manually tie lm_head.weight to embed_tokens (since we disabled tie_word_embeddings in config)
    if hasattr(model, 'lm_head') and hasattr(model, 'model'):
        if hasattr(model.model, 'language_model') and hasattr(model.model.language_model, 'embed_tokens'):
            model.lm_head.weight = model.model.language_model.embed_tokens.weight
            log.debug(_LOG_PREFIX, "  Manually tied lm_head.weight to embed_tokens.weight")
    
    # Load processor/tokenizer - use AutoTokenizer directly for faster loading
    from transformers import AutoTokenizer
    try:
        processor = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
    except Exception:
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    
    from .smartlm_types import ModelType
    return model, processor, ModelType.MISTRAL3

# File operations
from .smartlm_files import (
    download_with_progress, get_llm_model_list, get_mmproj_list,
    calculate_model_size, search_model_file, extract_repo_id_from_url,
    verify_model_integrity,
    ensure_model_path as ensure_model_path_core,
    ensure_mmproj_path as ensure_mmproj_path_core,
    discover_models_in_folder,
    filter_models_by_family_and_method,
    detect_prequantized_model,
)

# ============================================================================
# Re-exports for backward compatibility
# ============================================================================

__all__ = [
    # Enums
    'ModelType', 'ModelFamily', 'LoadingMethod',
    # Method support (v2 matrix)
    'METHOD_SUPPORT_V2',
    # UI helpers
    'get_model_family_list', 'get_loading_method_list',
    'get_supported_families', 'get_supported_families_by_name',
    # Type detection
    'get_model_family_from_name', 'detect_model_type',
    # Templates
    'get_template_dir', 'get_template_list', 'load_template',
    'update_template_settings',
    # Device
    'get_device_info', 'cleanup_memory_before_load',
    'LLAMA_CPP_AVAILABLE', 'LLAMA_CPP_MODULE',
    # Files
    'get_llm_model_list', 'get_mmproj_list',
    'discover_models_in_folder', 'filter_models_by_family_and_method',
    # v2 specific
    'ensure_model_path_v2', 'ensure_mmproj_path_v2',
    'filter_models_by_method_and_family',  # v2 wrapper (reversed argument order)
    'load_model_with_backend',
    # Transformers v5 compatibility
    'dtype_kwarg', 'get_dtype_kwarg_name',
    # Transformers model cache
    'clear_transformers_cache', 'get_cached_transformers_model', 'set_cached_transformers_model',
    # Docker container management
    'stop_all_docker_containers',
]


# ============================================================================
# Template Quantization Update Helper
# ============================================================================

def _maybe_update_template_quantization(ctx, is_prequantized: bool, prequant_type: str):
    # Update template with detected quantization if template was auto-created.
    #
    # Only updates if:
    # - ctx has a template_name
    # - The model is pre-quantized
    # - The template quantization is currently "auto" or different from detected
    #
    # Args:
    #     ctx: TemplateContext with template_name
    #     is_prequantized: Whether model is pre-quantized
    #     prequant_type: Detected quantization type (fp8, awq, gptq, etc.)
    if not is_prequantized or not prequant_type:
        return
    
    # Get template name from context
    template_name = getattr(ctx, 'template_name', None) if ctx else None
    if not template_name:
        return
    
    # Import here to avoid circular imports
    from .smartlm_templates import update_template_quantization
    
    # Map detected type to template quantization format
    quant_mapping = {
        "fp8": "fp8",
        "awq": "awq",
        "gptq": "gptq",
        "bnb": "4bit",  # BitsAndBytes is usually 4-bit
        "gguf": "gguf",
    }
    detected_quant = quant_mapping.get(prequant_type.lower(), prequant_type)
    
    # Update the template
    update_template_quantization(template_name, detected_quant, is_quantized=True)


# ============================================================================
# v2-Specific Wrapper Functions
# ============================================================================

def ensure_model_path_v2(template_name: str) -> tuple:
    # Download model if needed and return (model_path, model_folder_path, repo_id).
    #
    # v2 wrapper that uses the shared ensure_model_path with v2 update functions.
    log.debug(_LOG_PREFIX, f"ensure_model_path_v2: template_name={template_name}")
    
    template_info = load_template(template_name)
    if not template_info:
        raise ValueError(f"Template '{template_name}' not found")
    
    log.debug(_LOG_PREFIX, f"  template_info: repo_id={template_info.get('repo_id')}, local_path={template_info.get('local_path')}")
    
    result = ensure_model_path_core(
        template_info=template_info,
        template_name=template_name,
    )
    
    log.debug(_LOG_PREFIX, f"  result: model_path={result[0]}")
    return result


def ensure_mmproj_path_v2(template_info: dict, model_folder: str, template_name: str = None) -> Optional[str]:
    # Download mmproj file if needed and return local path.
    #
    # v2 wrapper for the shared ensure_mmproj_path function.
    return ensure_mmproj_path_core(
        template_info=template_info,
        model_folder=model_folder,
        template_name=template_name,
    )


# ============================================================================
# v2-Specific Filter Functions
# ============================================================================

def filter_models_by_method_and_family(
    loading_method: str,
    model_family: str,
    models: List[dict] = None
) -> List[str]:
    # Filter models by loading method and family for v2 workflow.
    #
    # Args:
    #     loading_method: Loading method string (e.g., "GGUF (llama-cpp-python)")
    #     model_family: Model family string (e.g., "Qwen")
    #     models: Optional pre-discovered models (calls discover_models_in_folder if None)
    #
    # Returns:
    #     List of model names matching criteria
    if models is None:
        models = discover_models_in_folder()
    
    return filter_models_by_family_and_method(models, model_family, loading_method)


# ============================================================================
# v2-Specific Model Loading
# ============================================================================

def load_model_with_backend(
    loading_method: str,
    model_family: str,
    model_path: str,
    ctx: TemplateContext,
    **kwargs
) -> Any:
    # Load model using specified backend (method-first workflow for v2).
    #
    # Routes to appropriate loader based on method + family combination:
    # - Transformers: smartlm_mistral.py, smartlm_qwenvl.py, smartlm_florence2.py, smartlm_llm.py
    # - GGUF: gguf_wrapper.py (universal)
    # - vLLM (Docker): smartlm_vllm_docker.py (Windows, Docker-based)
    # - vLLM (Native): smartlm_vllm_native.py (Linux, native pip install)
    #
    # Args:
    #     loading_method: "Transformers", "GGUF (llama-cpp-python)", "vLLM (Docker)", or "vLLM (Native)"
    #     model_family: "Mistral", "Qwen", "Florence", or "LLM (Text-Only)"
    #     model_path: Path to model folder or .gguf file
    #     ctx: TemplateContext with configuration values
    #     **kwargs: Additional loading parameters (quantization, device, etc.)
    #
    # Returns:
    #     Loaded model, processor/tokenizer tuple, and detected ModelType
    from . import smartlm_vllm_docker
    from . import florence2_wrapper
    
    # Only import native vLLM when needed (it prints warnings on Windows)
    smartlm_vllm_native = None
    
    log.debug(_LOG_PREFIX, f"load_model_with_backend: method={loading_method}, family={model_family}")
    log.debug(_LOG_PREFIX, f"  model_path={model_path}")
    log.debug(_LOG_PREFIX, f"  kwargs={kwargs}")
    
    # Extract cache-relevant kwargs
    quantization = kwargs.get('quantization', 'auto')
    attention_mode = kwargs.get('attention_mode', 'auto')
    memory_cleanup = kwargs.get('memory_cleanup', True)
    keep_model_loaded = kwargs.get('keep_model_loaded', False)
    
    # Resolve 'auto' values BEFORE cache check so keys are consistent
    # This ensures cache lookup uses the same resolved values as cache store
    if loading_method == "Transformers":
        # Resolve attention mode
        if attention_mode == "auto":
            resolved_attention = auto_select_attention()
        else:
            resolved_attention = attention_mode
        
        # Resolve quantization (for cache key, actual logic is below)
        if quantization == "auto":
            model_size_gb = calculate_model_size(Path(model_path))
            resolved_quantization = auto_select_quantization(model_size_gb)
        else:
            resolved_quantization = quantization
    else:
        resolved_attention = attention_mode
        resolved_quantization = quantization
    
    # Clear Transformers cache if memory_cleanup requested AND NOT keeping model loaded
    # The user explicitly wants to keep the model, so don't clear it even if memory_cleanup is True
    if memory_cleanup and not keep_model_loaded:
        clear_transformers_cache()
        cleanup_memory_before_load(aggressive=False)
    elif memory_cleanup and keep_model_loaded:
        # Only cleanup non-model memory (don't clear the Transformers cache)
        cleanup_memory_before_load(aggressive=False)
    
    # ============================================================================
    # CROSS-BACKEND CACHE INVALIDATION
    # ============================================================================
    # When switching between backends (e.g., GGUF → Transformers or vice versa),
    # we MUST clear the other backend's cache to free VRAM before loading.
    # This is critical even with keep_model_loaded=True - you can only keep ONE
    # model loaded at a time, not models from different backends.
    # We also stop Docker containers since they hold models in GPU memory.
    # ============================================================================
    
    # Track current backend for smart Docker container management
    # Get the currently loaded backend from cache status
    current_backend = None
    if get_cached_model_key():
        current_backend = "Transformers"
    elif get_cached_gguf_model_key():
        current_backend = "GGUF (llama-cpp-python)"
    # Note: Docker backends don't use local cache, so we check containers below
    
    # Docker backends list for easy checking
    docker_backends = ("vLLM (Docker)", "Ollama (Docker)", "llama.cpp (Docker)", "SGLang (Docker)")
    
    # Check if any Docker containers are running (indicates Docker backend currently active)
    docker_containers_running = False
    try:
        from . import smartlm_vllm_docker, smartlm_sglang_docker, smartlm_ollama_docker, smartlm_llamacpp_docker
        docker_containers_running = (
            smartlm_vllm_docker.get_running_vllm_containers() or
            smartlm_sglang_docker.get_running_sglang_containers() or
            smartlm_ollama_docker.is_ollama_container_running() or
            smartlm_llamacpp_docker.get_running_llamacpp_containers()
        )
        if docker_containers_running:
            current_backend = "Docker"  # Generic Docker backend
    except ImportError:
        pass
    except Exception:
        pass  # Failed to check containers, assume none running
    
    # Determine if we actually need to stop Docker containers
    # Only stop when switching FROM or TO Docker backends
    should_stop_docker = (
        loading_method in docker_backends or  # Switching TO Docker (stop others)
        current_backend == "Docker" or        # Switching FROM Docker (stop current)
        (current_backend and current_backend != loading_method)  # Backend switch involving potential cleanup
    )
    
    # Check which backend we're loading and clear OTHER backend caches + stop Docker containers if needed
    if loading_method == "Transformers":
        # Loading Transformers - clear GGUF cache and conditionally stop Docker containers
        if get_cached_gguf_model_key():
            log.msg(_LOG_PREFIX, f"Backend switch: clearing GGUF cache before loading Transformers model")
            clear_gguf_cache()
        # Stop Docker containers only if switching from Docker or if any are running
        if should_stop_docker:
            stop_all_docker_containers()
    elif loading_method == "GGUF (llama-cpp-python)":
        # Loading GGUF - clear Transformers cache and conditionally stop Docker containers
        if get_cached_model_key():
            log.msg(_LOG_PREFIX, f"Backend switch: clearing Transformers cache before loading GGUF model")
            clear_transformers_cache()
        # Stop Docker containers only if switching from Docker or if any are running
        if should_stop_docker:
            stop_all_docker_containers()
    elif loading_method == "vLLM (Native)":
        # Loading vLLM Native - clear both GGUF and Transformers caches and conditionally stop Docker containers
        if get_cached_model_key() or get_cached_gguf_model_key():
            log.msg(_LOG_PREFIX, f"Backend switch: clearing model caches before loading vLLM Native model")
            clear_transformers_cache()
            clear_gguf_cache()
        # Stop Docker containers only if switching from Docker or if any are running
        if should_stop_docker:
            stop_all_docker_containers()
    # Docker backends (vLLM Docker, Ollama Docker, llama.cpp Docker, SGLang Docker)
    # Clear local caches and stop OTHER Docker containers when switching
    elif loading_method in docker_backends:
        if get_cached_model_key() or get_cached_gguf_model_key():
            log.msg(_LOG_PREFIX, f"Backend switch: clearing local model caches before loading Docker model")
            clear_transformers_cache()
            clear_gguf_cache()
        # Always stop Docker containers when switching TO Docker (to stop other containers)
        # Note: We stop all containers here; the new container will be started by the specific backend
        stop_all_docker_containers()
    
    # ============================================================================
    # SAME-BACKEND CACHE CHECK (keep_model_loaded optimization)
    # ============================================================================
    # When keep_model_loaded=True, check if the SAME or DIFFERENT model is cached
    # within the same backend. Reuse if same, evict if different.
    # ============================================================================
    if loading_method == "Transformers":
        cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
        current_cached_key = get_cached_model_key()
        
        if current_cached_key and current_cached_key != cache_key:
            # Different model is cached - need to evict it first
            log.msg(_LOG_PREFIX, f"Multi-node workflow: evicting cached model to load different model")
            clear_all_model_caches()
        elif keep_model_loaded:
            # Same model - check cache for reuse
            cached = get_cached_transformers_model(cache_key)
            if cached:
                log.msg(_LOG_PREFIX, f"Using cached model (skipping load)")
                return cached  # Returns (model, processor, model_type)
    elif loading_method == "vLLM (Native)":
        # vLLM native also needs cache check - handled internally by _clear_vllm_cache_if_different
        pass
    
    # Parse enums
    try:
        method = LoadingMethod(loading_method)
        family = ModelFamily(model_family)
    except ValueError as e:
        raise ValueError(f"Invalid loading method or family: {e}")
    
    # Check if combination is supported (METHOD_SUPPORT_V2 maps method -> list of families)
    supported_families = METHOD_SUPPORT_V2.get(method, [])
    if family not in supported_families:
        # Provide more specific error messages for known incompatibilities
        from .smartlm_types import FLORENCE_COMPATIBLE, MISTRAL3_TRANSFORMERS_COMPATIBLE
        if family == ModelFamily.FLORENCE and method == LoadingMethod.TRANSFORMERS and not FLORENCE_COMPATIBLE:
            raise ValueError(f"Florence is not compatible with Transformers v5+. Please use Transformers v4.x or wait for Florence v3 support.")
        elif family == ModelFamily.MISTRAL and method == LoadingMethod.TRANSFORMERS and not MISTRAL3_TRANSFORMERS_COMPATIBLE:
            raise ValueError(f"Mistral3 requires Transformers v5+ for Transformers backend. Use vLLM (Docker) or upgrade Transformers.")
        else:
            raise ValueError(f"{model_family} is not supported with {loading_method}")
    
    log.debug(_LOG_PREFIX, f"  Routing to backend: {method.value} + {family.value}")
    
    # Route to correct backend
    if method == LoadingMethod.VLLM_DOCKER:
        # Apply widget overrides in single config save
        auto_start = kwargs.get('auto_start_container', False)
        auto_stop = kwargs.get('auto_stop_container', False)
        if auto_start or auto_stop:
            smartlm_vllm_docker.set_vllm_options(
                auto_start=True if auto_start else None,
                stop_after_generation=True if auto_stop else None
            )
        
        # vLLM Docker backend - returns dict with client info, not model/processor
        if family == ModelFamily.MISTRAL:
            # Create a simple wrapper object to hold vLLM client info
            class VLLMWrapper:
                def __init__(self, vllm_info):
                    self.is_vllm = True
                    self.is_gguf = False
                    self.is_quantized = True
                    self.vllm_client = vllm_info.get("client")
                    self.vllm_model_name = vllm_info.get("model_name")
            
            template_name = ctx.template_name
            # Get quantization - convert Transformers format to vLLM format if needed
            quantization = kwargs.get("quantization", "auto")
            # Get context_size for vLLM max_model_len
            context_size = kwargs.get("context_size", None)
            
            # Check if model is already pre-quantized (FP8, AWQ, GPTQ, etc.)
            is_prequantized, prequant_type = detect_prequantized_model(Path(model_path))
            if is_prequantized:
                log.debug(_LOG_PREFIX, f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
                # Update template with detected quantization
                _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
            
            # Check if this is a Mistral3/Pixtral vision model (doesn't support BitsAndBytes in vLLM)
            is_mistral3_vision = is_mistral3_vision_model(model_path)
            
            # Map Transformers-style quantization to vLLM-compatible options
            # vLLM supports: bitsandbytes (4bit only), awq, gptq, squeezellm, fp8
            # Note: vLLM bitsandbytes only supports 4-bit, not 8-bit
            # Note: Mistral3/Pixtral vision models do NOT support BitsAndBytes in vLLM
            if quantization == "auto":
                # Skip auto-quant for pre-quantized models
                if is_prequantized:
                    log.debug(_LOG_PREFIX, f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                elif is_mistral3_vision:
                    log.debug(_LOG_PREFIX, f"Auto mode: Mistral3/Pixtral vision model - BitsAndBytes not supported, using native dtype")
                    quantization = None
                else:
                    # Auto-select based on model size vs available VRAM
                    model_size_gb = calculate_model_size(Path(model_path))
                    auto_quant = auto_select_quantization(
                        model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                        estimated_size_gb=model_size_gb,
                    )
                    # vLLM only supports 4-bit with bitsandbytes (no 8-bit)
                    if auto_quant in ("4bit", "8bit"):
                        log.debug(_LOG_PREFIX, f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        log.debug(_LOG_PREFIX, f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None  # Let vLLM use default dtype
            elif quantization in ("4bit", "8bit"):
                if is_mistral3_vision:
                    log.warning(_LOG_PREFIX, "Mistral3/Pixtral vision models don't support BitsAndBytes in vLLM - using native dtype")
                    quantization = None
                elif quantization == "4bit":
                    log.debug(_LOG_PREFIX, "Using bitsandbytes 4-bit quantization for vLLM")
                    quantization = "bitsandbytes"
                else:
                    log.warning(_LOG_PREFIX, "vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
                    quantization = "bitsandbytes"
            elif quantization in ("fp16", "bf16", "fp32", "none"):
                quantization = None  # vLLM handles dtype automatically
            
            vllm_info = smartlm_vllm_docker.load_vllm(
                None,  # smart_lm_instance not needed, wrapper handles state
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            
            if vllm_info is None:
                raise RuntimeError(
                    "vLLM server not available or not serving the requested model.\n\n"
                    "Solutions:\n"
                    "  1. Start vLLM server with the correct model\n"
                    "  2. Enable 'auto_start' in docker_config.json\n"
                    "  3. Switch to Transformers loading method"
                )
            
            wrapper = VLLMWrapper(vllm_info)
            return wrapper, None, ModelType.MISTRAL3
        elif family == ModelFamily.QWEN:
            # Qwen vLLM Docker support - same pattern as Mistral
            class VLLMWrapper:
                def __init__(self, vllm_info):
                    self.is_vllm = True
                    self.is_gguf = False
                    self.is_quantized = True
                    self.vllm_client = vllm_info.get("client")
                    self.vllm_model_name = vllm_info.get("model_name")
            
            template_name = ctx.template_name
            quantization = kwargs.get("quantization", "auto")
            context_size = kwargs.get("context_size", None)
            
            # Check if model is already pre-quantized (FP8, AWQ, GPTQ, etc.)
            is_prequantized, prequant_type = detect_prequantized_model(Path(model_path))
            if is_prequantized:
                log.debug(_LOG_PREFIX, f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
            # Update template with detected quantization
            _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
            
            # Map Transformers-style quantization to vLLM-compatible options
            if quantization == "auto":
                if is_prequantized:
                    log.debug(_LOG_PREFIX, f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                else:
                    model_size_gb = calculate_model_size(Path(model_path))
                    auto_quant = auto_select_quantization(
                        model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                        estimated_size_gb=model_size_gb,
                    )
                    if auto_quant in ("4bit", "8bit"):
                        log.debug(_LOG_PREFIX, f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        log.debug(_LOG_PREFIX, f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None
            elif quantization in ("4bit", "8bit"):
                log.debug(_LOG_PREFIX, "Using bitsandbytes 4-bit quantization for vLLM")
                quantization = "bitsandbytes" if quantization == "4bit" else "bitsandbytes"
            elif quantization in ("fp16", "bf16", "fp32", "none"):
                quantization = None
            
            vllm_info = smartlm_vllm_docker.load_vllm(
                None,
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            
            if vllm_info is None:
                raise RuntimeError(
                    "vLLM server not available or not serving the requested model.\n\n"
                    "Solutions:\n"
                    "  1. Start vLLM server with the correct model\n"
                    "  2. Enable 'auto_start' in docker_config.json\n"
                    "  3. Switch to Transformers or SGLang loading method"
                )
            
            wrapper = VLLMWrapper(vllm_info)
            return wrapper, None, ModelType.QWENVL
        elif family == ModelFamily.LLM_TEXT:
            # LLM (Text-Only) vLLM Docker support - same pattern as Mistral
            class VLLMWrapper:
                def __init__(self, vllm_info):
                    self.is_vllm = True
                    self.is_gguf = False
                    self.is_quantized = True
                    self.vllm_client = vllm_info.get("client")
                    self.vllm_model_name = vllm_info.get("model_name")
            
            template_name = ctx.template_name
            quantization = kwargs.get("quantization", "auto")
            context_size = kwargs.get("context_size", None)
            
            # Check if model is already pre-quantized
            is_prequantized, prequant_type = detect_prequantized_model(Path(model_path))
            if is_prequantized:
                log.debug(_LOG_PREFIX, f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
            # Update template with detected quantization
            _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
            
            # Map Transformers-style quantization to vLLM-compatible options
            if quantization == "auto":
                if is_prequantized:
                    log.debug(_LOG_PREFIX, f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                else:
                    model_size_gb = calculate_model_size(Path(model_path))
                    auto_quant = auto_select_quantization(
                        model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                        estimated_size_gb=model_size_gb,
                    )
                    if auto_quant in ("4bit", "8bit"):
                        log.debug(_LOG_PREFIX, f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        log.debug(_LOG_PREFIX, f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None
            elif quantization == "4bit":
                log.debug(_LOG_PREFIX, "Using bitsandbytes 4-bit quantization for vLLM")
                quantization = "bitsandbytes"
            elif quantization == "8bit":
                log.warning(_LOG_PREFIX, "vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
                quantization = "bitsandbytes"
            elif quantization in ("fp16", "bf16", "fp32", "none"):
                quantization = None
            
            vllm_info = smartlm_vllm_docker.load_vllm(
                None,
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            
            if vllm_info is None:
                raise RuntimeError(
                    "vLLM server not available or not serving the requested model.\n\n"
                    "Solutions:\n"
                    "  1. Start vLLM server with the correct model\n"
                    "  2. Enable 'auto_start' in docker_config.json\n"
                    "  3. Switch to Transformers loading method"
                )
            
            wrapper = VLLMWrapper(vllm_info)
            return wrapper, None, ModelType.LLM
        else:
            raise ValueError(f"vLLM does not support {model_family}")
    
    elif method == LoadingMethod.SGLANG_DOCKER:
        # SGLang Docker backend - alternative to vLLM with RadixAttention
        from . import smartlm_sglang_docker
        
        # Apply widget overrides
        auto_start = kwargs.get('auto_start_container', False)
        auto_stop = kwargs.get('auto_stop_container', False)
        if auto_start or auto_stop:
            if auto_start:
                smartlm_sglang_docker.set_sglang_auto_start(True)
            if auto_stop:
                smartlm_sglang_docker.set_sglang_stop_after_generation(True)
        
        class SGLangWrapper:
            def __init__(self, sglang_info):
                self.is_sglang = True
                self.is_vllm = False
                self.is_gguf = False
                self.is_quantized = True
                self.sglang_client = sglang_info.get("client")
                self.sglang_model_name = sglang_info.get("model_name")
        
        template_name = ctx.template_name
        quantization = kwargs.get("quantization", "auto")
        context_size = kwargs.get("context_size", None)
        
        # Check if model is pre-quantized (FP8, AWQ, GPTQ)
        is_prequantized, prequant_type = detect_prequantized_model(Path(model_path))
        if is_prequantized:
            log.debug(_LOG_PREFIX, f"Model is pre-quantized ({prequant_type}), using native format")
            quantization = prequant_type.lower() if prequant_type in ("FP8", "AWQ", "GPTQ") else None
        # Update template with detected quantization
        _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
        
        if not is_prequantized and quantization == "auto":
            model_size_gb = calculate_model_size(Path(model_path))
            auto_quant = auto_select_quantization(
                model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                estimated_size_gb=model_size_gb,
            )
            # SGLang supports fp8, awq, gptq quantization
            if auto_quant in ("4bit", "8bit"):
                log.debug(_LOG_PREFIX, f"Auto mode: SGLang doesn't support bitsandbytes, using native dtype")
                quantization = None
            else:
                quantization = None
        elif quantization in ("4bit", "8bit"):
            log.warning(_LOG_PREFIX, "SGLang doesn't support bitsandbytes quantization - using native dtype")
            quantization = None
        elif quantization in ("fp16", "bf16", "fp32", "none"):
            quantization = None
        
        if family in (ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.LLM_TEXT):
            sglang_info = smartlm_sglang_docker.load_sglang(
                None,
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            
            if sglang_info is None:
                raise RuntimeError(
                    "SGLang server not available or not serving the requested model.\n\n"
                    "Solutions:\n"
                    "  1. Enable 'auto_start' in docker_config.json (sglang section)\n"
                    "  2. Ensure Docker is running\n"
                    "  3. Switch to vLLM (Docker) or Transformers loading method"
                )
            
            wrapper = SGLangWrapper(sglang_info)
            model_type = ModelType.MISTRAL3 if family == ModelFamily.MISTRAL else (
                ModelType.QWENVL if family == ModelFamily.QWEN else ModelType.LLM
            )
            return wrapper, None, model_type
        else:
            raise ValueError(f"SGLang does not support {model_family}")
    
    elif method == LoadingMethod.VLLM_NATIVE:
        # Native vLLM backend (Linux only, direct pip install)
        # Lazy import to avoid warnings on Windows when not using this backend
        from . import smartlm_vllm_native
        if not smartlm_vllm_native.VLLM_AVAILABLE:
            raise ImportError(
                "vLLM is required for native vLLM loading but was not found.\n\n"
                "Install with: pip install vllm\n"
                "Note: vLLM native is only available on Linux with NVIDIA GPUs."
            )
        
        # Create wrapper class for native vLLM
        class VLLMNativeWrapper:
            def __init__(self, vllm_model, model_name):
                self.is_vllm = True
                self.is_vllm_native = True
                self.is_gguf = False
                self.is_quantized = False
                self.vllm_model = vllm_model
                self.vllm_model_name = model_name
        
        template_name = ctx.template_name
        
        # Get quantization - convert Transformers format to vLLM format if needed
        quantization = kwargs.get("quantization", "auto")
        # Get context_size for vLLM max_model_len
        context_size = kwargs.get("context_size", None)
        
        # Check if model is already pre-quantized (FP8, AWQ, GPTQ, etc.)
        is_prequantized, prequant_type = detect_prequantized_model(Path(model_path))
        if is_prequantized:
            log.debug(_LOG_PREFIX, f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
        # Update template with detected quantization
        _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
        
        # Map Transformers-style quantization to vLLM-compatible options
        # Note: vLLM bitsandbytes only supports 4-bit, not 8-bit
        if quantization == "auto":
            # Skip auto-quant for pre-quantized models - they already fit in VRAM efficiently
            if is_prequantized:
                log.debug(_LOG_PREFIX, f"Auto mode: model already {prequant_type} quantized, using native dtype")
                quantization = None
            else:
                # Auto-select based on model size vs available VRAM
                model_size_gb = calculate_model_size(Path(model_path))
                auto_quant = auto_select_quantization(
                    model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                    estimated_size_gb=model_size_gb,
                )
                # vLLM only supports 4-bit with bitsandbytes (no 8-bit)
                if auto_quant in ("4bit", "8bit"):
                    log.debug(_LOG_PREFIX, f"Auto mode: using bitsandbytes 4-bit for vLLM Native (auto selected {auto_quant})")
                    quantization = "bitsandbytes"
                else:
                    log.debug(_LOG_PREFIX, f"Auto mode: sufficient VRAM, no quantization needed")
                    quantization = None  # Let vLLM use default dtype
        elif quantization == "4bit":
            log.debug(_LOG_PREFIX, "Using bitsandbytes 4-bit quantization for vLLM Native")
            quantization = "bitsandbytes"
        elif quantization == "8bit":
            log.warning(_LOG_PREFIX, "vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
            quantization = "bitsandbytes"
        elif quantization in ("fp16", "bf16", "fp32", "none"):
            quantization = None  # vLLM handles dtype automatically
        
        if family == ModelFamily.MISTRAL:
            vllm_info = smartlm_vllm_native.load_vllm(
                None,  # smart_lm_instance not needed, wrapper handles state
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            if vllm_info is None:
                raise RuntimeError(
                    "Failed to load model with native vLLM.\n\n"
                    "Solutions:\n"
                    "  1. Ensure vLLM is installed: pip install vllm\n"
                    "  2. Verify you're running on Linux with NVIDIA GPU\n"
                    "  3. Check that model path is valid"
                )
            
            wrapper = VLLMNativeWrapper(vllm_info.get("model"), model_path)
            return wrapper, None, ModelType.MISTRAL3
        elif family == ModelFamily.QWEN:
            vllm_info = smartlm_vllm_native.load_vllm(
                None,
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            if vllm_info is None:
                raise RuntimeError("Failed to load model with native vLLM")
            
            wrapper = VLLMNativeWrapper(vllm_info.get("model"), model_path)
            return wrapper, None, ModelType.QWENVL
        elif family == ModelFamily.LLM_TEXT:
            vllm_info = smartlm_vllm_native.load_vllm(
                None,
                template_name,
                model_path,
                quantization=quantization,
                context_size=context_size
            )
            if vllm_info is None:
                raise RuntimeError("Failed to load model with native vLLM")
            
            wrapper = VLLMNativeWrapper(vllm_info.get("model"), model_path)
            return wrapper, None, ModelType.LLM
        else:
            raise ValueError(f"vLLM (Native) does not support {model_family}")
    
    elif method == LoadingMethod.GGUF:
        # GGUF backend (llama-cpp-python)
        if family == ModelFamily.FLORENCE:
            raise ValueError("Florence-2 is not available in GGUF format")
        
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is required for GGUF models but was not found. "
                "Install with: pip install llama-cpp-python"
            )
        
        # Get model file path - handle both files and folders
        model_file = Path(model_path)
        
        if model_file.is_dir():
            # Folder provided - find GGUF files inside
            gguf_files = list(model_file.glob("*.gguf"))
            
            # Separate model files from mmproj files
            model_gguf_files = [f for f in gguf_files if 'mmproj' not in f.name.lower()]
            
            if not model_gguf_files:
                raise FileNotFoundError(f"No GGUF model files found in: {model_file}")
            
            # Select best GGUF file - prefer Q4_K_M > Q5_K_M > Q8_0 > BF16 for balance
            # User can specify exact file in local_path to override
            priority_order = ['Q4_K_M', 'Q5_K_M', 'Q8_0', 'Q6_K', 'Q4_K_S', 'BF16', 'F16']
            selected_file = None
            
            for priority in priority_order:
                for f in model_gguf_files:
                    if priority in f.name:
                        selected_file = f
                        break
                if selected_file:
                    break
            
            # Fallback to first file if no priority match
            if not selected_file:
                selected_file = model_gguf_files[0]
            
            model_file = selected_file
            log.msg(_LOG_PREFIX, f"Selected GGUF: {model_file.name} (from {len(model_gguf_files)} available)")
        
        if not model_file.exists():
            raise FileNotFoundError(f"GGUF model file not found: {model_file}")
        
        context_size = kwargs.get('context_size', 32768)
        device = kwargs.get('device', 'cuda')
        keep_model_loaded = kwargs.get('keep_model_loaded', False)
        
        # Determine GPU layers (-1 = full offload for CUDA)
        n_gpu_layers = -1 if device == "cuda" else 0
        
        # ============================================================================
        # GGUF Model Cache Check (Native llama-cpp-python ONLY)
        # ============================================================================
        # This caching ONLY applies to native GGUF loading (llama-cpp-python).
        # Docker backends (llama.cpp Docker, Ollama Docker) have separate loading
        # methods and manage model lifecycle via container lifecycle instead.
        # With proper KV cache clearing between calls, GGUF models can be safely reused.
        # ============================================================================
        gguf_cache_key = get_gguf_cache_key(str(model_file), context_size)
        current_gguf_cached_key = get_cached_gguf_model_key()
        
        if current_gguf_cached_key and current_gguf_cached_key != gguf_cache_key:
            # Different GGUF model is cached - need to evict it first
            log.msg(_LOG_PREFIX, f"GGUF cache: evicting cached model to load different model")
            clear_gguf_cache()
        elif current_gguf_cached_key:
            # Same model is cached - reuse it (regardless of keep_model_loaded)
            # If keep_model_loaded=False, the caller will unload AFTER generation
            # This avoids wasteful unload→load→generate→unload cycle
            cached = get_cached_gguf_model(gguf_cache_key)
            if cached:
                model, chat_handler, model_type = cached
                # Clear KV cache before reuse to ensure clean state
                if model is not None:
                    if hasattr(model, 'reset'):
                        model.reset()
                    if hasattr(model, '_ctx') and hasattr(model._ctx, 'kv_cache_clear'):
                        model._ctx.kv_cache_clear()
                if keep_model_loaded:
                    log.msg(_LOG_PREFIX, f"Using cached GGUF model (KV cache cleared)")
                else:
                    log.msg(_LOG_PREFIX, f"Using cached GGUF model for final run (will unload after)")
                return model, None, model_type
        
        # GGUF models use llama-cpp-python
        if family == ModelFamily.QWEN:
            # Qwen VL with vision support
            from llama_cpp import Llama
            
            # Get mmproj file for vision support - always search and update template
            mmproj_file = ensure_mmproj_path_v2(
                ctx.to_dict(), 
                str(model_file.parent),
                template_name=ctx.template_name
            )
            
            if mmproj_file:
                # Vision model with mmproj
                log.msg(_LOG_PREFIX, "Loading Qwen VL GGUF (vision)")
                
                # Detect Qwen version for appropriate chat handler
                model_name_lower = model_file.name.lower()
                is_qwen25 = "qwen2.5" in model_name_lower or "qwen_2_5" in model_name_lower
                
                try:
                    if is_qwen25:
                        from llama_cpp.llama_chat_format import Qwen25VLChatHandler
                        chat_handler = Qwen25VLChatHandler(clip_model_path=mmproj_file)
                    else:
                        from llama_cpp.llama_chat_format import Qwen2VLChatHandler
                        chat_handler = Qwen2VLChatHandler(clip_model_path=mmproj_file)
                except ImportError as e:
                    log.warning(_LOG_PREFIX, "Qwen chat handler not available, falling back to Llava")
                    from llama_cpp.llama_chat_format import Llava16ChatHandler
                    chat_handler = Llava16ChatHandler(clip_model_path=mmproj_file)
                
                model = Llama(
                    model_path=str(model_file),
                    chat_handler=chat_handler,
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                # Store chat_handler reference for proper VRAM cleanup later
                # The chat_handler holds the CLIP model which uses significant VRAM
                model._eclipse_chat_handler = chat_handler
                # Cache model if keep_model_loaded is enabled
                if keep_model_loaded:
                    set_cached_gguf_model(gguf_cache_key, model, chat_handler, ModelType.QWENVL)
                return model, None, ModelType.QWENVL
            else:
                # Text-only Qwen (no mmproj)
                log.msg(_LOG_PREFIX, "Loading Qwen GGUF (text-only)")
                model = Llama(
                    model_path=str(model_file),
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                # Cache model if keep_model_loaded is enabled
                if keep_model_loaded:
                    set_cached_gguf_model(gguf_cache_key, model, None, ModelType.LLM)
                return model, None, ModelType.LLM
        
        elif family == ModelFamily.MISTRAL or family == ModelFamily.LLM_TEXT:
            from llama_cpp import Llama
            
            # Check for mmproj file - always search and update template
            mmproj_file = ensure_mmproj_path_v2(
                ctx.to_dict(), 
                str(model_file.parent),
                template_name=ctx.template_name
            )
            
            if mmproj_file:
                # Vision model with mmproj (e.g., Ministral with Pixtral vision)
                log.msg(_LOG_PREFIX, f"Loading Mistral VL GGUF (vision): {model_file.name}")
                log.msg(_LOG_PREFIX, f"  mmproj: {Path(mmproj_file).name}")
                
                try:
                    from llama_cpp.llama_chat_format import Llava16ChatHandler
                    chat_handler = Llava16ChatHandler(clip_model_path=mmproj_file)
                    
                    model = Llama(
                        model_path=str(model_file),
                        chat_handler=chat_handler,
                        n_ctx=context_size,
                        n_gpu_layers=n_gpu_layers,
                        verbose=False,
                    )
                    # Store chat_handler reference for proper VRAM cleanup later
                    model._eclipse_chat_handler = chat_handler
                    # Cache model if keep_model_loaded is enabled
                    if keep_model_loaded:
                        set_cached_gguf_model(gguf_cache_key, model, chat_handler, ModelType.MISTRAL3)
                    return model, None, ModelType.MISTRAL3  # Vision-capable Mistral
                except ValueError as e:
                    error_msg = str(e)
                    if "unknown model architecture" in error_msg.lower():
                        # Extract architecture name from error
                        arch_name = error_msg.split(":")[-1].strip().strip("'")
                        raise ValueError(
                            f"Model architecture '{arch_name}' is not yet supported by llama-cpp-python. "
                            f"This is a new architecture that requires a newer version of llama.cpp. "
                            f"Options: 1) Wait for llama-cpp-python update, 2) Use 'Transformers' loading method instead, "
                            f"3) Build llama-cpp-python from source with latest llama.cpp"
                        )
                    log.warning(_LOG_PREFIX, f"Failed to load with vision support: {e}")
                    log.warning(_LOG_PREFIX, "Falling back to text-only mode")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"Failed to load with vision support: {e}")
                    log.warning(_LOG_PREFIX, "Falling back to text-only mode")
            
            # Text-only LLM
            log.msg(_LOG_PREFIX, f"Loading LLM GGUF: {model_file.name}")
            try:
                model = Llama(
                    model_path=str(model_file),
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                # Cache model if keep_model_loaded is enabled
                if keep_model_loaded:
                    set_cached_gguf_model(gguf_cache_key, model, None, ModelType.LLM)
                return model, None, ModelType.LLM
            except ValueError as e:
                error_msg = str(e)
                if "unknown model architecture" in error_msg.lower():
                    arch_name = error_msg.split(":")[-1].strip().strip("'")
                    raise ValueError(
                        f"Model architecture '{arch_name}' is not yet supported by llama-cpp-python. "
                        f"This is a new architecture that requires a newer version of llama.cpp. "
                        f"Options: 1) Wait for llama-cpp-python update, 2) Use 'Transformers' loading method instead, "
                        f"3) Build llama-cpp-python from source with latest llama.cpp"
                    )
                raise
        
        elif family == ModelFamily.LLAVA:
            # LLaVA vision models with mmproj
            from llama_cpp import Llama
            
            # Get mmproj file for vision support - always search and update template
            mmproj_file = ensure_mmproj_path_v2(
                ctx.to_dict(), 
                str(model_file.parent),
                template_name=ctx.template_name
            )
            
            if not mmproj_file:
                raise ValueError(
                    f"LLaVA requires an mmproj file for vision support. "
                    f"Please provide mmproj_url in the template or place the mmproj file in the model folder."
                )
            
            log.msg(_LOG_PREFIX, f"Loading LLaVA GGUF (vision): {model_file.name}")
            log.msg(_LOG_PREFIX, f"  mmproj: {Path(mmproj_file).name}")
            
            try:
                from llama_cpp.llama_chat_format import Llava16ChatHandler
                chat_handler = Llava16ChatHandler(clip_model_path=mmproj_file)
                
                model = Llama(
                    model_path=str(model_file),
                    chat_handler=chat_handler,
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                # Store chat_handler reference for proper VRAM cleanup later
                model._eclipse_chat_handler = chat_handler
                # Cache model if keep_model_loaded is enabled
                if keep_model_loaded:
                    set_cached_gguf_model(gguf_cache_key, model, chat_handler, ModelType.LLAVA)
                return model, None, ModelType.LLAVA
            except ValueError as e:
                error_msg = str(e)
                if "unknown model architecture" in error_msg.lower():
                    arch_name = error_msg.split(":")[-1].strip().strip("'")
                    raise ValueError(
                        f"Model architecture '{arch_name}' is not yet supported by llama-cpp-python. "
                        f"This is a new architecture that requires a newer version of llama.cpp. "
                        f"Options: 1) Wait for llama-cpp-python update, 2) Use 'Ollama (Docker)' loading method instead, "
                        f"3) Build llama-cpp-python from source with latest llama.cpp"
                    )
                raise
        
        else:
            raise ValueError(f"GGUF not supported for {model_family}")
    
    elif method == LoadingMethod.OLLAMA_DOCKER:
        # Ollama Docker backend - supports GGUF files OR Ollama registry models
        from . import smartlm_ollama_docker
        
        class OllamaWrapper:
            def __init__(self, ollama_info):
                self.is_vllm = False
                self.is_ollama = True
                self.is_gguf = ollama_info.get("is_gguf", False)
                self.is_quantized = True
                self.ollama_client = ollama_info.get("client")
                self.ollama_model_name = ollama_info.get("model_name")
                self.ollama_base_url = ollama_info.get("base_url")
        
        context_size = kwargs.get("context_size", 8192)
        auto_start = kwargs.get('auto_start_container', True)
        
        # Check if this is an Ollama registry model template
        model_source = ctx.model_source
        ollama_model_from_template = ctx.ollama_model
        
        if model_source == "ollama" and ollama_model_from_template:
            # Template specifies an Ollama registry model directly
            log.debug(_LOG_PREFIX, f"Using Ollama registry model from template: {ollama_model_from_template}")
            ollama_model_name = ollama_model_from_template
            use_gguf = False
            
            ollama_info = smartlm_ollama_docker.load_ollama(
                model_path=ollama_model_name,
                model_type="llm" if family == ModelFamily.LLM_TEXT else "vlm",
                use_gguf=False,
            )
            
            if ollama_info is None:
                raise RuntimeError(
                    f"Ollama Docker failed to load registry model: {ollama_model_name}\n\n"
                    f"Solutions:\n"
                    f"  1. Ensure Docker is installed and running\n"
                    f"  2. The model will be auto-pulled from Ollama registry on first use\n"
                    f"  3. Check your internet connection"
                )
            
            wrapper = OllamaWrapper(ollama_info)
            
            if family == ModelFamily.MISTRAL:
                return wrapper, None, ModelType.MISTRAL3
            elif family == ModelFamily.QWEN:
                return wrapper, None, ModelType.QWENVL
            elif family == ModelFamily.LLAVA:
                # LLAVA family includes both LLaVA and Mllama - Ollama handles detection internally
                return wrapper, None, ModelType.LLAVA
            else:
                return wrapper, None, ModelType.LLM
        
        # Try to find GGUF file OR infer Ollama registry model
        model_file = Path(model_path)
        use_gguf = False
        ollama_model_name = None
        
        if model_file.is_dir():
            # Check for GGUF files in directory
            gguf_files = list(model_file.glob("*.gguf"))
            if gguf_files:
                # Select best GGUF file
                model_file = gguf_files[0]
                for priority in ['Q4_K_M', 'Q5_K_M', 'Q8_0', 'Q6_K']:
                    for f in gguf_files:
                        if priority in f.name:
                            model_file = f
                            break
                use_gguf = True
            elif smartlm_ollama_docker.is_hf_model_directory(model_path):
                # HuggingFace Safetensors model - try to import into Ollama
                log.debug(_LOG_PREFIX, f"HuggingFace model detected, attempting to import into Ollama...")
                imported_name = smartlm_ollama_docker.import_hf_model_to_ollama(
                    model_path,
                    quantize="q4_K_M",  # Default quantization for efficiency
                )
                if imported_name:
                    ollama_model_name = imported_name
                    use_gguf = False
                else:
                    # Import failed, try to infer Ollama registry model
                    ollama_model_name = smartlm_ollama_docker.infer_ollama_model_name(model_path)
                    if not ollama_model_name:
                        raise ValueError(
                            f"Failed to import HuggingFace model into Ollama.\n\n"
                            f"The model at {model_path} could not be converted.\n"
                            f"Supported architectures: Llama, Mistral, Gemma, Phi3\n\n"
                            f"Alternatives:\n"
                            f"  1. Use 'Transformers' backend for native HF model loading\n"
                            f"  2. Use 'vLLM (Docker)' backend for HF models\n"
                            f"  3. Download a GGUF version and use 'llama.cpp (Docker)'"
                        )
            else:
                # No GGUF files, not a HF model - try to infer Ollama registry model
                ollama_model_name = smartlm_ollama_docker.infer_ollama_model_name(model_path)
                if not ollama_model_name:
                    raise ValueError(
                        f"No GGUF files in {model_path} and could not infer Ollama model name.\n\n"
                        f"For HuggingFace models without GGUF, Ollama (Docker) needs a matching\n"
                        f"model in the Ollama registry. Try:\n"
                        f"  1. Download a GGUF version of this model\n"
                        f"  2. Use 'vLLM (Docker)' or 'Transformers' backend for HF models\n"
                        f"  3. Check if an equivalent model exists in Ollama registry"
                    )
        elif str(model_file).lower().endswith('.gguf'):
            use_gguf = True
        else:
            # Single file that's not GGUF - try to infer Ollama model name
            ollama_model_name = smartlm_ollama_docker.infer_ollama_model_name(model_path)
            if not ollama_model_name:
                raise ValueError(
                    f"Ollama (Docker) requires a GGUF file or matching Ollama registry model.\n"
                    f"Got: {model_file}\n\n"
                    f"For HuggingFace safetensor models, use 'Transformers' or 'vLLM (Docker)' backend."
                )
        
        # Ensure model_family from widget is set on context
        ctx.model_family = model_family
        
        ollama_info = smartlm_ollama_docker.load_ollama(
            model_path=str(model_file) if use_gguf else ollama_model_name,
            model_type="llm" if family == ModelFamily.LLM_TEXT else "vlm",
            use_gguf=use_gguf,
            ctx=ctx,
        )
        
        if ollama_info is None:
            raise RuntimeError(
                "Ollama Docker not available or failed to load model.\n\n"
                "Solutions:\n"
                "  1. Ensure Docker is installed and running\n"
                "  2. Check that the GGUF file exists\n"
                "  3. Try 'llama.cpp (Docker)' backend as alternative"
            )
        
        wrapper = OllamaWrapper(ollama_info)
        
        if family == ModelFamily.MISTRAL:
            return wrapper, None, ModelType.MISTRAL3
        elif family == ModelFamily.QWEN:
            return wrapper, None, ModelType.QWENVL
        else:
            return wrapper, None, ModelType.LLM
    
    elif method == LoadingMethod.LLAMACPP_DOCKER:
        # llama.cpp Docker backend - supports Mistral3 GGUF models
        from . import smartlm_llamacpp_docker
        
        class LlamaCppWrapper:
            def __init__(self, llamacpp_info):
                self.is_vllm = False
                self.is_llamacpp_docker = True
                self.is_gguf = True
                self.is_quantized = True
                self.llamacpp_client = llamacpp_info.get("client")
                self.llamacpp_model_name = llamacpp_info.get("model_name")
                self.llamacpp_base_url = llamacpp_info.get("base_url")
        
        context_size = kwargs.get("context_size", 8192)
        auto_start = kwargs.get('auto_start_container', True)
        
        # Find GGUF file in model path
        model_file = Path(model_path)
        if model_file.is_dir():
            gguf_files = list(model_file.glob("*.gguf"))
            if not gguf_files:
                raise FileNotFoundError(f"No GGUF files found in {model_path}")
            # Select best GGUF file
            model_file = gguf_files[0]
            for priority in ['Q4_K_M', 'Q5_K_M', 'Q8_0', 'Q6_K']:
                for f in gguf_files:
                    if priority in f.name:
                        model_file = f
                        break
        
        if not str(model_file).lower().endswith('.gguf'):
            raise ValueError(f"llama.cpp (Docker) requires a GGUF model file, got: {model_file}")
        
        # Get mmproj path from ctx if available
        mmproj_file = ctx.mmproj_path if ctx.mmproj_path else None
        if not mmproj_file:
            # Try to get mmproj_url and download it
            mmproj_file = ensure_mmproj_path_v2(
                ctx.to_dict(), 
                str(model_file.parent),
                template_name=ctx.template_name
            )
        
        # Get models base path for correct Docker mount
        models_base = str(get_llm_models_path())
        
        llamacpp_info = smartlm_llamacpp_docker.load_llamacpp(
            model_path=str(model_file),
            model_type="llm" if family == ModelFamily.LLM_TEXT else "vlm",
            ctx_size=context_size,
            models_base_path=models_base,
            mmproj_path=mmproj_file,
        )
        
        if llamacpp_info is None:
            raise RuntimeError(
                "llama.cpp Docker not available or failed to load model.\n\n"
                "Solutions:\n"
                "  1. Ensure Docker is installed and running\n"
                "  2. Check that the GGUF file exists\n"
                "  3. Try 'Ollama (Docker)' backend as alternative"
            )
        
        wrapper = LlamaCppWrapper(llamacpp_info)
        
        if family == ModelFamily.MISTRAL:
            return wrapper, None, ModelType.MISTRAL3
        elif family == ModelFamily.QWEN:
            return wrapper, None, ModelType.QWENVL
        else:
            return wrapper, None, ModelType.LLM
    
    else:  # LoadingMethod.TRANSFORMERS
        # Transformers backend - load models directly
        quantization = kwargs.get('quantization', 'auto')
        attention_mode = kwargs.get('attention_mode', 'auto')
        device = kwargs.get('device', 'cuda')
        
        # Auto-select attention mode if 'auto'
        if attention_mode == "auto":
            attn_impl = auto_select_attention()
        else:
            attn_impl = attention_mode
        
        # Check if model is pre-quantized using multiple methods:
        # 1. Inspect config.json for quantization_config (most reliable)
        # 2. Check template's quantized flag
        # 3. Check filename markers (fallback)
        model_name = Path(model_path).name
        
        # Primary: Check actual model files (config.json, params.json)
        is_prequantized, quant_type = detect_prequantized_model(Path(model_path))
        
        # Secondary: Template flag (may be user-set, less reliable alone)
        template_is_quantized = ctx.quantized
        
        # Combine: Trust file inspection, but warn if template disagrees
        if is_prequantized and not template_is_quantized:
            log.debug(_LOG_PREFIX, f"Model detected as pre-quantized ({quant_type}) but template says quantized=false")
            # Update template with detected quantization
            if ctx.template_name:
                update_template_settings(ctx.template_name, {
                    "quantized": True,
                })
        elif not is_prequantized and template_is_quantized:
            # Trust template if file inspection didn't find quantization
            # (some formats may not have detectable markers)
            is_prequantized = True
            quant_type = "unknown"
            log.debug(_LOG_PREFIX, f"Template says quantized=true but no quantization config detected in files")
        
        # Handle quantization selection
        if is_prequantized:
            # Pre-quantized model - don't apply additional quantization (would break/corrupt)
            if quantization in ["4bit", "8bit"]:
                log.warning(_LOG_PREFIX, f"Model is pre-quantized ({quant_type}), ignoring {quantization} request")
            # For FP8: we'll use FineGrainedFP8Config(dequantize=True) to convert to BF16
            # For others: load as-is with native dtype handling
            quantization = "fp16"  # Placeholder - actual loading handled per-model family
            if quant_type == "fp8":
                log.msg(_LOG_PREFIX, f"Pre-quantized model ({quant_type}), will dequantize to BF16")
            else:
                log.msg(_LOG_PREFIX, f"Pre-quantized model ({quant_type}), loading with native dtype")
        elif quantization == "auto":
            # Auto-select based on model size vs available VRAM
            model_size_gb = calculate_model_size(Path(model_path))
            quantization = auto_select_quantization(
                model_name=model_name,
                estimated_size_gb=model_size_gb,
            )
        
        if family == ModelFamily.QWEN:
            # Load Qwen VL with transformers
            from transformers import AutoProcessor
            import transformers
            
            log.msg(_LOG_PREFIX, f"Loading Qwen VL ({quantization}, {attn_impl})")
            
            # Use AutoModelForVision2Seq to auto-detect the correct class from config
            # This handles both Qwen2.5-VL (Qwen2_5_VLForConditionalGeneration) and
            # Qwen3-VL (Qwen3VLForConditionalGeneration) automatically
            from transformers import AutoModelForVision2Seq, AutoConfig
            QwenVLModelClass = AutoModelForVision2Seq
            
            # Debug: show detected model class from config
            try:
                config = AutoConfig.from_pretrained(model_path)
                arch = config.architectures[0] if config.architectures else "unknown"
                log.debug(_LOG_PREFIX, f"  Config class: {type(config).__name__}, architecture: {arch}")
            except Exception:
                pass
            
            # model_path should already be verified/downloaded by ensure_model_path
            # Build common kwargs for from_pretrained
            load_kwargs = {"low_cpu_mem_usage": True}
            if attn_impl:
                load_kwargs["attn_implementation"] = attn_impl
            
            # Check if this is an FP8 pre-quantized model (needs device_map="auto")
            is_fp8_model = is_prequantized and quant_type == "fp8"
            
            # For FP8 models: Check if checkpoint has separate lm_head.weight
            # If yes, we need to disable tie_word_embeddings to load it correctly
            fp8_has_separate_lm_head = False
            if is_fp8_model:
                try:
                    from safetensors import safe_open
                    safetensor_files = [f for f in os.listdir(model_path) if f.endswith('.safetensors')]
                    for sf in safetensor_files:
                        with safe_open(os.path.join(model_path, sf), framework='pt') as f:
                            if 'lm_head.weight' in list(f.keys()):
                                fp8_has_separate_lm_head = True
                                log.debug(_LOG_PREFIX, "  FP8 model has separate lm_head.weight in checkpoint")
                                break
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not check for lm_head.weight: {e}")
            
            # Determine dtype and load config
            if quantization == "4bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                load_kwargs["device_map"] = {"": 0}  # All to GPU 0
                model = QwenVLModelClass.from_pretrained(model_path, **load_kwargs)
            elif quantization == "8bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                load_kwargs["device_map"] = {"": 0}  # All to GPU 0
                model = QwenVLModelClass.from_pretrained(model_path, **load_kwargs)
            elif is_fp8_model:
                # FP8 pre-quantized models are NOT supported by Transformers v4.x!
                # From HuggingFace model page: "Currently, Transformers does not support
                # loading these weights directly. We recommend deploying using vLLM or SGLang."
                #
                # The FP8 format uses fine-grained quantization with scale factors that
                # transformers cannot handle correctly - mixed dtypes cause runtime errors.
                #
                # From HuggingFace model page: "Currently, Transformers does not support
                # loading these weights directly. We recommend deploying using vLLM or SGLang."
                #
                # SOLUTION: Use vLLM or SGLang backend for FP8 models
                log.error(_LOG_PREFIX, "FP8 models are NOT supported by Transformers!")
                log.error(_LOG_PREFIX, "HuggingFace explicitly states: 'Transformers does not support loading these weights directly'")
                raise RuntimeError(
                    f"FP8 pre-quantized models cannot be loaded with Transformers.\n\n"
                    "From the model page: 'Currently, Transformers does not support loading these weights directly.\n"
                    "We recommend deploying using vLLM or SGLang.'\n\n"
                    "Solutions:\n"
                    "  1. Change loading_method to 'vLLM (Docker)' or 'SGLang (Docker)'\n"
                    "  2. Or use the non-FP8 version (e.g., Qwen3-VL-2B-Instruct instead of Qwen3-VL-2B-Instruct-FP8)"
                )
            else:
                # auto/fp16/bf16/fp32 - use device_map="auto" for proper GPU placement
                dtype_map = {
                    "fp16": torch.float16,
                    "bf16": torch.bfloat16,
                    "fp32": torch.float32,
                    "auto": "auto",
                }
                load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                load_kwargs["device_map"] = "auto"  # Use auto for consistent GPU placement
                log.debug(_LOG_PREFIX, f"  Loading model with device_map=auto, dtype={load_kwargs[dtype_kwarg()]}...")
                model = QwenVLModelClass.from_pretrained(model_path, **load_kwargs)
            
            processor = AutoProcessor.from_pretrained(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            # FP8 models are also pre-quantized, so skip torch.compile for them too
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"] or is_fp8_model
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization/FP8)")
            
            # Cache model if keep_model_loaded is enabled
            if keep_model_loaded:
                cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                set_cached_transformers_model(cache_key, model, processor, ModelType.QWENVL)
            
            return model, processor, ModelType.QWENVL
        
        elif family == ModelFamily.FLORENCE:
            # Load Florence-2 with transformers
            # Build load kwargs for florence2_wrapper
            florence_kwargs = {"low_cpu_mem_usage": True}
            if attn_impl:
                florence_kwargs["attn_implementation"] = attn_impl
            
            # Florence-2 supports BitsAndBytes quantization for lower VRAM usage
            if quantization == "4bit":
                from transformers import BitsAndBytesConfig
                florence_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                florence_kwargs["device_map"] = {"": 0}  # All to GPU 0 for BitsAndBytes
            elif quantization == "8bit":
                from transformers import BitsAndBytesConfig
                florence_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                florence_kwargs["device_map"] = {"": 0}  # All to GPU 0 for BitsAndBytes
            else:
                # Non-quantized: let ComfyUI handle offload
                dtype_map = {
                    "fp16": torch.float16,
                    "bf16": torch.bfloat16,
                    "fp32": torch.float32,
                    "auto": "auto",
                }
                florence_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                florence_kwargs["device_map"] = None  # ComfyUI handles memory
            
            model = florence2_wrapper.load_florence2_model(model_path, **florence_kwargs)
            processor = florence2_wrapper.load_florence2_processor(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"]
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization)")
            
            # Cache model if keep_model_loaded is enabled
            if keep_model_loaded:
                cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                set_cached_transformers_model(cache_key, model, processor, ModelType.FLORENCE2)
            
            return model, processor, ModelType.FLORENCE2
        
        elif family == ModelFamily.MISTRAL:
            # Load Mistral VL with transformers
            from transformers import AutoProcessor, AutoModelForVision2Seq
            import transformers
            import json
            
            log.msg(_LOG_PREFIX, f"Loading Mistral VL ({quantization}, {attn_impl})")
            
            # Dynamic model class loading from config.json architectures field
            MistralModelClass = None
            config_path = Path(model_path) / "config.json"
            
            if config_path.exists():
                try:
                    config_data = json.loads(config_path.read_text(encoding='utf-8'))
                    architectures = config_data.get("architectures", [])
                    
                    if architectures:
                        class_name = architectures[0]  # e.g., "Mistral3ForConditionalGeneration"
                        
                        # IMPORTANT: For generation, we need the "ForConditionalGeneration" class
                        # The base "Mistral3Model" doesn't have embed_tokens attribute directly
                        if class_name == "Mistral3Model":
                            class_name = "Mistral3ForConditionalGeneration"
                            log.debug(_LOG_PREFIX, f"  Overriding Mistral3Model -> Mistral3ForConditionalGeneration (for generation)")
                        
                        try:
                            MistralModelClass = getattr(transformers, class_name)
                            log.debug(_LOG_PREFIX, f"  Using model class: {class_name}")
                        except AttributeError:
                            log.warning(_LOG_PREFIX, f"Class '{class_name}' not in transformers v{transformers.__version__}")
                            if "mistral3" in class_name.lower():
                                log.warning(_LOG_PREFIX, "Mistral3 models require transformers >= 5.0")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not read config.json: {e}")
            
            # Fallback to Auto* class if dynamic loading failed
            if MistralModelClass is None:
                MistralModelClass = AutoModelForVision2Seq
                log.debug(_LOG_PREFIX, "  Using AutoModelForVision2Seq fallback")
            
            # Check for FP8 model - reuse result from earlier detect_prequantized_model()
            # quant_type is already available from the detection done at start of TRANSFORMERS block
            is_fp8_model = (quant_type == "fp8")
            
            # Check transformers version - v5+ supports FP8 natively
            transformers_version = tuple(int(x) for x in transformers.__version__.split('.')[:2])
            has_native_fp8 = transformers_version >= (5, 0)
            
            # FP8 models require transformers v5+ for native support
            if is_fp8_model and not has_native_fp8:
                model_name = Path(model_path).name
                raise ValueError(
                    f"FP8 model '{model_name}' requires transformers >= 5.0 (you have {transformers.__version__}).\n\n"
                    f"Options:\n"
                    f"  1. Upgrade transformers: pip install transformers>=5.0\n"
                    f"  2. Use 'vLLM (Docker)' loading method (recommended for FP8)\n"
                    f"  3. Download the non-FP8 version: mistralai/Mistral-Small-3.1-24B-Instruct-2503\n"
                    f"     or mistralai/Ministral-3B-Instruct (regular bf16/fp16)\n"
                    f"  4. Use a GGUF quantized version with 'GGUF (llama-cpp-python)' method"
                )
            elif is_fp8_model and has_native_fp8:
                log.msg(_LOG_PREFIX, f"Loading FP8 model with transformers {transformers.__version__} native support")
            
            # Config patching for Mistral3 models - ONLY needed for transformers < 5.0
            # Transformers 5.0+ has native support for mistral3/ministral3 model types
            # Patching the config with v5+ actually BREAKS the model architecture!
            config_backup_path = Path(model_path) / "config.json.smartlm_backup"
            config_patched = False
            original_tie_word_embeddings = True  # Default: assume tied (most common case)
            
            # CLEANUP: If a backup exists but we're using transformers 5.0+, restore it
            # This fixes models that were corrupted by earlier versions of this code
            if has_native_fp8 and config_backup_path.exists():
                try:
                    import shutil
                    shutil.move(str(config_backup_path), str(config_path))
                    log.warning(_LOG_PREFIX, "Restored original config.json from backup (was corrupted by earlier patching)")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not restore backup: {e}")
            
            # Read original tie_word_embeddings state (needed for lm_head tying later)
            if config_path.exists():
                try:
                    config_data = json.loads(config_path.read_text())
                    
                    # CRITICAL: Save original tie_word_embeddings state BEFORE any patching
                    # Check top-level first (takes precedence), then text_config
                    if "tie_word_embeddings" in config_data:
                        original_tie_word_embeddings = config_data.get("tie_word_embeddings", True)
                    elif "text_config" in config_data and "tie_word_embeddings" in config_data["text_config"]:
                        original_tie_word_embeddings = config_data["text_config"].get("tie_word_embeddings", True)
                    log.debug(_LOG_PREFIX, f"  Original tie_word_embeddings: {original_tie_word_embeddings}")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not read config.json: {e}")
            
            # ONLY patch config for transformers < 5.0 (legacy workaround)
            # For v5.0+ with native mistral3/ministral3 support, skip all patching
            if not has_native_fp8 and config_path.exists():
                log.debug(_LOG_PREFIX, "  Legacy mode (transformers < 5.0): applying config patches")
                try:
                    config_data = json.loads(config_path.read_text())
                    needs_patch = False
                    
                    # Check text_config for mistral3 or ministral3 - change to "mistral"
                    # This makes transformers create MistralModel (text-only) for the language backbone
                    # instead of nested Mistral3Model which causes key mismatches
                    if "text_config" in config_data:
                        text_model_type = config_data["text_config"].get("model_type", "")
                        if text_model_type in ("mistral3", "ministral3"):
                            config_data["text_config"]["model_type"] = "mistral"
                            needs_patch = True
                            log.debug(_LOG_PREFIX, f"  Patching text_config.model_type: {text_model_type} -> mistral")
                        
                        # Disable tie_word_embeddings in text_config (causes accelerate IndexError)
                        if config_data["text_config"].get("tie_word_embeddings", True):
                            config_data["text_config"]["tie_word_embeddings"] = False
                            needs_patch = True
                            log.debug(_LOG_PREFIX, "  Patching text_config.tie_word_embeddings: False")
                    
                    # Also disable tie_word_embeddings at top level
                    if config_data.get("tie_word_embeddings", True):
                        config_data["tie_word_embeddings"] = False
                        needs_patch = True
                        log.debug(_LOG_PREFIX, "  Patching tie_word_embeddings: False")
                    
                    if needs_patch:
                        import shutil
                        shutil.copy(config_path, config_backup_path)
                        config_path.write_text(json.dumps(config_data, indent=2))
                        config_patched = True
                        log.debug(_LOG_PREFIX, f"  Config backed up to: {config_backup_path.name}")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not patch config: {e}")
            else:
                log.debug(_LOG_PREFIX, "  Transformers 5.0+ detected: skipping config patches (native support)")
            
            # Fix tokenizer_config.json if it has invalid tokenizer class
            tokenizer_config_path = Path(model_path) / "tokenizer_config.json"
            if tokenizer_config_path.exists():
                try:
                    tokenizer_data = json.loads(tokenizer_config_path.read_text())
                    tokenizer_class = tokenizer_data.get("tokenizer_class", "")
                    # TokenizersBackend is not a valid class - use PreTrainedTokenizerFast
                    if tokenizer_class == "TokenizersBackend":
                        tokenizer_data["tokenizer_class"] = "PreTrainedTokenizerFast"
                        tokenizer_config_path.write_text(json.dumps(tokenizer_data, indent=2))
                        log.debug(_LOG_PREFIX, "  Patching tokenizer_class: TokenizersBackend -> PreTrainedTokenizerFast")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not patch tokenizer config: {e}")
            
            # Build common kwargs - matching official HuggingFace Mistral3 examples
            # Official: AutoModelForImageTextToText.from_pretrained(checkpoint, device_map="auto", torch_dtype=torch.bfloat16)
            load_kwargs = {
                "trust_remote_code": True,
            }
            
            log.debug(_LOG_PREFIX, f"  quantization={quantization}, MistralModelClass={MistralModelClass.__name__}, is_fp8={is_fp8_model}")
            
            # BitsAndBytes quantization requires GPU - weights are quantized on GPU
            # Note: Vision tower stays in full precision (~1-2GB), only LLM layers get quantized
            
            try:
                if quantization == "4bit":
                    from transformers import BitsAndBytesConfig
                    import tempfile
                    # Use FREE VRAM (not total) for max_memory to prevent OOM
                    # Leave 2GB buffer for PyTorch overhead and peak quantization memory
                    torch.cuda.empty_cache()
                    gc.collect()
                    free_vram_bytes = torch.cuda.mem_get_info()[0]  # Returns (free, total)
                    free_vram_gb = max(1, (free_vram_bytes / (1024**3)) - 2.0)  # 2GB buffer for quantization peak
                    
                    # Create temp folder for weight offloading during quantization
                    offload_dir = os.path.join(tempfile.gettempdir(), "smartlm_offload")
                    os.makedirs(offload_dir, exist_ok=True)
                    
                    load_kwargs["device_map"] = "auto"
                    load_kwargs["max_memory"] = {0: f"{free_vram_gb:.1f}GiB", "cpu": "48GiB"}
                    load_kwargs["low_cpu_mem_usage"] = True
                    load_kwargs["offload_folder"] = offload_dir  # Allow disk offload for large models
                    load_kwargs["offload_state_dict"] = True  # Offload state dict during loading to reduce peak
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                    )
                    log.msg(_LOG_PREFIX, f"Loading 4bit model (max GPU: {free_vram_gb:.1f}GB free, offload enabled)")
                    log.debug(_LOG_PREFIX, f"  load_kwargs: {load_kwargs}")
                    model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                elif quantization == "8bit":
                    from transformers import BitsAndBytesConfig
                    import tempfile
                    torch.cuda.empty_cache()
                    gc.collect()
                    free_vram_bytes = torch.cuda.mem_get_info()[0]
                    free_vram_gb = max(1, (free_vram_bytes / (1024**3)) - 2.0)  # 2GB buffer
                    
                    offload_dir = os.path.join(tempfile.gettempdir(), "smartlm_offload")
                    os.makedirs(offload_dir, exist_ok=True)
                    
                    load_kwargs["device_map"] = "auto"
                    load_kwargs["max_memory"] = {0: f"{free_vram_gb:.1f}GiB", "cpu": "48GiB"}
                    load_kwargs["low_cpu_mem_usage"] = True
                    load_kwargs["offload_folder"] = offload_dir
                    load_kwargs["offload_state_dict"] = True
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                    log.msg(_LOG_PREFIX, f"Loading 8bit model (max GPU: {free_vram_gb:.1f}GB free, offload enabled)")
                    log.debug(_LOG_PREFIX, f"  load_kwargs: {load_kwargs}")
                    model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                elif is_fp8_model:
                    # FP8 model: use device_map="auto" with proper FP8 quantization config
                    # DO NOT set torch_dtype - this causes partial/broken dequantization!
                    # Instead, use FineGrainedFP8Config(dequantize=True) for clean BF16 conversion
                    # or let transformers use native FP8 triton kernels
                    try:
                        from transformers import FineGrainedFP8Config
                        # Dequantize to BF16 for clean inference (recommended by Mistral)
                        load_kwargs["device_map"] = "auto"
                        load_kwargs["quantization_config"] = FineGrainedFP8Config(dequantize=True)
                        log.debug(_LOG_PREFIX, f"  Loading FP8 model with dequantize=True (BF16 conversion)...")
                        log.debug(_LOG_PREFIX, f"  load_kwargs: {load_kwargs}")
                        model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                    except ImportError:
                        # Fallback for older transformers - try native FP8 without dtype forcing
                        load_kwargs["device_map"] = "auto"
                        log.debug(_LOG_PREFIX, f"  FineGrainedFP8Config not available, loading FP8 natively...")
                        log.debug(_LOG_PREFIX, f"  load_kwargs: {load_kwargs}")
                        model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                else:
                    # Non-FP8, non-quantized: use device_map="auto"
                    dtype_map = {
                        "fp16": torch.float16,
                        "bf16": torch.bfloat16,
                        "fp32": torch.float32,
                        "auto": torch.bfloat16,
                    }
                    load_kwargs["device_map"] = "auto"
                    load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, torch.bfloat16)
                    log.debug(_LOG_PREFIX, f"  Loading model with device_map=auto, dtype={load_kwargs[dtype_kwarg()]}...")
                    log.debug(_LOG_PREFIX, f"  load_kwargs: {load_kwargs}")
                    model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                log.debug(_LOG_PREFIX, f"  Model loaded successfully")
                
                # Manual lm_head tying - ONLY for transformers < 5.0 with config patching
                # Transformers 5.0+ handles tie_word_embeddings correctly, so skip this
                if not has_native_fp8 and original_tie_word_embeddings:
                    # ONLY tie if original config had tie_word_embeddings=True AND we patched the config
                    # - If True: checkpoint doesn't include lm_head.weight, we must tie it manually
                    # - If False: checkpoint HAS lm_head.weight, do NOT overwrite it (causes gibberish!)
                    if hasattr(model, 'lm_head') and hasattr(model, 'model'):
                        if hasattr(model.model, 'language_model') and hasattr(model.model.language_model, 'embed_tokens'):
                            model.lm_head.weight = model.model.language_model.embed_tokens.weight
                            log.debug(_LOG_PREFIX, "  Manually tied lm_head.weight to embed_tokens.weight (legacy mode)")
                elif has_native_fp8:
                    log.debug(_LOG_PREFIX, "  Transformers 5.0+ handles tie_word_embeddings natively, skipping manual tying")
                
            except Exception as e:
                log.error(_LOG_PREFIX, f"ERROR loading Mistral model: {e}")
                import traceback
                traceback.print_exc()
                raise
            finally:
                # Restore original config if we patched it
                if config_patched and config_backup_path.exists():
                    try:
                        import shutil
                        shutil.move(str(config_backup_path), str(config_path))
                        log.debug(_LOG_PREFIX, "  Restored original config.json")
                    except Exception as e:
                        log.debug(_LOG_PREFIX, f"  Could not restore config backup: {e}")
            
            # Load processor for Mistral models
            # Use AutoProcessor (PixtralProcessor) for image support
            # MistralCommonBackend doesn't support images in apply_chat_template
            log.debug(_LOG_PREFIX, "  Loading processor...")
            from transformers import AutoProcessor, AutoTokenizer
            processor = AutoProcessor.from_pretrained(model_path)
            log.debug(_LOG_PREFIX, f"  Using AutoProcessor: {type(processor).__name__}")
            
            # Some models don't have chat_template in processor but have it in tokenizer
            # Copy it over if missing
            if not hasattr(processor, 'chat_template') or processor.chat_template is None:
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_path)
                    if hasattr(tokenizer, 'chat_template') and tokenizer.chat_template:
                        processor.chat_template = tokenizer.chat_template
                        log.debug(_LOG_PREFIX, "  Copied chat_template from tokenizer to processor")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not copy chat_template: {e}")
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"]
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization)")
            
            # Cache model if keep_model_loaded is enabled
            if keep_model_loaded:
                cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                set_cached_transformers_model(cache_key, model, processor, ModelType.MISTRAL3)
            
            return model, processor, ModelType.MISTRAL3
        
        elif family == ModelFamily.LLM_TEXT:
            # Load text-only LLM with transformers
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            log.msg(_LOG_PREFIX, f"Loading LLM ({quantization}, {attn_impl})")
            
            # Build common kwargs
            load_kwargs = {"device_map": "auto"}
            if attn_impl:
                load_kwargs["attn_implementation"] = attn_impl
            
            if quantization == "4bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
                model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
            elif quantization == "8bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
            else:
                dtype_map = {
                    "fp16": torch.float16,
                    "bf16": torch.bfloat16,
                    "fp32": torch.float32,
                    "auto": "auto",
                }
                load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
            
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"]
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization)")
            
            # Cache model if keep_model_loaded is enabled
            if keep_model_loaded:
                cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                set_cached_transformers_model(cache_key, model, tokenizer, ModelType.LLM)
            
            return model, tokenizer, ModelType.LLM
        
        elif family == ModelFamily.LLAVA:
            # LLAVA family includes both LLaVA and Mllama (Llama 3.2 Vision) models
            # Auto-detect which one it is based on config.json architecture
            detected_type = detect_llava_or_mllama(model_path)
            
            if detected_type == ModelType.MLLAMA:
                # ================================================================
                # Load Mllama (Llama 3.2 Vision) model with transformers
                # ================================================================
                from transformers import AutoProcessor, MllamaForConditionalGeneration, AutoConfig
                import json as json_module
                
                # Mllama's vision attention module (MllamaVisionAttention) doesn't have
                # the is_causal attribute required by flash_attention_2
                # Fall back to sdpa or eager for Mllama models
                mllama_attn_impl = attn_impl
                if attn_impl == "flash_attention_2":
                    mllama_attn_impl = "sdpa"  # SDPA is still efficient and compatible
                    log.debug(_LOG_PREFIX, "  Mllama: flash_attention_2 not supported for vision module, using sdpa")
                
                log.msg(_LOG_PREFIX, f"Loading Llama 3.2 Vision / Mllama ({quantization}, {mllama_attn_impl})")
                
                # ================================================================
                # Note: Mllama models have a vocab_size mismatch issue where
                # embed_tokens has 128264 tokens (includes image tokens) but
                # config.vocab_size is 128256. We fix this AFTER loading.
                # See: https://huggingface.co/docs/transformers/model_doc/mllama#usage-tips
                # ================================================================
                config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
                
                # Build common kwargs - use device_map=None for non-quantized (like Florence2)
                # This avoids accelerate resharding overhead and allows faster reload
                # Do NOT pass modified config - let model load with original config
                load_kwargs = {"low_cpu_mem_usage": True}
                if mllama_attn_impl:
                    load_kwargs["attn_implementation"] = mllama_attn_impl
                
                # Check for pre-quantization
                is_prequantized_mllama = False
                config_path = Path(model_path) / "config.json"
                if config_path.exists():
                    try:
                        config_data = json_module.loads(config_path.read_text(encoding='utf-8'))
                        if config_data.get("quantization_config"):
                            is_prequantized_mllama = True
                            log.debug(_LOG_PREFIX, f"  Model has quantization_config - pre-quantized")
                    except Exception as e:
                        log.debug(_LOG_PREFIX, f"  Could not read config.json: {e}")
                
                # For Mllama models, we need to exclude the vision tower from quantization
                # The vision encoder doesn't work well with BitsAndBytes quantization
                llm_int8_skip_modules = ["vision_tower", "multi_modal_projector", "vision_model"]
                
                # Handle quantization - set device_map based on quantization mode
                # BitsAndBytes requires device_map for quantized loading
                # Non-quantized uses device_map=None (like Florence2) for faster reload
                if is_prequantized_mllama:
                    if quantization in ["4bit", "8bit"]:
                        log.warning(_LOG_PREFIX, f"Model is pre-quantized, ignoring {quantization} request")
                    log.debug(_LOG_PREFIX, "  Loading pre-quantized Mllama model without additional quantization")
                    load_kwargs["device_map"] = {"":0}  # Pre-quantized needs device_map
                    model = MllamaForConditionalGeneration.from_pretrained(model_path, **load_kwargs)
                elif quantization == "4bit":
                    from transformers import BitsAndBytesConfig
                    load_kwargs["device_map"] = {"":0}  # BitsAndBytes requires device_map
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        llm_int8_skip_modules=llm_int8_skip_modules,
                    )
                    model = MllamaForConditionalGeneration.from_pretrained(model_path, **load_kwargs)
                elif quantization == "8bit":
                    from transformers import BitsAndBytesConfig
                    load_kwargs["device_map"] = {"":0}  # BitsAndBytes requires device_map
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_skip_modules=llm_int8_skip_modules,
                    )
                    model = MllamaForConditionalGeneration.from_pretrained(model_path, **load_kwargs)
                else:
                    # Non-quantized: device_map=None lets ComfyUI handle memory (like Florence2)
                    dtype_map = {
                        "fp16": torch.float16,
                        "bf16": torch.bfloat16,
                        "fp32": torch.float32,
                        "auto": "auto",
                    }
                    load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                    load_kwargs["device_map"] = None
                    model = MllamaForConditionalGeneration.from_pretrained(model_path, **load_kwargs)
                    # Move to GPU explicitly for non-quantized
                    if torch.cuda.is_available():
                        model = model.to("cuda")
                
                # Verify lm_head size matches input embeddings (should be fixed by config adjustment above)
                input_embeddings = model.get_input_embeddings()
                input_size = input_embeddings.weight.shape[0]
                lm_head = model.lm_head if hasattr(model, 'lm_head') else model.get_output_embeddings()
                output_size = lm_head.out_features if hasattr(lm_head, 'out_features') else model.config.vocab_size
                log.debug(_LOG_PREFIX, f"  Mllama vocab check: embeddings={input_size}, lm_head={output_size}")
                
                # CRITICAL FIX: Resize lm_head if it doesn't match embeddings
                # This happens because Mllama has image tokens in embeddings but config.vocab_size doesn't include them
                if output_size < input_size:
                    log.msg(_LOG_PREFIX, f"Resizing lm_head: {output_size} -> {input_size} (fixing image token mismatch)")
                    try:
                        import torch.nn as nn
                        
                        old_lm_head = model.lm_head
                        in_features = old_lm_head.in_features
                        
                        # Check if this is a BitsAndBytes quantized layer
                        is_bnb_quantized = hasattr(old_lm_head, 'weight') and hasattr(old_lm_head.weight, 'quant_state')
                        
                        if is_bnb_quantized:
                            # For BitsAndBytes 4-bit quantized lm_head, we need to dequantize first
                            log.debug(_LOG_PREFIX, f"  lm_head is BnB quantized, dequantizing and resizing")
                            import bitsandbytes as bnb
                            
                            # Dequantize the weights
                            old_weight = bnb.functional.dequantize_4bit(
                                old_lm_head.weight.data,
                                old_lm_head.weight.quant_state
                            )
                            
                            # Create new fp16 lm_head with correct size
                            new_lm_head = nn.Linear(in_features, input_size, bias=False, dtype=torch.float16, device="cuda:0")
                            
                            # Copy existing weights and initialize new ones
                            with torch.no_grad():
                                new_lm_head.weight.data[:output_size, :] = old_weight.half()
                                # Initialize new token weights with mean of existing
                                mean_weight = old_weight.mean(dim=0, keepdim=True).half()
                                new_lm_head.weight.data[output_size:, :] = mean_weight.expand(input_size - output_size, -1)
                            
                            model.lm_head = new_lm_head
                            
                            # CRITICAL: Also update config.vocab_size so beam search uses correct shape
                            model.config.vocab_size = input_size
                            if hasattr(model.config, 'text_config') and model.config.text_config is not None:
                                model.config.text_config.vocab_size = input_size
                            
                            log.msg(_LOG_PREFIX, f"✓ lm_head resized (dequantized fp16)")
                        else:
                            # Non-quantized model - use standard resize
                            model.resize_token_embeddings(input_size)
                            log.msg(_LOG_PREFIX, "✓ Token embeddings resized")
                            
                    except Exception as e:
                        log.warning(_LOG_PREFIX, f"Could not resize lm_head: {e}")
                        import traceback
                        traceback.print_exc()
                
                processor = AutoProcessor.from_pretrained(model_path)
                
                # Apply torch.compile if requested (non-quantized only)
                use_torch_compile = kwargs.get('use_torch_compile', False)
                is_quantized_model = quantization in ["4bit", "8bit"] or is_prequantized_mllama
                if use_torch_compile and not is_quantized_model and torch.cuda.is_available():
                    try:
                        model = torch.compile(model, mode="reduce-overhead")
                        log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                    except Exception as e:
                        log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
                elif use_torch_compile and is_quantized_model:
                    log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization)")
                
                # Cache model if keep_model_loaded is enabled
                if keep_model_loaded:
                    cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                    set_cached_transformers_model(cache_key, model, processor, ModelType.MLLAMA)
                
                return model, processor, ModelType.MLLAMA
            
            else:
                # ================================================================
                # Load LLaVA vision-language model with transformers
                # ================================================================
                from transformers import AutoProcessor, AutoModelForVision2Seq, LlavaForConditionalGeneration
                import json as json_module
                
                log.msg(_LOG_PREFIX, f"Loading LLaVA ({quantization}, {attn_impl})")
            
            # Build common kwargs - use device_map=None for non-quantized (like Florence2)
            # This avoids accelerate resharding overhead and allows faster reload
            load_kwargs = {"low_cpu_mem_usage": True}
            if attn_impl:
                load_kwargs["attn_implementation"] = attn_impl
            
            # Try to determine the correct model class from config
            LlavaModelClass = None
            config_path = Path(model_path) / "config.json"
            is_prequantized_llava = False
            custom_llava_class = None
            
            if config_path.exists():
                try:
                    import transformers
                    config_data = json_module.loads(config_path.read_text(encoding='utf-8'))
                    architectures = config_data.get("architectures", [])
                    
                    # Check if model has quantization_config (pre-quantized)
                    if config_data.get("quantization_config"):
                        is_prequantized_llava = True
                        log.debug(_LOG_PREFIX, f"  Model has quantization_config - pre-quantized")
                    
                    if architectures:
                        class_name = architectures[0]
                        custom_llava_class = class_name  # Save for error message
                        try:
                            LlavaModelClass = getattr(transformers, class_name)
                            log.debug(_LOG_PREFIX, f"  Using model class from config: {class_name}")
                        except AttributeError:
                            log.debug(_LOG_PREFIX, f"  Class '{class_name}' not found in transformers, trying alternatives")
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not read config.json: {e}")
            
            # Also check safetensors files for SCB weights (bitsandbytes pre-quantized)
            # SCB = Scale Column Bias, indicates 8-bit quantized weights
            if not is_prequantized_llava:
                try:
                    from safetensors import safe_open
                    safetensor_files = [f for f in os.listdir(model_path) if f.endswith('.safetensors')]
                    for sf in safetensor_files[:1]:  # Only check first file
                        with safe_open(os.path.join(model_path, sf), framework='pt') as f:
                            keys = list(f.keys())
                            if any('.SCB' in k or '.CB' in k for k in keys):
                                is_prequantized_llava = True
                                log.debug(_LOG_PREFIX, f"  Detected SCB weights in safetensors - pre-quantized with bitsandbytes")
                                break
                except Exception as e:
                    log.debug(_LOG_PREFIX, f"  Could not check safetensors for SCB: {e}")
            
            # Check if this is a custom LLaVA model that requires the llava package
            if custom_llava_class and custom_llava_class not in [
                "LlavaForConditionalGeneration", "LlavaNextForConditionalGeneration",
                "LlavaNextVideoForConditionalGeneration", "LlavaOnevisionForConditionalGeneration",
                "VipLlavaForConditionalGeneration", "VideoLlavaForConditionalGeneration"
            ] and LlavaModelClass is None:
                # Try importing from custom llava package
                try:
                    if custom_llava_class == "LlavaLlamaForCausalLM":
                        from llava.model.language_model.llava_llama import LlavaLlamaForCausalLM
                        LlavaModelClass = LlavaLlamaForCausalLM
                        log.debug(_LOG_PREFIX, f"  Using LlavaLlamaForCausalLM from llava package")
                    elif custom_llava_class == "LlavaMistralForCausalLM":
                        from llava.model.language_model.llava_mistral import LlavaMistralForCausalLM
                        LlavaModelClass = LlavaMistralForCausalLM
                        log.debug(_LOG_PREFIX, f"  Using LlavaMistralForCausalLM from llava package")
                    elif custom_llava_class == "LlavaQwenForCausalLM":
                        from llava.model.language_model.llava_qwen import LlavaQwenForCausalLM
                        LlavaModelClass = LlavaQwenForCausalLM
                        log.debug(_LOG_PREFIX, f"  Using LlavaQwenForCausalLM from llava package")
                    else:
                        # Try generic import from llava.model
                        from llava.model import LlavaLlamaForCausalLM as FallbackClass
                        LlavaModelClass = FallbackClass
                        log.debug(_LOG_PREFIX, f"  Using fallback LlavaLlamaForCausalLM from llava package")
                except ImportError as e:
                    # Custom llava package not installed
                    raise ValueError(
                        f"This LLaVA model uses custom architecture '{custom_llava_class}' which is not in standard transformers.\n\n"
                        f"The custom 'llava' package is required but not installed or failed to import.\n"
                        f"Error: {e}\n\n"
                        f"Installation: pip install git+https://github.com/haotian-liu/LLaVA.git\n\n"
                        f"Alternatively, use a standard LLaVA model that works with transformers, such as:\n"
                        f"  - llava-hf/llava-1.5-7b-hf\n"
                        f"  - llava-hf/llava-v1.6-mistral-7b-hf\n"
                        f"  - llava-hf/llava-v1.6-vicuna-7b-hf"
                    )
            
            # Fallback: try common LLaVA classes
            if LlavaModelClass is None:
                try:
                    from transformers import LlavaNextForConditionalGeneration
                    LlavaModelClass = LlavaNextForConditionalGeneration
                    log.debug(_LOG_PREFIX, "  Using LlavaNextForConditionalGeneration (LLaVA 1.6+)")
                except ImportError:
                    LlavaModelClass = LlavaForConditionalGeneration
                    log.debug(_LOG_PREFIX, "  Using LlavaForConditionalGeneration")
            
            # For LLaVA models, we need to exclude the vision tower from quantization
            # The vision encoder (CLIP) doesn't work well with BitsAndBytes quantization
            # Only quantize the language model layers
            llm_int8_skip_modules = ["vision_tower", "multi_modal_projector", "vision_model", "image_newline"]
            
            # Monkey-patch llava package to support SigLIP vision towers
            # The llava package only supports CLIP by default, but some models use SigLIP
            try:
                import llava.model.multimodal_encoder.builder as llava_builder
                original_build_vision_tower = llava_builder.build_vision_tower
                
                def patched_build_vision_tower(vision_tower_cfg, **kwargs):
                    # Patched vision tower builder that supports SigLIP
                    vision_tower = getattr(vision_tower_cfg, 'mm_vision_tower', getattr(vision_tower_cfg, 'vision_tower', None))
                    if vision_tower is None:
                        vision_tower = vision_tower_cfg
                    
                    # Check if it's a SigLIP model
                    if isinstance(vision_tower, str) and 'siglip' in vision_tower.lower():
                        from llava.model.multimodal_encoder.clip_encoder import CLIPVisionTower
                        # SigLIP is architecture-compatible with CLIP for the purposes of LLaVA
                        # We can use CLIPVisionTower which will load via transformers AutoModel
                        log.debug(_LOG_PREFIX, f"  Patching SigLIP vision tower: {vision_tower}")
                        return CLIPVisionTower(vision_tower, args=vision_tower_cfg, **kwargs)
                    
                    # Fall back to original for CLIP models
                    return original_build_vision_tower(vision_tower_cfg, **kwargs)
                
                # Apply the patch
                llava_builder.build_vision_tower = patched_build_vision_tower
                log.debug(_LOG_PREFIX, "  Applied SigLIP vision tower patch to llava package")
            except Exception as patch_error:
                log.debug(_LOG_PREFIX, f"  Could not patch llava for SigLIP (may not be needed): {patch_error}")
            
            # Check if model is already pre-quantized (has SCB weights from bitsandbytes)
            # These models cannot have additional quantization applied
            # Set device_map based on quantization mode:
            # - BitsAndBytes requires device_map for quantized loading
            # - Non-quantized uses device_map=None (like Florence2) for faster reload
            if is_prequantized_llava:
                if quantization in ["4bit", "8bit"]:
                    log.warning(_LOG_PREFIX, f"Model is already pre-quantized, ignoring {quantization} request")
                # Load pre-quantized model as-is
                log.debug(_LOG_PREFIX, "  Loading pre-quantized LLaVA model without additional quantization")
                load_kwargs["device_map"] = {"":0}  # Pre-quantized needs device_map
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            elif quantization == "4bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["device_map"] = {"":0}  # BitsAndBytes requires device_map
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    llm_int8_skip_modules=llm_int8_skip_modules,
                )
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            elif quantization == "8bit":
                from transformers import BitsAndBytesConfig
                load_kwargs["device_map"] = {"":0}  # BitsAndBytes requires device_map
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_skip_modules=llm_int8_skip_modules,
                )
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            else:
                # Non-quantized: device_map=None lets ComfyUI handle memory (like Florence2)
                dtype_map = {
                    "fp16": torch.float16,
                    "bf16": torch.bfloat16,
                    "fp32": torch.float32,
                    "auto": "auto",
                }
                load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                load_kwargs["device_map"] = None
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
                # Move to GPU explicitly for non-quantized
                if torch.cuda.is_available():
                    model = model.to("cuda")
            
            processor = AutoProcessor.from_pretrained(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized_model = quantization in ["4bit", "8bit"] or is_prequantized_llava
            if use_torch_compile and not is_quantized_model and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    log.msg(_LOG_PREFIX, "✓ Applied torch.compile optimization")
                except Exception as e:
                    log.warning(_LOG_PREFIX, f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized_model:
                log.debug(_LOG_PREFIX, "  torch.compile skipped (not compatible with quantization)")
            
            # Cache model if keep_model_loaded is enabled
            if keep_model_loaded:
                cache_key = get_transformers_cache_key(model_path, resolved_quantization, resolved_attention)
                set_cached_transformers_model(cache_key, model, processor, ModelType.LLAVA)
            
            return model, processor, ModelType.LLAVA
        
        else:
            raise ValueError(f"Unknown model family: {model_family}")


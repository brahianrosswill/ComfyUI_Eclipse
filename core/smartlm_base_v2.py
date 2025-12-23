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
    is_mistral3_vision_model,
)

# Template functions
from .smartlm_templates import (
    get_template_dir, get_template_list, load_template,
    update_template_settings,
    load_prompt_configs, MODEL_CONFIGS,
    get_dev_mode, get_llm_models_path,
    TemplateContext,
)

# Centralized logger
from .logger import log


# ============================================================================
# Local Logging Helpers (prefix: "SmartLM")
# ============================================================================

def debug_log(message: str):
    # Print debug message only when log_level is 'debug'.
    log.debug("SmartLM", message)


def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning("SmartLM", message)


def msg_log(message: str):
    # Print regular message (always shown).
    log.msg("SmartLM", message)


def error_log(message: str):
    # Print error message (always shown).
    log.error("SmartLM", message)


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
    get_device_info, cleanup_memory_before_load, soft_empty_cache,
    is_llama_cpp_available, get_llama_cpp_module,
    auto_select_attention, auto_select_quantization,
    LLAMA_CPP_AVAILABLE, LLAMA_CPP_MODULE,
)


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
    
    msg_log(f"Dequantizing FP8 weights to {target_dtype}...")
    
    fp8_count = 0
    total_count = 0
    
    for sf_file in safetensor_files:
        debug_log(f"  Processing {sf_file.name}")
        
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
                    debug_log(f"    Dequantized {key}: {fp8_tensor.dtype} -> {dequant.dtype}")
                else:
                    # No scale found, just convert dtype
                    state_dict[key] = fp8_tensor.to(target_dtype)
                    debug_log(f"    Converted {key}: {fp8_tensor.dtype} -> {target_dtype} (no scale)")
            
            # Copy normal tensors
            for key, tensor in normal_tensors.items():
                # Skip scale tensors - they're not needed after dequantization
                if not key.endswith(".weight_scale_inv") and not key.endswith(".activation_scale"):
                    state_dict[key] = tensor if tensor.dtype == target_dtype else tensor.to(target_dtype)
    
    msg_log(f"Dequantized {fp8_count}/{total_count} FP8 tensors")
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
    
    msg_log("Loading Mistral FP8 with manual dequantization...")
    warning_log("This may take a few minutes for initial dequantization.")
    
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
                debug_log("  Removed quantization_config from config")
            
            # Fix text_config.model_type: mistral3/ministral3 -> mistral
            # This makes transformers create MistralModel (text-only) for the language backbone
            if "text_config" in config_data:
                text_model_type = config_data["text_config"].get("model_type", "")
                if text_model_type in ("mistral3", "ministral3"):
                    config_data["text_config"]["model_type"] = "mistral"
                    needs_patch = True
                    debug_log(f"  Patched text_config.model_type: {text_model_type} -> mistral")
                
                # Disable tie_word_embeddings in text_config
                if config_data["text_config"].get("tie_word_embeddings", True):
                    config_data["text_config"]["tie_word_embeddings"] = False
                    needs_patch = True
                    debug_log("  Patched text_config.tie_word_embeddings: False")
            
            # Also disable tie_word_embeddings at top level
            if config_data.get("tie_word_embeddings", True):
                config_data["tie_word_embeddings"] = False
                needs_patch = True
                debug_log("  Patched tie_word_embeddings: False")
            
            if needs_patch:
                config_path.write_text(json.dumps(config_data, indent=2))
        except Exception as e:
            debug_log(f"  Config patch error: {e}")
    
    # Patch tokenizer_config.json
    tokenizer_config_path = Path(model_path) / "tokenizer_config.json"
    if tokenizer_config_path.exists():
        try:
            tokenizer_data = json.loads(tokenizer_config_path.read_text())
            if tokenizer_data.get("tokenizer_class") == "TokenizersBackend":
                tokenizer_data["tokenizer_class"] = "PreTrainedTokenizerFast"
                tokenizer_config_path.write_text(json.dumps(tokenizer_data, indent=2))
                debug_log("  Patched tokenizer_class: TokenizersBackend -> PreTrainedTokenizerFast")
        except Exception as e:
            debug_log(f"  Tokenizer config patch error: {e}")
    
    # Dequantize weights
    state_dict = dequantize_fp8_model(model_path, target_dtype=torch.bfloat16)
    
    # Load config and create model skeleton
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    
    attn_impl = kwargs.get("attn_implementation")
    
    msg_log("Creating model architecture...")
    
    # Create empty model on meta device
    from_config_kwargs = {dtype_kwarg(): torch.bfloat16}
    if attn_impl:
        from_config_kwargs["attn_implementation"] = attn_impl
    
    with torch.device("meta"):
        model = AutoModelForVision2Seq.from_config(config, **from_config_kwargs)
    
    msg_log("Moving to CPU and loading weights...")
    
    # Use to_empty() to move from meta to CPU with empty tensors
    model = model.to_empty(device="cpu")
    
    # Now load the state dict
    missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=False)
    
    if missing_keys:
        debug_log(f"  Missing keys: {len(missing_keys)} (some may be tied weights)")
    if unexpected_keys:
        debug_log(f"  Unexpected keys: {len(unexpected_keys)}")
    
    # Clear state_dict reference to free memory
    del state_dict
    gc.collect()
    
    msg_log("Moving model to GPU...")
    
    # Move to GPU
    model = model.to("cuda")
    model.eval()
    
    # Manually tie lm_head.weight to embed_tokens (since we disabled tie_word_embeddings in config)
    if hasattr(model, 'lm_head') and hasattr(model, 'model'):
        if hasattr(model.model, 'language_model') and hasattr(model.model.language_model, 'embed_tokens'):
            model.lm_head.weight = model.model.language_model.embed_tokens.weight
            debug_log("  Manually tied lm_head.weight to embed_tokens.weight")
    
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
    debug_log(f"ensure_model_path_v2: template_name={template_name}")
    
    template_info = load_template(template_name)
    if not template_info:
        raise ValueError(f"Template '{template_name}' not found")
    
    debug_log(f"  template_info: repo_id={template_info.get('repo_id')}, local_path={template_info.get('local_path')}")
    
    result = ensure_model_path_core(
        template_info=template_info,
        template_name=template_name,
    )
    
    debug_log(f"  result: model_path={result[0]}")
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
    
    debug_log(f"load_model_with_backend: method={loading_method}, family={model_family}")
    debug_log(f"  model_path={model_path}")
    debug_log(f"  kwargs={kwargs}")
    
    # Cleanup memory before loading if requested
    if kwargs.get('memory_cleanup', True):
        cleanup_memory_before_load()
    
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
    
    debug_log(f"  Routing to backend: {method.value} + {family.value}")
    
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
                debug_log(f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
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
                    debug_log(f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                elif is_mistral3_vision:
                    debug_log(f"Auto mode: Mistral3/Pixtral vision model - BitsAndBytes not supported, using native dtype")
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
                        debug_log(f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        debug_log(f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None  # Let vLLM use default dtype
            elif quantization in ("4bit", "8bit"):
                if is_mistral3_vision:
                    warning_log("Mistral3/Pixtral vision models don't support BitsAndBytes in vLLM - using native dtype")
                    quantization = None
                elif quantization == "4bit":
                    debug_log("Using bitsandbytes 4-bit quantization for vLLM")
                    quantization = "bitsandbytes"
                else:
                    warning_log("vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
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
                debug_log(f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
            # Update template with detected quantization
            _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
            
            # Map Transformers-style quantization to vLLM-compatible options
            if quantization == "auto":
                if is_prequantized:
                    debug_log(f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                else:
                    model_size_gb = calculate_model_size(Path(model_path))
                    auto_quant = auto_select_quantization(
                        model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                        estimated_size_gb=model_size_gb,
                    )
                    if auto_quant in ("4bit", "8bit"):
                        debug_log(f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        debug_log(f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None
            elif quantization in ("4bit", "8bit"):
                debug_log("Using bitsandbytes 4-bit quantization for vLLM")
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
                debug_log(f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
            # Update template with detected quantization
            _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
            
            # Map Transformers-style quantization to vLLM-compatible options
            if quantization == "auto":
                if is_prequantized:
                    debug_log(f"Auto mode: model already {prequant_type} quantized, using native dtype")
                    quantization = None
                else:
                    model_size_gb = calculate_model_size(Path(model_path))
                    auto_quant = auto_select_quantization(
                        model_name=model_path.split("/")[-1] if "/" in model_path else model_path,
                        estimated_size_gb=model_size_gb,
                    )
                    if auto_quant in ("4bit", "8bit"):
                        debug_log(f"Auto mode: using bitsandbytes 4-bit for vLLM (auto selected {auto_quant})")
                        quantization = "bitsandbytes"
                    else:
                        debug_log(f"Auto mode: sufficient VRAM, no quantization needed")
                        quantization = None
            elif quantization == "4bit":
                debug_log("Using bitsandbytes 4-bit quantization for vLLM")
                quantization = "bitsandbytes"
            elif quantization == "8bit":
                warning_log("vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
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
            debug_log(f"Model is pre-quantized ({prequant_type}), using native format")
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
                debug_log(f"Auto mode: SGLang doesn't support bitsandbytes, using native dtype")
                quantization = None
            else:
                quantization = None
        elif quantization in ("4bit", "8bit"):
            warning_log("SGLang doesn't support bitsandbytes quantization - using native dtype")
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
            debug_log(f"Model is pre-quantized ({prequant_type}), skipping additional quantization")
        # Update template with detected quantization
        _maybe_update_template_quantization(ctx, is_prequantized, prequant_type)
        
        # Map Transformers-style quantization to vLLM-compatible options
        # Note: vLLM bitsandbytes only supports 4-bit, not 8-bit
        if quantization == "auto":
            # Skip auto-quant for pre-quantized models - they already fit in VRAM efficiently
            if is_prequantized:
                debug_log(f"Auto mode: model already {prequant_type} quantized, using native dtype")
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
                    debug_log(f"Auto mode: using bitsandbytes 4-bit for vLLM Native (auto selected {auto_quant})")
                    quantization = "bitsandbytes"
                else:
                    debug_log(f"Auto mode: sufficient VRAM, no quantization needed")
                    quantization = None  # Let vLLM use default dtype
        elif quantization == "4bit":
            debug_log("Using bitsandbytes 4-bit quantization for vLLM Native")
            quantization = "bitsandbytes"
        elif quantization == "8bit":
            warning_log("vLLM bitsandbytes only supports 4-bit. Falling back to 4-bit.")
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
            msg_log(f"Selected GGUF: {model_file.name} (from {len(model_gguf_files)} available)")
        
        if not model_file.exists():
            raise FileNotFoundError(f"GGUF model file not found: {model_file}")
        
        context_size = kwargs.get('context_size', 32768)
        device = kwargs.get('device', 'cuda')
        
        # Determine GPU layers (-1 = full offload for CUDA)
        n_gpu_layers = -1 if device == "cuda" else 0
        
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
                msg_log("Loading Qwen VL GGUF (vision)")
                
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
                    warning_log("Qwen chat handler not available, falling back to Llava")
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
                return model, None, ModelType.QWENVL
            else:
                # Text-only Qwen (no mmproj)
                msg_log("Loading Qwen GGUF (text-only)")
                model = Llama(
                    model_path=str(model_file),
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
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
                msg_log(f"Loading Mistral VL GGUF (vision): {model_file.name}")
                msg_log(f"  mmproj: {Path(mmproj_file).name}")
                
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
                    warning_log(f"Failed to load with vision support: {e}")
                    warning_log("Falling back to text-only mode")
                except Exception as e:
                    warning_log(f"Failed to load with vision support: {e}")
                    warning_log("Falling back to text-only mode")
            
            # Text-only LLM
            msg_log(f"Loading LLM GGUF: {model_file.name}")
            try:
                model = Llama(
                    model_path=str(model_file),
                    n_ctx=context_size,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
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
            
            msg_log(f"Loading LLaVA GGUF (vision): {model_file.name}")
            msg_log(f"  mmproj: {Path(mmproj_file).name}")
            
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
            debug_log(f"Using Ollama registry model from template: {ollama_model_from_template}")
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
                debug_log(f"HuggingFace model detected, attempting to import into Ollama...")
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
            debug_log(f"Model detected as pre-quantized ({quant_type}) but template says quantized=false")
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
            debug_log(f"Template says quantized=true but no quantization config detected in files")
        
        # Handle quantization selection
        if is_prequantized:
            # Pre-quantized model - don't apply additional quantization (would break/corrupt)
            if quantization in ["4bit", "8bit"]:
                warning_log(f"Model is pre-quantized ({quant_type}), ignoring {quantization} request")
            # For FP8: we'll use FineGrainedFP8Config(dequantize=True) to convert to BF16
            # For others: load as-is with native dtype handling
            quantization = "fp16"  # Placeholder - actual loading handled per-model family
            if quant_type == "fp8":
                msg_log(f"Pre-quantized model ({quant_type}), will dequantize to BF16")
            else:
                msg_log(f"Pre-quantized model ({quant_type}), loading with native dtype")
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
            
            msg_log(f"Loading Qwen VL ({quantization}, {attn_impl})")
            
            # Use AutoModelForVision2Seq to auto-detect the correct class from config
            # This handles both Qwen2.5-VL (Qwen2_5_VLForConditionalGeneration) and
            # Qwen3-VL (Qwen3VLForConditionalGeneration) automatically
            from transformers import AutoModelForVision2Seq, AutoConfig
            QwenVLModelClass = AutoModelForVision2Seq
            
            # Debug: show detected model class from config
            try:
                config = AutoConfig.from_pretrained(model_path)
                arch = config.architectures[0] if config.architectures else "unknown"
                debug_log(f"  Config class: {type(config).__name__}, architecture: {arch}")
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
                                debug_log("  FP8 model has separate lm_head.weight in checkpoint")
                                break
                except Exception as e:
                    debug_log(f"  Could not check for lm_head.weight: {e}")
            
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
                error_log("FP8 models are NOT supported by Transformers!")
                error_log("HuggingFace explicitly states: 'Transformers does not support loading these weights directly'")
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
                debug_log(f"  Loading model with device_map=auto, dtype={load_kwargs[dtype_kwarg()]}...")
                model = QwenVLModelClass.from_pretrained(model_path, **load_kwargs)
            
            processor = AutoProcessor.from_pretrained(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            # FP8 models are also pre-quantized, so skip torch.compile for them too
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"] or is_fp8_model
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    msg_log("✓ Applied torch.compile optimization")
                except Exception as e:
                    warning_log(f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                debug_log("  torch.compile skipped (not compatible with quantization/FP8)")
            
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
                    msg_log("✓ Applied torch.compile optimization")
                except Exception as e:
                    warning_log(f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                debug_log("  torch.compile skipped (not compatible with quantization)")
            
            return model, processor, ModelType.FLORENCE2
        
        elif family == ModelFamily.MISTRAL:
            # Load Mistral VL with transformers
            from transformers import AutoProcessor, AutoModelForVision2Seq
            import transformers
            import json
            
            msg_log(f"Loading Mistral VL ({quantization}, {attn_impl})")
            
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
                            debug_log(f"  Overriding Mistral3Model -> Mistral3ForConditionalGeneration (for generation)")
                        
                        try:
                            MistralModelClass = getattr(transformers, class_name)
                            debug_log(f"  Using model class: {class_name}")
                        except AttributeError:
                            warning_log(f"Class '{class_name}' not in transformers v{transformers.__version__}")
                            if "mistral3" in class_name.lower():
                                warning_log("Mistral3 models require transformers >= 5.0")
                except Exception as e:
                    debug_log(f"  Could not read config.json: {e}")
            
            # Fallback to Auto* class if dynamic loading failed
            if MistralModelClass is None:
                MistralModelClass = AutoModelForVision2Seq
                debug_log("  Using AutoModelForVision2Seq fallback")
            
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
                msg_log(f"Loading FP8 model with transformers {transformers.__version__} native support")
            
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
                    warning_log("Restored original config.json from backup (was corrupted by earlier patching)")
                except Exception as e:
                    debug_log(f"  Could not restore backup: {e}")
            
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
                    debug_log(f"  Original tie_word_embeddings: {original_tie_word_embeddings}")
                except Exception as e:
                    debug_log(f"  Could not read config.json: {e}")
            
            # ONLY patch config for transformers < 5.0 (legacy workaround)
            # For v5.0+ with native mistral3/ministral3 support, skip all patching
            if not has_native_fp8 and config_path.exists():
                debug_log("  Legacy mode (transformers < 5.0): applying config patches")
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
                            debug_log(f"  Patching text_config.model_type: {text_model_type} -> mistral")
                        
                        # Disable tie_word_embeddings in text_config (causes accelerate IndexError)
                        if config_data["text_config"].get("tie_word_embeddings", True):
                            config_data["text_config"]["tie_word_embeddings"] = False
                            needs_patch = True
                            debug_log("  Patching text_config.tie_word_embeddings: False")
                    
                    # Also disable tie_word_embeddings at top level
                    if config_data.get("tie_word_embeddings", True):
                        config_data["tie_word_embeddings"] = False
                        needs_patch = True
                        debug_log("  Patching tie_word_embeddings: False")
                    
                    if needs_patch:
                        import shutil
                        shutil.copy(config_path, config_backup_path)
                        config_path.write_text(json.dumps(config_data, indent=2))
                        config_patched = True
                        debug_log(f"  Config backed up to: {config_backup_path.name}")
                except Exception as e:
                    debug_log(f"  Could not patch config: {e}")
            else:
                debug_log("  Transformers 5.0+ detected: skipping config patches (native support)")
            
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
                        debug_log("  Patching tokenizer_class: TokenizersBackend -> PreTrainedTokenizerFast")
                except Exception as e:
                    debug_log(f"  Could not patch tokenizer config: {e}")
            
            # Build common kwargs - matching official HuggingFace Mistral3 examples
            # Official: AutoModelForImageTextToText.from_pretrained(checkpoint, device_map="auto", torch_dtype=torch.bfloat16)
            load_kwargs = {
                "trust_remote_code": True,
            }
            
            debug_log(f"  quantization={quantization}, MistralModelClass={MistralModelClass.__name__}, is_fp8={is_fp8_model}")
            
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
                    msg_log(f"Loading 4bit model (max GPU: {free_vram_gb:.1f}GB free, offload enabled)")
                    debug_log(f"  load_kwargs: {load_kwargs}")
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
                    msg_log(f"Loading 8bit model (max GPU: {free_vram_gb:.1f}GB free, offload enabled)")
                    debug_log(f"  load_kwargs: {load_kwargs}")
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
                        debug_log(f"  Loading FP8 model with dequantize=True (BF16 conversion)...")
                        debug_log(f"  load_kwargs: {load_kwargs}")
                        model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                    except ImportError:
                        # Fallback for older transformers - try native FP8 without dtype forcing
                        load_kwargs["device_map"] = "auto"
                        debug_log(f"  FineGrainedFP8Config not available, loading FP8 natively...")
                        debug_log(f"  load_kwargs: {load_kwargs}")
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
                    debug_log(f"  Loading model with device_map=auto, dtype={load_kwargs[dtype_kwarg()]}...")
                    debug_log(f"  load_kwargs: {load_kwargs}")
                    model = MistralModelClass.from_pretrained(model_path, **load_kwargs)
                debug_log(f"  Model loaded successfully")
                
                # Manual lm_head tying - ONLY for transformers < 5.0 with config patching
                # Transformers 5.0+ handles tie_word_embeddings correctly, so skip this
                if not has_native_fp8 and original_tie_word_embeddings:
                    # ONLY tie if original config had tie_word_embeddings=True AND we patched the config
                    # - If True: checkpoint doesn't include lm_head.weight, we must tie it manually
                    # - If False: checkpoint HAS lm_head.weight, do NOT overwrite it (causes gibberish!)
                    if hasattr(model, 'lm_head') and hasattr(model, 'model'):
                        if hasattr(model.model, 'language_model') and hasattr(model.model.language_model, 'embed_tokens'):
                            model.lm_head.weight = model.model.language_model.embed_tokens.weight
                            debug_log("  Manually tied lm_head.weight to embed_tokens.weight (legacy mode)")
                elif has_native_fp8:
                    debug_log("  Transformers 5.0+ handles tie_word_embeddings natively, skipping manual tying")
                
            except Exception as e:
                error_log(f"ERROR loading Mistral model: {e}")
                import traceback
                traceback.print_exc()
                raise
            finally:
                # Restore original config if we patched it
                if config_patched and config_backup_path.exists():
                    try:
                        import shutil
                        shutil.move(str(config_backup_path), str(config_path))
                        debug_log("  Restored original config.json")
                    except Exception as e:
                        debug_log(f"  Could not restore config backup: {e}")
            
            # Load processor for Mistral models
            # Use AutoProcessor (PixtralProcessor) for image support
            # MistralCommonBackend doesn't support images in apply_chat_template
            debug_log("  Loading processor...")
            from transformers import AutoProcessor, AutoTokenizer
            processor = AutoProcessor.from_pretrained(model_path)
            debug_log(f"  Using AutoProcessor: {type(processor).__name__}")
            
            # Some models don't have chat_template in processor but have it in tokenizer
            # Copy it over if missing
            if not hasattr(processor, 'chat_template') or processor.chat_template is None:
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_path)
                    if hasattr(tokenizer, 'chat_template') and tokenizer.chat_template:
                        processor.chat_template = tokenizer.chat_template
                        debug_log("  Copied chat_template from tokenizer to processor")
                except Exception as e:
                    debug_log(f"  Could not copy chat_template: {e}")
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized = quantization in ["4bit", "8bit"]
            if use_torch_compile and not is_quantized and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    msg_log("✓ Applied torch.compile optimization")
                except Exception as e:
                    warning_log(f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                debug_log("  torch.compile skipped (not compatible with quantization)")
            
            return model, processor, ModelType.MISTRAL3
        
        elif family == ModelFamily.LLM_TEXT:
            # Load text-only LLM with transformers
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            msg_log(f"Loading LLM ({quantization}, {attn_impl})")
            
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
                    msg_log("✓ Applied torch.compile optimization")
                except Exception as e:
                    warning_log(f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized:
                debug_log("  torch.compile skipped (not compatible with quantization)")
            
            return model, tokenizer, ModelType.LLM
        
        elif family == ModelFamily.LLAVA:
            # Load LLaVA vision-language model with transformers
            from transformers import AutoProcessor, AutoModelForVision2Seq, LlavaForConditionalGeneration
            import json as json_module
            
            msg_log(f"Loading LLaVA ({quantization}, {attn_impl})")
            
            # Build common kwargs
            load_kwargs = {"device_map": "auto", "low_cpu_mem_usage": True}
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
                        debug_log(f"  Model has quantization_config - pre-quantized")
                    
                    if architectures:
                        class_name = architectures[0]
                        custom_llava_class = class_name  # Save for error message
                        try:
                            LlavaModelClass = getattr(transformers, class_name)
                            debug_log(f"  Using model class from config: {class_name}")
                        except AttributeError:
                            debug_log(f"  Class '{class_name}' not found in transformers, trying alternatives")
                except Exception as e:
                    debug_log(f"  Could not read config.json: {e}")
            
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
                                debug_log(f"  Detected SCB weights in safetensors - pre-quantized with bitsandbytes")
                                break
                except Exception as e:
                    debug_log(f"  Could not check safetensors for SCB: {e}")
            
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
                        debug_log(f"  Using LlavaLlamaForCausalLM from llava package")
                    elif custom_llava_class == "LlavaMistralForCausalLM":
                        from llava.model.language_model.llava_mistral import LlavaMistralForCausalLM
                        LlavaModelClass = LlavaMistralForCausalLM
                        debug_log(f"  Using LlavaMistralForCausalLM from llava package")
                    elif custom_llava_class == "LlavaQwenForCausalLM":
                        from llava.model.language_model.llava_qwen import LlavaQwenForCausalLM
                        LlavaModelClass = LlavaQwenForCausalLM
                        debug_log(f"  Using LlavaQwenForCausalLM from llava package")
                    else:
                        # Try generic import from llava.model
                        from llava.model import LlavaLlamaForCausalLM as FallbackClass
                        LlavaModelClass = FallbackClass
                        debug_log(f"  Using fallback LlavaLlamaForCausalLM from llava package")
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
                    debug_log("  Using LlavaNextForConditionalGeneration (LLaVA 1.6+)")
                except ImportError:
                    LlavaModelClass = LlavaForConditionalGeneration
                    debug_log("  Using LlavaForConditionalGeneration")
            
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
                    """Patched vision tower builder that supports SigLIP"""
                    vision_tower = getattr(vision_tower_cfg, 'mm_vision_tower', getattr(vision_tower_cfg, 'vision_tower', None))
                    if vision_tower is None:
                        vision_tower = vision_tower_cfg
                    
                    # Check if it's a SigLIP model
                    if isinstance(vision_tower, str) and 'siglip' in vision_tower.lower():
                        from llava.model.multimodal_encoder.clip_encoder import CLIPVisionTower
                        # SigLIP is architecture-compatible with CLIP for the purposes of LLaVA
                        # We can use CLIPVisionTower which will load via transformers AutoModel
                        debug_log(f"  Patching SigLIP vision tower: {vision_tower}")
                        return CLIPVisionTower(vision_tower, args=vision_tower_cfg, **kwargs)
                    
                    # Fall back to original for CLIP models
                    return original_build_vision_tower(vision_tower_cfg, **kwargs)
                
                # Apply the patch
                llava_builder.build_vision_tower = patched_build_vision_tower
                debug_log("  Applied SigLIP vision tower patch to llava package")
            except Exception as patch_error:
                debug_log(f"  Could not patch llava for SigLIP (may not be needed): {patch_error}")
            
            # Check if model is already pre-quantized (has SCB weights from bitsandbytes)
            # These models cannot have additional quantization applied
            if is_prequantized_llava:
                if quantization in ["4bit", "8bit"]:
                    warning_log(f"Model is already pre-quantized, ignoring {quantization} request")
                # Load pre-quantized model as-is
                debug_log("  Loading pre-quantized LLaVA model without additional quantization")
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            elif quantization == "4bit":
                from transformers import BitsAndBytesConfig
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
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_skip_modules=llm_int8_skip_modules,
                )
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            else:
                dtype_map = {
                    "fp16": torch.float16,
                    "bf16": torch.bfloat16,
                    "fp32": torch.float32,
                    "auto": "auto",
                }
                load_kwargs[dtype_kwarg()] = dtype_map.get(quantization, "auto")
                model = LlavaModelClass.from_pretrained(model_path, **load_kwargs)
            
            processor = AutoProcessor.from_pretrained(model_path)
            
            # Apply torch.compile if requested (non-quantized only)
            use_torch_compile = kwargs.get('use_torch_compile', False)
            is_quantized_model = quantization in ["4bit", "8bit"] or is_prequantized_llava
            if use_torch_compile and not is_quantized_model and torch.cuda.is_available():
                try:
                    model = torch.compile(model, mode="reduce-overhead")
                    msg_log("✓ Applied torch.compile optimization")
                except Exception as e:
                    warning_log(f"torch.compile failed: {e}")
            elif use_torch_compile and is_quantized_model:
                debug_log("  torch.compile skipped (not compatible with quantization)")
            
            return model, processor, ModelType.LLAVA
        
        else:
            raise ValueError(f"Unknown model family: {model_family}")


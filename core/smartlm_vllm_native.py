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

# Native vLLM integration for Eclipse SmartLM (Linux only).
#
# This module handles native vLLM loading on Linux where vLLM can be installed directly
# via pip without Docker. For Windows, use smartlm_vllm_docker.py instead.
#
# vLLM provides optimized inference for LLMs with:
# - Continuous batching
# - PagedAttention
# - Tensor parallelism
# - Native FP8 support
# ==============================================================================
# CRITICAL: Disable vLLM v1 engine and multiprocessing BEFORE importing vLLM
# This prevents the spawn/fork issue when vLLM is used as a library in ComfyUI
# where CUDA is already initialized before vLLM loads.
# vLLM v1 engine spawns a separate EngineCore process which re-executes main.py
# ==============================================================================
import os
os.environ["VLLM_USE_V1"] = "0"  # Force v0 engine (no multiprocessing)
os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"  # Disable v1 multiprocessing if v1 is used
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "fork"  # Use fork instead of spawn
import gc
import platform
import torch
from pathlib import Path
from typing import Optional, Dict, Any, List

from .smartlm_templates import get_dev_mode
from .logger import log


# Local logging helpers with "vLLM Native" prefix
def debug_log(message: str):
    # Print debug message only when log_level is 'debug'
    log.debug("vLLM Native", message)


def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher
    log.warning("vLLM Native", message)


def msg_log(message: str):
    # Print regular message (always shown)
    log.msg("vLLM Native", message)


def error_log(message: str):
    # Print error message (always shown)
    log.error("vLLM Native", message)


# ==============================================================================
# PLATFORM CHECK
# ==============================================================================

IS_LINUX = platform.system() == "Linux"

if not IS_LINUX:
    warning_log("This module is for Linux only. Use smartlm_vllm_docker.py on Windows.")


# ==============================================================================
# NATIVE vLLM AVAILABILITY CHECK
# ==============================================================================

VLLM_AVAILABLE = False
VLLM_VERSION = ""

try:
    import vllm
    VLLM_AVAILABLE = True
    VLLM_VERSION = getattr(vllm, '__version__', 'unknown')
    msg_log(f"✓ vLLM {VLLM_VERSION} available")
except ImportError:
    warning_log("vLLM not installed. Install with: pip install vllm")


def is_vllm_available() -> bool:
    # Check if native vLLM is available
    return VLLM_AVAILABLE and IS_LINUX


# ==============================================================================
# vLLM MODEL LOADING (Native)
# ==============================================================================

# Cache for loaded vLLM models
# NOTE: Only ONE model is kept cached at a time to prevent VRAM accumulation
# in multi-node workflows. Loading a different model will evict the cached one.
_vllm_model_cache: Dict[str, Any] = {}


def _clear_vllm_cache_if_different(new_cache_key: str):
    """Clear vLLM cache if a different model is being loaded.
    
    This prevents VRAM accumulation when multiple SmartLoader nodes
    use different models in the same workflow.
    """
    global _vllm_model_cache
    
    if _vllm_model_cache and new_cache_key not in _vllm_model_cache:
        debug_log("Clearing previous vLLM model from cache (different model requested)")
        # Unload all cached models
        for key in list(_vllm_model_cache.keys()):
            try:
                llm = _vllm_model_cache.pop(key)
                del llm
            except Exception as e:
                debug_log(f"  Error clearing vLLM model {key}: {e}")
        
        # Force garbage collection
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()


def load_vllm(
    smart_lm_instance,
    template_name: str,
    model_path: str,
    quantization: str = None,
    context_size: int = None,
    gpu_memory_utilization: float = None
) -> Optional[Dict[str, Any]]:
    # Load model via native vLLM (Linux only).
    #
    # This function uses vLLM's LLM class directly for optimized inference.
    # Only ONE model is cached at a time - loading a different model will
    # evict the previous one to prevent VRAM accumulation in multi-node workflows.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance
    #     template_name: Template name from config
    #     model_path: Full path to model folder
    #     quantization: Quantization method (bitsandbytes, awq, gptq, fp8, or None)
    #     context_size: Maximum context window size (max_model_len in vLLM)
    #     gpu_memory_utilization: GPU memory utilization (0.0-1.0)
    #
    # Returns:
    #     Dict with vLLM model info, or None if unavailable
    if not is_vllm_available():
        warning_log("Not available on this platform")
        return None
    
    try:
        from vllm import LLM, SamplingParams
    except ImportError as e:
        error_log(f"Failed to import vLLM: {e}")
        return None
    
    model_name = Path(model_path).name
    
    # Build cache key that includes quantization and context_size
    cache_key = f"{model_path}:{quantization or 'none'}:{context_size or 'auto'}"
    
    # Clear cache if loading a different model (prevents VRAM accumulation)
    _clear_vllm_cache_if_different(cache_key)
    
    # Check if model is already loaded with same settings
    if cache_key in _vllm_model_cache:
        debug_log(f"Using cached vLLM model: {model_name}")
        llm = _vllm_model_cache[cache_key]
    else:
        msg_log(f"Loading model: {model_name}")
        
        # Detect WSL environment
        is_wsl = False
        try:
            with open('/proc/version', 'r') as f:
                is_wsl = 'microsoft' in f.read().lower() or 'wsl' in f.read().lower()
        except:
            pass
        
        # Build LLM kwargs
        llm_kwargs = {
            "model": model_path,
            "dtype": "auto",  # Let vLLM auto-detect (supports FP8 natively)
            "seed": 0,  # Explicit seed (None is deprecated in v0.13)
            "allowed_local_media_path": "/",  # Allow loading local images for vision models
            "trust_remote_code": True,  # Required for newer model architectures (Mistral 3/Pixtral)
            "disable_log_stats": True,  # Reduce log spam
        }
        
        # ==============================================================================
        # MISTRAL NATIVE FORMAT DETECTION
        # Mistral models distributed in native format have consolidated.safetensors
        # and require special loading parameters (config_format, load_format, tokenizer_mode)
        # HuggingFace-converted models (model.safetensors with language_model.* prefix) 
        # are broken in vLLM 0.12+ due to weight mapping issues with Pixtral loader
        # NOTE: Mistral native format is incompatible with bitsandbytes quantization
        #       (load_format conflicts: "mistral" vs "bitsandbytes")
        # ==============================================================================
        model_dir = Path(model_path)
        consolidated_path = model_dir / "consolidated.safetensors"
        params_json_path = model_dir / "params.json"  # Mistral native format indicator
        config_json_path = model_dir / "config.json"
        
        # Check for Mistral native format (consolidated.safetensors or params.json)
        is_mistral_native = consolidated_path.exists() or params_json_path.exists()
        
        # Also check config.json for Mistral3/Pixtral vision models
        # These need enforce_eager to avoid CUDA graph crashes
        is_mistral3_vision = False
        if config_json_path.exists():
            try:
                import json
                with open(config_json_path, 'r') as f:
                    config = json.load(f)
                architectures = config.get("architectures", [])
                model_type = config.get("model_type", "")
                vision_type = config.get("vision_config", {}).get("model_type", "")
                is_mistral3_vision = (
                    "Mistral3ForConditionalGeneration" in architectures or
                    model_type == "mistral3" or
                    vision_type == "pixtral"
                )
                if is_mistral3_vision:
                    debug_log("  Detected Mistral3/Pixtral vision model from config.json")
            except Exception as e:
                debug_log(f"  Could not read config.json: {e}")
        
        # Fallback: check model name for ministral/pixtral
        model_name_lower = Path(model_path).name.lower()
        if "ministral" in model_name_lower or "pixtral" in model_name_lower:
            is_mistral3_vision = True
            debug_log("  Detected Mistral3/Pixtral from model name")
        
        # Check if bitsandbytes quantization is requested or might be auto-selected
        # Note: 'auto' quantization might select bitsandbytes based on VRAM, which conflicts with mistral load_format
        is_bitsandbytes = quantization and quantization.lower() == 'bitsandbytes'
        is_auto_quant = quantization and quantization.lower() == 'auto'
        
        # Also check if auto-quantization will likely need bitsandbytes (model too big for VRAM)
        needs_quantization = False
        if is_auto_quant and is_mistral_native:
            try:
                import torch
                # Estimate model size from consolidated.safetensors
                model_size_gb = consolidated_path.stat().st_size / (1024**3) if consolidated_path.exists() else 0
                if torch.cuda.is_available():
                    free_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) * 0.85
                    # If model (in bf16) doesn't fit, quantization will be needed
                    needs_quantization = (model_size_gb * 2) > free_vram_gb  # bf16 = 2x safetensors size
                    debug_log(f"  Auto-quant check: model={model_size_gb:.1f}GB, free_vram={free_vram_gb:.1f}GB, needs_quant={needs_quantization}")
            except Exception as e:
                debug_log(f"  Auto-quant check failed: {e}")
                needs_quantization = True  # Assume we might need quantization
        
        if is_mistral_native and not is_bitsandbytes and not (is_auto_quant and needs_quantization):
            msg_log("✓ Detected Mistral native format (consolidated.safetensors)")
            llm_kwargs["config_format"] = "mistral"
            llm_kwargs["load_format"] = "mistral"
            llm_kwargs["tokenizer_mode"] = "mistral"
            debug_log("  Using Mistral native loading: config_format=mistral, load_format=mistral, tokenizer_mode=mistral")
        elif is_mistral_native and (is_bitsandbytes or (is_auto_quant and needs_quantization)):
            # Bitsandbytes requires load_format="bitsandbytes", can't use mistral native format
            warning_log("⚠ Mistral native format detected but quantization needed - using HuggingFace shards")
            warning_log("  Note: Model will load from model-*.safetensors shards instead of consolidated.safetensors")
            # Don't set mistral format options - let it try standard HuggingFace loading
        
        # Disable CUDA graphs on WSL (causes crashes during graph capture)
        # Also disable for Mistral3/Pixtral vision models (CUDA graph crashes with exit code 139)
        if is_wsl:
            llm_kwargs["enforce_eager"] = True
            debug_log("  WSL detected: enabling enforce_eager to disable CUDA graphs")
        elif is_mistral3_vision:
            llm_kwargs["enforce_eager"] = True
            debug_log("  Mistral3/Pixtral vision model: enabling enforce_eager to avoid CUDA graph crashes")
        
        # Set max_model_len (context_size)
        if context_size and context_size > 0:
            llm_kwargs["max_model_len"] = context_size
            debug_log(f"  Context size: {context_size}")
        else:
            llm_kwargs["max_model_len"] = 8192  # Reasonable default
            debug_log("  Context size: 8192 (default)")
        
        # Set GPU memory utilization
        if gpu_memory_utilization and 0 < gpu_memory_utilization <= 1.0:
            llm_kwargs["gpu_memory_utilization"] = gpu_memory_utilization
        else:
            llm_kwargs["gpu_memory_utilization"] = 0.85  # Leave some VRAM for ComfyUI
        debug_log(f"  GPU memory utilization: {llm_kwargs['gpu_memory_utilization']}")
        
        # Handle quantization
        # vLLM supports: bitsandbytes, awq, gptq, squeezellm, fp8
        if quantization and quantization.lower() not in ('none', 'auto', 'fp16', 'bf16', 'fp32'):
            llm_kwargs["quantization"] = quantization.lower()
            msg_log(f"  Quantization: {quantization}")
        
        try:
            # Load model with vLLM
            # Note: We disable v1 engine and multiprocessing via env vars at module load time
            llm = LLM(**llm_kwargs)
            
            # Cache for reuse
            _vllm_model_cache[cache_key] = llm
            msg_log("✓ Model loaded successfully")
            
        except Exception as e:
            error_log(f"Failed to load model: {e}")
            return None
    
    # Store in smart_lm_instance
    if smart_lm_instance is not None:
        smart_lm_instance.vllm_model = llm
        smart_lm_instance.vllm_model_path = model_path
        smart_lm_instance.is_vllm = True
        smart_lm_instance.is_vllm_native = True
        smart_lm_instance.is_gguf = False
    
    return {
        "model": llm,
        "model_path": model_path,
        "model_name": model_name,
        "backend": "vllm_native",
    }


# ==============================================================================
# vLLM GENERATION (Native)
# ==============================================================================

def generate_vllm(
    smart_lm_instance,
    prompt: str,
    image_paths: list = None,
    max_tokens: int = 512,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    seed: int = None,
    llm_mode: str = None,
    instruction_template: str = "",
    repetition_penalty: float = 1.0,
    **kwargs
) -> str:
    # Generate text using native vLLM.
    #
    # Supports both:
    # - Vision models with image_paths
    # - Text-only LLM with llm_mode for few-shot examples
    #
    # Args:
    #     smart_lm_instance: SmartLM instance with loaded vLLM model
    #     prompt: Text prompt
    #     image_paths: List of image paths for vision models (max 16 for video frames)
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Top-p (nucleus) sampling
    #     top_k: Top-k sampling
    #     seed: Random seed for reproducibility
    #     llm_mode: LLM mode key for few-shot examples (text-only models)
    #     instruction_template: Custom instruction template (text-only models)
    #     repetition_penalty: Repetition penalty
    #     **kwargs: Additional arguments
    #
    # Returns:
    #     Generated text string (or tuple (cleaned, raw) for LLM mode)
    if not hasattr(smart_lm_instance, 'vllm_model') or smart_lm_instance.vllm_model is None:
        raise RuntimeError("vLLM model not loaded. Call load_vllm first.")
    
    try:
        from vllm import SamplingParams
    except ImportError as e:
        raise RuntimeError(f"vLLM not available: {e}")
    
    llm = smart_lm_instance.vllm_model
    
    # Build sampling params - only include seed if it's a valid integer
    # vLLM doesn't accept seed=None, it must be omitted or a valid int
    sampling_kwargs = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,  # vLLM supports top_k sampling
    }
    
    # Only add seed if it's a valid integer (not None)
    if seed is not None and isinstance(seed, int):
        sampling_kwargs["seed"] = seed
    
    debug_log(f"SamplingParams: max_tokens={max_tokens}, temp={temperature}, top_p={top_p}, top_k={top_k}, seed={seed}")
    sampling_params = SamplingParams(**sampling_kwargs)
    
    # Handle images for vision models (video frames are passed as images, max 16)
    if image_paths:
        # vLLM 0.12+ vision model support
        # Use chat API which handles image placeholders automatically
        try:
            debug_log(f"Vision generation with {len(image_paths)} image(s)")
            
            # Parse prompt to extract system instruction and user message
            # Format: "system_instruction\n\nuser_message" or just "prompt" for Custom
            system_prompt = None
            user_message = ""
            
            if "\n\n" in prompt:
                parts = prompt.split("\n\n", 1)  # Split only on first \n\n
                system_prompt = parts[0].strip()
                if len(parts) > 1:
                    remaining = parts[1].strip()
                    if remaining.startswith("Additional context:"):
                        user_message = remaining.replace("Additional context:", "").strip()
                    elif remaining:
                        user_message = remaining
                debug_log(f"  Parsed - System: {system_prompt[:50] if system_prompt else 'None'}..., User: {user_message[:50] if user_message else 'empty'}...")
            else:
                # No separator - use entire prompt as user message (Custom task)
                user_message = prompt
            
            # Build content list with images and optional text
            content = []
            for img_path in image_paths:
                debug_log(f"Adding image: {img_path}")
                # vLLM 0.12+ requires file:// URL for local files
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"file://{img_path}"}
                })
            
            # Add user text if provided
            if user_message:
                content.append({
                    "type": "text",
                    "text": user_message
                })
            
            # Build chat message with system role if we have a system prompt
            conversation = []
            if system_prompt:
                conversation.append({"role": "system", "content": system_prompt})
            
            conversation.append({
                "role": "user",
                "content": content
            })
            
            debug_log(f"Using chat API for vision")
            outputs = llm.chat(conversation, sampling_params=sampling_params)
            
        except Exception as e:
            warning_log(f"Vision generation failed: {e}")
            debug_log(f"Vision error details: {type(e).__name__}: {e}")
            # Fall back to text-only
            warning_log("Falling back to text-only generation")
            outputs = llm.generate([prompt], sampling_params=sampling_params)
    elif llm_mode:
        # Text-only LLM with few-shot examples
        from .smartlm_templates import get_llm_few_shot_examples
        LLM_FEW_SHOT_EXAMPLES = get_llm_few_shot_examples()
        
        config = LLM_FEW_SHOT_EXAMPLES.get(llm_mode, LLM_FEW_SHOT_EXAMPLES.get("direct_chat", {}))
        if llm_mode not in LLM_FEW_SHOT_EXAMPLES:
            warning_log(f"Mode '{llm_mode}' not found, using direct_chat")
        
        system_prompt = config.get("system_prompt", "You are a helpful assistant.")
        examples = config.get("examples", [])
        template = instruction_template if instruction_template else config.get("instruction_template", "")
        
        debug_log(f"  LLM mode: system_prompt={system_prompt[:50]}..., {len(examples)} examples")
        
        # Build messages for chat API
        if llm_mode != "direct_chat" and template:
            req = template.replace("{prompt}", prompt) if "{prompt}" in template else f"{template} {prompt}"
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(examples)
            messages.append({"role": "user", "content": req})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        
        debug_log(f"Using chat API for LLM")
        outputs = llm.chat(messages, sampling_params=sampling_params)
    else:
        # Simple text-only generation (no llm_mode)
        debug_log("Text-only generation")
        outputs = llm.generate([prompt], sampling_params=sampling_params)
    
    # Extract generated text
    if outputs and len(outputs) > 0:
        result = outputs[0].outputs[0].text
        
        # Strip thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking, DeepSeek-R1)
        from .common import strip_thinking_tags
        cleaned_result, raw_result = strip_thinking_tags(result)
        
        # For LLM mode, return tuple (cleaned, raw) for compatibility
        if llm_mode:
            return cleaned_result, raw_result
        
        return cleaned_result
    
    return "" if not llm_mode else ("", "")


def unload_vllm(smart_lm_instance=None, model_path: str = None):
    # Unload vLLM model from cache and free GPU memory.
    #
    # Args:
    #     smart_lm_instance: SmartLM instance to clear
    #     model_path: Specific model path to unload, or None to unload all
    global _vllm_model_cache
    import gc
    import torch
    
    models_to_delete = []
    
    if model_path:
        # Find cache keys containing this model path
        for key in list(_vllm_model_cache.keys()):
            if model_path in key:
                models_to_delete.append(key)
    else:
        models_to_delete = list(_vllm_model_cache.keys())
    
    # Delete models from cache
    for key in models_to_delete:
        if key in _vllm_model_cache:
            llm = _vllm_model_cache.pop(key)
            # Try to delete the LLM engine properly
            try:
                del llm
            except:
                pass
            debug_log(f"Unloaded model: {key}")
    
    if not models_to_delete:
        debug_log("No models to unload")
    else:
        debug_log(f"Unloaded {len(models_to_delete)} model(s)")
    
    if smart_lm_instance is not None:
        if hasattr(smart_lm_instance, 'vllm_model') and smart_lm_instance.vllm_model is not None:
            try:
                del smart_lm_instance.vllm_model
            except:
                pass
        smart_lm_instance.vllm_model = None
        smart_lm_instance.vllm_model_path = None
        smart_lm_instance.is_vllm = False
        smart_lm_instance.is_vllm_native = False
    
    # Force garbage collection and CUDA memory cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        msg_log("GPU memory cleared")


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================

__all__ = [
    # Availability
    'VLLM_AVAILABLE',
    'VLLM_VERSION',
    'IS_LINUX',
    'is_vllm_available',
    
    # Loading
    'load_vllm',
    'unload_vllm',
    
    # Generation
    'generate_vllm',
]

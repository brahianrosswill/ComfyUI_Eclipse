from __future__ import annotations

# Smart Loader Plus - Advanced Model Loader with Integrated LoRA Support
#
# Comprehensive model loader supporting multiple model formats and quantization methods:
# - Standard Checkpoints (.safetensors, .ckpt)
# - UNet-only models
# - Nunchaku quantized models (Flux and Qwen-Image with SVDQuant INT4/FP4/FP8)
# - GGUF quantized models (INT4/INT8 quantization)
#
# Features:
# - Automatic model type detection
# - Format-specific loading options (cache, attention, offload)
# - Template system for saving/loading configurations with intelligent field filtering
# - Model-only LoRA support with up to 3 slots
# - Graceful fallback when extensions are not installed
# - Comprehensive VRAM management and cleanup
# - Auto-fill template names for easy updates

from typing import Any
import os
import sys
import json
import time
import gc

import torch  # type: ignore
import comfy  # type: ignore
import comfy.sd  # type: ignore
import comfy.utils  # type: ignore
import comfy.model_sampling  # type: ignore
import folder_paths  # type: ignore
import comfy.model_management as mm  # type: ignore

from ..core import CATEGORY, RESOLUTION_PRESETS, RESOLUTION_MAP
from ..core.common import cleanup_memory_before_load
from ..core.logger import log
from comfy_api.latest import io  # type: ignore

_LOG_PREFIX = "Smart Loader+"
# Import Nunchaku wrapper
from ..core.nunchaku_wrapper import (
    NUNCHAKU_AVAILABLE,
    detect_nunchaku_model,
    load_nunchaku_model,
    get_nunchaku_info
)

# Import GGUF wrapper
from ..core.gguf_wrapper import (
    GGUF_AVAILABLE,
    detect_gguf_model,
    load_gguf_model
)

# Register custom folder path for GGUF diffusion models (if GGUF is available)
if GGUF_AVAILABLE:
    base = folder_paths.folder_names_and_paths.get("diffusion_models_gguf", ([], {}))
    base = base[0] if isinstance(base[0], (list, set, tuple)) else []
    orig, _ = folder_paths.folder_names_and_paths.get("diffusion_models", ([], {}))
    folder_paths.folder_names_and_paths["diffusion_models_gguf"] = (orig or base, {".gguf"})
    
    # Add .gguf extension support to clip and text_encoders folders
    if "clip" in folder_paths.folder_names_and_paths:
        clip_data = folder_paths.folder_names_and_paths["clip"]
        clip_paths, clip_exts = clip_data[0], clip_data[1] if len(clip_data) >= 2 else ([], {})
        if ".gguf" not in clip_exts:
            clip_exts = set(clip_exts) if isinstance(clip_exts, set) else set(clip_exts.keys()) if isinstance(clip_exts, dict) else set()
            clip_exts.add(".gguf")
            folder_paths.folder_names_and_paths["clip"] = (clip_paths, clip_exts)
            # Clear cache to force re-scan with new extension
            if hasattr(folder_paths, 'filename_list_cache') and "clip" in folder_paths.filename_list_cache:
                del folder_paths.filename_list_cache["clip"]
            if hasattr(folder_paths, 'cache_helper'):
                folder_paths.cache_helper.clear()
    
    if "text_encoders" in folder_paths.folder_names_and_paths:
        te_data = folder_paths.folder_names_and_paths["text_encoders"]
        te_paths, te_exts = te_data[0], te_data[1] if len(te_data) >= 2 else ([], {})
        if ".gguf" not in te_exts:
            te_exts = set(te_exts) if isinstance(te_exts, set) else set(te_exts.keys()) if isinstance(te_exts, dict) else set()
            te_exts.add(".gguf")
            folder_paths.folder_names_and_paths["text_encoders"] = (te_paths, te_exts)
            # Clear cache to force re-scan with new extension
            if hasattr(folder_paths, 'filename_list_cache') and "text_encoders" in folder_paths.filename_list_cache:
                del folder_paths.filename_list_cache["text_encoders"]
            if hasattr(folder_paths, 'cache_helper'):
                folder_paths.cache_helper.clear()

# Add .safetensors and .sft extension support to checkpoints and diffusion_models folders
for folder_name in ["checkpoints", "diffusion_models"]:
    if folder_name in folder_paths.folder_names_and_paths:
        folder_data = folder_paths.folder_names_and_paths[folder_name]
        # Handle both 2-tuple and 3-tuple formats
        if len(folder_data) >= 2:
            paths, exts = folder_data[0], folder_data[1]
        else:
            continue
        exts = set(exts) if isinstance(exts, set) else set(exts.keys()) if isinstance(exts, dict) else set()
        # Ensure common extensions are present
        for ext in [".safetensors", ".sft", ".ckpt", ".pt", ".bin"]:
            exts.add(ext)
        folder_paths.folder_names_and_paths[folder_name] = (paths, exts)

MAX_RESOLUTION = 32768
LATENT_CHANNELS = 4
UNET_DOWNSAMPLE = 8

from ..core.loader_templates import (
    TEMPLATE_DIR,
    get_template_dir,
    ensure_template_dir,
    get_template_list,
    load_template,
    get_template_mtime,
)

def _detect_latent_channels_from_vae_obj(vae_obj) -> int:
    # Infer latent channel count from a VAE-like object
    try:
        if hasattr(vae_obj, 'channels') and isinstance(getattr(vae_obj, 'channels'), int):
            return getattr(vae_obj, 'channels')
        if hasattr(vae_obj, 'latent_channels') and isinstance(getattr(vae_obj, 'latent_channels'), int):
            return getattr(vae_obj, 'latent_channels')
        for attr in ('encoder', 'conv_in', 'down_blocks'):
            sub = getattr(vae_obj, attr, None)
            if sub is not None and hasattr(sub, 'weight'):
                return sub.weight.shape[0]
    except Exception:
        pass
    return LATENT_CHANNELS

def is_nunchaku_model(model: Any) -> bool:
    # Check if a model is a Nunchaku model (FLUX or Qwen) by detecting wrapper class
    try:
        model_wrapper = model.model.diffusion_model
        
        if hasattr(model_wrapper, '_orig_mod'):
            actual_wrapper = model_wrapper._orig_mod
            wrapper_class_name = type(actual_wrapper).__name__
            return wrapper_class_name in ('ComfyFluxWrapper', 'ComfyQwenImageWrapper')
        else:
            wrapper_class_name = type(model_wrapper).__name__
            return wrapper_class_name in ('ComfyFluxWrapper', 'ComfyQwenImageWrapper')
    except Exception:
        return False

def apply_loras_to_model(model: Any, clip: Any, lora_params: list) -> tuple:
    # Apply LoRAs to model (standard or Nunchaku).
    #
    # Parameters:
    #     model: The model to apply LoRAs to
    #     clip: The CLIP model (for standard models only)
    #     lora_params: List of tuples (lora_name, model_weight)
    #
    # Returns:
    #     (modified_model, modified_clip)
    if not lora_params:
        return (model, clip)
    
    # Check if this is a Nunchaku model
    if is_nunchaku_model(model):
        log.msg("LoRA", "Detected Nunchaku model, applying LoRAs via wrapper")
        return _apply_loras_nunchaku(model, clip, lora_params)
    else:
        log.msg("LoRA", "Applying LoRAs to standard model")
        return _apply_loras_standard(model, clip, lora_params)

def _apply_loras_standard(model: Any, clip: Any, lora_params: list) -> tuple:
    # Apply LoRAs to standard (non-Nunchaku) models using ComfyUI's loader
    model_lora = model
    clip_lora = clip
    
    for lora_name, model_weight in lora_params:
        lora_path = folder_paths.get_full_path("loras", lora_name)
        lora = comfy.utils.load_torch_file(lora_path, safe_load=True)
        
        # Use model_weight for both model and clip (model-only mode)
        model_lora, clip_lora = comfy.sd.load_lora_for_models(
            model_lora, clip_lora, lora, model_weight, model_weight
        )
        log.msg("LoRA", f"Applied {lora_name} with weight {model_weight}")
    
    return (model_lora, clip_lora)

def _apply_loras_nunchaku(model: Any, clip: Any, lora_params: list) -> tuple:
    # Apply LoRAs to Nunchaku models (FLUX or Qwen) via wrapper
    try:
        from ..core.nunchaku_wrapper import ComfyFluxWrapper, ComfyQwenImageWrapper
    except ImportError as e:
        log.warning("LoRA", f"Nunchaku wrappers not available for LoRA application: {e}")
        log.msg("LoRA", "Returning model unchanged")
        return (model, clip)
    
    # Get the model wrapper
    model_wrapper = model.model.diffusion_model
    
    # Detect wrapper type
    if hasattr(model_wrapper, '_orig_mod'):
        actual_wrapper = model_wrapper._orig_mod
        wrapper_class_name = type(actual_wrapper).__name__
    else:
        actual_wrapper = model_wrapper
        wrapper_class_name = type(model_wrapper).__name__
    
    is_qwen = (wrapper_class_name == 'ComfyQwenImageWrapper')
    is_flux = (wrapper_class_name == 'ComfyFluxWrapper')
    
    if not (is_qwen or is_flux):
        log.warning("LoRA", f"Unknown wrapper type: {wrapper_class_name}")
        return (model, clip)
    
    # For Qwen models, simply update the loras list on the wrapper
    if is_qwen:
        log.msg("LoRA", "Applying LoRAs to Qwen model via ComfyQwenImageWrapper")
        
        # Get the wrapper (handle OptimizedModule case)
        if hasattr(model_wrapper, '_orig_mod'):
            wrapper = model_wrapper._orig_mod
        else:
            wrapper = model_wrapper
        
        # Clear existing LoRAs and add new ones
        wrapper.loras = []
        for lora_name, model_weight in lora_params:
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
            wrapper.loras.append((lora_path, model_weight))
            log.msg("LoRA", f"Applied Qwen LoRA {lora_name} with weight {model_weight}")
        
        return (model, clip)
    
    # For Flux models, use the original implementation with ComfyFluxWrapper
    log.msg("LoRA", "Applying LoRAs to Flux model via ComfyFluxWrapper")
    
    try:
        from nunchaku.lora.flux import to_diffusers  # type: ignore
    except ImportError as e:
        log.warning("LoRA", f"nunchaku.lora.flux not available: {e}")
        log.msg("LoRA", "Returning model unchanged")
        return (model, clip)
    
    # Handle OptimizedModule case
    if hasattr(model_wrapper, '_orig_mod'):
        transformer = model_wrapper._orig_mod.model
        
        # Create a new model structure
        ret_model = model.__class__(
            model.model, model.load_device, model.offload_device,
            model.size, model.weight_inplace_update
        )
        ret_model.model = model.model
        
        # Create a new ComfyFluxWrapper
        original_wrapper = model_wrapper._orig_mod
        ret_model_wrapper = ComfyFluxWrapper(
            transformer,
            config=original_wrapper.config,
            pulid_pipeline=original_wrapper.pulid_pipeline,
            customized_forward=original_wrapper.customized_forward,
            forward_kwargs=original_wrapper.forward_kwargs,
            ctx_for_copy=getattr(original_wrapper, 'ctx_for_copy', {}),
        )
        
        # Copy internal state
        ret_model_wrapper._prev_timestep = original_wrapper._prev_timestep
        ret_model_wrapper._cache_context = original_wrapper._cache_context
        if hasattr(original_wrapper, '_original_time_text_embed'):
            ret_model_wrapper._original_time_text_embed = original_wrapper._original_time_text_embed
        
        ret_model.model.diffusion_model = ret_model_wrapper
    else:
        # Non-OptimizedModule case
        transformer = model_wrapper.model
        
        ret_model = model.__class__(
            model.model, model.load_device, model.offload_device,
            model.size, model.weight_inplace_update
        )
        
        original_wrapper = model_wrapper
        ret_model_wrapper = ComfyFluxWrapper(
            transformer,
            config=original_wrapper.config,
            pulid_pipeline=original_wrapper.pulid_pipeline,
            customized_forward=original_wrapper.customized_forward,
            forward_kwargs=original_wrapper.forward_kwargs,
            ctx_for_copy=getattr(original_wrapper, 'ctx_for_copy', {}),
        )
        
        # Copy internal state
        ret_model_wrapper._prev_timestep = original_wrapper._prev_timestep
        ret_model_wrapper._cache_context = original_wrapper._cache_context
        if hasattr(original_wrapper, '_original_time_text_embed'):
            ret_model_wrapper._original_time_text_embed = original_wrapper._original_time_text_embed
        
        ret_model.model.diffusion_model = ret_model_wrapper
    
    # Restore transformer to original wrapper
    if hasattr(model_wrapper, '_orig_mod'):
        model_wrapper._orig_mod.model = transformer
    else:
        model_wrapper.model = transformer
    
    ret_model_wrapper.model = transformer
    
    # Clear existing LoRA list
    ret_model_wrapper.loras = []
    
    # Track max input channels
    max_in_channels = ret_model.model.model_config.unet_config["in_channels"]
    
    # Add all LoRAs
    for lora_name, model_weight in lora_params:
        lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
        ret_model_wrapper.loras.append((lora_path, model_weight))
        log.msg("LoRA", f"Applied Nunchaku LoRA {lora_name} with weight {model_weight}")
        
        # Check input channels
        sd = to_diffusers(lora_path)
        if "transformer.x_embedder.lora_A.weight" in sd:
            new_in_channels = sd["transformer.x_embedder.lora_A.weight"].shape[1]
            assert new_in_channels % 4 == 0, f"Invalid LoRA input channels: {new_in_channels}"
            new_in_channels = new_in_channels // 4
            max_in_channels = max(max_in_channels, new_in_channels)
    
    # Update input channels if needed
    if max_in_channels > ret_model.model.model_config.unet_config["in_channels"]:
        ret_model.model.model_config.unet_config["in_channels"] = max_in_channels
    
    return (ret_model, clip)

def apply_model_sampling(model, sampling_method: str, shift: float, base_shift: float = 0.5, 
                         width: int = 1024, height: int = 1024, original_timesteps: int = 50,
                         zsnr: bool = False, sampling_subtype: str = "eps", 
                         sigma_max: float = 120.0, sigma_min: float = 0.002):
    # Apply model sampling configuration based on method.
    #
    # Parameters:
    #     model: The model to patch
    #     sampling_method: Sampling method (SD3, AuraFlow, Flux, Stable Cascade, LCM, ContinuousEDM, ContinuousV, LTXV, or None)
    #     shift: Universal shift parameter (used as shift for SD3/AuraFlow/Stable Cascade, max_shift for Flux/LTXV)
    #     base_shift: Base shift for Flux/LTXV sampling (default: 0.5)
    #     width: Width for Flux sampling shift calculation (default: 1024)
    #     height: Height for Flux sampling shift calculation (default: 1024)
    #     original_timesteps: Original timesteps for LCM sampling (default: 50)
    #     zsnr: Enable zero-terminal SNR for LCM sampling (default: False)
    #     sampling_subtype: Subtype for ContinuousEDM (eps, v_prediction, edm, edm_playground_v2.5, cosmos_rflow)
    #     sigma_max: Maximum sigma for ContinuousEDM/V (default: 120.0)
    #     sigma_min: Minimum sigma for ContinuousEDM/V (default: 0.002)
    #
    # Returns:
    #     Patched model or original model if method is "None"
    if sampling_method == "None" or not sampling_method:
        return model
    
    if sampling_method == "SD3":
        return _apply_sd3_sampling(model, shift=shift, multiplier=1000.0)
    elif sampling_method == "AuraFlow":
        return _apply_auraflow_sampling(model, shift=shift, multiplier=1.0)
    elif sampling_method == "Flux":
        return _apply_flux_sampling(model, max_shift=shift, base_shift=base_shift, width=width, height=height)
    elif sampling_method == "Stable Cascade":
        return _apply_stable_cascade_sampling(model, shift=shift)
    elif sampling_method == "LCM":
        return _apply_lcm_sampling(model, original_timesteps=original_timesteps, zsnr=zsnr)
    elif sampling_method == "ContinuousEDM":
        return _apply_continuous_edm_sampling(model, sampling_subtype=sampling_subtype, sigma_max=sigma_max, sigma_min=sigma_min)
    elif sampling_method == "ContinuousV":
        return _apply_continuous_v_sampling(model, sigma_max=sigma_max, sigma_min=sigma_min)
    elif sampling_method == "LTXV":
        return _apply_ltxv_sampling(model, max_shift=shift, base_shift=base_shift)
    else:
        log.warning("Model Sampling", f"Unknown sampling method '{sampling_method}', skipping")
        return model

def _apply_sd3_sampling(model, shift: float, multiplier: float = 1000.0):
    # Apply SD3 sampling (ModelSamplingDiscreteFlow + CONST)
    m = model.clone()
    
    sampling_base = comfy.model_sampling.ModelSamplingDiscreteFlow
    sampling_type = comfy.model_sampling.CONST
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(shift=shift, multiplier=multiplier)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied SD3 sampling: shift={shift}, multiplier={multiplier}")
    return m

def _apply_auraflow_sampling(model, shift: float, multiplier: float = 1.0):
    # Apply AuraFlow sampling (ModelSamplingDiscreteFlow + CONST with multiplier=1.0)
    m = model.clone()
    
    sampling_base = comfy.model_sampling.ModelSamplingDiscreteFlow
    sampling_type = comfy.model_sampling.CONST
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(shift=shift, multiplier=multiplier)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied AuraFlow sampling: shift={shift}, multiplier={multiplier}")
    return m

def _apply_flux_sampling(model, max_shift: float, base_shift: float, width: int, height: int):
    # Apply Flux sampling (ModelSamplingFlux + CONST with calculated shift)
    m = model.clone()
    
    # Calculate shift using linear interpolation formula based on image dimensions
    # Formula: shift = ((width * height / 1024) * slope) + intercept
    # where slope = (max_shift - base_shift) / (4096 - 256)
    # and intercept = base_shift - slope * 256
    x1 = 256
    x2 = 4096
    mm = (max_shift - base_shift) / (x2 - x1)
    b = base_shift - mm * x1
    shift = (width * height / (8 * 8 * 2 * 2)) * mm + b
    
    sampling_base = comfy.model_sampling.ModelSamplingFlux
    sampling_type = comfy.model_sampling.CONST
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(shift=shift)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied Flux sampling: max_shift={max_shift}, base_shift={base_shift}, width={width}, height={height}, calculated_shift={shift:.4f}")
    return m

def _apply_stable_cascade_sampling(model, shift: float):
    # Apply Stable Cascade sampling (StableCascadeSampling + EPS)
    m = model.clone()
    
    sampling_base = comfy.model_sampling.StableCascadeSampling
    sampling_type = comfy.model_sampling.EPS
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(shift=shift)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied Stable Cascade sampling: shift={shift}")
    return m

def _apply_lcm_sampling(model, original_timesteps: int = 50, zsnr: bool = False):
    # Apply LCM sampling (ModelSamplingDiscreteDistilled + LCM)
    m = model.clone()
    
    # Define LCM sampling type
    class LCM(comfy.model_sampling.EPS):
        def calculate_denoised(self, sigma, model_output, model_input):
            timestep = self.timestep(sigma).view(sigma.shape[:1] + (1,) * (model_output.ndim - 1))
            sigma = sigma.view(sigma.shape[:1] + (1,) * (model_output.ndim - 1))
            x0 = model_input - model_output * sigma

            sigma_data = 0.5
            scaled_timestep = timestep * 10.0  # timestep_scaling

            c_skip = sigma_data**2 / (scaled_timestep**2 + sigma_data**2)
            c_out = scaled_timestep / (scaled_timestep**2 + sigma_data**2) ** 0.5

            return c_out * x0 + c_skip * model_input
    
    # Define distilled sampling base
    class ModelSamplingDiscreteDistilled(comfy.model_sampling.ModelSamplingDiscrete):
        def __init__(self, model_config=None):
            super().__init__(model_config, zsnr=zsnr)
            self.original_timesteps = original_timesteps
            self.skip_steps = self.num_timesteps // self.original_timesteps

            sigmas_valid = torch.zeros((self.original_timesteps), dtype=torch.float32)
            for x in range(self.original_timesteps):
                sigmas_valid[self.original_timesteps - 1 - x] = self.sigmas[self.num_timesteps - 1 - x * self.skip_steps]

            self.set_sigmas(sigmas_valid)

        def timestep(self, sigma):
            log_sigma = sigma.log()
            dists = log_sigma.to(self.log_sigmas.device) - self.log_sigmas[:, None]
            return (dists.abs().argmin(dim=0).view(sigma.shape) * self.skip_steps + (self.skip_steps - 1)).to(sigma.device)

        def sigma(self, timestep):
            t = torch.clamp(((timestep.float().to(self.log_sigmas.device) - (self.skip_steps - 1)) / self.skip_steps).float(), min=0, max=(len(self.sigmas) - 1))
            low_idx = t.floor().long()
            high_idx = t.ceil().long()
            w = t.frac()
            log_sigma = (1 - w) * self.log_sigmas[low_idx] + w * self.log_sigmas[high_idx]
            return log_sigma.exp().to(timestep.device)
    
    sampling_base = ModelSamplingDiscreteDistilled
    sampling_type = LCM
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied LCM sampling: original_timesteps={original_timesteps}, zsnr={zsnr}")
    return m

def _apply_continuous_edm_sampling(model, sampling_subtype: str = "eps", sigma_max: float = 120.0, sigma_min: float = 0.002):
    # Apply ContinuousEDM sampling
    m = model.clone()
    
    sampling_base = comfy.model_sampling.ModelSamplingContinuousEDM
    latent_format = None
    sigma_data = 1.0
    
    if sampling_subtype == "eps":
        sampling_type = comfy.model_sampling.EPS
    elif sampling_subtype == "edm" or sampling_subtype == "edm_playground_v2.5":
        sampling_type = comfy.model_sampling.EDM
        sigma_data = 0.5
        if sampling_subtype == "edm_playground_v2.5":
            latent_format = comfy.latent_formats.SDXL_Playground_2_5()
    elif sampling_subtype == "v_prediction":
        sampling_type = comfy.model_sampling.V_PREDICTION
    elif sampling_subtype == "cosmos_rflow":
        sampling_type = comfy.model_sampling.COSMOS_RFLOW
        sampling_base = comfy.model_sampling.ModelSamplingCosmosRFlow
    else:
        log.warning("Model Sampling", f"Unknown ContinuousEDM subtype '{sampling_subtype}', using eps")
        sampling_type = comfy.model_sampling.EPS
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(sigma_min, sigma_max, sigma_data)
    m.add_object_patch("model_sampling", model_sampling)
    if latent_format is not None:
        m.add_object_patch("latent_format", latent_format)
    
    log.msg("Model Sampling", f"Applied ContinuousEDM sampling: subtype={sampling_subtype}, sigma_max={sigma_max}, sigma_min={sigma_min}, sigma_data={sigma_data}")
    return m

def _apply_continuous_v_sampling(model, sigma_max: float = 500.0, sigma_min: float = 0.03):
    # Apply ContinuousV sampling (v_prediction only)
    m = model.clone()
    
    sampling_type = comfy.model_sampling.V_PREDICTION
    sigma_data = 1.0
    
    class ModelSamplingAdvanced(comfy.model_sampling.ModelSamplingContinuousV, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(sigma_min, sigma_max, sigma_data)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied ContinuousV sampling: sigma_max={sigma_max}, sigma_min={sigma_min}")
    return m

def _apply_ltxv_sampling(model, max_shift: float = 2.05, base_shift: float = 0.95):
    # Apply LTXV sampling (for video models, uses token-based shift calculation)
    m = model.clone()
    
    # LTXV uses token count instead of width/height
    # Default to 4096 tokens if we can't determine from latent
    tokens = 4096
    
    # Calculate shift using linear interpolation formula based on token count
    x1 = 1024
    x2 = 4096
    mm = (max_shift - base_shift) / (x2 - x1)
    b = base_shift - mm * x1
    shift = tokens * mm + b
    
    sampling_base = comfy.model_sampling.ModelSamplingFlux
    sampling_type = comfy.model_sampling.CONST
    
    class ModelSamplingAdvanced(sampling_base, sampling_type):  # type: ignore[misc,valid-type]
        pass
    
    model_sampling = ModelSamplingAdvanced(model.model.model_config)
    model_sampling.set_parameters(shift=shift)
    m.add_object_patch("model_sampling", model_sampling)
    
    log.msg("Model Sampling", f"Applied LTXV sampling: max_shift={max_shift}, base_shift={base_shift}, tokens={tokens}, calculated_shift={shift:.4f}")
    return m

_support_messages_printed = False

def _print_support_messages():
    global _support_messages_printed
    if not _support_messages_printed:
        _support_messages_printed = True
        
        nunchaku_info = get_nunchaku_info()
        if nunchaku_info['available']:
            version = nunchaku_info['version'] if nunchaku_info['version'] else 'installed'
            log.debug(_LOG_PREFIX, f"✓ Nunchaku support: {version}")
        
        if GGUF_AVAILABLE:
            log.debug(_LOG_PREFIX, "✓ GGUF support available")

_print_support_messages()

class RvLoader_SmartLoader_Plus(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        nunchaku_info = get_nunchaku_info()
        weight_dtype_options = ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"]
        
        # Get available LoRAs
        loras = ["None"] + folder_paths.get_filename_list("loras")
        
        # Get available CLIP files from both clip and text_encoders folders
        clip_files = []
        # Get from clip folder
        clip_files.extend(folder_paths.get_filename_list("clip"))
        # Get from text_encoders folder if it exists
        if "text_encoders" in folder_paths.folder_names_and_paths:
            clip_files.extend(folder_paths.get_filename_list("text_encoders"))
        clips = ["None"] + clip_files
        
        return io.Schema(
            node_id="Smart Loader Plus [Eclipse]",
            display_name="Smart Loader Plus",
            category=CATEGORY.MAIN.value + CATEGORY.LOADER.value,
            inputs=[
                io.Combo.Input("template_action", options=["None", "Load", "Save"], default="None", tooltip="Load/Save configuration templates"),
                io.Combo.Input("template_name", options=get_template_list(), default="None", tooltip="Select template to load/delete"),
                io.String.Input("new_template_name", default="", tooltip="Name for new template (when saving)"),
                io.Combo.Input("model_type", options=["Standard Checkpoint", "UNet Model", "Nunchaku Flux", "Nunchaku Qwen", "Nunchaku ZImage", "GGUF Model"], default="Standard Checkpoint", tooltip="Select model type"),
                io.Combo.Input("ckpt_name", options=["None"] + folder_paths.get_filename_list("checkpoints"), default="None", tooltip="Select checkpoint file"),
                io.Combo.Input("unet_name", options=["None"] + folder_paths.get_filename_list("diffusion_models"), default="None", tooltip="Select UNet diffusion model"),
                io.Combo.Input("nunchaku_name", options=["None"] + folder_paths.get_filename_list("diffusion_models"), default="None", tooltip="Select Nunchaku Flux model"),
                io.Combo.Input("qwen_name", options=["None"] + folder_paths.get_filename_list("diffusion_models"), default="None", tooltip="Select Nunchaku Qwen model"),
                io.Combo.Input("zimage_name", options=["None"] + folder_paths.get_filename_list("diffusion_models"), default="None", tooltip="Select Nunchaku ZImage model"),
                io.Combo.Input("gguf_name", options=["None"] + (folder_paths.get_filename_list("diffusion_models_gguf") if "diffusion_models_gguf" in folder_paths.folder_names_and_paths else []), default="None", tooltip="Select GGUF model"),
                io.Combo.Input("weight_dtype", options=weight_dtype_options, default="default", tooltip="Weight dtype for UNet model"),
                io.Combo.Input("data_type", options=["bfloat16", "float16"], default="bfloat16", tooltip="Model data type for Nunchaku"),
                io.Float.Input("cache_threshold", default=0.0, min=0.0, max=1.0, step=0.001, tooltip="Cache threshold for Nunchaku"),
                io.Combo.Input("attention", options=["flash-attention2", "nunchaku-fp16"], default="flash-attention2", tooltip="Attention implementation"),
                io.Combo.Input("i2f_mode", options=["enabled", "always"], default="enabled", tooltip="GEMM implementation"),
                io.Combo.Input("cpu_offload", options=["auto", "enable", "disable"], default="auto", tooltip="CPU offload"),
                io.Int.Input("num_blocks_on_gpu", default=30, min=1, max=60, step=1, tooltip="Blocks on GPU (Nunchaku Qwen)"),
                io.Combo.Input("use_pin_memory", options=["enable", "disable"], default="enable", tooltip="Use pinned memory"),
                io.Combo.Input("gguf_dequant_dtype", options=["default", "target", "float32", "float16", "bfloat16"], default="default", tooltip="Dequantization dtype"),
                io.Combo.Input("gguf_patch_dtype", options=["default", "target", "float32", "float16", "bfloat16"], default="default", tooltip="LoRA patch dtype"),
                io.Boolean.Input("gguf_patch_on_device", default=False, label_on="yes", label_off="no", tooltip="Apply patches on GPU"),
                io.Boolean.Input("configure_clip", default=True, label_on="yes", label_off="no", tooltip="Enable CLIP configuration"),
                io.Boolean.Input("configure_vae", default=True, label_on="yes", label_off="no", tooltip="Enable VAE configuration"),
                io.Boolean.Input("configure_latent", default=True, label_on="yes", label_off="no", tooltip="Enable latent configuration"),
                io.Boolean.Input("configure_sampler", default=True, label_on="yes", label_off="no", tooltip="Enable sampler configuration"),
                io.Boolean.Input("configure_model_only_lora", default=False, label_on="yes", label_off="no", tooltip="Enable model-only LoRA configuration"),
                io.Boolean.Input("configure_model_sampling", default=False, label_on="yes", label_off="no", tooltip="Enable advanced model sampling configuration"),
                io.Combo.Input("sampling_method", options=["None", "SD3", "AuraFlow", "Flux", "Stable Cascade", "LCM", "ContinuousEDM", "ContinuousV", "LTXV"], default="None", tooltip="Sampling method: SD3 (shift=3.0), AuraFlow (shift=1.73), Flux (max_shift=1.15), Stable Cascade (shift=2.0), LCM (distilled), ContinuousEDM/V (continuous sampling), LTXV (video)"),
                io.Combo.Input("sampling_subtype", options=["eps", "v_prediction", "edm", "edm_playground_v2.5", "cosmos_rflow"], default="eps", tooltip="Subtype for ContinuousEDM sampling (eps, v_prediction, edm, edm_playground_v2.5, cosmos_rflow)"),
                io.Float.Input("shift", default=3.0, min=0.0, max=100.0, step=0.01, tooltip="Universal shift parameter (SD3: 3.0, AuraFlow: 1.73, Flux max_shift: 1.15, Stable Cascade: 2.0)"),
                io.Float.Input("base_shift", default=0.5, min=0.0, max=100.0, step=0.01, tooltip="Base shift for Flux/LTXV sampling (default: 0.5)"),
                io.Int.Input("sampling_width", default=1024, min=16, max=MAX_RESOLUTION, step=8, tooltip="Width for Flux sampling shift calculation"),
                io.Int.Input("sampling_height", default=1024, min=16, max=MAX_RESOLUTION, step=8, tooltip="Height for Flux sampling shift calculation"),
                io.Int.Input("original_timesteps", default=50, min=1, max=1000, step=1, tooltip="Original timesteps for LCM sampling (default: 50)"),
                io.Boolean.Input("zsnr", default=False, label_on="yes", label_off="no", tooltip="Enable zero-terminal SNR for LCM sampling"),
                io.Float.Input("sigma_max", default=120.0, min=0.0, max=1000.0, step=0.001, tooltip="Maximum sigma for ContinuousEDM/V sampling (EDM: 120.0, V: 500.0)"),
                io.Float.Input("sigma_min", default=0.002, min=0.0, max=1000.0, step=0.001, tooltip="Minimum sigma for ContinuousEDM/V sampling (EDM: 0.002, V: 0.03)"),
                io.Combo.Input("clip_source", options=["Baked", "External"], default="Baked", tooltip="CLIP source"),
                io.Combo.Input("clip_count", options=["1", "2", "3", "4"], default="1", tooltip="Number of CLIP models"),
                io.Combo.Input("clip_name1", options=clips, default="None", tooltip="Primary CLIP model"),
                io.Combo.Input("clip_name2", options=clips, default="None", tooltip="Secondary CLIP model"),
                io.Combo.Input("clip_name3", options=clips, default="None", tooltip="Third CLIP model"),
                io.Combo.Input("clip_name4", options=clips, default="None", tooltip="Fourth CLIP model"),
                io.Combo.Input("clip_type", options=["flux", "flux2", "sd3", "sdxl", "stable_cascade", "stable_audio", "hunyuan_dit", "mochi", "ltxv", "hunyuan_video", "pixart", "cosmos", "lumina2", "wan", "hidream", "chroma", "ace", "omnigen2", "qwen_image", "hunyuan_image", "hunyuan_video_15", "ovis", "kandinsky5", "kandinsky5_image", "newbie"], default="flux", tooltip="CLIP architecture type"),
                io.Boolean.Input("enable_clip_layer", default=True, label_on="yes", label_off="no", tooltip="Trim CLIP to specific layer"),
                io.Int.Input("stop_at_clip_layer", default=-2, min=-24, max=-1, step=1, tooltip="CLIP layer to stop at"),
                io.Combo.Input("vae_source", options=["Baked", "External"], default="Baked", tooltip="VAE source"),
                io.Combo.Input("vae_name", options=["None"] + folder_paths.get_filename_list("vae"), default="None", tooltip="External VAE file"),
                io.Combo.Input("resolution", options=RESOLUTION_PRESETS, default="1024x1024 (1:1)", tooltip="Preset resolution or Custom"),
                io.Int.Input("width", default=1024, min=16, max=MAX_RESOLUTION, step=8, tooltip="Custom width"),
                io.Int.Input("height", default=1024, min=16, max=MAX_RESOLUTION, step=8, tooltip="Custom height"),
                io.Combo.Input("lora_count", options=["1", "2", "3"], default="1", tooltip="Number of LoRA slots to configure"),
                io.Boolean.Input("lora_switch_1", default=False, label_on="ON", label_off="OFF", tooltip="Enable LoRA 1"),
                io.Combo.Input("lora_name_1", options=loras, default="None", tooltip="LoRA 1 file"),
                io.Float.Input("lora_weight_1", default=1.0, min=-10.0, max=10.0, step=0.01, tooltip="LoRA 1 model weight"),
                io.Boolean.Input("lora_switch_2", default=False, label_on="ON", label_off="OFF", tooltip="Enable LoRA 2"),
                io.Combo.Input("lora_name_2", options=loras, default="None", tooltip="LoRA 2 file"),
                io.Float.Input("lora_weight_2", default=1.0, min=-10.0, max=10.0, step=0.01, tooltip="LoRA 2 model weight"),
                io.Boolean.Input("lora_switch_3", default=False, label_on="ON", label_off="OFF", tooltip="Enable LoRA 3"),
                io.Combo.Input("lora_name_3", options=loras, default="None", tooltip="LoRA 3 file"),
                io.Float.Input("lora_weight_3", default=1.0, min=-10.0, max=10.0, step=0.01, tooltip="LoRA 3 model weight"),
                io.Combo.Input("sampler_name", options=comfy.samplers.KSampler.SAMPLERS, default="euler", tooltip="Sampling algorithm"),
                io.Combo.Input("scheduler", options=comfy.samplers.KSampler.SCHEDULERS, default="normal", tooltip="Scheduler"),
                io.Int.Input("steps", default=20, min=1, max=10000, tooltip="Sampling steps"),
                io.Float.Input("cfg", default=8.0, min=0.0, max=100.0, step=0.1, round=0.01, tooltip="CFG scale"),
                io.Float.Input("flux_guidance", default=3.5, min=0.0, max=100.0, step=0.1, tooltip="Flux guidance scale"),
                io.Int.Input("batch_size", default=1, min=1, max=4096, tooltip="Batch size"),
                io.Combo.Input("model_device", options=["auto", "cpu"], default="auto", tooltip="Device for model loading (auto: ComfyUI automatic, cpu: force CPU)"),
                io.Combo.Input("clip_device", options=["auto", "cpu"], default="auto", tooltip="Device for CLIP loading (auto: ComfyUI automatic, cpu: force CPU)"),
                io.Combo.Input("vae_device", options=["auto", "cpu"], default="auto", tooltip="Device for VAE loading (auto: ComfyUI automatic, cpu: force CPU)"),
                io.Boolean.Input("memory_cleanup", default=True, label_on="yes", label_off="no", tooltip="Perform memory cleanup before loading"),
            ],
            outputs=[
                io.Custom("pipe").Output("pipe"),
            ],
        )
    
    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        mtime = get_template_mtime()
        return str(mtime) if mtime else str(time.time())

    @classmethod
    def execute(cls, **kwargs):
        # Extract all parameters
        template_action = kwargs.get('template_action', 'None')
        template_name = kwargs.get('template_name', 'None')
        new_template_name = kwargs.get('new_template_name', '')
        
        model_type = kwargs.get('model_type', 'Standard Checkpoint')
        ckpt_name = kwargs.get('ckpt_name', 'None')
        unet_name = kwargs.get('unet_name', 'None')
        nunchaku_name = kwargs.get('nunchaku_name', 'None')
        qwen_name = kwargs.get('qwen_name', 'None')
        zimage_name = kwargs.get('zimage_name', 'None')
        gguf_name = kwargs.get('gguf_name', 'None')
        weight_dtype = kwargs.get('weight_dtype', 'default')
        
        data_type = kwargs.get('data_type', 'bfloat16')
        cache_threshold = kwargs.get('cache_threshold', 0.0)
        attention = kwargs.get('attention', 'flash-attention2')
        i2f_mode = kwargs.get('i2f_mode', 'enabled')
        cpu_offload = kwargs.get('cpu_offload', 'auto')
        num_blocks_on_gpu = kwargs.get('num_blocks_on_gpu', 30)
        use_pin_memory = kwargs.get('use_pin_memory', 'enable')
        
        gguf_dequant_dtype = kwargs.get('gguf_dequant_dtype', 'default')
        gguf_patch_dtype = kwargs.get('gguf_patch_dtype', 'default')
        gguf_patch_on_device = kwargs.get('gguf_patch_on_device', False)
        
        model_device = kwargs.get('model_device', 'auto')
        clip_device = kwargs.get('clip_device', 'auto')
        vae_device = kwargs.get('vae_device', 'auto')
        
        # Resolve device selections
        resolved_model_device = mm.get_torch_device() if model_device == "auto" else torch.device("cpu")
        resolved_clip_device = mm.text_encoder_device() if clip_device == "auto" else torch.device("cpu")
        resolved_vae_device = mm.vae_device() if vae_device == "auto" else torch.device("cpu")
        
        configure_clip = kwargs.get('configure_clip', True)
        configure_vae = kwargs.get('configure_vae', True)
        configure_latent = kwargs.get('configure_latent', True)
        configure_sampler = kwargs.get('configure_sampler', True)
        configure_model_only_lora = kwargs.get('configure_model_only_lora', False)
        configure_model_sampling = kwargs.get('configure_model_sampling', False)
        
        sampling_method = kwargs.get('sampling_method', 'None')
        sampling_subtype = kwargs.get('sampling_subtype', 'eps')
        shift = kwargs.get('shift', 3.0)
        base_shift = kwargs.get('base_shift', 0.5)
        sampling_width = kwargs.get('sampling_width', 1024)
        sampling_height = kwargs.get('sampling_height', 1024)
        original_timesteps = kwargs.get('original_timesteps', 50)
        zsnr = kwargs.get('zsnr', False)
        sigma_max = kwargs.get('sigma_max', 120.0)
        sigma_min = kwargs.get('sigma_min', 0.002)
        
        clip_source = kwargs.get('clip_source', 'Baked')
        clip_count = kwargs.get('clip_count', '1')
        clip_name1 = kwargs.get('clip_name1', 'None')
        clip_name2 = kwargs.get('clip_name2', 'None')
        clip_name3 = kwargs.get('clip_name3', 'None')
        clip_name4 = kwargs.get('clip_name4', 'None')
        clip_type = kwargs.get('clip_type', 'flux')
        enable_clip_layer = kwargs.get('enable_clip_layer', True)
        stop_at_clip_layer = kwargs.get('stop_at_clip_layer', -2)
        
        vae_source = kwargs.get('vae_source', 'Baked')
        vae_name = kwargs.get('vae_name', 'None')
        
        resolution = kwargs.get('resolution', '1024x1024 (1:1)')
        width = kwargs.get('width', 1024)
        height = kwargs.get('height', 1024)
        batch_size = kwargs.get('batch_size', 1)
        
        lora_count = kwargs.get('lora_count', '1')
        
        sampler_name = kwargs.get('sampler_name', 'euler')
        scheduler = kwargs.get('scheduler', 'normal')
        steps = kwargs.get('steps', 20)
        cfg = kwargs.get('cfg', 8.0)
        flux_guidance = kwargs.get('flux_guidance', 3.5)
        
        memory_cleanup = kwargs.get('memory_cleanup', True)
        
        # Normalize inputs
        configure_clip = bool(configure_clip)
        configure_vae = bool(configure_vae)
        configure_latent = bool(configure_latent)
        configure_sampler = bool(configure_sampler)
        configure_model_only_lora = bool(configure_model_only_lora)
        configure_model_sampling = bool(configure_model_sampling)
        enable_clip_layer = bool(enable_clip_layer)
        clip_count_int = int(clip_count)
        lora_count_int = int(lora_count)
        
        is_standard = (model_type == "Standard Checkpoint")
        is_unet = (model_type == "UNet Model")
        is_nunchaku = (model_type == "Nunchaku Flux")
        is_qwen = (model_type == "Nunchaku Qwen")
        is_zimage = (model_type == "Nunchaku ZImage")
        is_gguf = (model_type == "GGUF Model")
        use_baked_clip = (clip_source == "Baked")
        use_baked_vae = (vae_source == "Baked")
        
        loaded_model = None
        loaded_clip = None
        loaded_vae = None
        ckpt_parts = None
        checkpoint_name = ""
        
        safe_exts = {".safetensors", ".sft"}
        
        # ============================================================
        # STEP 0: Pre-Load Memory Cleanup
        # ============================================================
        
        if memory_cleanup:
            cleanup_memory_before_load()
        
        # ============================================================
        # STEP 1: Load Model (Standard Checkpoint, UNet, Nunchaku Flux, Nunchaku Qwen, Nunchaku ZImage, or GGUF)
        # ============================================================
        
        if is_standard:
            # Load standard checkpoint
            if ckpt_name in (None, '', 'None'):
                raise ValueError("Please select a checkpoint file")
            
            ckpt_path = folder_paths.get_full_path("checkpoints", ckpt_name)
            if not ckpt_path or not os.path.isfile(ckpt_path):
                raise FileNotFoundError(f"Checkpoint not found: {ckpt_name}")
            
            _, ext = os.path.splitext(ckpt_path.lower())
            if ext not in safe_exts:
                log.warning(_LOG_PREFIX, f"'{ckpt_name}' uses extension '{ext}'. Consider .safetensors for safety.")
            
            if not os.access(ckpt_path, os.R_OK):
                raise RuntimeError(f"Checkpoint file not readable: {ckpt_path}")
            
            # Load checkpoint with conditional outputs
            # Temporarily override device settings if forcing CPU
            original_unet_device = mm.unet_offload_device
            original_text_device = mm.text_encoder_device
            original_vae_device = mm.vae_device
            
            if model_device == "cpu":
                mm.unet_offload_device = lambda: torch.device("cpu")
            if clip_device == "cpu" and (configure_clip and use_baked_clip):
                mm.text_encoder_device = lambda: torch.device("cpu")
            if vae_device == "cpu" and (configure_vae and use_baked_vae):
                mm.vae_device = lambda: torch.device("cpu")
            
            try:
                loaded_ckpt = comfy.sd.load_checkpoint_guess_config(
                    ckpt_path,
                    output_vae=use_baked_vae if configure_vae else False,
                    output_clip=use_baked_clip if configure_clip else False,
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                )
            finally:
                # Restore original device functions
                mm.unet_offload_device = original_unet_device
                mm.text_encoder_device = original_text_device
                mm.vae_device = original_vae_device
            
            checkpoint_name = ckpt_name
            ckpt_parts = loaded_ckpt[:3] if hasattr(loaded_ckpt, '__len__') and len(loaded_ckpt) >= 3 else None
            loaded_model = ckpt_parts[0] if ckpt_parts else loaded_ckpt
            
        elif is_nunchaku:
            # ============================================================
            # STEP 1B: Load Nunchaku Quantized Model
            # ============================================================
            
            if nunchaku_name in (None, '', 'None'):
                raise ValueError("Please select a Nunchaku model file")
            
            nunchaku_path = folder_paths.get_full_path("diffusion_models", nunchaku_name)
            if not nunchaku_path or not os.path.isfile(nunchaku_path):
                raise FileNotFoundError(f"Nunchaku model not found: {nunchaku_name}")
            
            _, ext = os.path.splitext(nunchaku_path.lower())
            if ext not in safe_exts:
                log.warning(_LOG_PREFIX, f"'{nunchaku_name}' uses extension '{ext}'. Consider .safetensors.")
            
            if not os.access(nunchaku_path, os.R_OK):
                raise RuntimeError(f"Nunchaku file not readable: {nunchaku_path}")
            
            if not NUNCHAKU_AVAILABLE:
                log.warning("Nunchaku Flux", "Nunchaku support not available - install the 'nunchaku' pip package")
                log.msg("Nunchaku Flux", "Run: pip install nunchaku")
                loaded_model = None
                checkpoint_name = ""
            else:
                # Load with Nunchaku wrapper
                try:
                    log.msg("Nunchaku Flux", f"Loading quantized model: {nunchaku_name}")
                    
                    loaded_model = load_nunchaku_model(
                        model_path=nunchaku_path,
                        device=None,  # Auto-detect
                        dtype=None,  # Will be determined from data_type
                        cpu_offload=(cpu_offload == "enable" or cpu_offload == "auto"),
                        cache_threshold=cache_threshold,
                        attention=attention,
                        data_type=data_type,
                        i2f_mode=i2f_mode,
                        model_type="flux"
                    )
                    
                    # Set checkpoint name from the model file
                    checkpoint_name = nunchaku_name
                    
                except Exception as e:
                    log.error("Nunchaku Flux", f"Failed to load model '{nunchaku_name}': {e}")
                    loaded_model = None
                    checkpoint_name = ""
        
        elif is_qwen:
            # ============================================================
            # STEP 1D: Load Nunchaku Qwen Model
            # ============================================================
            
            if qwen_name in (None, '', 'None'):
                raise ValueError("Please select a Nunchaku Qwen model file")
            
            qwen_path = folder_paths.get_full_path("diffusion_models", qwen_name)
            if not qwen_path or not os.path.isfile(qwen_path):
                raise FileNotFoundError(f"Nunchaku Qwen model not found: {qwen_name}")
            
            _, ext = os.path.splitext(qwen_path.lower())
            if ext not in safe_exts:
                log.warning(_LOG_PREFIX, f"'{qwen_name}' uses extension '{ext}'. Consider .safetensors.")
            
            if not os.access(qwen_path, os.R_OK):
                raise RuntimeError(f"Qwen file not readable: {qwen_path}")
            
            if not NUNCHAKU_AVAILABLE:
                log.warning("Nunchaku Qwen", "Nunchaku support not available - install the 'nunchaku' pip package")
                log.msg("Nunchaku Qwen", "Run: pip install nunchaku")
                loaded_model = None
                checkpoint_name = ""
            else:
                # Load Nunchaku Qwen model
                checkpoint_name = qwen_name
                
                try:
                    loaded_model = load_nunchaku_model(
                        model_path=qwen_path,
                        device=None,  # Auto-detect
                        dtype=None,  # Auto-detect
                        cpu_offload=(cpu_offload == "enable" or cpu_offload == "auto"),
                        num_blocks_on_gpu=num_blocks_on_gpu,
                        use_pin_memory=(use_pin_memory == "enable"),
                        model_type="qwen"
                    )
                    
                except Exception as e:
                    log.error("Nunchaku Qwen", f"Failed to load model '{qwen_name}': {e}")
                    loaded_model = None
                    checkpoint_name = ""
        
        elif is_zimage:
            # ============================================================
            # STEP 1E: Load Nunchaku ZImage Model
            # ============================================================
            
            if zimage_name in (None, '', 'None'):
                raise ValueError("Please select a Nunchaku ZImage model file")
            
            zimage_path = folder_paths.get_full_path("diffusion_models", zimage_name)
            if not zimage_path or not os.path.isfile(zimage_path):
                raise FileNotFoundError(f"Nunchaku ZImage model not found: {zimage_name}")
            
            _, ext = os.path.splitext(zimage_path.lower())
            if ext not in safe_exts:
                log.warning(_LOG_PREFIX, f"'{zimage_name}' uses extension '{ext}'. Consider .safetensors.")
            
            if not os.access(zimage_path, os.R_OK):
                raise RuntimeError(f"ZImage file not readable: {zimage_path}")
            
            if not NUNCHAKU_AVAILABLE:
                log.warning("Nunchaku ZImage", "Nunchaku support not available - install the 'nunchaku' pip package")
                log.msg("Nunchaku ZImage", "Run: pip install nunchaku")
                loaded_model = None
                checkpoint_name = ""
            else:
                # Load Nunchaku ZImage model
                checkpoint_name = zimage_name
                
                try:
                    loaded_model = load_nunchaku_model(
                        model_path=zimage_path,
                        device=None,  # Auto-detect
                        dtype=None,  # Auto-detect
                        cpu_offload=(cpu_offload == "enable" or cpu_offload == "auto"),
                        num_blocks_on_gpu=num_blocks_on_gpu,
                        use_pin_memory=(use_pin_memory == "enable"),
                        model_type="zimage"
                    )
                    
                except Exception as e:
                    log.error("Nunchaku ZImage", f"Failed to load model '{zimage_name}': {e}")
                    loaded_model = None
                    checkpoint_name = ""
        
        elif is_gguf:
            # ============================================================
            # STEP 1F: Load GGUF Quantized Model
            # ============================================================
            
            if gguf_name in (None, '', 'None'):
                raise ValueError("Please select a GGUF model file")
            
            gguf_path = folder_paths.get_full_path("diffusion_models", gguf_name)
            if not gguf_path or not os.path.isfile(gguf_path):
                raise FileNotFoundError(f"GGUF model not found: {gguf_name}")
            
            if not gguf_path.lower().endswith('.gguf'):
                log.warning(_LOG_PREFIX, f"'{gguf_name}' doesn't have .gguf extension")
            
            if not os.access(gguf_path, os.R_OK):
                raise RuntimeError(f"GGUF file not readable: {gguf_path}")
            
            if not GGUF_AVAILABLE:
                log.warning("GGUF", "GGUF support not available - install the 'gguf' pip package")
                log.msg("GGUF", "Run: pip install gguf")
                loaded_model = None
                checkpoint_name = ""
            else:
                # Load GGUF model
                checkpoint_name = gguf_name
                
                try:
                    loaded_model = load_gguf_model(
                        model_path=gguf_path,
                        dequant_dtype=gguf_dequant_dtype,
                        patch_dtype=gguf_patch_dtype,
                        patch_on_device=gguf_patch_on_device
                    )
                    
                except Exception as e:
                    log.error("GGUF", f"Failed to load model '{gguf_name}': {e}")
                    loaded_model = None
                    checkpoint_name = ""
            
        elif is_unet:
            # ============================================================
            # STEP 1G: Load Standard UNet Model
            # ============================================================
            
            if unet_name in (None, '', 'None'):
                raise ValueError("Please select a UNet model file")
            
            unet_path = folder_paths.get_full_path("diffusion_models", unet_name)
            if not unet_path or not os.path.isfile(unet_path):
                raise FileNotFoundError(f"UNet model not found: {unet_name}")
            
            _, ext = os.path.splitext(unet_path.lower())
            if ext not in safe_exts:
                log.warning(_LOG_PREFIX, f"'{unet_name}' uses extension '{ext}'. Consider .safetensors.")
            
            if not os.access(unet_path, os.R_OK):
                raise RuntimeError(f"UNet file not readable: {unet_path}")
            
            # Check if we need baked components (CLIP or VAE)
            needs_baked_clip = configure_clip and use_baked_clip
            needs_baked_vae = configure_vae and use_baked_vae
            needs_vae_for_latent = configure_latent and not configure_vae
            
            if needs_baked_clip or needs_baked_vae or needs_vae_for_latent:
                # Try to load as checkpoint to extract baked components
                try:
                    loaded_ckpt = comfy.sd.load_checkpoint_guess_config(
                        unet_path,
                        output_vae=(needs_baked_vae or needs_vae_for_latent),
                        output_clip=needs_baked_clip,
                        embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    )
                    
                    ckpt_parts = loaded_ckpt[:3] if hasattr(loaded_ckpt, '__len__') and len(loaded_ckpt) >= 3 else None
                    loaded_model = ckpt_parts[0] if ckpt_parts else loaded_ckpt
                    checkpoint_name = unet_name
                    
                except Exception as e:
                    # If checkpoint loading fails, fall back to diffusion model loading
                    log.msg(_LOG_PREFIX, f"Note: UNet file doesn't contain baked components: {e}")
                    
                    # Configure model options
                    model_options: dict[str, Any] = {}
                    if weight_dtype == "fp8_e4m3fn":
                        model_options["dtype"] = torch.float8_e4m3fn
                    elif weight_dtype == "fp8_e4m3fn_fast":
                        model_options["dtype"] = torch.float8_e4m3fn
                        model_options["fp8_optimizations"] = True
                    elif weight_dtype == "fp8_e5m2":
                        model_options["dtype"] = torch.float8_e5m2
                    
                    loaded_model = comfy.sd.load_diffusion_model(unet_path, model_options=model_options)
                    checkpoint_name = unet_name
            else:
                # No baked components needed - use standard diffusion model loading
                model_options = {}
                if weight_dtype == "fp8_e4m3fn":
                    model_options["dtype"] = torch.float8_e4m3fn
                elif weight_dtype == "fp8_e4m3fn_fast":
                    model_options["dtype"] = torch.float8_e4m3fn
                    model_options["fp8_optimizations"] = True
                elif weight_dtype == "fp8_e5m2":
                    model_options["dtype"] = torch.float8_e5m2
                
                loaded_model = comfy.sd.load_diffusion_model(unet_path, model_options=model_options)
                checkpoint_name = unet_name
        
        else:
            raise ValueError("Invalid model_type. Choose 'Standard Checkpoint', 'UNet Model', 'Nunchaku Flux', 'Nunchaku Qwen', 'Nunchaku ZImage', or 'GGUF Model'")
        
        # ============================================================
        # STEP 2: Load CLIP (if configured)
        # ============================================================
        
        if configure_clip:
            if use_baked_clip:
                # Use baked CLIP from checkpoint (or UNet if it has one)
                # Note: Quantized models don't have baked CLIP
                if is_nunchaku or is_qwen or is_zimage or is_gguf:
                    if is_nunchaku:
                        model_label = "Nunchaku Flux"
                    elif is_qwen:
                        model_label = "Nunchaku Qwen"
                    elif is_zimage:
                        model_label = "Nunchaku ZImage"
                    else:
                        model_label = "GGUF"
                    log.warning(model_label, "Quantized models don't contain baked CLIP - please use External CLIP")
                elif ckpt_parts and ckpt_parts[1]:
                    base_clip = ckpt_parts[1]
                    if enable_clip_layer:
                        loaded_clip = base_clip.clone()
                        loaded_clip.clip_layer(stop_at_clip_layer)
                    else:
                        loaded_clip = base_clip
                else:
                    log.warning(_LOG_PREFIX, "Baked CLIP requested but not found in checkpoint")
            
            else:
                # Load external CLIP files
                clip_paths = []
                clip_names = [clip_name1, clip_name2, clip_name3, clip_name4]
                
                for i in range(clip_count_int):
                    clip_name = clip_names[i] if i < len(clip_names) else "None"
                    if clip_name not in (None, '', 'None'):
                        clip_path = folder_paths.get_full_path("clip", clip_name)
                        if clip_path and os.path.isfile(clip_path):
                            clip_paths.append(clip_path)
                        else:
                            log.warning(_LOG_PREFIX, f"CLIP file '{clip_name}' not found, skipping")
                
                if not clip_paths:
                    raise ValueError("No valid CLIP files found. Please select at least one CLIP model")
                
                # Map clip_type string to CLIPType enum
                clip_type_map = {
                    "sdxl": comfy.sd.CLIPType.STABLE_DIFFUSION,
                    "stable_cascade": comfy.sd.CLIPType.STABLE_CASCADE,
                    "sd3": comfy.sd.CLIPType.SD3,
                    "stable_audio": comfy.sd.CLIPType.STABLE_AUDIO,
                    "hunyuan_dit": comfy.sd.CLIPType.HUNYUAN_DIT,
                    "flux": comfy.sd.CLIPType.FLUX,
                    "flux2": comfy.sd.CLIPType.FLUX2,
                    "mochi": comfy.sd.CLIPType.MOCHI,
                    "ltxv": comfy.sd.CLIPType.LTXV,
                    "hunyuan_video": comfy.sd.CLIPType.HUNYUAN_VIDEO,
                    "pixart": comfy.sd.CLIPType.PIXART,
                    "cosmos": comfy.sd.CLIPType.COSMOS,
                    "lumina2": comfy.sd.CLIPType.LUMINA2,
                    "wan": comfy.sd.CLIPType.WAN,
                    "hidream": comfy.sd.CLIPType.HIDREAM,
                    "chroma": comfy.sd.CLIPType.CHROMA,
                    "ace": comfy.sd.CLIPType.ACE,
                    "omnigen2": comfy.sd.CLIPType.OMNIGEN2,
                    "qwen_image": comfy.sd.CLIPType.QWEN_IMAGE,
                    "hunyuan_image": comfy.sd.CLIPType.HUNYUAN_IMAGE,
                    "hunyuan_video_15": comfy.sd.CLIPType.HUNYUAN_VIDEO_15,
                    "ovis": comfy.sd.CLIPType.OVIS,
                    "kandinsky5": comfy.sd.CLIPType.KANDINSKY5,
                    "kandinsky5_image": comfy.sd.CLIPType.KANDINSKY5_IMAGE,
                    "newbie": comfy.sd.CLIPType.NEWBIE,
                }
                resolved_clip_type = clip_type_map.get(clip_type, comfy.sd.CLIPType.STABLE_DIFFUSION)
                
                # Temporarily override device function if forcing CPU
                original_text_device = mm.text_encoder_device
                if clip_device == "cpu":
                    mm.text_encoder_device = lambda: torch.device("cpu")
                
                try:
                    loaded_clip = comfy.sd.load_clip(
                        ckpt_paths=clip_paths,
                        embedding_directory=folder_paths.get_folder_paths("embeddings"),
                        clip_type=resolved_clip_type,
                    )
                finally:
                    mm.text_encoder_device = original_text_device
        
        # ============================================================
        # STEP 3: Load VAE (if configured or needed for latent channel detection)
        # ============================================================
        
        # If latent is configured, we need VAE for channel detection even if configure_vae is False
        needs_vae_for_latent = configure_latent and not configure_vae
        
        if configure_vae or needs_vae_for_latent:
            if use_baked_vae or needs_vae_for_latent:
                # Use baked VAE from checkpoint (or UNet if it has one)
                # Note: Nunchaku models don't have baked VAE
                if is_nunchaku:
                    if needs_vae_for_latent:
                        log.warning("Nunchaku", "Nunchaku models don't contain baked VAE - please enable 'Configure VAE' and use External VAE")
                elif ckpt_parts and ckpt_parts[2]:
                    loaded_vae = ckpt_parts[2]
                else:
                    # Fastfail: If latent is needed but no baked VAE exists
                    if needs_vae_for_latent:
                        raise ValueError(
                            "Cannot create latent: Model has no baked VAE. "
                            "Please enable 'Configure VAE' and set vae_source to 'External', "
                            "or disable 'Configure Latent'."
                        )
                    log.warning(_LOG_PREFIX, "Baked VAE requested but not found in model")
            
            elif configure_vae and not use_baked_vae:
                # Load external VAE file
                if vae_name in (None, '', 'None'):
                    log.warning(_LOG_PREFIX, "External VAE requested but none selected")
                else:
                    vae_path = folder_paths.get_full_path("vae", vae_name)
                    if vae_path and os.path.isfile(vae_path):
                        # Temporarily override device function if forcing CPU
                        original_vae_device = mm.vae_device
                        if vae_device == "cpu":
                            mm.vae_device = lambda: torch.device("cpu")
                        
                        try:
                            vae_sd = comfy.utils.load_torch_file(vae_path)
                            loaded_vae = comfy.sd.VAE(sd=vae_sd)
                        finally:
                            mm.vae_device = original_vae_device
                    else:
                        log.warning(_LOG_PREFIX, f"VAE file '{vae_name}' not found")
        
        # ============================================================
        # STEP 4: Apply LoRAs (if configured)
        # ============================================================
        
        # Initialize LoRA params list
        lora_params = []
        
        if configure_model_only_lora:
            # Collect enabled LoRAs
            for i in range(1, lora_count_int + 1):
                lora_switch = kwargs.get(f'lora_switch_{i}', False)
                lora_name = kwargs.get(f'lora_name_{i}', 'None')
                lora_weight = kwargs.get(f'lora_weight_{i}', 1.0)
                
                if lora_switch and lora_name not in (None, '', 'None'):
                    lora_params.append((lora_name, lora_weight))
            
            # Apply LoRAs if any enabled
            if lora_params:
                log.msg("LoRA", f"Applying {len(lora_params)} LoRA(s)...")
                loaded_model, loaded_clip = apply_loras_to_model(loaded_model, loaded_clip, lora_params)
        
        # Generate LoRA string
        lora_string = ""
        if lora_params:
            lora_string = ' '.join(f"<lora:{name}:{weight}:{weight}>" for name, weight in lora_params)
        
        # ============================================================
        # STEP 4.5: Apply Model Sampling (if configured)
        # ============================================================
        
        if configure_model_sampling and loaded_model is not None:
            # Auto-fill Flux dimensions from latent config if available
            flux_width = sampling_width
            flux_height = sampling_height
            
            if configure_latent and sampling_method == "Flux":
                # Map preset resolution to width/height
                if resolution != "Custom" and resolution in RESOLUTION_MAP:
                    auto_width, auto_height = RESOLUTION_MAP[resolution]
                    flux_width = auto_width
                    flux_height = auto_height
                else:
                    # Use custom dimensions
                    flux_width = width
                    flux_height = height
                
                log.msg("Model Sampling", f"Auto-filled Flux dimensions from latent: {flux_width}x{flux_height}")
            
            loaded_model = apply_model_sampling(
                loaded_model, 
                sampling_method=sampling_method,
                shift=shift,
                base_shift=base_shift,
                width=flux_width,
                height=flux_height,
                original_timesteps=original_timesteps,
                zsnr=zsnr,
                sampling_subtype=sampling_subtype,
                sigma_max=sigma_max,
                sigma_min=sigma_min
            )
        
        # ============================================================
        # STEP 5: Create Latent Tensor (if configured)
        # ============================================================
        
        latent_tensor = None
        final_width = width
        final_height = height
        
        if configure_latent:
            # Map preset resolution to width/height
            if resolution != "Custom" and resolution in RESOLUTION_MAP:
                final_width, final_height = RESOLUTION_MAP[resolution]
            
            # Detect latent channels from VAE
            detected_channels = LATENT_CHANNELS
            if loaded_vae:
                detected_channels = _detect_latent_channels_from_vae_obj(loaded_vae)
            
            # Create latent tensor
            latent_tensor = torch.zeros([
                batch_size,
                detected_channels,
                final_height // UNET_DOWNSAMPLE,
                final_width // UNET_DOWNSAMPLE
            ], device="cpu")
        
        # ============================================================
        # STEP 6: Construct output pipe with sampler settings
        # ============================================================
        
        if loaded_model is None:
            if is_gguf:
                ext_hint = "Ensure the 'gguf' pip package is installed."
            elif is_nunchaku or is_qwen or is_zimage:
                ext_hint = "Ensure the 'nunchaku' pip package is installed."
            else:
                ext_hint = ""
            raise RuntimeError(
                f"Failed to load {model_type} model. Check the console log above for details.\n"
                f"The model could not be loaded — ensure the file exists and is not corrupted. {ext_hint}"
            )
        
        pipe = {
            "model": loaded_model,
            "clip": loaded_clip if configure_clip else None,
            "vae": loaded_vae if configure_vae else None,
            "latent": {"samples": latent_tensor} if latent_tensor is not None else None,
            "width": final_width if configure_latent else None,
            "height": final_height if configure_latent else None,
            "batch_size": batch_size if configure_latent else None,
            "model_name": checkpoint_name,
            "vae_name": vae_name if not use_baked_vae and vae_name not in (None, '', 'None') else '',
            "clip_skip": stop_at_clip_layer if is_standard and use_baked_clip and enable_clip_layer else None,
            "is_nunchaku": is_nunchaku,
            "flux_guidance": flux_guidance,
            "lora_names": lora_string,
        }
        
        # Add sampler settings if configured
        if configure_sampler:
            pipe["sampler_name"] = sampler_name
            pipe["scheduler"] = scheduler
            pipe["steps"] = steps
            pipe["cfg"] = cfg
            pipe["_allow_overwrite"] = False
        
        return io.NodeOutput(pipe)

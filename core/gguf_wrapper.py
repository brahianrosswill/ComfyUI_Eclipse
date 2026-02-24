# GGUF Model Wrapper for Smart Loader Plus
#
# This module provides detection and loading support for GGUF quantized models.
# GGUF models are quantized diffusion models (INT4/INT8) that require special loading.
#
# Key Features:
# - Automatic detection via .gguf file extension
# - Graceful fallback when ComfyUI-GGUF is not installed
# - Support for dequantization and patch dtype control
# - Compatible with ComfyUI ModelPatcher interface via GGUFModelPatcher

import os
import inspect
from typing import Optional, Any, Callable
from pathlib import Path
import torch #type: ignore

from .logger import log


_LOG_PREFIX = "GGUF"


log.debug(_LOG_PREFIX, "Module loading started...")

# Try to import GGUF - graceful fallback if not available
GGUF_AVAILABLE = False
GGMLOps: Optional[Any] = None
gguf_sd_loader: Optional[Callable[[str], dict]] = None
GGUFModelPatcher: Optional[Any] = None

log.debug(_LOG_PREFIX, "Starting GGUF imports...")

try:
    # Check if ComfyUI-GGUF extension exists
    import sys
    # Path: core/gguf_wrapper.py -> ComfyUI_Eclipse -> custom_nodes
    custom_nodes_path = Path(__file__).parent.parent.parent
    gguf_path = custom_nodes_path / "ComfyUI-GGUF"
    
    log.debug(_LOG_PREFIX, f"Looking for ComfyUI-GGUF at: {gguf_path}")
    log.debug(_LOG_PREFIX, f"Path exists: {gguf_path.exists()}")
    
    if gguf_path.exists():
        # Import GGUF components using importlib (proper package import)
        log.debug(_LOG_PREFIX, "Attempting to import GGUF classes...")
        
        import importlib
        gguf_parent = str(gguf_path.parent)
        sys.path.insert(0, gguf_parent)
        
        try:
            # Import main components
            ops_module = importlib.import_module("ComfyUI-GGUF.ops")
            GGMLOps = ops_module.GGMLOps
            
            loader_module = importlib.import_module("ComfyUI-GGUF.loader")
            gguf_sd_loader = loader_module.gguf_sd_loader
            
            nodes_module = importlib.import_module("ComfyUI-GGUF.nodes")
            GGUFModelPatcher = nodes_module.GGUFModelPatcher
            
            log.msg(_LOG_PREFIX, "✓ GGUF components imported successfully")
            GGUF_AVAILABLE = True
        finally:
            sys.path.remove(gguf_parent)
    else:
        log.warning(_LOG_PREFIX, "ComfyUI-GGUF extension not found")
        
except Exception as e:
    import traceback
    log.error(_LOG_PREFIX, "Could not import GGUF components:")
    log.error(_LOG_PREFIX, f"Exception type: {type(e).__name__}")
    log.error(_LOG_PREFIX, f"Exception message: {e}")
    traceback.print_exc()
    GGMLOps = None
    gguf_sd_loader = None
    GGUFModelPatcher = None

# ComfyUI imports
try:
    import comfy.sd #type: ignore
    import comfy.model_management #type: ignore
except ImportError:
    # For standalone testing
    comfy = None


def is_gguf_available() -> bool:
    # Check if GGUF support is available.
    #
    # Returns:
    #     True if ComfyUI-GGUF is installed and imported successfully
    return GGUF_AVAILABLE


def detect_gguf_model(model_path: str) -> bool:
    # Detect if a model file is in GGUF format.
    #
    # Args:
    #     model_path: Path to model file
    #
    # Returns:
    #     True if file has .gguf extension
    if not model_path:
        return False
    
    return model_path.lower().endswith('.gguf')


def load_gguf_model(
    model_path: str,
    dequant_dtype: str = "default",
    patch_dtype: str = "default",
    patch_on_device: bool = False,
) -> object:
    # Load a GGUF quantized model.
    #
    # Args:
    #     model_path: Path to .gguf model file
    #     dequant_dtype: Dequantization dtype (default/target/float32/float16/bfloat16)
    #     patch_dtype: LoRA patch dtype (default/target/float32/float16/bfloat16)
    #     patch_on_device: Apply LoRA patches on GPU (faster but uses more VRAM)
    #
    # Returns:
    #     GGUFModelPatcher object
    #
    # Raises:
    #     ImportError: If GGUF support is not available
    #     ValueError: If model file not found or invalid parameters
    #     RuntimeError: If model loading fails
    
    # Check if GGUF is available
    if not GGUF_AVAILABLE:
        raise ImportError(
            "GGUF support not available.\n\n"
            "ComfyUI-GGUF extension is required to load GGUF models.\n\n"
            "Installation instructions:\n"
            "  1. Navigate to ComfyUI/custom_nodes/\n"
            "  2. Clone: git clone https://github.com/city96/ComfyUI-GGUF\n"
            "  3. Install: pip install --upgrade gguf\n"
            "  4. Restart ComfyUI\n\n"
            "Alternatively, use a standard (non-quantized) model."
        )
    
    # Validate model file exists
    if not os.path.exists(model_path):
        raise ValueError(f"Model file not found: {model_path}")
    
    # Validate file extension
    if not detect_gguf_model(model_path):
        raise ValueError(f"Not a GGUF model file (expected .gguf extension): {model_path}")
    
    log.msg(_LOG_PREFIX, f"Loading quantized model: {os.path.basename(model_path)}")
    log.msg(_LOG_PREFIX, f"  Dequant dtype: {dequant_dtype}")
    log.msg(_LOG_PREFIX, f"  Patch dtype: {patch_dtype}")
    log.msg(_LOG_PREFIX, f"  Patch on device: {patch_on_device}")
    
    # Type guards for mypy
    if GGMLOps is None or gguf_sd_loader is None or GGUFModelPatcher is None:
        raise ImportError("GGUF components not loaded properly")
    
    try:
        # Create custom ops with dtype settings
        ops = GGMLOps()
        
        # Set dequantization dtype
        if dequant_dtype == "default":
            ops.Linear.dequant_dtype = None  # type: ignore
        elif dequant_dtype == "target":
            ops.Linear.dequant_dtype = "target"  # type: ignore
        else:
            ops.Linear.dequant_dtype = getattr(torch, dequant_dtype)  # type: ignore
        
        # Set patch dtype
        if patch_dtype == "default":
            ops.Linear.patch_dtype = None  # type: ignore
        elif patch_dtype == "target":
            ops.Linear.patch_dtype = "target"  # type: ignore
        else:
            ops.Linear.patch_dtype = getattr(torch, patch_dtype)  # type: ignore
        
        # Load state dict from GGUF file
        log.msg(_LOG_PREFIX, "Loading state dict from GGUF file...")
        sd, extra = gguf_sd_loader(model_path)
        
        # Load diffusion model with custom operations
        # Pass metadata if load_diffusion_model_state_dict supports it
        log.msg(_LOG_PREFIX, "Loading diffusion model...")
        kwargs = {}
        valid_params = inspect.signature(comfy.sd.load_diffusion_model_state_dict).parameters
        if "metadata" in valid_params:
            kwargs["metadata"] = extra.get("metadata", {})
        
        model = comfy.sd.load_diffusion_model_state_dict(
            sd, 
            model_options={"custom_operations": ops},
            **kwargs,
        )
        
        if model is None:
            raise RuntimeError(f"Could not detect model type of: {model_path}")
        
        # Wrap in GGUF model patcher
        log.msg(_LOG_PREFIX, "Wrapping in GGUFModelPatcher...")
        model = GGUFModelPatcher.clone(model)  # type: ignore
        model.patch_on_device = patch_on_device  # type: ignore
        
        log.msg(_LOG_PREFIX, f"✓ Model loaded successfully: {os.path.basename(model_path)}")
        
        return model
        
    except Exception as e:
        raise RuntimeError(
            f"Failed to load GGUF model '{os.path.basename(model_path)}':\n{e}\n\n"
            f"This might indicate:\n"
            f"  - Corrupted model file\n"
            f"  - Incompatible GGUF version\n"
            f"  - Unsupported model architecture\n"
            f"  - Missing gguf Python package (pip install --upgrade gguf)\n"
        )


# Export public API
__all__ = [
    'is_gguf_available',
    'detect_gguf_model', 
    'load_gguf_model',
    'GGUF_AVAILABLE',
]

log.msg(_LOG_PREFIX, f"Module loaded. GGUF available: {GGUF_AVAILABLE}")




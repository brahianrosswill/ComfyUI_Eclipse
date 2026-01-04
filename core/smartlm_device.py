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

# SmartLM Device - VRAM, GPU, and Memory Management
#
# Handles device detection and memory management:
# - VRAM/GPU detection and info
# - Memory cleanup functions
# - Device capability checks
# - llama-cpp-python availability
# - Temporary file cleanup
#
# Used by both smartlm_base.py (v1) and smartlm_base_v2.py.

import gc
import torch
import psutil
from pathlib import Path
from typing import Dict, Optional, Any

from .logger import log
from .common import cleanup_memory_before_load
from .smartlm_templates import get_llm_models_path

_LOG_PREFIX = "SmartLM"


# ============================================================================
# llama-cpp-python Availability Check
# ============================================================================

LLAMA_CPP_AVAILABLE = False
LLAMA_CPP_MODULE = None


def _check_llama_cpp():
    # Check for llama-cpp-python availability.
    global LLAMA_CPP_AVAILABLE, LLAMA_CPP_MODULE
    
    try:
        import llama_cpp
        LLAMA_CPP_MODULE = "llama_cpp"
        LLAMA_CPP_AVAILABLE = True
        return True
    except ImportError:
        LLAMA_CPP_AVAILABLE = False
        LLAMA_CPP_MODULE = None
        return False


def is_llama_cpp_available() -> bool:
    # Check if llama-cpp-python is available.
    return LLAMA_CPP_AVAILABLE


def get_llama_cpp_module() -> Optional[str]:
    # Get the name of the available llama-cpp module.
    return LLAMA_CPP_MODULE


def log_llama_cpp_status():
    # Log llama-cpp-python status and GPU offloading support.
    global LLAMA_CPP_AVAILABLE, LLAMA_CPP_MODULE
    
    if not LLAMA_CPP_AVAILABLE:
        log.msg(_LOG_PREFIX, f"llama-cpp-python not found (optional for GGUF models)")
        return
    
    try:
        import llama_cpp
        version = getattr(llama_cpp, '__version__', 'unknown')
        log.msg(_LOG_PREFIX, f"llama-cpp-python version: {version}")
        
        # Check if GPU offloading is supported
        if hasattr(llama_cpp, 'llama_supports_gpu_offload'):
            try:
                gpu_support = llama_cpp.llama_supports_gpu_offload()
                if gpu_support:
                    log.msg(_LOG_PREFIX, f"✓ GPU offloading available")
            except Exception:
                pass
    except Exception as e:
        log.warning(_LOG_PREFIX, f"Could not check llama-cpp version: {e}")


# Initialize on module load
_check_llama_cpp()


# ============================================================================
# Device Detection Functions
# ============================================================================

def get_gpu_info() -> Dict[str, Any]:
    # Get information about all available GPUs.
    #
    # Returns:
    #     Dict with:
    #         - gpu_count: Number of GPUs
    #         - gpus: List of dicts with 'index', 'name', 'vram_gb', 'free_gb' per GPU
    #         - total_vram_gb: Combined VRAM of all GPUs
    #         - min_vram_gb: Smallest GPU VRAM (bottleneck for tensor parallelism)
    result = {
        "gpu_count": 0,
        "gpus": [],
        "total_vram_gb": 0,
        "min_vram_gb": 0,
    }
    
    if not torch.cuda.is_available():
        return result
    
    try:
        gpu_count = torch.cuda.device_count()
        result["gpu_count"] = gpu_count
        
        min_vram = float('inf')
        total_vram = 0
        
        for i in range(gpu_count):
            props = torch.cuda.get_device_properties(i)
            vram_gb = props.total_memory / (1024**3)
            
            # Get free memory for this GPU
            try:
                free_bytes, _ = torch.cuda.mem_get_info(i)
                free_gb = free_bytes / (1024**3)
            except (AttributeError, RuntimeError):
                # Fallback for older PyTorch or if device not accessible
                free_gb = vram_gb * 0.9  # Estimate 90% free
            
            result["gpus"].append({
                "index": i,
                "name": props.name,
                "vram_gb": round(vram_gb, 2),
                "free_gb": round(free_gb, 2),
            })
            
            total_vram += vram_gb
            min_vram = min(min_vram, vram_gb)
        
        result["total_vram_gb"] = round(total_vram, 2)
        result["min_vram_gb"] = round(min_vram, 2) if min_vram != float('inf') else 0
        
    except Exception as e:
        log.debug(_LOG_PREFIX, f"GPU detection failed: {e}")
    
    return result


def estimate_model_size_gb(model_path: str) -> float:
    # Estimate model size in GB from weight files.
    #
    # Handles models that may have multiple formats (Mistral-native consolidated.safetensors
    # AND HuggingFace sharded model-*.safetensors) - avoids double-counting.
    #
    # Priority:
    # 1. consolidated.safetensors (Mistral-native) - if exists, use this
    # 2. model.safetensors or model-*.safetensors (HuggingFace) - sharded or single
    # 3. *.bin files (older PyTorch format)
    # 4. *.gguf files (quantized)
    #
    # Args:
    #     model_path: Path to model folder or file
    #
    # Returns:
    #     Estimated model size in GB
    total_size_gb = 0
    try:
        model_folder = Path(model_path)
        
        # Handle single file (e.g., GGUF)
        if model_folder.is_file():
            return round(model_folder.stat().st_size / (1024**3), 2)
        
        if not model_folder.exists():
            return 0
        
        # Check for Mistral-native format first (consolidated.safetensors)
        consolidated = model_folder / "consolidated.safetensors"
        if consolidated.exists():
            # Use consolidated.safetensors as the model size
            # This is the Mistral-native format that vLLM will actually load
            total_size_gb = consolidated.stat().st_size / (1024**3)
            log.debug(_LOG_PREFIX, f"Using consolidated.safetensors size: {total_size_gb:.2f}GB")
            return round(total_size_gb, 2)
        
        # Check for HuggingFace format (model.safetensors or sharded model-*.safetensors)
        hf_single = model_folder / "model.safetensors"
        hf_sharded = list(model_folder.glob("model-*.safetensors"))
        
        if hf_single.exists():
            total_size_gb = hf_single.stat().st_size / (1024**3)
        elif hf_sharded:
            for f in hf_sharded:
                total_size_gb += f.stat().st_size / (1024**3)
        else:
            # Fallback: sum all safetensors (older or non-standard naming)
            for f in model_folder.glob("*.safetensors"):
                total_size_gb += f.stat().st_size / (1024**3)
        
        # Also check for .bin files if no safetensors found
        if total_size_gb == 0:
            for f in model_folder.glob("*.bin"):
                # Skip optimizer/training files
                if "optimizer" in f.name.lower() or "training" in f.name.lower():
                    continue
                total_size_gb += f.stat().st_size / (1024**3)
        
        # Also check for GGUF files
        if total_size_gb == 0:
            for f in model_folder.glob("*.gguf"):
                total_size_gb += f.stat().st_size / (1024**3)
                
    except Exception as e:
        log.debug(_LOG_PREFIX, f"Could not estimate model size: {e}")
    
    return round(total_size_gb, 2)


def check_model_fits(
    model_path: str,
    gpu_memory_utilization: float = 0.9,
    tensor_parallel_size: int = 1,
) -> Dict[str, Any]:
    # Check if a model will fit in available VRAM.
    #
    # Args:
    #     model_path: Path to model folder or file
    #     gpu_memory_utilization: Fraction of VRAM to use (0.0-1.0)
    #     tensor_parallel_size: Number of GPUs to use for tensor parallelism
    #
    # Returns:
    #     Dict with:
    #         - fits: bool - Whether model will fit
    #         - model_size_gb: Estimated model size
    #         - estimated_required_gb: Model + overhead
    #         - available_vram_gb: Usable VRAM with utilization setting
    #         - gpu_info: Full GPU info dict
    #         - suggested_tensor_parallel: Recommended tensor parallel size
    #         - message: Human-readable status
    gpu_info = get_gpu_info()
    model_size_gb = estimate_model_size_gb(model_path)
    
    # Model weights + ~30% for KV cache/activations overhead
    overhead_multiplier = 1.3
    estimated_required_gb = model_size_gb * overhead_multiplier
    
    result = {
        "fits": False,
        "model_size_gb": model_size_gb,
        "estimated_required_gb": round(estimated_required_gb, 2),
        "available_vram_gb": 0,
        "gpu_info": gpu_info,
        "suggested_tensor_parallel": 1,
        "message": "",
    }
    
    if gpu_info["gpu_count"] == 0:
        result["message"] = "No GPUs detected"
        return result
    
    # Calculate available VRAM based on tensor parallelism
    if tensor_parallel_size <= 1:
        # Single GPU: use first GPU's VRAM
        available_vram = gpu_info["gpus"][0]["vram_gb"] * gpu_memory_utilization
    else:
        # Multi-GPU: limited by smallest GPU (tensor parallelism splits model)
        # With tensor parallelism, model is split across GPUs
        tp_size = min(tensor_parallel_size, gpu_info["gpu_count"])
        available_vram = gpu_info["min_vram_gb"] * gpu_memory_utilization * tp_size
    
    result["available_vram_gb"] = round(available_vram, 2)
    
    # Check if model fits
    if estimated_required_gb <= available_vram:
        result["fits"] = True
        result["message"] = f"Model ({model_size_gb:.1f}GB) fits in available VRAM ({available_vram:.1f}GB)"
    else:
        # Model doesn't fit with current settings - calculate what would work
        result["fits"] = False
        
        # Check if tensor parallelism could help
        if gpu_info["gpu_count"] > 1:
            for tp in range(2, gpu_info["gpu_count"] + 1):
                potential_vram = gpu_info["min_vram_gb"] * gpu_memory_utilization * tp
                if estimated_required_gb <= potential_vram:
                    result["suggested_tensor_parallel"] = tp
                    result["message"] = (
                        f"Model ({model_size_gb:.1f}GB, needs ~{estimated_required_gb:.1f}GB) "
                        f"exceeds single GPU VRAM ({available_vram:.1f}GB). "
                        f"Consider using tensor_parallel_size={tp} with {gpu_info['gpu_count']} GPUs."
                    )
                    break
            else:
                # Even with all GPUs, model won't fit
                max_vram = gpu_info["min_vram_gb"] * gpu_memory_utilization * gpu_info["gpu_count"]
                result["message"] = (
                    f"Model ({model_size_gb:.1f}GB, needs ~{estimated_required_gb:.1f}GB) "
                    f"exceeds total available VRAM ({max_vram:.1f}GB across {gpu_info['gpu_count']} GPUs). "
                    f"Consider using a quantized (GGUF) version or a smaller model."
                )
        else:
            # Single GPU and model doesn't fit
            result["message"] = (
                f"Model ({model_size_gb:.1f}GB, needs ~{estimated_required_gb:.1f}GB) "
                f"exceeds available VRAM ({available_vram:.1f}GB on single GPU). "
                f"Consider using a quantized (GGUF) version or a smaller model."
            )
    
    return result


def get_device_info() -> Dict[str, Any]:
    # Get comprehensive device and memory information.
    #
    # Returns:
    #     Dict with gpu, system_memory, device_type, recommended_device, device_name
    gpu_info = {"available": False, "total_memory": 0, "free_memory": 0}
    device_type = "cpu"
    recommended_device = "cpu"
    
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        total = props.total_memory / (1024**3)
        
        # Get actual free memory (not just PyTorch allocations)
        # memory_reserved = CUDA memory reserved by PyTorch (includes cached/unused)
        # memory_allocated = actively used by tensors
        # For true free: use torch.cuda.mem_get_info() which reports actual GPU free memory
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info(0)
            free_memory = free_bytes / (1024**3)
        except AttributeError:
            # Fallback for older PyTorch versions
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            free_memory = total - reserved
        
        gpu_info = {
            "available": True,
            "total_memory": total,
            "free_memory": free_memory,
        }
        device_type = "cuda"
        recommended_device = "cuda"
    elif hasattr(torch.backends, 'mps') and hasattr(torch.backends.mps, 'is_available') and torch.backends.mps.is_available():
        device_type = "mps"
        recommended_device = "mps"
        gpu_info = {"available": True, "total_memory": 0, "free_memory": 0}
    
    sys_mem = psutil.virtual_memory()
    return {
        "gpu": gpu_info,
        "system_memory": {
            "total": sys_mem.total / (1024**3),
            "available": sys_mem.available / (1024**3),
        },
        "device_type": device_type,
        "recommended_device": recommended_device,
        "device": recommended_device,
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    }


def get_available_devices() -> list:
    # Get list of available compute devices for dropdown.
    # Returns device names that can be used in model loading.
    #
    # Returns:
    #     List of device strings, e.g. ["cuda", "cpu"] or ["mps", "cpu"]
    devices = []
    
    # Check for CUDA (NVIDIA) - also covers AMD ROCm which uses torch.cuda API
    if torch.cuda.is_available():
        devices.append("cuda")
    
    # Check for MPS (Apple Silicon)
    if hasattr(torch.backends, 'mps') and hasattr(torch.backends.mps, 'is_available'):
        if torch.backends.mps.is_available():
            devices.append("mps")
    
    # CPU is always available as fallback
    devices.append("cpu")
    
    return devices


def is_nvidia_gpu() -> bool:
    # Check if an NVIDIA GPU is available.
    return torch.cuda.is_available()


def get_available_vram() -> float:
    # Get available GPU VRAM in GB.
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        total = props.total_memory / (1024**3)
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        return total - allocated
    return 0.0


def get_available_system_memory() -> float:
    # Get available system memory in GB.
    sys_mem = psutil.virtual_memory()
    return sys_mem.available / (1024**3)

# ============================================================================
# Temporary File Cleanup
# ============================================================================

def cleanup_temp_gguf_files(model_path: str = None):
    # Clean up temporary GGUF files that may be left from failed loads.
    #
    # Args:
    #     model_path: Optional specific path to clean, otherwise cleans LLM folder
    try:
        import folder_paths
        
        if model_path:
            # Clean specific model folder
            model_folder = Path(model_path).parent if Path(model_path).is_file() else Path(model_path)
            temp_files = list(model_folder.glob("*.gguf.tmp"))
        else:
            # Clean entire LLM folder
            llm_dir = get_llm_models_path()
            temp_files = list(llm_dir.rglob("*.gguf.tmp"))
        
        for temp_file in temp_files:
            try:
                temp_file.unlink()
                log.msg(_LOG_PREFIX, f"Cleaned up temp file: {temp_file.name}")
            except Exception as e:
                log.warning(_LOG_PREFIX, f"Could not delete temp file {temp_file}: {e}")
        
        if temp_files:
            log.msg(_LOG_PREFIX, f"Cleaned up {len(temp_files)} temporary file(s)")
            
    except Exception as e:
        log.warning(_LOG_PREFIX, f"Error during temp file cleanup: {e}")


# ============================================================================
# Attention Mode Auto-Selection
# ============================================================================

def auto_select_attention() -> str:
    # Auto-select attention implementation based on availability.
    #
    # Priority:
    # 1. flash_attention_2 (fastest, requires flash-attn package)
    # 2. sdpa (PyTorch's scaled dot product attention)
    # 3. eager (fallback)
    #
    # Returns:
    #     Attention mode: "flash_attention_2", "sdpa", or "eager"
    # Try flash_attention_2 first
    try:
        import flash_attn
        return "flash_attention_2"
    except ImportError:
        pass
    
    # Check for SDPA support (PyTorch 2.0+)
    if hasattr(torch.nn.functional, 'scaled_dot_product_attention'):
        return "sdpa"
    
    # Fallback to eager
    return "eager"


# ============================================================================
# Quantization Auto-Selection
# ============================================================================

def auto_select_quantization(
    model_name: str,
    estimated_size_gb: float = 0.0,
    device_info: Optional[Dict[str, Any]] = None
) -> str:
    # Auto-select quantization based on available memory.
    #
    # Calculates required VRAM from file size with overhead factors for:
    # - KV cache, activations, and buffers
    # - BitsAndBytes keeps embeddings/layernorms in fp32 (~20% extra)
    #
    # Args:
    #     model_name: Model name (for logging only)
    #     estimated_size_gb: Model size in GB from disk
    #     device_info: Device info dict (from get_device_info())
    #
    # Returns:
    #     Quantization mode: "fp16", "8bit", or "4bit"
    if device_info is None:
        device_info = get_device_info()
    
    # Get available memory
    if device_info["recommended_device"] in {"cpu", "mps"}:
        available = device_info["system_memory"]["available"]
    else:
        available = device_info["gpu"]["free_memory"]
    
    # If size unknown, default to fp16 (caller should warn)
    if estimated_size_gb <= 0:
        return "fp16"
    
    # Calculate requirements with overhead for KV cache, activations, etc.
    # File size (bf16/fp16) ≈ model weights size
    # BitsAndBytes quantization keeps embeddings and layernorms in fp32 (~20% extra)
    # 8-bit (bitsandbytes) ≈ 50% of fp16 weight size + fp32 layers + buffers
    # 4-bit (bitsandbytes) ≈ 25% of fp16 weight size + fp32 layers + buffers
    # Use conservative estimates to avoid OOM errors
    needed_fp16 = estimated_size_gb * 1.3  # 30% overhead for activations
    needed_8bit = estimated_size_gb * 0.85  # ~50% quantized + 20% fp32 layers + 15% buffers
    needed_4bit = estimated_size_gb * 0.55  # ~25% quantized + 20% fp32 layers + 10% buffers
    
    # Choose quantization based on available memory with safety margin
    # Leave at least 1GB headroom for inference operations
    safety_margin = 1.0
    effective_available = available - safety_margin
    
    if needed_fp16 <= effective_available:
        selected = "fp16"
    elif needed_8bit <= effective_available:
        selected = "8bit"
    elif needed_4bit <= effective_available:
        selected = "4bit"
    else:
        selected = "4bit"
        log.warning(_LOG_PREFIX, f"Low memory ({available:.1f} GB). Using 4-bit.")
    
    # Log the auto-selection decision
    log.msg(_LOG_PREFIX, f"Auto quantization: model={estimated_size_gb:.1f}GB, free VRAM={available:.1f}GB (need: fp16={needed_fp16:.1f}, 8bit={needed_8bit:.1f}, 4bit={needed_4bit:.1f}) → {selected}")
    
    return selected

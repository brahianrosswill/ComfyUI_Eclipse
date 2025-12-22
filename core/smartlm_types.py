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

# SmartLM Types - Core Enums and Type Definitions
#
# Single source of truth for all SmartLM enums and type-related functions.
# Used by both smartlm_base.py (v1) and smartlm_base_v2.py.

from enum import Enum
from typing import List, Dict
import platform


# ============================================================================
# Platform Detection
# ============================================================================

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"


# ============================================================================
# Core Enums
# ============================================================================

class ModelType(Enum):
    # Model architecture types supported by SmartLM.
    QWENVL = "qwenvl"
    FLORENCE2 = "florence2"
    MISTRAL3 = "mistral3"  # Mistral3 vision-language models
    LLAVA = "llava"  # LLaVA vision-language models (high token usage ~2900/image)
    LLM = "llm"  # Text-only LLM (no vision)
    UNKNOWN = "unknown"


class ModelFamily(Enum):
    # Model families for UI categorization
    MISTRAL = "Mistral"
    QWEN = "Qwen"
    FLORENCE = "Florence"
    LLAVA = "LLaVA"  # Generic vision models (LLaVA, Gemma3, MiniCPM-V, Moondream, etc.)
    LLM_TEXT = "LLM (Text-Only)"


class LoadingMethod(Enum):
    # Available model loading backends
    TRANSFORMERS = "Transformers"
    GGUF = "GGUF (llama-cpp-python)"
    VLLM_DOCKER = "vLLM (Docker)"        # Cross-platform Docker-based vLLM
    VLLM_NATIVE = "vLLM (Native)"        # Linux only (pip install vllm)
    SGLANG_DOCKER = "SGLang (Docker)"    # Cross-platform Docker-based SGLang (alternative to vLLM)
    OLLAMA_DOCKER = "Ollama (Docker)"    # Docker-based Ollama (supports Mistral3 GGUF)
    LLAMACPP_DOCKER = "llama.cpp (Docker)"  # Docker-based llama.cpp server (supports Mistral3 GGUF)


# ============================================================================
# Transformers Version Detection
# ============================================================================

import transformers
_transformers_version = tuple(map(int, transformers.__version__.split('.')[:2])) if transformers.__version__[0].isdigit() else (4, 0)
if 'rc' in transformers.__version__.lower():
    _transformers_version = (5, 0)

# Florence-2 is incompatible with transformers v5 (many breaking changes)
# Warning is printed by florence2_wrapper.py
FLORENCE_COMPATIBLE = _transformers_version < (5, 0)

# Mistral3 (Ministral, Pixtral vision models) REQUIRES transformers v5+
# The Mistral3ForConditionalGeneration architecture doesn't exist in v4
# vLLM backend works with any transformers version
MISTRAL3_TRANSFORMERS_COMPATIBLE = _transformers_version >= (5, 0)


# ============================================================================
# Method Support Matrices
# ============================================================================

# Platform-specific vLLM method
_VLLM_METHOD = LoadingMethod.VLLM_DOCKER if IS_WINDOWS else LoadingMethod.VLLM_NATIVE
_SGLANG_METHOD = LoadingMethod.SGLANG_DOCKER  # SGLang is Docker-only on all platforms

# v1 Matrix: Family -> Methods (what methods support this family?)
METHOD_SUPPORT = {
    # Note: Mistral GGUF disabled - mistral3 architecture not yet supported by llama-cpp-python
    ModelFamily.MISTRAL: [LoadingMethod.TRANSFORMERS, _VLLM_METHOD, _SGLANG_METHOD],
    ModelFamily.QWEN: [LoadingMethod.TRANSFORMERS, LoadingMethod.GGUF, _VLLM_METHOD, _SGLANG_METHOD],
    ModelFamily.FLORENCE: [LoadingMethod.TRANSFORMERS],  # Florence only supports transformers
    ModelFamily.LLAVA: [LoadingMethod.OLLAMA_DOCKER],  # LLaVA family only via Ollama registry models
    ModelFamily.LLM_TEXT: [LoadingMethod.TRANSFORMERS, LoadingMethod.GGUF, _VLLM_METHOD, _SGLANG_METHOD],
}

# v2 Matrix: Method -> Families (what families support this method?)
METHOD_SUPPORT_V2 = {
    LoadingMethod.TRANSFORMERS: [ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.FLORENCE, ModelFamily.LLM_TEXT],
    # Note: Mistral GGUF disabled in llama.cpp local - mistral3 architecture not yet supported by llama-cpp-python
    # LLaVA GGUF supported via Llava16ChatHandler with mmproj file
    LoadingMethod.GGUF: [ModelFamily.QWEN, ModelFamily.LLAVA, ModelFamily.LLM_TEXT],
    _VLLM_METHOD: [ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.LLM_TEXT],
    _SGLANG_METHOD: [ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.LLM_TEXT],  # SGLang supports same as vLLM
    # Docker backends with full Mistral3/GGUF support
    # LLaVA = generic vision models from Ollama registry (LLaVA, Gemma3, MiniCPM-V, Moondream, Llama3.2-Vision, etc.)
    LoadingMethod.OLLAMA_DOCKER: [ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.LLAVA, ModelFamily.LLM_TEXT],
    LoadingMethod.LLAMACPP_DOCKER: [ModelFamily.MISTRAL, ModelFamily.QWEN, ModelFamily.LLAVA, ModelFamily.LLM_TEXT],
}

# NOTE: We no longer filter out Florence/Mistral from dropdowns based on transformers version.
# Users can still select them, but will get clear error messages at runtime explaining
# the incompatibility and how to fix it (downgrade/upgrade transformers or use alternative backend).
# This provides better UX - users see all options and understand why something doesn't work.


# ============================================================================
# UI Helper Functions
# ============================================================================

def get_model_family_list() -> List[str]:
    # Get list of all model family names for UI dropdown.
    # Note: All families are shown regardless of transformers version.
    # Users get clear error messages at runtime for incompatible combinations.
    return [family.value for family in ModelFamily]


def get_loading_method_list() -> List[str]:
    # Get list of all loading method names for UI dropdown.
    # Platform-specific filtering:
    # - vLLM (Docker): Available on ALL platforms with Docker (Windows, Linux, Mac)
    # - vLLM (Native): Only available on Linux (native pip install vllm)
    methods = []
    for method in LoadingMethod:
        # Filter platform-specific vLLM methods
        # Docker vLLM is available on all platforms
        # Native vLLM only works on Linux
        if method == LoadingMethod.VLLM_NATIVE and not IS_LINUX:
            continue  # Skip Native vLLM on non-Linux (Windows/Mac don't support native vLLM)
        methods.append(method.value)
    return methods


def get_supported_methods(family: ModelFamily) -> List[str]:
    # Get list of supported loading methods for a model family (v1 workflow)
    methods = METHOD_SUPPORT.get(family, [])
    return [method.value for method in methods]


def get_supported_families(method: LoadingMethod) -> List[str]:
    # Get list of supported families for a loading method (v2 workflow)
    families = METHOD_SUPPORT_V2.get(method, [])
    return [family.value for family in families]


def get_supported_families_by_name(method_name: str) -> List[str]:
    # Get supported families by method name string (for UI)
    try:
        method = LoadingMethod(method_name)
        return get_supported_families(method)
    except ValueError:
        return get_model_family_list()


# ============================================================================
# Model Type Detection Functions
# ============================================================================

def get_model_family_from_name(model_name: str) -> ModelFamily:
    # Detect model family from model name/path by reading config.json if available
    import json
    from pathlib import Path
    
    model_path = Path(model_name)
    model_lower = model_name.lower()
    
    # GGUF files don't have config.json - skip to name-based detection
    is_gguf = model_lower.endswith('.gguf')
    
    # Try to read config.json for accurate detection (non-GGUF only)
    config_file = None
    if not is_gguf:
        if model_path.is_dir():
            config_file = model_path / "config.json"
        elif model_path.is_file():
            # Single file - check parent folder (but not for GGUF)
            config_file = model_path.parent / "config.json"
    
    if config_file and config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding='utf-8'))
            
            # Get model_type and architectures from config
            model_type = config.get("model_type", "").lower()
            architectures = [a.lower() for a in config.get("architectures", [])]
            
            # Check for vision capabilities
            has_vision = (
                "vision_config" in config or
                "image_size" in config or
                "visual" in str(config.get("architectures", [])).lower() or
                "vl" in model_type or
                "vision" in model_type or
                any("vision" in a or "vl" in a or "image" in a for a in architectures)
            )
            
            # Florence-2 detection
            if "florence" in model_type or any("florence" in a for a in architectures):
                return ModelFamily.FLORENCE
            
            # Qwen detection
            if "qwen" in model_type or any("qwen" in a for a in architectures):
                if has_vision or "vl" in model_type:
                    return ModelFamily.QWEN
                else:
                    return ModelFamily.LLM_TEXT
            
            # Mistral/Pixtral detection
            if "mistral" in model_type or "pixtral" in model_type or any("mistral" in a or "pixtral" in a for a in architectures):
                if has_vision or "pixtral" in model_type:
                    return ModelFamily.MISTRAL
                else:
                    return ModelFamily.LLM_TEXT
            
            # Generic vision model check
            if has_vision:
                # Try to match to known vision families by name
                if "qwen" in model_lower:
                    return ModelFamily.QWEN
                elif "mistral" in model_lower or "pixtral" in model_lower:
                    return ModelFamily.MISTRAL
                elif "florence" in model_lower:
                    return ModelFamily.FLORENCE
            
            # No vision - it's a text-only LLM
            return ModelFamily.LLM_TEXT
            
        except Exception:
            pass  # Fall through to name-based detection
    
    # Fallback: Name-based detection for GGUF or when config.json is not available
    if "llava" in model_lower:
        # LLaVA models (vision)
        return ModelFamily.LLAVA
    elif "mistral" in model_lower or "ministral" in model_lower:
        # Distinguish vision vs text-only Mistral models by name
        is_vision_model = (
            "ministral-3" in model_lower or 
            "mistral-small-3" in model_lower or
            "pixtral" in model_lower
        )
        if is_vision_model:
            return ModelFamily.MISTRAL
        else:
            return ModelFamily.LLM_TEXT
    elif "qwen" in model_lower:
        if "vl" in model_lower or "vision" in model_lower:
            return ModelFamily.QWEN
        else:
            return ModelFamily.LLM_TEXT
    elif "florence" in model_lower:
        return ModelFamily.FLORENCE
    else:
        return ModelFamily.LLM_TEXT


def detect_model_type(template_info: dict) -> ModelType:
    # Detect model type from template configuration
    model_type = template_info.get("model_type", "").lower()
    repo_id = template_info.get("repo_id", "").lower()
    local_path = template_info.get("local_path", "").lower()
    mmproj_path = template_info.get("mmproj_path", "")
    
    # Explicit LLM type
    if model_type == "llm":
        return ModelType.LLM
    
    # Mistral3 detection (Ministral-3, Mistral-Small-3, etc.)
    if model_type == "mistral3" or "mistral" in repo_id or "ministral" in repo_id:
        # Check if it's a vision model (Mistral3/Ministral3) vs text-only
        if "ministral" in repo_id or "mistral-3" in repo_id or "mistral-small-3" in repo_id:
            return ModelType.MISTRAL3
    
    # QwenVL detection
    if model_type == "qwenvl" or "qwen" in repo_id:
        return ModelType.QWENVL
    
    # Florence-2 detection
    if model_type == "florence2" or "florence" in repo_id:
        return ModelType.FLORENCE2
    
    # LLaVA detection
    if model_type == "llava" or "llava" in repo_id:
        return ModelType.LLAVA
    
    # Text-only GGUF detection: GGUF file without mmproj
    if local_path.endswith(".gguf") and not mmproj_path:
        return ModelType.LLM
    
    return ModelType.UNKNOWN


def is_mistral3_vision_model(model_path: str) -> bool:
    # Check if a model is a Mistral3/Pixtral vision model.
    #
    # These models have specific limitations:
    # - Don't support BitsAndBytes quantization in vLLM
    # - Require transformers v5+ for Transformers backend
    # - Need --load-format mistral with consolidated.safetensors
    #
    # Args:
    #     model_path: Path to the model directory or model name
    #
    # Returns:
    #     True if model is a Mistral3/Pixtral vision model
    import json
    from pathlib import Path
    
    model_dir = Path(model_path)
    model_lower = str(model_path).lower()
    
    # Try config.json first (most accurate)
    config_file = model_dir / "config.json" if model_dir.is_dir() else None
    
    if config_file and config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding='utf-8'))
            
            # Check architecture and model_type
            architectures = config.get("architectures", [])
            model_type = config.get("model_type", "")
            vision_config = config.get("vision_config", {})
            
            # Mistral3ForConditionalGeneration is the vision model architecture
            if "Mistral3ForConditionalGeneration" in architectures:
                return True
            
            # Check for mistral3 model type with vision config
            if model_type == "mistral3" and vision_config:
                return True
            
            # Check for pixtral vision encoder
            if vision_config.get("model_type") == "pixtral":
                return True
                
        except Exception:
            pass  # Fall through to name-based detection
    
    # Fallback: Name-based detection
    # Ministral-3, Mistral-Small-3, and Pixtral are vision models
    if any(pattern in model_lower for pattern in ["ministral-3", "ministral3", "mistral-small-3", "pixtral"]):
        return True
    
    return False


def is_model_architecture_supported(repo_id: str) -> bool:
    # Check if a model architecture is supported by the installed transformers version
    if not repo_id:
        return True  # No repo_id means likely GGUF or local - assume supported
    
    # Known unsupported architectures and their minimum required transformers versions
    architecture_requirements = {
        'qwen3-vl': ('4.57.1', 'Qwen3-VL'),
        'qwen3_vl': ('4.57.1', 'Qwen3-VL'),
    }
    
    # Check if repo contains known unsupported architecture markers
    repo_lower = repo_id.lower()
    unsupported_arch = None
    
    for pattern, (min_version, arch_name) in architecture_requirements.items():
        if pattern in repo_lower:
            unsupported_arch = (pattern, min_version, arch_name)
            break
    
    if not unsupported_arch:
        return True  # Not a known problematic architecture
    
    # Check transformers version
    try:
        import transformers
        from packaging import version
        
        current_version = version.parse(transformers.__version__)
        required_version = version.parse(unsupported_arch[1])
        
        return current_version >= required_version
    except:
        # If we can't check version, assume supported to avoid false positives
        return True

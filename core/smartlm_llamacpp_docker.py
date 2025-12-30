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

# llama.cpp/Docker integration for Eclipse SmartLM.
#
# llama.cpp server is the reference GGUF inference engine:
# - Native GGUF support (designed for it)
# - Fast inference with optimized kernels
# - Flexible GPU layer offloading
# - OpenAI-compatible API
#
# Docker image: ghcr.io/ggerganov/llama.cpp:server-cuda

import json
import subprocess
import time
import requests
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from .logger import log
from .smartlm_device import get_gpu_info, estimate_model_size_gb
from .smartlm_templates import get_llm_models_path, get_llm_models_absolute_path
from . import docker_error_handler


# ==============================================================================
# LOGGING HELPERS
# ==============================================================================

def debug_log(message: str):
    log.debug("llama.cpp Docker", message)


def warning_log(message: str):
    log.warning("llama.cpp Docker", message)


def msg_log(message: str):
    log.msg("llama.cpp Docker", message)


def error_log(message: str):
    log.error("llama.cpp Docker", message)


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Use CUDA-enabled server image from ggml-org (official repo)
LLAMACPP_DOCKER_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda"
LLAMACPP_DEFAULT_PORT = 8080
LLAMACPP_CONTAINER_PREFIX = "eclipse-llamacpp"

# mmproj patterns for auto-detection (vision support)
MMPROJ_PATTERNS = [
    "mmproj*.gguf",      # Official naming: mmproj-F16.gguf, mmproj-Q8_0.gguf
    "*-mmproj.gguf",     # e.g., model-mmproj.gguf
    "*_mmproj.gguf",
    "*mmproj*.gguf",
    "*projector*.gguf",
    "*-clip-*.gguf",     # Some models use clip naming
]


# ==============================================================================
# CONFIGURATION
# ==============================================================================

_CONFIG_PATH = Path(__file__).parent.parent / "docker_config.json"


def _get_llamacpp_config() -> Dict[str, Any]:
    # Get llama.cpp-specific configuration from docker_config.json.
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("llamacpp", {})
    except Exception as e:
        debug_log(f"Could not load llamacpp config: {e}")
    
    return {
        "enabled": False,
        "port": LLAMACPP_DEFAULT_PORT,
        "n_gpu_layers": -1,  # -1 = all layers on GPU
        "ctx_size": 8192,    # Context size
        "n_predict": 1024,   # Max tokens to predict
    }


def get_llamacpp_startup_timeout() -> int:
    # Get llama.cpp startup timeout from config (default 120s / 2 min).
    config = _get_llamacpp_config()
    return config.get("startup_timeout", 120)


def get_llamacpp_request_timeout() -> int:
    # Get llama.cpp request timeout from config (default 180s / 3 min).
    config = _get_llamacpp_config()
    return config.get("request_timeout", 180)


def _save_llamacpp_config(llamacpp_config: Dict[str, Any]):
    # Save llama.cpp configuration to docker_config.json.
    try:
        config = {}
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        config["llamacpp"] = llamacpp_config
        
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        error_log(f"Could not save llamacpp config: {e}")


def load_llamacpp_model_containers() -> Dict[str, Dict]:
    # Load model-to-container mappings for llama.cpp.
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("llamacpp_containers", {})
    except Exception:
        pass
    return {}


def save_llamacpp_model_container(model_name: str, container_id: str):
    # Save model-container mapping for llama.cpp.
    try:
        config = {}
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        if "llamacpp_containers" not in config:
            config["llamacpp_containers"] = {}
        
        config["llamacpp_containers"][model_name] = {
            "container_id": container_id,
            "created": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }
        
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
            
        debug_log(f"Saved container {container_id[:12]} for {model_name}")
    except Exception as e:
        error_log(f"Could not save container mapping: {e}")


def _load_full_config() -> Dict[str, Any]:
    # Load full docker_config.json.
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        debug_log(f"Could not load config: {e}")
    return {}


def _save_full_config(config: Dict[str, Any]):
    # Save full docker_config.json.
    try:
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        error_log(f"Could not save config: {e}")


def get_llamacpp_config() -> Dict[str, Any]:
    # Get llama.cpp configuration (public API).
    return _get_llamacpp_config()


def set_llamacpp_options(
    auto_start: bool = None,
    stop_after_generation: bool = None,
    n_gpu_layers: int = None,
    ctx_size: int = None,
    port: int = None,
 ) -> bool:
    # Set llama.cpp configuration options.
    #
    # Args:
    #     auto_start: Whether to auto-start container (None = don't change)
    #     stop_after_generation: Whether to stop after generation (None = don't change)
    #     n_gpu_layers: GPU layers (-1 = all, None = don't change)
    #     ctx_size: Context size (None = don't change)
    #     port: Port number (None = don't change)
    #
    # Returns:
    #     bool: True if saved successfully
    try:
        config = _load_full_config()
        if "llamacpp" not in config:
            config["llamacpp"] = {}
        
        if auto_start is not None:
            config["llamacpp"]["auto_start"] = auto_start
        if stop_after_generation is not None:
            config["llamacpp"]["stop_after_generation"] = stop_after_generation
        if n_gpu_layers is not None:
            config["llamacpp"]["n_gpu_layers"] = n_gpu_layers
        if ctx_size is not None:
            config["llamacpp"]["ctx_size"] = ctx_size
        if port is not None:
            config["llamacpp"]["port"] = port
        
        _save_full_config(config)
        return True
    except Exception as e:
        error_log(f"Failed to set llama.cpp options: {e}")
        return False


# ==============================================================================
# DOCKER HELPERS
# ==============================================================================

def _run_docker_cmd(args: List[str], timeout: int = 30) -> tuple[bool, str]:
    # Run a docker command and return (success, output).
    try:
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding='utf-8',
            errors='replace',  # Handle non-UTF8 bytes gracefully on Windows
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def _get_container_name(model_name: str) -> str:
    # Generate container name from model name.
    # Sanitize model name for container naming
    safe_name = model_name.replace("/", "-").replace(":", "-").replace(".", "-")
    return f"{LLAMACPP_CONTAINER_PREFIX}-{safe_name}"


def is_container_running(container_id_or_name: str) -> bool:
    # Check if a container is running.
    success, output = _run_docker_cmd(["ps", "-q", "-f", f"id={container_id_or_name}"])
    if success and output:
        return True
    success, output = _run_docker_cmd(["ps", "-q", "-f", f"name={container_id_or_name}"])
    return success and bool(output.strip())


def is_container_exists(container_id_or_name: str) -> bool:
    # Check if a container exists (running or stopped).
    success, output = _run_docker_cmd(["ps", "-aq", "-f", f"id={container_id_or_name}"])
    if success and output:
        return True
    success, output = _run_docker_cmd(["ps", "-aq", "-f", f"name={container_id_or_name}"])
    return success and bool(output.strip())


def get_running_llamacpp_containers() -> List[str]:
    # Get list of running llama.cpp containers.
    success, output = _run_docker_cmd(["ps", "-q", "-f", f"name={LLAMACPP_CONTAINER_PREFIX}"])
    if success and output:
        return output.strip().split('\n')
    return []


# ==============================================================================
# DOCKER IMAGE MANAGEMENT
# ==============================================================================

def is_image_available(image_name: str) -> bool:
    # Check if a Docker image is available locally.
    success, output = _run_docker_cmd(["images", "-q", image_name])
    return success and bool(output.strip())


def pull_docker_image(image_name: str, timeout: int = 300) -> bool:
    # Pull a Docker image from registry.
    #
    # Args:
    #     image_name: Image to pull (e.g., "ghcr.io/ggerganov/llama.cpp:server-cuda")
    #     timeout: Maximum seconds to wait for pull (default 5 minutes)
    #
    # Returns:
    #     bool: True if image was pulled successfully
    msg_log(f"Pulling Docker image: {image_name} (this may take a few minutes)...")
    
    try:
        # Use longer timeout for image pull
        result = subprocess.run(
            ["docker", "pull", image_name],
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding='utf-8',
            errors='replace',  # Handle non-UTF8 bytes gracefully on Windows
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        if result.returncode == 0:
            msg_log(f"✓ Image {image_name} pulled successfully")
            return True
        else:
            error_log(f"Failed to pull image: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        error_log(f"Image pull timed out after {timeout}s - check your internet connection")
        return False
    except Exception as e:
        error_log(f"Failed to pull image: {e}")
        return False


def ensure_llamacpp_image() -> bool:
    # Ensure the llama.cpp Docker image is available locally.
    # Pulls it if not present.
    #
    # Returns:
    #     bool: True if image is available
    if is_image_available(LLAMACPP_DOCKER_IMAGE):
        debug_log(f"Image {LLAMACPP_DOCKER_IMAGE} is available locally")
        return True
    
    msg_log(f"Image {LLAMACPP_DOCKER_IMAGE} not found locally, downloading...")
    return pull_docker_image(LLAMACPP_DOCKER_IMAGE)


# ==============================================================================
# CONTAINER LIFECYCLE
# ==============================================================================

def start_llamacpp_container(
    model_path: str,
    models_base_path: str = None,
    mmproj_path: str = None,
    port: int = None,
    n_gpu_layers: int = -1,
    ctx_size: int = 8192,
    wait_for_ready: bool = True,
) -> bool:
    # Start llama.cpp Docker container with specified GGUF model.
    #
    # Args:
    #     model_path: Full path to GGUF model file
    #     models_base_path: Base directory to mount (parent of model)
    #     mmproj_path: Optional path to mmproj file for vision support (auto-detected if None)
    #     port: Port to expose (default: 8080)
    #     n_gpu_layers: Number of layers to offload to GPU (-1 = all)
    #     ctx_size: Context size
    #     wait_for_ready: Wait for server to be ready
    #
    # Returns:
    #     bool: True if container started successfully
    # Ensure Docker daemon is running (auto-start on Windows)
    if not ensure_docker_running():
        error_log("Docker is not available or could not be started")
        return False
    
    # Ensure Docker image is available (auto-pull if needed)
    if not ensure_llamacpp_image():
        error_log("Failed to get llama.cpp Docker image - check your internet connection")
        return False
    
    config = _get_llamacpp_config()
    port = port or config.get("port", LLAMACPP_DEFAULT_PORT)
    n_gpu_layers = n_gpu_layers if n_gpu_layers != -1 else config.get("n_gpu_layers", -1)
    ctx_size = ctx_size or config.get("ctx_size", 8192)
    
    model_path = Path(model_path)
    model_name = model_path.name
    
    # Auto-detect mmproj file for vision support
    detected_mmproj = None
    if mmproj_path:
        detected_mmproj = Path(mmproj_path)
        if not detected_mmproj.exists():
            warning_log(f"Specified mmproj file not found: {mmproj_path}")
            detected_mmproj = None
    else:
        # Auto-detect mmproj in the same directory as the model
        parent_dir = model_path.parent
        for pattern in MMPROJ_PATTERNS:
            matches = list(parent_dir.glob(pattern))
            # Exclude the main model file
            matches = [m for m in matches if m != model_path]
            if matches:
                detected_mmproj = matches[0]
                msg_log(f"Auto-detected mmproj: {detected_mmproj.name}")
                break
    
    # Check if we have a saved container for this model
    saved_containers = load_llamacpp_model_containers()
    container_name = _get_container_name(model_name)
    _set_last_container(container_name)  # Track for error diagnosis
    
    if model_name in saved_containers:
        saved_id = saved_containers[model_name]["container_id"]
        if is_container_exists(saved_id):
            if is_container_running(saved_id):
                msg_log(f"✓ Container already running for {model_name}")
                return True
            else:
                # Restart existing container
                msg_log(f"Restarting container for {model_name}...")
                success, _ = _run_docker_cmd(["start", saved_id])
                if success:
                    msg_log("✓ Container restarted")
                    if wait_for_ready:
                        startup_timeout = get_llamacpp_startup_timeout()
                        return wait_for_llamacpp_ready(port, timeout=startup_timeout, container_name=container_name)
                    return True
    
    # Check if container with same name already exists (even if not tracked in config)
    if is_container_exists(container_name):
        if is_container_running(container_name):
            msg_log(f"✓ Reusing existing running container: {container_name}")
            # Save to config for future tracking
            success, container_id = _run_docker_cmd(["ps", "-q", "-f", f"name={container_name}"])
            if success and container_id:
                save_llamacpp_model_container(model_name, container_id.strip())
            return True
        else:
            # Container exists but stopped - restart it
            msg_log(f"Restarting existing container: {container_name}")
            # Stop any OTHER running llama.cpp containers first
            for cid in get_running_llamacpp_containers():
                warning_log(f"Stopping other container {cid[:12]}...")
                _run_docker_cmd(["stop", cid])
            
            success, _ = _run_docker_cmd(["start", container_name])
            if success:
                msg_log("✓ Container restarted")
                # Save to config for future tracking
                success, container_id = _run_docker_cmd(["ps", "-q", "-f", f"name={container_name}"])
                if success and container_id:
                    save_llamacpp_model_container(model_name, container_id.strip())
                if wait_for_ready:
                    startup_timeout = get_llamacpp_startup_timeout()
                    return wait_for_llamacpp_ready(port, timeout=startup_timeout, container_name=container_name)
                return True
            else:
                # Failed to restart, remove and recreate
                warning_log(f"Failed to restart container, will recreate")
                _run_docker_cmd(["rm", "-f", container_name])
    
    # Stop any existing llama.cpp containers (we only run one at a time)
    for container_id in get_running_llamacpp_containers():
        warning_log(f"Stopping existing container {container_id[:12]}...")
        _run_docker_cmd(["stop", container_id])
    
    msg_log(f"Starting new llama.cpp container for: {model_name}")
    
    # Determine mount path - use llm_models_absolute_path from eclipse_config
    if models_base_path:
        mount_path = Path(models_base_path)
    else:
        try:
            mount_path = Path(get_llm_models_absolute_path())
            debug_log(f"Using llm_models_absolute_path: {mount_path}")
        except ValueError:
            # Fallback to model parent dir if not configured
            mount_path = model_path.parent
            warning_log(f"llm_models_absolute_path not configured, using model parent: {mount_path}")
    
    # Calculate relative model path inside container
    if models_base_path:
        rel_path = model_path.relative_to(models_base_path)
        docker_model_path = f"/models/{rel_path.as_posix()}"
    else:
        docker_model_path = f"/models/{model_name}"
    
    # Calculate mmproj path inside container (if available)
    docker_mmproj_path = None
    if detected_mmproj:
        if models_base_path:
            try:
                mmproj_rel = detected_mmproj.relative_to(models_base_path)
                docker_mmproj_path = f"/models/{mmproj_rel.as_posix()}"
            except ValueError:
                # mmproj not under models_base, use filename only
                docker_mmproj_path = f"/models/{detected_mmproj.name}"
        else:
            docker_mmproj_path = f"/models/{detected_mmproj.name}"
    
    # Convert to Docker-compatible path format
    mount_posix = mount_path.as_posix()
    
    # Log GPU info
    gpu_info = get_gpu_info()
    if gpu_info["gpu_count"] > 0:
        for gpu in gpu_info["gpus"]:
            debug_log(f"GPU {gpu['index']}: {gpu['name']} ({gpu['vram_gb']}GB)")
    
    # Log model size
    model_size = estimate_model_size_gb(str(model_path))
    if model_size > 0:
        msg_log(f"Model size: ~{model_size}GB")
    
    # Log vision support
    if docker_mmproj_path:
        msg_log(f"  → Vision support: ENABLED (mmproj: {detected_mmproj.name})")
    else:
        msg_log(f"  → Vision support: disabled (no mmproj file found)")
    
    # Build docker command
    docker_cmd = [
        "run",
        "-d",  # Detached
        "--name", container_name,
        "--gpus", "all",
        "-v", f"{mount_posix}:/models",
        "-p", f"{port}:8080",
        LLAMACPP_DOCKER_IMAGE,
        "-m", docker_model_path,
        "--host", "0.0.0.0",
        "--port", "8080",
        "-c", str(ctx_size),
        "-ngl", str(n_gpu_layers),
    ]
    
    # Add mmproj for vision support
    if docker_mmproj_path:
        docker_cmd.extend(["--mmproj", docker_mmproj_path])
    
    debug_log(f"Docker command: docker {' '.join(docker_cmd)}")
    
    # Track container name for error diagnosis
    _set_last_container(container_name)
    
    success, output = _run_docker_cmd(docker_cmd, timeout=60)
    
    if success:
        container_id = output.strip()
        msg_log(f"✓ Container created: {container_id[:12]}")
        
        # Save container mapping
        save_llamacpp_model_container(model_name, container_id)
        
        if wait_for_ready:
            startup_timeout = get_llamacpp_startup_timeout()
            return wait_for_llamacpp_ready(port, timeout=startup_timeout, container_name=container_name)
        return True
    else:
        error_log(f"Failed to start container: {output}")
        _set_failure_reason(f"Docker container creation failed: {output}")
        return False


def stop_llamacpp_container(model_name: str = None) -> bool:
    # Stop llama.cpp container.
    #
    # Args:
    #     model_name: Specific model container to stop, or None for all
    #
    # Returns:
    #     bool: True if stopped successfully
    if model_name:
        containers = load_llamacpp_model_containers()
        if model_name in containers:
            container_id = containers[model_name]["container_id"]
            success, _ = _run_docker_cmd(["stop", container_id])
            return success
        return True
    else:
        # Stop all llama.cpp containers
        for container_id in get_running_llamacpp_containers():
            _run_docker_cmd(["stop", container_id])
        return True


def remove_llamacpp_container(model_name: str = None) -> bool:
    # Remove llama.cpp container.
    if model_name:
        containers = load_llamacpp_model_containers()
        if model_name in containers:
            container_id = containers[model_name]["container_id"]
            _run_docker_cmd(["rm", "-f", container_id])
        return True
    else:
        # Remove all llama.cpp containers
        success, output = _run_docker_cmd(["ps", "-aq", "-f", f"name={LLAMACPP_CONTAINER_PREFIX}"])
        if success and output:
            for container_id in output.strip().split('\n'):
                _run_docker_cmd(["rm", "-f", container_id])
        return True


# Module-level variable to track last failure reason
_last_failure_reason = None
_last_container_name = None  # Track container for error diagnosis


def get_last_failure_reason() -> Optional[str]:
    # Get the last failure reason for better error messages.
    global _last_failure_reason
    return _last_failure_reason


def _set_failure_reason(reason: str):
    # Set the last failure reason.
    global _last_failure_reason
    _last_failure_reason = reason


def _set_last_container(container_name: str):
    # Track the last container name for error diagnosis.
    global _last_container_name
    _last_container_name = container_name


def wait_for_llamacpp_ready(port: int = LLAMACPP_DEFAULT_PORT, timeout: int = 120, container_name: str = None) -> bool:
    # Wait for llama.cpp server to be ready.
    global _last_failure_reason, _last_container_name
    url = f"http://localhost:{port}/health"
    
    # Use provided container name or the last tracked one
    diag_container = container_name or _last_container_name
    
    msg_log(f"Waiting for llama.cpp to be ready (timeout: {timeout}s)...")
    
    start_time = time.time()
    poll_interval = 3
    
    while time.time() - start_time < timeout:
        # Check if container is still running
        running_containers = get_running_llamacpp_containers()
        if not running_containers:
            warning_log("llama.cpp container stopped unexpectedly")
            # Use centralized error handler to diagnose
            if diag_container:
                error = docker_error_handler.diagnose_llamacpp_error(diag_container, timeout_occurred=False)
                _set_failure_reason(docker_error_handler.format_error_message(error))
            else:
                _set_failure_reason("Container stopped unexpectedly - check docker logs for errors")
            return False
        
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                elapsed = time.time() - start_time
                msg_log(f"✓ llama.cpp ready in {elapsed:.1f}s")
                _last_failure_reason = None  # Clear on success
                return True
        except requests.exceptions.RequestException:
            pass
        
        elapsed = int(time.time() - start_time)
        if elapsed % 15 == 0 and elapsed > 0:
            msg_log(f"Still waiting for llama.cpp... ({elapsed}s)")
        
        time.sleep(poll_interval)
    
    # Timeout occurred - use centralized error handler to diagnose
    warning_log(f"llama.cpp did not become ready within {timeout}s")
    if diag_container:
        error = docker_error_handler.diagnose_llamacpp_error(diag_container, timeout_occurred=True)
        _set_failure_reason(docker_error_handler.format_error_message(error))
        # Log more details for debugging
        if error.raw_log:
            debug_log(f"Container log excerpt: {error.raw_log[:300]}")
    else:
        _set_failure_reason(f"Server startup timeout ({timeout}s) - model may be too large or GPU memory insufficient")
    return False


# ==============================================================================
# GENERATION API
# ==============================================================================

def generate_llamacpp(
    smart_lm_instance,
    prompt: str,
    image_paths: List[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    seed: int = -1,
    repetition_penalty: float = 1.0,
    llm_mode: str = None,
) -> tuple:
    # Generate text using llama.cpp Docker server.
    #
    # Compatible interface with generate_ollama for SmartLoader v2.
    #
    # Args:
    #     smart_lm_instance: LlamaCppWrapper instance
    #     prompt: Text prompt
    #     image_paths: Optional list of image file paths for vision
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Top-p sampling
    #     top_k: Top-k sampling (not directly supported, ignored)
    #     seed: Random seed (-1 for random)
    #     repetition_penalty: Repetition penalty
    #     llm_mode: LLM mode for text-only generation (for API compatibility)
    #
    # Returns:
    #     tuple: (result_text, data_dict)
    
    config = _get_llamacpp_config()
    port = config.get("port", LLAMACPP_DEFAULT_PORT)
    
    # Build messages in OpenAI format
    content = []
    
    # Add images if provided (vision support)
    if image_paths:
        for img_path in image_paths:
            try:
                with open(img_path, 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}
                })
            except Exception as e:
                warning_log(f"Failed to load image {img_path}: {e}")
    
    # Add text prompt
    content.append({"type": "text", "text": prompt})
    
    messages = [{"role": "user", "content": content}]
    
    # llama.cpp server supports OpenAI-compatible endpoint
    url = f"http://localhost:{port}/v1/chat/completions"
    
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
    }
    
    if repetition_penalty != 1.0:
        payload["repeat_penalty"] = repetition_penalty
    
    if seed >= 0:
        payload["seed"] = seed
    
    request_timeout = get_llamacpp_request_timeout()
    
    try:
        debug_log(f"Sending request to llama.cpp: {url}")
        response = requests.post(url, json=payload, timeout=request_timeout)
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            # Clean up whitespace
            result = result.strip()
            
            # Fix common UTF-8 encoding artifacts (mojibake)
            encoding_fixes = {
                'âĢĻ': "'",   # Right single quotation mark (U+2019)
                'âĢľ': '"',   # Left double quotation mark (U+201C)
                'âĢĿ': '"',   # Right double quotation mark (U+201D)
                'âĢĺ': "'",   # Left single quotation mark (U+2018)
                'âĢ"': '—',   # Em dash (U+2014)
                'âĢ"': '–',   # En dash (U+2013)
                'âĢ¦': '…',   # Horizontal ellipsis (U+2026)
            }
            for wrong, correct in encoding_fixes.items():
                result = result.replace(wrong, correct)
            
            # Strip thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking, DeepSeek-R1)
            from .common import strip_thinking_tags
            result, _ = strip_thinking_tags(result)
            
            msg_log(f"✓ Generated {len(result)} chars")
            return result, {"usage": data.get("usage", {})}
        else:
            error_text = response.text
            error_log(f"llama.cpp API error: {response.status_code} - {error_text}")
            
            # Check for context overflow error and provide helpful message
            if response.status_code == 400 and "exceed_context_size" in error_text:
                import json as json_module
                try:
                    error_data = json_module.loads(error_text)
                    error_info = error_data.get("error", {})
                    n_prompt = error_info.get("n_prompt_tokens", 0)
                    n_ctx = error_info.get("n_ctx", 0)
                    excess = n_prompt - n_ctx if n_prompt and n_ctx else 0
                    
                    raise RuntimeError(
                        f"Context overflow: {n_prompt:,} tokens > {n_ctx:,} max context\n\n"
                        f"Each image uses ~2,000-3,000 tokens. You have {excess:,} tokens over the limit.\n\n"
                        f"Solutions:\n"
                        f"  • Reduce number of images/frames (try {max(1, (n_prompt - n_ctx) // 2500)} fewer)\n"
                        f"  • Increase context_size widget (if your GPU has enough VRAM)\n"
                        f"  • Use a shorter prompt"
                    )
                except json_module.JSONDecodeError:
                    pass
            
            return f"Error: llama.cpp returned {response.status_code}", {}
            
    except requests.exceptions.Timeout:
        error_log(f"llama.cpp request timed out ({request_timeout}s)")
        return "Error: Request timed out", {}
    except Exception as e:
        error_log(f"llama.cpp request failed: {e}")
        return f"Error: {str(e)}", {}


def generate_with_llamacpp(
    messages: List[Dict[str, Any]],
    port: int = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
    stop: List[str] = None,
) -> Optional[str]:
    # Generate text using llama.cpp server.
    #
    # Uses OpenAI-compatible endpoint.
    #
    # Args:
    #     messages: List of message dicts with 'role' and 'content'
    #     port: Server port
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Top-p sampling
    #     stop: Stop sequences
    #
    # Returns:
    #     Generated text or None on error
    config = _get_llamacpp_config()
    port = port or config.get("port", LLAMACPP_DEFAULT_PORT)
    
    # llama.cpp server supports OpenAI-compatible endpoint
    url = f"http://localhost:{port}/v1/chat/completions"
    
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
    }
    
    if stop:
        payload["stop"] = stop
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            error_log(f"llama.cpp API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        error_log("llama.cpp request timed out")
        return None
    except Exception as e:
        error_log(f"llama.cpp request failed: {e}")
        return None


def generate_completion_llamacpp(
    prompt: str,
    port: int = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
    stop: List[str] = None,
) -> Optional[str]:
    # Generate text completion (non-chat) using llama.cpp server.
    #
    # Args:
    #     prompt: Text prompt
    #     port: Server port
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Top-p sampling
    #     stop: Stop sequences
    #
    # Returns:
    #     Generated text or None on error
    config = _get_llamacpp_config()
    port = port or config.get("port", LLAMACPP_DEFAULT_PORT)
    
    # Use completion endpoint
    url = f"http://localhost:{port}/completion"
    
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
    }
    
    if stop:
        payload["stop"] = stop
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("content", "")
        else:
            error_log(f"llama.cpp completion error: {response.status_code}")
            return None
            
    except Exception as e:
        error_log(f"llama.cpp completion failed: {e}")
        return None


# ==============================================================================
# HIGH-LEVEL API
# ==============================================================================

def load_gguf_model(
    model_path: str,
    models_base_path: str = None,
    mmproj_path: str = None,
    n_gpu_layers: int = -1,
    ctx_size: int = 8192,
) -> bool:
    # Load a GGUF model using llama.cpp Docker.
    #
    # Args:
    #     model_path: Path to GGUF file
    #     models_base_path: Base models directory
    #     mmproj_path: Path to mmproj file for vision (auto-detected if None)
    #     n_gpu_layers: GPU layers (-1 = all)
    #     ctx_size: Context size
    #
    # Returns:
    #     bool: True if model loaded successfully
    return start_llamacpp_container(
        model_path=model_path,
        models_base_path=models_base_path,
        mmproj_path=mmproj_path,
        n_gpu_layers=n_gpu_layers,
        ctx_size=ctx_size,
        wait_for_ready=True,
    )


def get_llamacpp_server_status() -> Dict[str, Any]:
    # Get llama.cpp server status.
    config = _get_llamacpp_config()
    port = config.get("port", LLAMACPP_DEFAULT_PORT)
    
    result = {
        "running": False,
        "port": port,
        "model": None,
    }
    
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        if response.status_code == 200:
            result["running"] = True
            
            # Try to get model info
            props_response = requests.get(f"http://localhost:{port}/props", timeout=2)
            if props_response.status_code == 200:
                props = props_response.json()
                result["model"] = props.get("model_path", "unknown")
                
    except requests.exceptions.RequestException:
        pass
    
    return result


# ==============================================================================
# UNIFIED LOAD API (for SmartLoader v2)
# ==============================================================================

def load_llamacpp(
    model_path: str,
    model_type: str = "llm",
    n_gpu_layers: int = -1,
    ctx_size: int = 8192,
    models_base_path: str = None,
    mmproj_path: str = None,
    **kwargs,
) -> Dict[str, Any]:
    # Load a GGUF model via llama.cpp Docker for SmartLoader v2 integration.
    #
    # Args:
    #     model_path: Path to GGUF file
    #     model_type: Type of model ("llm", "vlm")
    #     n_gpu_layers: GPU layers (-1 = all)
    #     ctx_size: Context size
    #     models_base_path: Base models directory
    #     mmproj_path: Path to mmproj file for vision (auto-detected if None)
    #     **kwargs: Additional configuration options
    #
    # Returns:
    #     Dict with client info: {"client": None, "model_name": str, "base_url": str, "backend": str}
    config = _get_llamacpp_config()
    port = config.get("port", LLAMACPP_DEFAULT_PORT)
    base_url = f"http://localhost:{port}"
    
    # Extract model name from path
    model_name = Path(model_path).stem if model_path else "unknown"
    
    # Load the model (starts container if needed)
    if not load_gguf_model(
        model_path=model_path,
        models_base_path=models_base_path,
        mmproj_path=mmproj_path,
        n_gpu_layers=n_gpu_layers,
        ctx_size=ctx_size,
    ):
        # Get specific failure reason if available
        failure_reason = get_last_failure_reason()
        if failure_reason:
            raise RuntimeError(f"Failed to load GGUF model {model_path} in llama.cpp Docker: {failure_reason}")
        else:
            raise RuntimeError(f"Failed to load GGUF model {model_path} in llama.cpp Docker")
    
    msg_log(f"✓ llama.cpp Docker ready: {model_name} @ {base_url}")
    
    return {
        "client": None,  # llama.cpp uses HTTP API, no client object
        "model_name": model_name,
        "base_url": base_url,
        "backend": "llamacpp_docker",
        "model_type": model_type,
    }


# ==============================================================================
# PLATFORM DETECTION
# ==============================================================================

import platform
import os

IS_WINDOWS = platform.system() == "Windows"


# ==============================================================================
# AVAILABILITY CHECK & DOCKER DAEMON MANAGEMENT
# ==============================================================================

LLAMACPP_DOCKER_AVAILABLE = False
DOCKER_DAEMON_RUNNING = False


def is_llamacpp_docker_available() -> bool:
    # Check if llama.cpp Docker is available.
    success, _ = _run_docker_cmd(["--version"])
    return success


def is_docker_daemon_running() -> bool:
    # Check if Docker daemon is running and responsive.
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            text=True,
            encoding='utf-8',
            errors='replace',  # Handle non-UTF8 bytes gracefully on Windows
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0
    except Exception:
        return False


def start_docker_daemon(wait_timeout: int = 60) -> bool:
    # Attempt to start Docker Desktop on Windows.
    #
    # Args:
    #     wait_timeout: Maximum seconds to wait for Docker to start
    #
    # Returns:
    #     bool: True if Docker daemon is now running
    global DOCKER_DAEMON_RUNNING
    
    if is_docker_daemon_running():
        DOCKER_DAEMON_RUNNING = True
        return True
    
    if not IS_WINDOWS:
        warning_log("Auto-start only supported on Windows")
        return False
    
    # Common Docker Desktop paths on Windows
    docker_paths = [
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe"),
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    ]
    
    docker_exe = None
    for path in docker_paths:
        if os.path.exists(path):
            docker_exe = path
            break
    
    if not docker_exe:
        warning_log("Docker Desktop executable not found")
        return False
    
    msg_log("Starting Docker Desktop...")
    
    try:
        # Start Docker Desktop (detached, no window)
        subprocess.Popen(
            [docker_exe],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        # Wait for daemon to be ready
        msg_log(f"Waiting for Docker daemon to start (up to {wait_timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            if is_docker_daemon_running():
                DOCKER_DAEMON_RUNNING = True
                msg_log("✓ Docker daemon started successfully")
                return True
            time.sleep(2)
        
        warning_log(f"⚠ Docker daemon did not start within {wait_timeout}s")
        return False
        
    except Exception as e:
        error_log(f"Failed to start Docker Desktop: {e}")
        return False


def ensure_docker_running() -> bool:
    # Ensure Docker is running. Start it if needed.
    #
    # Returns:
    #     bool: True if Docker is available and running
    global DOCKER_DAEMON_RUNNING
    
    if not LLAMACPP_DOCKER_AVAILABLE:
        return False
    
    if DOCKER_DAEMON_RUNNING or is_docker_daemon_running():
        DOCKER_DAEMON_RUNNING = True
        return True
    
    # Try to start Docker (Windows only)
    if IS_WINDOWS:
        return start_docker_daemon()
    
    return False


# Check on module load
LLAMACPP_DOCKER_AVAILABLE = is_llamacpp_docker_available()
if LLAMACPP_DOCKER_AVAILABLE:
    DOCKER_DAEMON_RUNNING = is_docker_daemon_running()
    if DOCKER_DAEMON_RUNNING:
        debug_log("Docker available for llama.cpp (daemon running)")
    else:
        debug_log("Docker available for llama.cpp (will auto-start when needed)")

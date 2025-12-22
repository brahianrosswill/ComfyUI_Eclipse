# MIT License
# 
# Copyright (c) 2025 RenderVoid
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# SGLang Docker Integration for Eclipse SmartLM
# =============================================
#
# Alternative to vLLM for high-performance LLM inference via Docker.
# SGLang (from LMSYS team) uses RadixAttention for efficient KV cache reuse.
#
# Features:
# - OpenAI-compatible API (same interface as vLLM)
# - Better throughput for batch processing
# - RadixAttention for KV cache reuse
# - FlashInfer attention backend
# - Supports FP8 quantized models natively
#
# Docker Image: lmsysorg/sglang:latest
# Default Port: 30000
# API Endpoint: http://localhost:30000/v1

from __future__ import annotations

import json
import os
import subprocess
import time
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .logger import log

# ==============================================================================
# LOCAL LOGGING HELPERS (prefix: "SGLang Docker")
# ==============================================================================

def debug_log(message: str):
    # Print debug message only when log_level is 'debug'.
    log.debug("SGLang Docker", message)


def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning("SGLang Docker", message)


def msg_log(message: str):
    # Print regular message (always shown).
    log.msg("SGLang Docker", message)


def error_log(message: str):
    # Print error message (always shown).
    log.error("SGLang Docker", message)


# ==============================================================================
# PLATFORM DETECTION
# ==============================================================================

import platform
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"


# ==============================================================================
# DOCKER AVAILABILITY DETECTION (FAST FAIL)
# ==============================================================================

def _check_docker_installed() -> Tuple[bool, Optional[str]]:
    # Check if Docker CLI is installed and return version.
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, version
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False, None


DOCKER_AVAILABLE, DOCKER_VERSION = _check_docker_installed()


def is_docker_daemon_running() -> bool:
    # Check if Docker daemon is running.
    if not DOCKER_AVAILABLE:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


DOCKER_DAEMON_RUNNING = is_docker_daemon_running()


def is_docker_available() -> bool:
    # Quick check if Docker is installed.
    return DOCKER_AVAILABLE


def is_sglang_docker_available() -> bool:
    # Check if SGLang can run via Docker (requires Docker + GPU support).
    return DOCKER_AVAILABLE


def start_docker_daemon() -> bool:
    # Attempt to start Docker daemon (platform-specific).
    if not DOCKER_AVAILABLE:
        warning_log("Docker not installed")
        return False
    
    if is_docker_daemon_running():
        return True
    
    msg_log("Attempting to start Docker daemon...")
    
    try:
        if IS_WINDOWS:
            # Try Docker Desktop on Windows
            docker_desktop_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                os.path.expanduser(r"~\AppData\Local\Docker\Docker Desktop.exe"),
            ]
            for path in docker_desktop_paths:
                if os.path.exists(path):
                    subprocess.Popen([path], shell=True)
                    msg_log("Started Docker Desktop, waiting for daemon...")
                    break
            else:
                warning_log("Docker Desktop not found in standard locations")
                return False
                
        elif IS_LINUX:
            # Try systemctl on Linux
            subprocess.run(["sudo", "systemctl", "start", "docker"], timeout=30)
            
        elif IS_MACOS:
            # Try opening Docker app on macOS
            subprocess.run(["open", "-a", "Docker"])
            
        # Wait for daemon to be ready
        for i in range(30):  # 30 second timeout
            if is_docker_daemon_running():
                msg_log("Docker daemon is now running")
                return True
            time.sleep(1)
            if i % 5 == 0:
                msg_log(f"Waiting for Docker daemon... ({i}s)")
        
        warning_log("Docker daemon did not start within timeout")
        return False
        
    except Exception as e:
        warning_log(f"Failed to start Docker daemon: {e}")
        return False


def ensure_docker_running() -> bool:
    # Ensure Docker daemon is running, attempt to start if not.
    global DOCKER_DAEMON_RUNNING
    
    if is_docker_daemon_running():
        DOCKER_DAEMON_RUNNING = True
        return True
    
    DOCKER_DAEMON_RUNNING = False
    
    if start_docker_daemon():
        DOCKER_DAEMON_RUNNING = True
        return True
    
    return False


# ==============================================================================
# GPU DETECTION
# ==============================================================================

def get_available_gpus() -> List[int]:
    # Get list of available NVIDIA GPU indices.
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return [int(idx.strip()) for idx in result.stdout.strip().split('\n') if idx.strip()]
    except:
        pass
    return []


def get_gpu_memory(gpu_idx: int = 0) -> Tuple[int, int]:
    # Get (used_mb, total_mb) for a GPU.
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--id={gpu_idx}", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) == 2:
                return int(parts[0].strip()), int(parts[1].strip())
    except:
        pass
    return 0, 0


def get_free_gpu_memory_mb(gpu_idx: int = 0) -> int:
    # Get free GPU memory in MB.
    used, total = get_gpu_memory(gpu_idx)
    return total - used if total > 0 else 0


# ==============================================================================
# CONFIGURATION MANAGEMENT
# ==============================================================================

# Configuration file path
CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "docker_config.json"

# Default SGLang configuration
DEFAULT_SGLANG_CONFIG = {
    "sglang": {
        "enabled": True,
        "url": "http://localhost:30000/v1",
        "docker_image": "lmsysorg/sglang:latest",
        "auto_start": True,
        "stop_after_generation": False,
        "timeout": 5,
        "request_timeout": 600,
        "container_name_prefix": "eclipse_sglang",
        "gpu_memory_utilization": 0.6,
        "tp_size": 1,  # Tensor parallelism
        "dp_size": 1,  # Data parallelism
        "port": 30000,
    },
    "paths": {
        "models_base": "",
    },
    "model_containers": {}
}


def load_docker_config() -> Dict[str, Any]:
    # Load Docker config from file, or create default if not exists.
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            # Ensure sglang section exists
            if "sglang" not in config:
                config["sglang"] = DEFAULT_SGLANG_CONFIG["sglang"].copy()
                save_docker_config(config)
            return config
        except Exception as e:
            warning_log(f"Error loading docker_config.json: {e}")
    
    # Create default config
    save_docker_config(DEFAULT_SGLANG_CONFIG)
    return DEFAULT_SGLANG_CONFIG.copy()


def save_docker_config(config: Dict[str, Any]) -> bool:
    # Save Docker config to file.
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        error_log(f"Error saving docker_config.json: {e}")
        return False


def get_sglang_config() -> Dict[str, Any]:
    # Get SGLang-specific configuration.
    config = load_docker_config()
    return config.get("sglang", DEFAULT_SGLANG_CONFIG["sglang"].copy())


def get_paths_config() -> Dict[str, Any]:
    # Get paths configuration.
    config = load_docker_config()
    return config.get("paths", {})


def is_sglang_enabled() -> bool:
    # Check if SGLang backend is enabled.
    return get_sglang_config().get("enabled", True)


def get_sglang_url() -> str:
    # Get SGLang API URL.
    return get_sglang_config().get("url", "http://localhost:30000/v1")


def get_sglang_docker_image() -> str:
    # Get SGLang Docker image name.
    return get_sglang_config().get("docker_image", "lmsysorg/sglang:latest")


def get_sglang_port() -> int:
    # Get SGLang port.
    return get_sglang_config().get("port", 30000)


def get_sglang_request_timeout() -> int:
    # Get request timeout for SGLang API calls.
    return get_sglang_config().get("request_timeout", 600)


def get_models_base_path() -> str:
    # Get base path for models.
    config = load_docker_config()
    return config.get("paths", {}).get("models_base", "")


def set_models_base_path(path: str) -> bool:
    # Set base path for models.
    config = load_docker_config()
    if "paths" not in config:
        config["paths"] = {}
    config["paths"]["models_base"] = path
    return save_docker_config(config)


def set_sglang_auto_start(enabled: bool) -> bool:
    # Enable/disable auto-start feature.
    config = load_docker_config()
    if "sglang" not in config:
        config["sglang"] = DEFAULT_SGLANG_CONFIG["sglang"].copy()
    config["sglang"]["auto_start"] = enabled
    return save_docker_config(config)


def set_sglang_stop_after_generation(enabled: bool) -> bool:
    # Enable/disable auto-stop after generation.
    config = load_docker_config()
    if "sglang" not in config:
        config["sglang"] = DEFAULT_SGLANG_CONFIG["sglang"].copy()
    config["sglang"]["stop_after_generation"] = enabled
    return save_docker_config(config)


# ==============================================================================
# MODEL-CONTAINER TRACKING
# ==============================================================================

def get_container_for_model(model_name: str) -> Optional[Dict[str, Any]]:
    # Get container info for a model (for reuse).
    config = load_docker_config()
    containers = config.get("sglang_model_containers", {})
    return containers.get(model_name)


def save_container_for_model(model_name: str, container_info: Dict[str, Any]) -> bool:
    # Save container info for a model.
    config = load_docker_config()
    if "sglang_model_containers" not in config:
        config["sglang_model_containers"] = {}
    config["sglang_model_containers"][model_name] = container_info
    return save_docker_config(config)


def update_container_last_used(model_name: str) -> bool:
    # Update last_used timestamp for a container.
    config = load_docker_config()
    containers = config.get("sglang_model_containers", {})
    if model_name in containers:
        containers[model_name]["last_used"] = time.time()
        return save_docker_config(config)
    return False


def cleanup_stale_containers(max_age_hours: int = 24) -> int:
    # Remove container entries older than max_age_hours.
    config = load_docker_config()
    containers = config.get("sglang_model_containers", {})
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    removed = 0
    for model_name in list(containers.keys()):
        last_used = containers[model_name].get("last_used", 0)
        if now - last_used > max_age_seconds:
            del containers[model_name]
            removed += 1
    
    if removed > 0:
        save_docker_config(config)
    return removed


# ==============================================================================
# CONTAINER MANAGEMENT
# ==============================================================================

def is_sglang_container_running() -> bool:
    # Check if any SGLang container is running.
    containers = get_running_sglang_containers()
    return len(containers) > 0


def get_running_sglang_containers() -> List[Dict[str, str]]:
    # Get list of running SGLang containers.
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=eclipse_sglang", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            containers = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append({
                        "id": parts[0],
                        "name": parts[1],
                        "status": parts[2]
                    })
            return containers
    except Exception as e:
        debug_log(f"Error getting containers: {e}")
    return []


def is_container_exists(container_name: str) -> bool:
    # Check if a container exists (running or stopped).
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return container_name in result.stdout
    except:
        return False


def is_container_running(container_name: str) -> bool:
    # Check if a specific container is running.
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--filter", "status=running", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return container_name in result.stdout
    except:
        return False


def start_existing_container(container_name: str) -> bool:
    # Start an existing stopped container.
    try:
        msg_log(f"Starting existing container: {container_name}")
        result = subprocess.run(
            ["docker", "start", container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            msg_log(f"Container {container_name} started")
            return True
        warning_log(f"Failed to start container: {result.stderr}")
        return False
    except Exception as e:
        warning_log(f"Error starting container: {e}")
        return False


def stop_sglang_container(container_name: str = None) -> bool:
    # Stop SGLang container(s).
    try:
        if container_name:
            containers = [{"name": container_name}]
        else:
            containers = get_running_sglang_containers()
        
        if not containers:
            debug_log("No SGLang containers to stop")
            return True
        
        for container in containers:
            name = container.get("name", container_name)
            msg_log(f"Stopping container: {name}")
            result = subprocess.run(
                ["docker", "stop", name],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                msg_log(f"Container {name} stopped")
            else:
                warning_log(f"Failed to stop {name}: {result.stderr}")
        
        return True
    except Exception as e:
        warning_log(f"Error stopping containers: {e}")
        return False


def remove_sglang_container(container_name: str) -> bool:
    # Remove an SGLang container.
    try:
        msg_log(f"Removing container: {container_name}")
        result = subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        warning_log(f"Error removing container: {e}")
        return False


def wait_for_sglang_ready(url: str, timeout: int = 300, poll_interval: int = 5) -> bool:
    # Wait for SGLang server to be ready.
    import requests
    
    start_time = time.time()
    health_url = url.rstrip('/v1') + '/health'
    
    msg_log(f"Waiting for SGLang to be ready (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        # Check if container is still running before checking health
        if not is_sglang_container_running():
            error_log("Container stopped unexpectedly! Check 'docker logs eclipse_sglang_*' for details.")
            return False
        
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                elapsed = time.time() - start_time
                msg_log(f"✓ SGLang ready in {elapsed:.1f}s")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            debug_log(f"Health check error: {e}")
        
        elapsed = int(time.time() - start_time)
        if elapsed % 15 == 0 and elapsed > 0:
            msg_log(f"Still waiting for SGLang... ({elapsed}s)")
        
        time.sleep(poll_interval)
    
    warning_log(f"SGLang did not become ready within {timeout}s")
    return False


# ==============================================================================
# SGLANG CONTAINER STARTUP
# ==============================================================================

def start_sglang_container(
    model_path: str,
    quantization: str = None,
    context_size: int = None,
    gpu_ids: List[int] = None,
    tp_size: int = None,
    dp_size: int = None,
) -> Optional[str]:
    # Start an SGLang container for a model.
    #
    # Args:
    #     model_path: Path to the model folder
    #     quantization: Quantization method (fp8, awq, gptq, or None)
    #     context_size: Maximum context length (max_model_len)
    #     gpu_ids: List of GPU indices to use
    #     tp_size: Tensor parallelism size
    #     dp_size: Data parallelism size
    #
    # Returns:
    #     Container name if successful, None otherwise
    if not ensure_docker_running():
        error_log("Docker is not running")
        return None
    
    sglang_config = get_sglang_config()
    model_name = Path(model_path).name
    
    # Generate container name
    safe_name = model_name.lower().replace(" ", "_").replace(".", "_")[:30]
    container_name = f"{sglang_config.get('container_name_prefix', 'eclipse_sglang')}_{safe_name}"
    
    # Check if we can reuse existing container
    container_info = get_container_for_model(model_name)
    if container_info:
        existing_name = container_info.get("container_name")
        port = container_info.get("port", get_sglang_port())
        if existing_name and is_container_running(existing_name):
            msg_log(f"Reusing running container: {existing_name}")
            update_container_last_used(model_name)
            return existing_name
        elif existing_name and is_container_exists(existing_name):
            if start_existing_container(existing_name):
                # Wait for SGLang to be ready after restart
                url = f"http://localhost:{port}/v1"
                msg_log("Waiting for SGLang to be ready after restart...")
                if wait_for_sglang_ready(url, timeout=120):
                    update_container_last_used(model_name)
                    return existing_name
                else:
                    warning_log("Container restarted but SGLang not ready, will recreate")
                    remove_sglang_container(existing_name)
    
    # Stop any existing SGLang containers (single model at a time for VRAM)
    stop_sglang_container()
    
    # Check GPU memory
    free_mem = get_free_gpu_memory_mb(0)
    if free_mem < 4000:  # Require at least 4GB free
        warning_log(f"Low GPU memory: {free_mem}MB free. Model may not load.")
    
    # Build docker run command
    docker_image = get_sglang_docker_image()
    port = get_sglang_port()
    gpu_util = sglang_config.get("gpu_memory_utilization")
    
    # Determine model path for container
    models_base = get_models_base_path()
    if models_base and model_path.startswith(models_base):
        # Model is within configured base path
        relative_path = os.path.relpath(model_path, models_base)
        container_model_path = f"/models/{relative_path}"
        volume_mount = f"{models_base}:/models"
    else:
        # Mount model directory directly
        model_dir = os.path.dirname(model_path)
        container_model_path = f"/models/{model_name}"
        volume_mount = f"{model_dir}:/models"
    
    # Handle Windows path conversion for Docker
    if IS_WINDOWS:
        # Convert Windows path to Docker-compatible format
        volume_mount = volume_mount.replace("\\", "/")
        # Convert drive letter (C: -> /c)
        if len(volume_mount) >= 2 and volume_mount[1] == ":":
            drive = volume_mount[0].lower()
            volume_mount = f"/{drive}{volume_mount[2:]}"
    
    # Build command
    tp = tp_size or sglang_config.get("tp_size", 1)
    dp = dp_size or sglang_config.get("dp_size", 1)
    
    cmd = [
        "docker", "run",
        "-d",  # Detached mode
        "--gpus", "all",
        "--name", container_name,
        "-p", f"{port}:{port}",
        "-v", volume_mount,
        "--shm-size", "16g",
        "--ipc", "host",
        docker_image,
        "python3", "-m", "sglang.launch_server",
        "--model-path", container_model_path,
        "--port", str(port),
        "--host", "0.0.0.0",
        "--mem-fraction-static", str(gpu_util),
        "--tp", str(tp),
        "--dp", str(dp),
    ]
    
    # Add quantization if specified
    if quantization:
        quant_lower = quantization.lower()
        if quant_lower == "fp8":
            cmd.extend(["--quantization", "fp8"])
        elif quant_lower == "awq":
            cmd.extend(["--quantization", "awq"])
        elif quant_lower == "gptq":
            cmd.extend(["--quantization", "gptq"])
    
    # Add context size if specified
    if context_size:
        cmd.extend(["--context-length", str(context_size)])
    
    # Log and execute
    msg_log(f"Starting SGLang container for: {model_name}")
    debug_log(f"Docker command: {' '.join(cmd)}")
    
    # Check if image exists, pull if needed
    try:
        check_image = subprocess.run(
            ["docker", "images", "-q", docker_image],
            capture_output=True,
            text=True,
            timeout=10
        )
        if not check_image.stdout.strip():
            msg_log(f"Pulling SGLang image: {docker_image} (this may take 5-10 minutes)...")
            msg_log("  Watch Docker Desktop or run 'docker pull lmsysorg/sglang:latest' for progress")
            # Don't capture output so user sees docker pull progress in terminal
            # Use Popen for non-blocking with timeout
            pull_process = subprocess.Popen(
                ["docker", "pull", docker_image],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            # Stream output line by line
            last_layer = ""
            while True:
                line = pull_process.stdout.readline()
                if not line and pull_process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    # Show layer progress updates
                    if "Pulling" in line or "Download" in line or "Pull complete" in line:
                        if line != last_layer:
                            msg_log(f"  {line[:80]}")
                            last_layer = line
            
            pull_process.wait(timeout=1800)
            if pull_process.returncode != 0:
                error_log(f"Failed to pull image (exit code {pull_process.returncode})")
                return None
            msg_log("✓ Image pulled successfully")
    except subprocess.TimeoutExpired:
        error_log("Image pull timed out (30 min limit)")
        return None
    except Exception as e:
        warning_log(f"Could not check/pull image: {e}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # Container creation should be fast after image is pulled
        )
        
        if result.returncode != 0:
            error_log(f"Failed to start container: {result.stderr}")
            return None
        
        container_id = result.stdout.strip()[:12]
        msg_log(f"Container started: {container_name} ({container_id})")
        
        # Wait for SGLang to be ready
        url = f"http://localhost:{port}/v1"
        if not wait_for_sglang_ready(url, timeout=300):
            error_log("SGLang failed to start within timeout")
            # Check container logs for errors
            log_result = subprocess.run(
                ["docker", "logs", "--tail", "50", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            if log_result.stdout:
                error_log(f"Container logs:\n{log_result.stdout[-1000:]}")
            stop_sglang_container(container_name)
            return None
        
        # Save container info for reuse
        save_container_for_model(model_name, {
            "container_name": container_name,
            "container_id": container_id,
            "model_path": model_path,
            "port": port,
            "last_used": time.time(),
            "quantization": quantization,
        })
        
        return container_name
        
    except subprocess.TimeoutExpired:
        error_log("Docker command timed out")
        return None
    except Exception as e:
        error_log(f"Error starting container: {e}")
        return None


def auto_start_sglang_for_model(
    model_path: str,
    config: Dict[str, Any] = None,
    quantization: str = None,
    context_size: int = None,
) -> bool:
    # Auto-start SGLang for a specific model.
    #
    # Args:
    #     model_path: Path to the model
    #     config: Optional config override
    #     quantization: Quantization method
    #     context_size: Context length
    #
    # Returns:
    #     True if container started successfully
    if config and not config.get("auto_start", True):
        debug_log("Auto-start disabled in config")
        return False
    
    container_name = start_sglang_container(
        model_path,
        quantization=quantization,
        context_size=context_size,
    )
    
    return container_name is not None


# ==============================================================================
# SGLANG MODEL LOADING & GENERATION
# ==============================================================================

def is_sglang_available() -> bool:
    # Check if SGLang server is running and accessible.
    try:
        if not is_sglang_enabled():
            return False
        
        url = get_sglang_url()
        timeout = get_sglang_config().get("timeout", 5)
        
        import requests
        response = requests.get(f"{url.rstrip('/v1')}/health", timeout=timeout)
        return response.status_code == 200
    except:
        return False


def is_sglang_serving_model(model_path: str) -> Optional[str]:
    # Check if SGLang server is serving the specified model.
    #
    # Args:
    #     model_path: Path to model folder or model name
    #
    # Returns:
    #     str: The model ID if found
    #     None: If server not running or model not found
    try:
        from openai import OpenAI
        
        if not is_sglang_enabled():
            return None
        
        url = get_sglang_url()
        timeout = get_sglang_config().get("timeout", 5)
        request_timeout = get_sglang_request_timeout()
        
        # Quick health check
        import requests
        response = requests.get(f"{url.rstrip('/v1')}/health", timeout=timeout)
        if response.status_code != 200:
            return None
        
        # Check models
        client = OpenAI(base_url=url, api_key="not-needed", timeout=request_timeout)
        models = client.models.list()
        available_models = [m.id for m in models.data]
        
        # Extract model name from path
        model_name = Path(model_path).name
        
        # Try to find matching model
        for available in available_models:
            if model_name in available or available in model_name:
                return available
        
        return None
        
    except Exception as e:
        debug_log(f"Error checking SGLang model: {e}")
        return None


def load_sglang(
    smart_lm_instance,
    template_name: str,
    model_path: str,
    quantization: str = None,
    context_size: int = None
) -> Optional[Dict[str, Any]]:
    # Load a model via SGLang Docker.
    #
    # This function is model-agnostic - works with any model supported by SGLang.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance
    #     template_name: Template name
    #     model_path: Full path to model folder
    #     quantization: Quantization method (fp8, awq, gptq, or None)
    #     context_size: Maximum context window size
    #
    # Returns:
    #     Dict with SGLang client info, or None if unavailable
    try:
        from openai import OpenAI
    except ImportError:
        warning_log("Requires openai package: pip install openai")
        return None
    
    if not is_sglang_docker_available():
        warning_log("SGLang not available (Docker not found)")
        return None
    
    if not ensure_docker_running():
        warning_log("Docker is not running and could not be started")
        return None
    
    sglang_config = get_sglang_config()
    url = get_sglang_url()
    
    # Check if SGLang is serving the correct model
    matched_model = is_sglang_serving_model(model_path)
    model_name = Path(model_path).name
    
    if not matched_model:
        # Try auto-start
        if sglang_config.get("auto_start", True):
            msg_log(f"Attempting auto-start for {model_name}...")
            try:
                if auto_start_sglang_for_model(model_path, sglang_config, quantization=quantization, context_size=context_size):
                    matched_model = is_sglang_serving_model(model_path)
                    if matched_model:
                        msg_log("✓ Auto-started successfully!")
                    else:
                        warning_log("Auto-start completed but model not detected")
                        return None
                else:
                    warning_log("Auto-start failed")
                    return None
            except Exception as e:
                warning_log(f"Auto-start error: {e}")
                return None
        
        if not matched_model:
            warning_log(f"Model '{model_name}' not found in SGLang server")
            return None
    
    # Model found - create client
    request_timeout = get_sglang_request_timeout()
    client = OpenAI(base_url=url, api_key="not-needed", timeout=request_timeout)
    
    # Update last used timestamp
    update_container_last_used(model_name)
    
    # Store SGLang client info
    if smart_lm_instance is not None:
        smart_lm_instance.sglang_client = client
        smart_lm_instance.sglang_model_name = matched_model
        smart_lm_instance.is_sglang = True
        smart_lm_instance.is_quantized = True
    
    debug_log("Using SGLang (Docker) backend")
    debug_log(f"Model: {matched_model}")
    msg_log("✓ SGLang optimized inference enabled")
    
    return {"mode": "sglang", "client": client, "model_name": matched_model}


def generate_sglang(
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
    # Generate text using SGLang API (OpenAI-compatible).
    #
    # This function is model-agnostic - works with ANY model served by SGLang.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance with sglang_client
    #     prompt: Text prompt
    #     image_paths: Optional list of image paths for vision models
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Nucleus sampling parameter
    #     top_k: Top-k sampling (not used by OpenAI API)
    #     seed: Random seed for reproducibility
    #     llm_mode: LLM mode key for few-shot examples
    #     instruction_template: Custom instruction template
    #     repetition_penalty: Repetition penalty (not used by OpenAI API)
    #
    # Returns:
    #     Generated text (or tuple (cleaned, raw) for LLM mode)
    debug_log(f"generate_sglang: model={getattr(smart_lm_instance, 'sglang_model_name', 'unknown')}")
    debug_log(f"  prompt={prompt[:100] if prompt else 'None'}...")
    debug_log(f"  image_paths={image_paths}")
    debug_log(f"  llm_mode={llm_mode}")
    
    client = smart_lm_instance.sglang_client
    model_name = smart_lm_instance.sglang_model_name
    
    # Build messages
    messages = []
    
    if image_paths and len(image_paths) > 0:
        # Vision + text (multimodal)
        system_prompt = None
        user_message = ""
        
        if "\n\n" in prompt:
            parts = prompt.split("\n\n", 1)
            system_prompt = parts[0].strip()
            if len(parts) > 1:
                remaining = parts[1].strip()
                if remaining.startswith("Additional context:"):
                    user_message = remaining.replace("Additional context:", "").strip()
                elif remaining:
                    user_message = remaining
        else:
            user_message = prompt
        
        # Build image data
        image_data = []
        for img_path in image_paths:
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')
                image_data.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    }
                })
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        content = image_data.copy()
        if user_message:
            content.append({"type": "text", "text": user_message})
        messages.append({"role": "user", "content": content})
        
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
    else:
        # Simple text only
        messages.append({"role": "user", "content": prompt})
    
    # Call SGLang API
    try:
        gen_start = time.time()
        msg_log("Starting generation...")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
        )
        
        gen_elapsed = time.time() - gen_start
        result = response.choices[0].message.content
        
        # Calculate tokens/sec
        usage_info = ""
        if hasattr(response, 'usage') and response.usage:
            tokens = response.usage.completion_tokens
            if tokens and gen_elapsed > 0:
                tok_per_sec = tokens / gen_elapsed
                usage_info = f" ({tokens} tokens, {tok_per_sec:.1f} tok/s)"
        
        msg_log(f"✓ Generation completed in {gen_elapsed:.1f}s{usage_info}")
        
        # Check if we should stop container after generation
        sglang_config = get_sglang_config()
        if sglang_config.get("stop_after_generation", False):
            stop_start = time.time()
            msg_log("Stopping container to free VRAM...")
            stop_sglang_container()
            stop_elapsed = time.time() - stop_start
            msg_log(f"✓ Container stopped in {stop_elapsed:.1f}s")
        
        # Strip thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking, DeepSeek-R1)
        from .common import strip_thinking_tags
        cleaned_result, raw_result = strip_thinking_tags(result)
        
        # For LLM mode, return tuple (cleaned, raw) for compatibility
        if llm_mode:
            return cleaned_result, raw_result
        
        return cleaned_result
        
    except Exception as e:
        error_msg = str(e)
        
        if "is not a multimodal model" in error_msg or "image" in error_msg.lower():
            model_name_short = Path(model_name).name if "/" in model_name else model_name
            error_log(f"Model '{model_name_short}' may not support vision")
            raise RuntimeError(
                f"Model '{model_name_short}' may not support image input.\n\n"
                "Try using a multimodal model or remove image input."
            ) from e
        
        error_log(f"SGLang generation error: {e}")
        raise


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================

__all__ = [
    # Platform detection
    'IS_WINDOWS',
    'IS_LINUX',
    'IS_MACOS',
    
    # Availability
    'DOCKER_AVAILABLE',
    'DOCKER_VERSION',
    'DOCKER_DAEMON_RUNNING',
    'is_docker_available',
    'is_docker_daemon_running',
    'is_sglang_docker_available',
    'start_docker_daemon',
    'ensure_docker_running',
    
    # Configuration
    'load_docker_config',
    'save_docker_config',
    'get_sglang_config',
    'get_paths_config',
    'get_sglang_url',
    'get_sglang_docker_image',
    'get_sglang_port',
    'get_models_base_path',
    'set_models_base_path',
    'set_sglang_auto_start',
    'set_sglang_stop_after_generation',
    
    # Container tracking
    'get_container_for_model',
    'save_container_for_model',
    'update_container_last_used',
    'cleanup_stale_containers',
    
    # Container management
    'is_sglang_container_running',
    'get_running_sglang_containers',
    'is_container_exists',
    'is_container_running',
    'start_existing_container',
    'stop_sglang_container',
    'remove_sglang_container',
    'start_sglang_container',
    'auto_start_sglang_for_model',
    
    # SGLang API
    'is_sglang_available',
    'is_sglang_serving_model',
    'wait_for_sglang_ready',
    'load_sglang',
    'generate_sglang',
]

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

# smartlm_gguf.py - Unified GGUF Backend (llama-cpp-python)
#
# Handles all GGUF format models:
# - Vision models with MMProj (QwenVL, LLaVA)
# - Text-only LLMs
#
# Uses llama-cpp-python library for inference

import gc
import torch
import base64
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from .smartlm_templates import get_dev_mode
from .logger import log


# ==============================================================================
# LOGGING HELPERS
# ==============================================================================

def debug_log(message: str):
    # Print debug message only when log_level is 'debug'.
    log.debug("GGUF", message)


def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning("GGUF", message)


def msg_log(message: str):
    # Print regular message (always shown).
    log.msg("GGUF", message)


def error_log(message: str):
    # Print error message (always shown).
    log.error("GGUF", message)


# ==============================================================================
# GGUF DETECTION
# ==============================================================================

def is_gguf_model(model_path: str) -> bool:
    # Check if model path is a GGUF format file.
    #
    # Detects GGUF models by:
    # - .gguf file extension
    # - Quantization markers (Q4_K_M, Q5_K_S, Q8_0, etc.)
    # - "gguf" in repo/path name
    #
    # Args:
    #     model_path: Path to the model file or directory
    #
    # Returns:
    #     True if this appears to be a GGUF model
    model_path_lower = model_path.lower()
    
    # Check .gguf extension
    has_gguf_ext = model_path_lower.endswith(".gguf")
    
    # Check for "gguf" in name (e.g., "model-GGUF" repos)
    has_gguf_name = "gguf" in model_path_lower
    
    # Check for GGUF quantization markers (Q4_K_M, Q5_K_S, Q8_0, etc.)
    gguf_quant_markers = [
        "_q4_", "_q5_", "_q6_", "_q8_", 
        "-q4-", "-q5-", "-q6-", "-q8-",
        "_k_m", "_k_s", "_k_l", 
        "q4_k", "q5_k", "q6_k", "q8_0", 
        ".q4_", ".q5_", ".q6_", ".q8_"
    ]
    has_gguf_quant = any(marker in model_path_lower for marker in gguf_quant_markers)
    
    return has_gguf_ext or has_gguf_name or has_gguf_quant


# ==============================================================================
# NOTE: v1 loading functions (load_gguf_model, _load_gguf_vision, _load_gguf_text)
# have been removed as they are no longer used.
# v2 uses smartlm_llamacpp_docker.py for GGUF model loading via Docker backend.
# The generation functions below are still used by v2.
# ==============================================================================


# ==============================================================================
# GENERATION - UNIFIED
# ==============================================================================

def generate_gguf(smart_lm_instance, model_type: str, image: Any, prompt: str,
                  max_tokens: int, temperature: float, top_p: float, top_k: int,
                  seed: int, repetition_penalty: float, frame_count: int = 8):
    # Unified GGUF generator.
    #
    # Args:
    #     smart_lm_instance: SmartLM instance with loaded model
    #     model_type: "vision" or "text"
    #     image: Image tensor (can be None for text-only)
    #     prompt: Input prompt
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Top-p (nucleus) sampling
    #     top_k: Top-k sampling
    #     seed: Random seed (or None)
    #     repetition_penalty: Repetition penalty
    #     frame_count: Max frames for video (vision only)
    #
    # Returns:
    #     Generated text string
    if model_type == "vision": 
        return _generate_gguf_vision(smart_lm_instance, image, prompt, max_tokens, 
                                     temperature, top_p, top_k, seed, 
                                     repetition_penalty, frame_count)
    else:
        return _generate_gguf_text(smart_lm_instance, prompt, max_tokens, 
                                   temperature, top_p, top_k, seed, 
                                   repetition_penalty)


def _generate_gguf_vision(smart_lm_instance, image: Any, prompt: str, max_tokens: int,
                          temperature: float, top_p: float, top_k: int, seed: Optional[int],
                          repetition_penalty: float = 1.0, frame_count: int = 8) -> str:
    # Generate with vision GGUF model using llama-cpp-python.
    #
    # Handles:
    # - Single images
    # - Video frames (multiple frames)
    # - Text-only prompts (no image)
    #
    # Note: LLaVA and similar vision models don't use system messages effectively.
    # The instruction must be placed in the user message WITH the image.
    
    # Set seed if provided (already clamped by JavaScript)
    if seed is not None:
        smart_lm_instance.model.set_seed(seed)
    
    # Parse prompt format: "system instruction\n\nuser_message" or just "prompt"
    # For vision models, the instruction goes in user message (not system message)
    instruction = ""
    user_message = ""  # Optional additional context from user_prompt widget
    
    if "\n\n" in prompt:
        # Split into instruction and user message
        instruction, user_message = prompt.split("\n\n", 1)
        instruction = instruction.strip()
        user_message = user_message.strip()
    else:
        # No separator - use entire prompt as instruction
        instruction = prompt.strip()
    
    if get_dev_mode():
        msg_log(f"[DEBUG GGUF] Instruction: {instruction[:80]}...")
        msg_log(f"[DEBUG GGUF] User message: {user_message[:80] if user_message else '(empty)'}...")
    
    # For vision GGUF models (LLaVA, etc.), instruction must be in user message
    # System messages are not well supported by these models
    messages: list[dict[str, Any]] = []
    
    # Build the full prompt text: instruction + optional user message
    full_prompt = instruction
    if user_message:
        full_prompt = f"{instruction}\n\n{user_message}"
    
    # Track image count for error messages
    image_count = 0
    
    # Add image if provided
    if image is not None:
        # Handle video (multiple frames) or single image
        if len(image.shape) == 4 and image.shape[0] > 1:
            # For video, llama.cpp expects images in the content array - limit to frame_count
            total_frames = image.shape[0]
            actual_frame_count = min(frame_count, total_frames)
            image_count = actual_frame_count
            image_content = []
            
            # Add instruction text FIRST, then all images
            image_content.append({"type": "text", "text": full_prompt})
            
            for i in range(actual_frame_count):
                pil_image = smart_lm_instance.tensor_to_pil(image[i])
                # Convert to base64 data URL for llama.cpp
                buffered = BytesIO()
                try:
                    pil_image.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    image_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_str}"}
                    })
                finally:
                    # Cleanup memory per frame
                    buffered.close()
                    del pil_image, buffered
            
            # Force garbage collection after processing all frames
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            messages.append({
                "role": "user",
                "content": image_content
            })
        else:
            # Single image - instruction + image in user message
            image_count = 1
            pil_image = smart_lm_instance.tensor_to_pil(image)
            buffered = BytesIO()
            try:
                pil_image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # User content: instruction text + image
                # Instruction MUST be with image for LLaVA to follow it
                user_content = [
                    {"type": "text", "text": full_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_str}"}}
                ]
                
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            finally:
                # Cleanup memory
                buffered.close()
                del pil_image, buffered
    else:
        # Text-only prompt (no image)
        messages.append({
            "role": "user",
            "content": full_prompt
        })
    
    # Generate response
    try:
        response = smart_lm_instance.model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repetition_penalty,
            stream=False
        )
    except ValueError as e:
        error_msg = str(e)
        # Check for context overflow error
        if "Prompt exceeds n_ctx" in error_msg or "exceeds" in error_msg.lower() and "ctx" in error_msg.lower():
            # Parse the actual values from error message like "Prompt exceeds n_ctx: 34613 > 32768"
            import re
            match = re.search(r'(\d+)\s*>\s*(\d+)', error_msg)
            if match:
                used_tokens = int(match.group(1))
                max_ctx = int(match.group(2))
                excess = used_tokens - max_ctx
                raise RuntimeError(
                    f"Context overflow: {used_tokens:,} tokens > {max_ctx:,} max context\n\n"
                    f"Each image uses ~2,000-3,000 tokens. You have {excess:,} tokens over the limit.\n\n"
                    f"Solutions:\n"
                    f"  • Reduce number of images/frames (try {max(1, image_count - (excess // 2500))} or fewer)\n"
                    f"  • Increase context_size widget (if your GPU has enough VRAM)\n"
                    f"  • Use a shorter prompt"
                ) from e
            else:
                raise RuntimeError(
                    f"Context overflow: Prompt too large for model's context window.\n\n"
                    f"Each image uses ~2,000-3,000 tokens.\n\n"
                    f"Solutions:\n"
                    f"  • Reduce number of images/frames\n"
                    f"  • Increase context_size widget\n"
                    f"  • Use a shorter prompt"
                ) from e
        raise
    
    # Extract text from response
    text = response['choices'][0]['message']['content']
    
    # Clear messages to free base64 image data from memory
    messages.clear()
    del response
    
    # Clean up common formatting artifacts
    text = text.strip()
    # Remove leading colon and space (e.g., ": The video shows..." -> "The video shows...")
    if text.startswith(": "):
        text = text[2:]
    elif text.startswith(":"):
        text = text[1:].lstrip()
    
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
        text = text.replace(wrong, correct)
    
    # Strip thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking, DeepSeek-R1)
    from .common import strip_thinking_tags
    text, _ = strip_thinking_tags(text)
    
    return text


def _generate_gguf_text(smart_lm_instance, prompt: str, max_tokens: int,
                        temperature: float, top_p: float, top_k: int, seed: Optional[int],
                        repetition_penalty: float = 1.0) -> str:
    # Generate with text-only GGUF model using llama-cpp-python.
    #
    # Uses create_chat_completion() for text generation.
    
    # Set seed if provided
    if seed is not None:
        smart_lm_instance.model.set_seed(seed)
    
    # Build messages for chat completion
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
    
    # Generate response
    try:
        response = smart_lm_instance.model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repetition_penalty,
            stream=False
        )
        
        text = response['choices'][0]['message']['content']
        text = text.strip()
        
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
            text = text.replace(wrong, correct)
        
        # Strip thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking, DeepSeek-R1)
        from .common import strip_thinking_tags
        text, _ = strip_thinking_tags(text)
        
        return text
        
    except Exception as e:
        error_log(f"GGUF text generation error: {e}")
        raise


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_gguf_info() -> dict:
    # Get information about llama-cpp-python availability and capabilities.
    #
    # Returns:
    #     Dict with 'available', 'version', 'gpu_offload' keys
    from .smartlm_device import LLAMA_CPP_AVAILABLE
    
    info = {
        "available": LLAMA_CPP_AVAILABLE,
        "version": None,
        "gpu_offload": False
    }
    
    if LLAMA_CPP_AVAILABLE:
        try:
            import llama_cpp
            info["version"] = getattr(llama_cpp, '__version__', 'unknown')
            
            # Check if GPU offloading is supported
            if hasattr(llama_cpp, 'llama_supports_gpu_offload'):
                try:
                    info["gpu_offload"] = llama_cpp.llama_supports_gpu_offload()
                except:
                    pass
        except Exception:
            pass
    
    return info


def cleanup_gguf_model(smart_lm_instance):
    # Properly cleanup GGUF model and free VRAM.
    #
    # CRITICAL: Must cleanup chat_handler separately as it holds CLIP model in VRAM.
    # The chat_handler (Qwen25VLChatHandler, Llava16ChatHandler, etc.) loads the
    # vision encoder (mmproj) which can use 1-2GB+ of VRAM.
    #
    # Qwen2.5-VL uses mtmd (multimodal) context - must call mtmd_free()
    # Legacy LLaVA uses clip context - must call clip_free()
    debug_log("Cleaning up GGUF model and freeing VRAM...")
    
    model = None
    
    # Get the actual model object (may be wrapped)
    if hasattr(smart_lm_instance, 'model'):
        model = smart_lm_instance.model
    else:
        model = smart_lm_instance
    
    # Helper function to cleanup a chat handler's vision context
    def cleanup_chat_handler_vision(handler):
        # Cleanup vision model from a chat handler (mtmd for Qwen2.5-VL, CLIP for LLaVA).
        if handler is None:
            return
        
        # NEW VISION SYSTEM: mtmd context (Qwen2.5-VL uses this)
        if hasattr(handler, 'mtmd_ctx') and handler.mtmd_ctx is not None:
            debug_log("Freeing mtmd vision context (Qwen2.5-VL)...")
            try:
                # Try using exit_stack if available (context manager pattern)
                if hasattr(handler, '_exit_stack'):
                    handler._exit_stack.close()
                    debug_log("Closed _exit_stack")
                # Try direct mtmd_free call
                elif hasattr(handler, '_mtmd_cpp') and handler._mtmd_cpp is not None:
                    if hasattr(handler._mtmd_cpp, 'mtmd_free'):
                        handler._mtmd_cpp.mtmd_free(handler.mtmd_ctx)
                        debug_log("Called mtmd_free()")
                handler.mtmd_ctx = None
            except Exception as e:
                debug_log(f"mtmd cleanup error (may be ok): {e}")
        
        # Try llama_cpp's mtmd module directly
        try:
            from llama_cpp import mtmd_cpp
            if hasattr(mtmd_cpp, 'mtmd_free'):
                # Look for mtmd context in various locations
                for attr in ['mtmd_ctx', '_mtmd_ctx', 'ctx']:
                    ctx = getattr(handler, attr, None)
                    if ctx is not None:
                        debug_log(f"Calling mtmd_free() on handler.{attr}")
                        try:
                            mtmd_cpp.mtmd_free(ctx)
                            setattr(handler, attr, None)
                        except:
                            pass
        except ImportError:
            pass  # mtmd_cpp not available in this version
        
        # OLD VISION SYSTEM: CLIP context (legacy LLaVA)
        clip_attrs = ['clip_ctx', '_clip_ctx', 'clip_model', '_clip_model', '_llava_ctx']
        for attr in clip_attrs:
            if hasattr(handler, attr):
                clip_ctx = getattr(handler, attr, None)
                if clip_ctx is not None:
                    debug_log(f"Found CLIP context at handler.{attr}")
                    try:
                        from llama_cpp import llava_cpp
                        if hasattr(llava_cpp, 'clip_free'):
                            debug_log("Calling clip_free() to release CLIP VRAM")
                            llava_cpp.clip_free(clip_ctx)
                    except Exception as e:
                        debug_log(f"clip_free failed: {e}")
                    try:
                        setattr(handler, attr, None)
                    except:
                        pass
        
        # Call _clip_free method if available (some handlers have this)
        if hasattr(handler, '_clip_free') and callable(handler._clip_free):
            try:
                handler._clip_free()
                debug_log("Called handler._clip_free()")
            except:
                pass
        
        # Clear any cached embeddings
        for attr in ['image_embeds', '_image_embeds', 'embeds', '_last_image_embed']:
            if hasattr(handler, attr):
                try:
                    setattr(handler, attr, None)
                except:
                    pass
        if hasattr(handler, '_cache'):
            try:
                handler._cache.clear()
            except:
                pass
        
        # For Qwen/Llava handlers that wrap another handler
        if hasattr(handler, '_llava_cpp') and handler._llava_cpp is not None:
            debug_log("Found _llava_cpp wrapper, cleaning up inner handler")
            cleanup_chat_handler_vision(handler._llava_cpp)
            try:
                handler._llava_cpp = None
            except:
                pass
        
        # Some handlers have a 'handler' attribute pointing to inner handler
        if hasattr(handler, 'handler') and handler.handler is not None:
            cleanup_chat_handler_vision(handler.handler)
            try:
                handler.handler = None
            except:
                pass
    
    # Cleanup chat handler stored on the model (our custom reference)
    if model is not None and hasattr(model, '_eclipse_chat_handler') and model._eclipse_chat_handler is not None:
        try:
            debug_log("Cleaning up GGUF chat_handler (vision encoder)")
            chat_handler = model._eclipse_chat_handler
            cleanup_chat_handler_vision(chat_handler)
            model._eclipse_chat_handler = None
            del chat_handler
        except Exception as e:
            warning_log(f"Error cleaning up chat_handler: {e}")
    
    # Legacy: cleanup chat_handler_ref if present (old method)
    if hasattr(smart_lm_instance, 'chat_handler_ref') and smart_lm_instance.chat_handler_ref is not None:
        try:
            cleanup_chat_handler_vision(smart_lm_instance.chat_handler_ref)
            smart_lm_instance.chat_handler_ref = None
        except:
            pass
    
    # Cleanup the Llama model's internal chat_handler reference
    if model is not None and hasattr(model, 'chat_handler') and model.chat_handler is not None:
        try:
            debug_log("Cleaning up Llama internal chat_handler")
            cleanup_chat_handler_vision(model.chat_handler)
            model.chat_handler = None
        except:
            pass
    
    # Cleanup main Llama model - need to call close() or free the context
    if model is not None:
        try:
            # Try close() method first (newer versions of llama-cpp-python)
            if hasattr(model, 'close') and callable(model.close):
                debug_log("Calling model.close()")
                model.close()
            # Try _ctx cleanup (internal llama context)
            elif hasattr(model, '_ctx') and model._ctx is not None:
                try:
                    from llama_cpp import llama_cpp
                    if hasattr(llama_cpp, 'llama_free'):
                        debug_log("Calling llama_free() on model context")
                        llama_cpp.llama_free(model._ctx)
                        model._ctx = None
                except Exception as e:
                    debug_log(f"llama_free failed: {e}")
            # Also try freeing the model itself if it has __del__
            if hasattr(model, '__del__'):
                try:
                    model.__del__()
                except:
                    pass
        except Exception as e:
            warning_log(f"Error cleaning up Llama model: {e}")
    
    # Clear the reference in the wrapper
    if hasattr(smart_lm_instance, 'model'):
        try:
            smart_lm_instance.model = None
        except:
            pass
    
    # Force garbage collection multiple times to ensure cleanup
    for _ in range(3):
        gc.collect()
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        # Also try ipc_collect for shared memory
        try:
            torch.cuda.ipc_collect()
        except:
            pass
    
    msg_log("✓ GGUF cleanup complete")


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Detection
    'is_gguf_model',
    # Loading
    'load_gguf_model',
    # Generation
    'generate_gguf',
    # Utilities
    'get_gguf_info',
    'cleanup_gguf_model',
]

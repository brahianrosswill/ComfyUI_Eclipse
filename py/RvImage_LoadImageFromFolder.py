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

import os
import torch
import numpy as np
import nodes
import folder_paths
import json
import re

from PIL import Image, ImageOps
from xml.dom import minidom
from typing import Any, Dict, List, Optional, Tuple, Union
from server import PromptServer
from ..core import CATEGORY
from ..core.common import SCHEDULERS_ANY
from ..core.logger import log
from ..core.file_cache import FileListCache


_LOG_PREFIX = "Load Image From Folder"


# Supported image extensions
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')

# Extensions that commonly contain generation metadata
METADATA_EXTENSIONS = ('.png', '.webp', '.tiff', '.tif')


# ============================================================================
# Metadata extraction functions (from RvImage_LoadImagePath_Pipe)
# ============================================================================

EASYDIFFUSION_MAPPING_A = {
    "prompt": "Prompt",
    "negative_prompt": "Negative Prompt",
    "seed": "Seed",
    "use_stable_diffusion_model": "Stable Diffusion model",
    "clip_skip": "Clip Skip",
    "use_vae_model": "VAE model",
    "sampler_name": "Sampler",
    "width": "Width",
    "height": "Height",
    "num_inference_steps": "Steps",
    "guidance_scale": "Guidance Scale",
}

EASYDIFFUSION_MAPPING_B = {
    "prompt": "prompt",
    "negative_prompt": "negative_prompt",
    "seed": "seed",
    "use_stable_diffusion_model": "use_stable_diffusion_model",
    "clip_skip": "clip_skip",
    "use_vae_model": "use_vae_model",
    "sampler_name": "sampler_name",
    "width": "width",
    "height": "height",
    "num_inference_steps": "num_inference_steps",
    "guidance_scale": "guidance_scale",
}

IMV_CIVITAI_SAMPLER_MAP = {
    'Euler a': 'euler_ancestral',
    'Euler': 'euler',
    'LMS': 'lms',
    'Heun': 'heun',
    'DPM2': 'dpm_2',
    'DPM2 a': 'dpm_2_ancestral',
    'DPM++ 2S a': 'dpmpp_2s_ancestral',
    'DPM++ 2M': 'dpmpp_2m',
    'DPM++ SDE': 'dpmpp_sde',
    'DPM++ 2M SDE': 'dpmpp_2m_sde',
    'DPM++ 3M SDE': 'dpmpp_3m_sde',
    'DPM fast': 'dpm_fast',
    'DPM adaptive': 'dpm_adaptive',
    'DDIM': 'ddim',
    'PLMS': 'plms',
    'UniPC': 'uni_pc',
    'LCM': 'lcm',
}

INV_CIVITAI_SCHEDULER_MAP = {
    'Karras': 'karras',
    'Exponential': 'exponential',
    'SGM Uniform': 'sgm_uniform',
    'Simple': 'simple',
    'DDIM Uniform': 'ddim_uniform',
    'Beta': 'beta',
    'Linear Quadratic': 'linear_quadratic',
    'KL Optimal': 'kl_optimal',
    'Simple Test': 'simple_test',
}


def handle_auto1111(params):
    if params and "\nSteps:" in params:
        if "Negative prompt:" in params:
            prompt_index = [params.index("\nNegative prompt:"), params.index("\nSteps:")]
            neg = params[prompt_index[0] + 1 + len("Negative prompt: "):prompt_index[-1]]
        else:
            prompt_index = [params.index("\nSteps:")]
            neg = ""
        pos = params[:prompt_index[0]]
        return pos, neg
    elif params:
        if "Negative prompt:" in params:
            prompt_index = [params.index("\nNegative prompt:")]
            neg = params[prompt_index[0] + 1 + len("Negative prompt: "):]
        else:
            prompt_index = [len(params)]
            neg = ""
        pos = params[:prompt_index[0]]
        return pos, neg
    else:
        return "", ""


def handle_ezdiff(params):
    data = json.loads(params)
    if data.get("prompt"):
        ed = EASYDIFFUSION_MAPPING_B
    else:
        ed = EASYDIFFUSION_MAPPING_A
    pos = data.get(ed["prompt"])
    data.pop(ed["prompt"])
    neg = data.get(ed["negative_prompt"])
    return pos, neg


def handle_invoke_modern(params):
    meta = json.loads(params.get("sd-metadata"))
    img = meta.get("image")
    prompt = img.get("prompt")
    index = [prompt.rfind("["), prompt.rfind("]")]
    if -1 not in index:
        pos = prompt[:index[0]]
        neg = prompt[index[0] + 1:index[1]]
        return pos, neg
    else:
        return prompt, ""


def handle_invoke_legacy(params):
    dream = params.get("Dream")
    pi = dream.rfind('"')
    ni = [dream.rfind("["), dream.rfind("]")]
    if -1 not in ni:
        pos = dream[1:ni[0]]
        neg = dream[ni[0] + 1:ni[1]]
        return pos, neg
    else:
        pos = dream[1:pi]
        return pos, ""


def handle_novelai(params):
    pos = params.get("Description")
    comment = params.get("Comment", "{}")
    comment_json = json.loads(comment)
    neg = comment_json.get("uc")
    return pos, neg


def handle_comfyui(params):
    gen_data = {}
    
    if "parameters" in params:
        gen_data["parameters"] = params["parameters"]
    
    if "workflow" in params:
        try:
            gen_data["workflow"] = json.loads(params["workflow"])
        except Exception:
            gen_data["workflow"] = params["workflow"]
    
    if "lora_weights" in params:
        try:
            gen_data["lora_weights"] = json.loads(params["lora_weights"])
        except Exception:
            gen_data["lora_weights"] = params["lora_weights"]
    
    # Try to extract prompts from workflow if parameters field is missing
    if "parameters" not in gen_data and "workflow" in gen_data and isinstance(gen_data["workflow"], dict):
        try:
            workflow = gen_data["workflow"]
            nodes = workflow.get("nodes", [])
            links = workflow.get("links", [])
            
            # Build node ID to node mapping for connection tracing
            node_map = {}
            for node in nodes:
                if isinstance(node, dict) and "id" in node:
                    node_map[node["id"]] = node
            
            def is_valid_prompt_text(text):
                # Check if text looks like an actual prompt (not config values, formulas, etc.)
                if not text or not isinstance(text, str):
                    return False
                text = text.strip()
                # Skip empty, pure numbers, short config values, code/formulas
                if len(text) == 0 or text.isdigit() or len(text) < 3:
                    return False
                # Skip common formula patterns
                if any(pattern in text for pattern in ['a + ", " + b', 'CLIP_G', 'CLIP_L']):
                    return False
                return True
            
            def find_connected_node_by_link(link_id):
                # Find the source node connected by a specific link ID
                for link_data in links:
                    if isinstance(link_data, list) and len(link_data) >= 3:
                        if link_data[0] == link_id:
                            source_node_id = link_data[1]
                            return node_map.get(source_node_id)
                return None
            
            def get_text_from_node(node, visited=None):
                # Helper to extract text from a node, following connections if needed
                if visited is None:
                    visited = set()
                
                if not isinstance(node, dict):
                    return None
                
                node_id = node.get("id")
                if node_id in visited:
                    return None  # Prevent infinite loops
                visited.add(node_id)
                
                node_type = node.get("type", "")
                widgets_values = node.get("widgets_values", [])
                
                # For Text Multiline nodes, check widget value first (they usually have the prompt)
                if node_type in ["Text Multiline", "String Multiline [RvTools]", "Text", "String"]:
                    if widgets_values and len(widgets_values) > 0:
                        text = str(widgets_values[0]).strip()
                        if is_valid_prompt_text(text):
                            return text
                
                # If no direct text, check if text is coming from an input connection
                # Only follow STRING/text type inputs (not CLIP, MODEL, etc.)
                inputs = node.get("inputs", [])
                for input_def in inputs:
                    if not isinstance(input_def, dict):
                        continue
                    
                    input_type = input_def.get("type", "")
                    input_name = input_def.get("name", "")
                    
                    # Follow text-type inputs AND conditioning inputs (for module nodes)
                    if input_type not in ["STRING", "*", "CONDITIONING"] and input_name not in ["text", "text_g", "text_l", "string_1", "string_2", "conditioning"]:
                        continue
                    
                    # Check if this input is connected (has a link)
                    link = input_def.get("link")
                    if link is not None:
                        source_node = find_connected_node_by_link(link)
                        if source_node:
                            # Recursively get text from source node
                            source_text = get_text_from_node(source_node, visited)
                            if source_text:
                                return source_text
                
                # Fallback: check widgets for any valid text (for other node types)
                if widgets_values and len(widgets_values) > 0:
                    text = str(widgets_values[0]).strip()
                    if is_valid_prompt_text(text):
                        return text
                
                return None
            
            # Strategy 1: Trace backwards from KSampler nodes to find the actual prompts used
            sampler_prompts_pos = []
            sampler_prompts_neg = []
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                node_type = node.get("type", "")
                # Include various sampler node types (standard and custom)
                if node_type not in ["KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"]:
                    continue
                
                # Extract sampler settings from the first KSampler found
                if "seed" not in gen_data:
                    widgets_values = node.get("widgets_values", [])
                    if widgets_values and len(widgets_values) >= 6:
                        try:
                            gen_data["seed"] = int(widgets_values[0])
                            gen_data["steps"] = int(widgets_values[1])
                            gen_data["cfg_scale"] = float(widgets_values[2])
                            gen_data["sampler_name"] = str(widgets_values[3])
                            gen_data["scheduler"] = str(widgets_values[4])
                        except (ValueError, IndexError):
                            pass
                
                # Find positive and negative conditioning inputs
                inputs = node.get("inputs", [])
                for input_def in inputs:
                    if not isinstance(input_def, dict):
                        continue
                    
                    input_name = input_def.get("name", "")
                    link = input_def.get("link")
                    
                    if link is None:
                        continue
                    
                    # Trace positive conditioning
                    if input_name == "positive":
                        conditioning_node = find_connected_node_by_link(link)
                        if conditioning_node:
                            # This should be a CLIPTextEncode node or conditioning node
                            text = get_text_from_node(conditioning_node)
                            if text:
                                sampler_prompts_pos.append(text)
                    
                    # Trace negative conditioning
                    elif input_name == "negative":
                        conditioning_node = find_connected_node_by_link(link)
                        if conditioning_node:
                            text = get_text_from_node(conditioning_node)
                            if text:
                                sampler_prompts_neg.append(text)
            
            # Use sampler-traced prompts (prefer last sampler for final generation)
            if sampler_prompts_pos:
                gen_data["text_pos_from_workflow"] = sampler_prompts_pos[-1]
            
            if sampler_prompts_neg:
                gen_data["text_neg_from_workflow"] = sampler_prompts_neg[-1]
            
            # Strategy 2: Fallback to priority-based search if sampler tracing didn't work
            if "text_pos_from_workflow" not in gen_data or "text_neg_from_workflow" not in gen_data:
                positive_candidates = []
                negative_candidates = []
                
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    
                    node_type = node.get("type", "")
                    node_id = node.get("id", 0)
                    
                    # Skip bypassed nodes (mode 2 = muted/bypassed in ComfyUI)
                    node_mode = node.get("mode", 0)
                    if node_mode == 2:
                        continue
                    
                    # Common ComfyUI prompt node types (including preview/display nodes)
                    if node_type in ["CLIPTextEncode", "CLIPTextEncodeSDXL", "CLIPTextEncodeFlux", 
                                     "ShowText|pysssss", "Text Multiline", "String Multiline [RvTools]", 
                                     "String Multiline [Eclipse]"]:
                        title = node.get("title", "").lower()
                        widgets_values = node.get("widgets_values", [])
                        
                        # For ShowText and String Multiline nodes, get text from widgets directly
                        text = None
                        if "showtext" in node_type.lower() or "string multiline" in node_type.lower() or "text multiline" in node_type.lower():
                            if widgets_values and len(widgets_values) > 0:
                                text = str(widgets_values[0]).strip()
                        else:
                            # For CLIPTextEncode, extract text (following connections if needed)
                            text = get_text_from_node(node)
                        
                        if not text or not is_valid_prompt_text(text):
                            continue
                        
                        text_length = len(text)
                        
                        # Calculate priority based on title and type
                        priority = 0
                        if "primary prompt" in title or "final prompt" in title:
                            priority = 100  # Highest priority
                        elif "prompt preview" in title or "🐍 prompt" in title:
                            priority = 90  # High priority for prompt preview nodes
                        elif "primary" in title:
                            priority = 80
                        elif "pos" in title or "prompt" in title:
                            priority = 50
                        elif "neg" in title or "negative" in title:
                            priority = 50
                        
                        # Determine if positive or negative (use text_length then node_id as tiebreakers)
                        if "neg" in title or "negative" in title or "cte-" in title:
                            negative_candidates.append((priority, text_length, node_id, text))
                        else:
                            positive_candidates.append((priority, text_length, node_id, text))
                
                # Sort by priority (highest first), then by text_length (longest first), then node_id (lowest first)
                # Longer text = main prompt, shorter text = detailer adjustments
                if "text_pos_from_workflow" not in gen_data and positive_candidates:
                    positive_candidates.sort(reverse=False, key=lambda x: (-x[0], -x[1], x[2]))
                    gen_data["text_pos_from_workflow"] = positive_candidates[0][3]
                
                if "text_neg_from_workflow" not in gen_data and negative_candidates:
                    negative_candidates.sort(reverse=False, key=lambda x: (-x[0], -x[1], x[2]))
                    gen_data["text_neg_from_workflow"] = negative_candidates[0][3]
        except Exception as e:
            log.debug(_LOG_PREFIX, f"Failed to parse workflow for prompts: {e}")
    
    if "parameters" in gen_data:
        params_str = gen_data["parameters"]
        if "Steps:" in params_str:
            try:
                if "Steps: " in params_str:
                    steps_start = params_str.find("Steps: ") + 7
                    steps_end = params_str.find(",", steps_start)
                    if steps_end == -1:
                        steps_end = params_str.find("\n", steps_start)
                    gen_data["steps"] = int(params_str[steps_start:steps_end].strip())
                
                if "Sampler: " in params_str:
                    sampler_start = params_str.find("Sampler: ") + 9
                    sampler_end = params_str.find(",", sampler_start)
                    if sampler_end == -1:
                        sampler_end = params_str.find("\n", sampler_start)
                    gen_data["sampler_name"] = params_str[sampler_start:sampler_end].strip()
                
                if gen_data.get("sampler_name"):
                    sampler_full = gen_data["sampler_name"]
                    schedulers_to_check = set(INV_CIVITAI_SCHEDULER_MAP.keys()) | set(SCHEDULERS_ANY)
                    if isinstance(sampler_full, str):
                        sampler_full_l = sampler_full.lower()
                        for sched in schedulers_to_check:
                            try:
                                sched_l = str(sched).lower()
                                if re.search(r"(?:\s|^)" + re.escape(sched_l) + r"\s*$", sampler_full_l):
                                    sched_start = sampler_full_l.rfind(sched_l)
                                    if sched_start >= 0:
                                        actual_sched = sampler_full[sched_start:]
                                        gen_data["sampler_name"] = sampler_full[:sched_start].strip()
                                        gen_data["scheduler"] = actual_sched
                                        break
                            except Exception:
                                continue
                
                if "CFG scale: " in params_str:
                    cfg_start = params_str.find("CFG scale: ") + 11
                    cfg_end = params_str.find(",", cfg_start)
                    if cfg_end == -1:
                        cfg_end = params_str.find("\n", cfg_start)
                    gen_data["cfg_scale"] = float(params_str[cfg_start:cfg_end].strip())
                
                if "Seed: " in params_str:
                    seed_start = params_str.find("Seed: ") + 6
                    seed_end = params_str.find(",", seed_start)
                    if seed_end == -1:
                        seed_end = params_str.find("\n", seed_start)
                    gen_data["seed"] = int(params_str[seed_start:seed_end].strip())
                
                if "Size: " in params_str:
                    size_start = params_str.find("Size: ") + 6
                    size_end = params_str.find(",", size_start)
                    if size_end == -1:
                        size_end = params_str.find("\n", size_start)
                    size_str = params_str[size_start:size_end].strip()
                    if "x" in size_str:
                        width, height = size_str.split("x")
                        gen_data["width_param"] = int(width.strip())
                        gen_data["height_param"] = int(height.strip())
                
                if "Hashes: " in params_str:
                    hashes_start = params_str.find("Hashes: ") + 8
                    hashes_end = params_str.find("}", hashes_start) + 1
                    if hashes_end > hashes_start:
                        hashes_str = params_str[hashes_start:hashes_end]
                        try:
                            gen_data["model_hashes"] = json.loads(hashes_str)
                        except Exception:
                            gen_data["model_hashes"] = hashes_str
                
                if "Version: " in params_str:
                    version_start = params_str.find("Version: ") + 9
                    version_end = params_str.find("\n", version_start)
                    if version_end == -1:
                        version_end = len(params_str)
                    gen_data["version"] = params_str[version_start:version_end].strip()
                    
            except Exception:
                pass
    
    if "sampler_name" in gen_data:
        gen_data["sampler_name"] = IMV_CIVITAI_SAMPLER_MAP.get(gen_data["sampler_name"], gen_data["sampler_name"])
    if "scheduler" in gen_data:
        gen_data["scheduler"] = INV_CIVITAI_SCHEDULER_MAP.get(gen_data["scheduler"], gen_data["scheduler"])
    
    return gen_data


def handle_drawthings(params):
    try:
        data = minidom.parseString(params.get("XML:com.adobe.xmp"))
        data_json = json.loads(data.getElementsByTagName("exif:UserComment")[0].childNodes[1].childNodes[1].childNodes[0].data)
    except Exception:
        return "", ""
    else:
        pos = data_json.get("c")
        neg = data_json.get("uc")
        return pos, neg


def extract_image_metadata(img) -> Dict[str, Any]:
    # Extract metadata from a PIL Image object and return a pipe dict.
    prompt = ""
    negative = ""
    width = img.width
    height = img.height
    steps = 0
    sampler = ""
    scheduler = ""
    cfg_scale = 0.0
    seed = 0
    model_hashes = {}
    comfyui_processed = False
    
    if img.format == "PNG" or ("parameters" in img.info or "workflow" in img.info or "lora_weights" in img.info):
        if "parameters" in img.info or "workflow" in img.info or "lora_weights" in img.info:
            gen_data = handle_comfyui(img.info)
            if gen_data:
                comfyui_processed = True
                steps = gen_data.get("steps", 0)
                sampler = gen_data.get("sampler_name", "")
                scheduler = gen_data.get("scheduler", "")
                cfg_scale = gen_data.get("cfg_scale", 0.0)
                seed = gen_data.get("seed", 0)
                model_hashes = gen_data.get("model_hashes", {})
                
                if "parameters" in gen_data:
                    params_str = gen_data["parameters"]
                    if "Negative prompt:" in params_str:
                        parts = params_str.split("Negative prompt:")
                        if len(parts) >= 2:
                            prompt = parts[0].strip()
                            neg_part = parts[1]
                            if "Steps:" in neg_part:
                                negative = neg_part.split("Steps:")[0].strip()
                            else:
                                negative = neg_part.strip()
                    else:
                        if "Steps:" in params_str:
                            prompt = params_str.split("Steps:")[0].strip()
                        else:
                            prompt = params_str.strip()
                
                # Use workflow-extracted prompts if parameters field didn't provide them
                if not prompt and "text_pos_from_workflow" in gen_data:
                    prompt = gen_data["text_pos_from_workflow"]
                if not negative and "text_neg_from_workflow" in gen_data:
                    negative = gen_data["text_neg_from_workflow"]
        
        elif "parameters" in img.info and not comfyui_processed:
            params = img.info.get("parameters")
            prompt, negative = handle_auto1111(params)

        elif "negative_prompt" in img.info or "Negative Prompt" in img.info:
            params = str(img.info).replace("'", '"')
            prompt, negative = handle_ezdiff(params)
            
        elif "sd-metadata" in img.info:
            prompt, negative = handle_invoke_modern(img.info)
            
        elif "Dream" in img.info:
            prompt, negative = handle_invoke_legacy(img.info)
            
        elif img.info.get("Software") == "NovelAI":
            prompt, negative = handle_novelai(img.info)
            
        elif "XML:com.adobe.xmp" in img.info:
            prompt, negative = handle_drawthings(img.info)
    
    # Extract model name from hashes if available
    model_name = ""
    if isinstance(model_hashes, dict):
        for key in model_hashes.keys():
            if key.startswith("Model:"):
                model_name = key.replace("Model:", "", 1)
                break
    
    pipe = {
        "steps": steps,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "cfg": cfg_scale,
        "seed": seed,
        "width": width,
        "height": height,
        "text_pos": prompt,
        "text_neg": negative,
        "model_name": model_name,
        "path": '',
    }
    
    return pipe


# ============================================================================
# File list cache imported from core/file_cache.py
# ============================================================================
# FileListCache is imported at the top of the file from ..core.file_cache


# ============================================================================
# Main node class
# ============================================================================

class RvImage_LoadImageFromFolder:
    # Load images from one or more folders with index control.
    # Useful for batch processing workflows like captioning or tagging.
    #
    # MULTI-FOLDER SUPPORT:
    # - Enter multiple folder paths, one per line
    # - Index spans across all folders (cumulative)
    # - Each folder is cached separately for efficiency
    # - Folders are processed in order listed
    #
    # Extracts metadata from images (ComfyUI, Auto1111, NovelAI, etc.).
    # Outputs current image, mask, metadata pipe, filepath, and counts.
    #
    # File list is cached for consistent ordering across executions.
    # Use refresh_list to force a rescan of the folder(s).
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "folder_path": ("STRING", {"default": "", "multiline": True, "tooltip": "Path(s) to folder(s) containing images. One folder per line. Can be absolute or relative to ComfyUI input folder. Index spans across all folders."}),
                "include_subfolders": ("BOOLEAN", {"default": True, "tooltip": "Include images from subfolders recursively."}),
                "index": ("INT", {"default": 0, "min": -4, "max": 999999, "step": 1, "tooltip": "Image index. Special modes: -1=Random, -2=Increment, -3=Decrement, -4=Shuffle (no repeat)."}),
                "sort_by": (["name", "date_modified", "date_created", "size"], {"default": "name", "tooltip": "How to sort the image list."}),
                "sort_order": (["ascending", "descending"], {"default": "ascending", "tooltip": "Sort order for the image list."}),
                "stop_at_end": ("BOOLEAN", {"default": True, "tooltip": "Stop workflow when index reaches end of list. Disable to wrap around."}),
                "extract_metadata": ("BOOLEAN", {"default": False, "tooltip": "Extract generation metadata from images (slower). Disable for faster loading if you don't need the pipe output."}),
                "refresh_list": ("BOOLEAN", {"default": False, "tooltip": "Force refresh of the cached file list. Enable once to rescan the folder, then disable. Useful after adding/removing files."}),
            },
        }

    CATEGORY = CATEGORY.MAIN.value + CATEGORY.IMAGE.value
    RETURN_TYPES = ("IMAGE", "MASK", "pipe")
    RETURN_NAMES = ("image", "mask", "pipe")
    FUNCTION = "execute"
    
    @classmethod
    def IS_CHANGED(cls, folder_path, include_subfolders, index, sort_by, sort_order, stop_at_end, extract_metadata, refresh_list):
        # Force re-execution when folder_path, index, or relevant settings change.
        # This ensures the node always processes the correct image and detects folder changes.
        # Include folder_path hash to detect folder changes (even when index is same) 
        # Include index to detect image advancement
        # Include refresh_list to force re-scan when requested
        import hashlib
        folder_hash = hashlib.md5(folder_path.encode()).hexdigest()[:8]
        return f"{folder_hash}_{index}_{refresh_list}"

    def _get_image_files(self, folder_path: str, include_subfolders: bool) -> List[str]:
        # Get all image files from the folder.
        image_files = []
        
        if not os.path.exists(folder_path):
            return image_files
        
        if include_subfolders:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(SUPPORTED_EXTENSIONS):
                        image_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(folder_path):
                filepath = os.path.join(folder_path, file)
                if os.path.isfile(filepath) and file.lower().endswith(SUPPORTED_EXTENSIONS):
                    image_files.append(filepath)
        
        return image_files

    def _sort_files(self, files: List[str], sort_by: str, sort_order: str) -> List[str]:
        # Sort the file list based on criteria.
        # IMPORTANT: Always uses full path or filename as secondary sort key to ensure deterministic ordering.
        # This prevents the issue where files with the same primary sort key (e.g., same timestamp)
        # could appear in different orders across executions.
        reverse = sort_order == "descending"
        
        if sort_by == "name":
            # Sort by full path (case-insensitive) for consistent ordering across subfolders
            # This makes it easier to track progress when stopping/continuing later
            files.sort(key=lambda x: x.lower(), reverse=reverse)
        elif sort_by == "date_modified":
            # Primary: modification time, Secondary: full path for determinism
            files.sort(key=lambda x: (os.path.getmtime(x), x.lower()), reverse=reverse)
        elif sort_by == "date_created":
            # Primary: creation time, Secondary: full path for determinism
            # On Windows, getctime is creation time; on Unix, it's the last metadata change
            files.sort(key=lambda x: (os.path.getctime(x), x.lower()), reverse=reverse)
        elif sort_by == "size":
            # Primary: file size, Secondary: full path for determinism
            files.sort(key=lambda x: (os.path.getsize(x), x.lower()), reverse=reverse)
        
        return files
    
    def _get_or_create_file_list(
        self, 
        folder_path: str, 
        include_subfolders: bool, 
        sort_by: str, 
        sort_order: str,
        refresh: bool = False
    ) -> List[str]:
        # Get file list from cache or create and cache it.
        # This ensures consistent ordering across executions.
        cache_key = FileListCache.get_cache_key(folder_path, include_subfolders, sort_by, sort_order)
        
        # Check if we need to refresh
        if refresh:
            FileListCache.invalidate(folder_path)
            log.msg(_LOG_PREFIX, f"Refreshing file list for: {folder_path}")
        
        # Try to get from cache
        cached_list = FileListCache.get_cached_list(cache_key)
        if cached_list is not None:
            cache_info = FileListCache.get_cache_info(cache_key)
            log.msg(_LOG_PREFIX, f"Using cached file list ({cache_info['count']} images)")
            return cached_list
        
        # Build new list
        log.msg(_LOG_PREFIX, f"Building file list for: {folder_path}")
        image_files = self._get_image_files(folder_path, include_subfolders)
        
        # Sort the list (with deterministic secondary key)
        image_files = self._sort_files(image_files, sort_by, sort_order)
        
        # Cache the result
        params = {
            "folder_path": folder_path,
            "include_subfolders": include_subfolders,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "count": len(image_files)
        }
        FileListCache.set_cached_list(cache_key, image_files, params)
        log.msg(_LOG_PREFIX, f"Cached file list ({len(image_files)} images)")
        
        return image_files

    def _load_image_with_metadata(self, filepath: str, extract_metadata: bool = False) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor], Dict[str, Any]]:
        # Load a single image, optionally extract metadata, and convert to tensor.
        
        empty_pipe = {
            "steps": 0,
            "sampler_name": "",
            "scheduler": "",
            "cfg": 0.0,
            "seed": 0,
            "width": 64,
            "height": 64,
            "text_pos": "",
            "text_neg": "",
            "model_name": "",
            "path": "",           # Base folder (set later in execute)
            "filename": filepath, # Full path to the image
        }
        
        try:
            img = Image.open(filepath)
            
            # Extract metadata before any transformations (only if requested and file type supports it)
            if extract_metadata and filepath.lower().endswith(METADATA_EXTENSIONS):
                pipe = extract_image_metadata(img)
            else:
                # Use empty_pipe template to ensure all fields are present with defaults
                pipe = empty_pipe.copy()
            
            # Always set these values (path is set later in execute with folder_path)
            pipe["filename"] = filepath
            
            # Apply EXIF transpose
            img = ImageOps.exif_transpose(img)
            
            # Update dimensions after transpose
            pipe["width"] = img.width
            pipe["height"] = img.height
            
            if img.mode == 'I':
                img = img.point(lambda i: i * (1 / 255))
            
            # Convert to RGB for image tensor
            image_rgb = img.convert("RGB")
            image_np = np.array(image_rgb).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np)[None,]
            
            # Extract mask from alpha channel if present
            if 'A' in img.getbands():
                mask_np = np.array(img.getchannel('A')).astype(np.float32) / 255.0
                mask_tensor = 1. - torch.from_numpy(mask_np)
            else:
                mask_tensor = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            
            return image_tensor, mask_tensor.unsqueeze(0), pipe
            
        except Exception as e:
            log.error(_LOG_PREFIX, f"Failed to load image {filepath}: {e}")
            return None, None, empty_pipe

    def _resolve_folder_path(self, folder_path: str) -> str:
        # Resolve folder path - can be absolute or relative to input directory.
        if not folder_path:
            return folder_paths.get_input_directory()
        
        # Strip quotes from path (in case user pastes path with quotes)
        folder_path = folder_path.strip().strip('"').strip("'")
        
        # If absolute path exists, use it
        if os.path.isabs(folder_path) and os.path.exists(folder_path):
            return folder_path
        
        # Try relative to input directory
        input_dir = folder_paths.get_input_directory()
        relative_path = os.path.join(input_dir, folder_path)
        if os.path.exists(relative_path):
            return relative_path
        
        # Try relative to ComfyUI root
        comfy_root = os.path.dirname(os.path.dirname(folder_paths.get_input_directory()))
        root_relative = os.path.join(comfy_root, folder_path)
        if os.path.exists(root_relative):
            return root_relative
        
        # Return as-is, will fail gracefully later
        return folder_path

    def execute(
        self,
        folder_path: str,
        include_subfolders: bool,
        index: int,
        sort_by: str,
        sort_order: str,
        stop_at_end: bool = True,
        extract_metadata: bool = False,
        refresh_list: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        # Execute the node with multi-folder support.
        
        # Parse multiple folders (one per line)
        folder_lines = [f.strip() for f in folder_path.strip().split('\n') if f.strip()]
        
        if not folder_lines:
            log.error(_LOG_PREFIX, "No folder paths provided")
            raise ValueError("No folder paths provided")
        
        # Build combined file list from all folders
        # Each folder is cached separately (Option B)
        all_files: List[Tuple[str, int, str]] = []  # [(filepath, folder_index, folder_path), ...]
        folder_info: List[Tuple[str, int, int]] = []  # [(resolved_path, start_idx, count), ...]
        skipped_folders: List[str] = []
        
        cumulative_idx = 0
        for folder_idx, folder_line in enumerate(folder_lines):
            # Resolve folder path
            resolved_path = self._resolve_folder_path(folder_line)
            
            # Check if folder exists
            if not os.path.exists(resolved_path):
                log.warning(_LOG_PREFIX, f"Folder not found, skipping: {folder_line}")
                skipped_folders.append(folder_line)
                continue
            
            # Invalidate cache if refresh requested
            if refresh_list:
                FileListCache.invalidate(resolved_path)
            
            # Get file list from cache or build it
            image_files = self._get_or_create_file_list(
                resolved_path, 
                include_subfolders, 
                sort_by, 
                sort_order,
                refresh=False  # Already invalidated above if needed
            )
            
            if not image_files:
                log.warning(_LOG_PREFIX, f"No images in folder, skipping: {folder_line}")
                skipped_folders.append(folder_line)
                continue
            
            # Track folder info
            folder_info.append((resolved_path, cumulative_idx, len(image_files)))
            
            # Add files to combined list with folder tracking
            for filepath in image_files:
                all_files.append((filepath, len(folder_info) - 1, resolved_path))
            
            cumulative_idx += len(image_files)
            log.msg(_LOG_PREFIX, f"Folder {len(folder_info)}: {os.path.basename(resolved_path)} ({len(image_files)} images)")
        
        # Check if we have any valid folders/files
        total_count = len(all_files)
        total_folders = len(folder_info)
        
        if total_count == 0:
            if skipped_folders:
                log.error(_LOG_PREFIX, f"No images found. Skipped folders: {skipped_folders}")
                raise ValueError(f"No images found in any provided folders. Skipped: {skipped_folders}")
            else:
                log.error(_LOG_PREFIX, "No images found in any provided folders")
                raise ValueError("No images found in any provided folders")
        
        log.msg(_LOG_PREFIX, f"Total: {total_count} images across {total_folders} folder(s)")
        
        # Clamp index to valid range first
        # This handles the case where user changes to a smaller folder but index is still high
        start_index = index % total_count
        
        # Warn if index exceeds available images (e.g., after switching to a smaller folder)
        if index > total_count:
            log.warning(_LOG_PREFIX, f"Index {index} exceeds image count ({total_count}). Wrapping to index {start_index}.")
        
        # Only stop if the original index equals total_count exactly (meaning we just finished)
        # If index > total_count (e.g., old folder had more images), we wrap to start
        if stop_at_end and index == total_count:
            log.msg(_LOG_PREFIX, f"Reached end of all folders ({total_count} images in {total_folders} folders). Stopping workflow and disabling auto-queue.")
            PromptServer.instance.send_sync("stop-iteration", {})
            nodes.interrupt_processing()
            # Return empty tensors - won't be used since workflow is interrupted
            # But we must return to prevent further execution
            empty_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            empty_mask = torch.zeros((1, 64, 64), dtype=torch.float32)
            return (empty_image, empty_mask, {"stopped": True, "reason": "end_of_folders"})
        
        # Try to load image, skip to next on failure
        current_index = start_index
        attempts = 0
        max_attempts = total_count
        
        while attempts < max_attempts:
            current_filepath, current_folder_idx, current_folder_path = all_files[current_index]
            current_image, current_mask, pipe = self._load_image_with_metadata(current_filepath, extract_metadata)
            
            if current_image is not None:
                # Get folder info for this file
                folder_path_resolved, folder_start, folder_count = folder_info[current_folder_idx]
                local_index = current_index - folder_start
                
                # Log with multi-folder context
                if total_folders > 1:
                    log.msg(_LOG_PREFIX, f"Folder {current_folder_idx + 1}/{total_folders}: {os.path.basename(folder_path_resolved)}")
                    log.msg(_LOG_PREFIX, f"Image {local_index + 1}/{folder_count} (global: {current_index + 1}/{total_count}): {os.path.basename(current_filepath)}")
                else:
                    log.msg(_LOG_PREFIX, f"Loading image {current_index + 1}/{total_count}: {os.path.basename(current_filepath)}")
                
                # Standard pipe values
                pipe["total_count"] = total_count
                pipe["current_index"] = current_index
                pipe["path"] = folder_path_resolved  # Base folder from input
                
                # Multi-folder pipe values
                pipe["folder_index"] = current_folder_idx
                pipe["folder_count"] = total_folders
                pipe["local_index"] = local_index
                pipe["local_count"] = folder_count
                
                # Note: index advancement is handled client-side in graphToPrompt hook
                # (similar to how seed randomization works in eclipse-seed.js)
                
                return (current_image, current_mask, pipe)
            
            # Failed to load, try next image
            log.warning(_LOG_PREFIX, f"Skipping unreadable image {current_index + 1}/{total_count}: {os.path.basename(current_filepath)}")
            current_index = (current_index + 1) % total_count
            attempts += 1
            
            # Check if we've wrapped around and should stop
            if stop_at_end and current_index < start_index:
                log.msg(_LOG_PREFIX, f"Reached end of all folders after skipping failed images. Stopping workflow and disabling auto-queue.")
                PromptServer.instance.send_sync("stop-iteration", {})
                nodes.interrupt_processing()
                # Return empty tensors - won't be used since workflow is interrupted
                empty_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
                empty_mask = torch.zeros((1, 64, 64), dtype=torch.float32)
                return (empty_image, empty_mask, {"stopped": True, "reason": "end_of_folders"})
        
        # All images failed to load
        log.error(_LOG_PREFIX, f"Could not load any images from {total_folders} folder(s)")
        raise ValueError(f"Could not load any images from {total_folders} folder(s)")


NODE_NAME = 'Load Image From Folder [Eclipse]'
NODE_DESC = 'Load Image From Folder'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvImage_LoadImageFromFolder
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}

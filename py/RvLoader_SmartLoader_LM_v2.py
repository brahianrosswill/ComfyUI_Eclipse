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

# RvLoader_SmartLoader_LM_v2 - Smart Language Model Loader v2
#
# Template-first workflow:
# 1. Template (unfiltered - shows all templates)
# 2. Model Family (auto-loaded from template if selected)
# 3. Loading Method (auto-loaded from template if saved)
# 4. Model Selection (auto-discovered, filtered by family)

import nodes
import torch
import gc
import regex as re  
from ..core import CATEGORY
from ..core.smartlm_transformers import get_florence_tasks
from ..core.smartlm_templates import update_template_settings, get_llm_models_path, get_config_value, TemplateContext, get_system_prompt
# v2 uses standalone smartlm_base_v2 - no dependency on smartlm_base
from ..core.smartlm_base_v2 import (
    MODEL_CONFIGS,
    get_template_list,
    load_template,
    detect_model_type,
    ModelType,
    ModelFamily,
    LoadingMethod,
    get_llm_model_list,
    get_mmproj_list,
    get_template_dir,
    get_loading_method_list,
    get_model_family_list,
    get_supported_families,
    discover_models_in_folder,
    filter_models_by_method_and_family,
    load_model_with_backend,
    ensure_model_path_v2,
)

# Use central resolvers from templates for Florence id<->display mapping
from ..core.smartlm_templates import resolve_florence_display_from_id as florence_machine_key_to_display

# User-friendly quantization display names -> internal values
# Transformers: 4bit/8bit use bitsandbytes automatically
# vLLM: Only 4-bit supported via bitsandbytes (8bit not available in vLLM)
# vLLM auto-detects AWQ/GPTQ/FP8 pre-quantized models from config.json
# Auto/FP16/BF16/FP32: no quantization applied (dtype only)
QUANT_DISPLAY_V2 = {
    "Auto (Best for VRAM)": "auto",
    "4-bit (Lowest VRAM)": "4bit",      # Transformers + vLLM bitsandbytes
    "8-bit (Balanced)": "8bit",         # Transformers only (vLLM falls back to 4bit)
    "None (FP16)": "fp16",              # No quantization, FP16 dtype
    "None (BF16)": "bf16",              # No quantization, BF16 dtype
    "None (FP32)": "fp32",              # No quantization, FP32 dtype
}
QUANT_OPTIONS_V2 = list(QUANT_DISPLAY_V2.keys())


from ..core.logger import log
import folder_paths
import os
import uuid


def get_comfyui_temp_image_path(suffix: str = '.jpg') -> str:
    # Get a temp image path in ComfyUI's temp folder (ComfyUI/temp).
    #
    # This folder is cleared on every ComfyUI start, so it's better than
    # the system temp folder which can accumulate files.
    #
    # Args:
    #     suffix: File extension (default: '.jpg')
    #
    # Returns:
    #     Full path to a unique temp file in ComfyUI's temp folder
    temp_dir = folder_paths.get_temp_directory()
    unique_name = f"smartlm_temp_{uuid.uuid4().hex}{suffix}"
    return os.path.join(temp_dir, unique_name)


_LOG_PREFIX = "SmartLM"


class RvLoader_SmartLoader_LM_v2:
    # Smart Language Model Loader v2 - Template-First Workflow (Standalone)
    #
    # Workflow:
    # 1. Template: Optional - provides repo_id, paths, family, and loading method
    # 2. Model Family: Auto-loaded from template (or choose manually)
    # 3. Loading Method: Auto-loaded from template if saved (or choose manually)
    # 4. Model Name: Auto-discovered models from models/LLM/ folder
    #
    # Key improvements:
    # - Template-first workflow: select template to auto-populate settings
    # - Unfiltered template list: see all templates at once
    # - Auto-discovery of local models
    # - Full vLLM support
    # - Better method-specific options
    # - Completely standalone - no dependency on smartlm_base.py

    @classmethod
    def INPUT_TYPES(cls):
        templates = get_template_list()
        
        # Get available loading methods and families
        loading_methods = get_loading_method_list()
        all_families = get_model_family_list()
        
        # Discover available models (will be filtered by JS based on method + family)
        discovered_models = discover_models_in_folder()
        # discovered_models is List[dict] with keys: name, path, family, is_gguf, is_folder
        all_model_names = ["None"] + sorted([m["name"] for m in discovered_models]) if discovered_models else ["None"]
        
        # Unified task list for ALL model families (JS will filter by family)
        # Load tasks from config file (smartlm_prompt_defaults.json)
        preset_prompts = MODEL_CONFIGS.get("_preset_prompts", {})
        
        # Debug output (only once per session, respects log_level)
        if not getattr(RvLoader_SmartLoader_LM_v2, '_tasks_logged', False):
            if isinstance(preset_prompts, dict):
                custom_n = len(preset_prompts.get('custom', []))
                vision_n = len(preset_prompts.get('vision', []))
                detection_n = len(preset_prompts.get('detection', []))
                text_n = len(preset_prompts.get('text', []))
                log.debug(_LOG_PREFIX, f"Task counts - Custom: {custom_n}, Vision: {vision_n}, Detection: {detection_n}, Text: {text_n}")
            else:
                log.debug(_LOG_PREFIX, f"preset_prompts is NOT a dict: {type(preset_prompts)}")
            RvLoader_SmartLoader_LM_v2._tasks_logged = True
        
        # New consolidated format: vision + detection + text (keys align with JSON)
        if isinstance(preset_prompts, dict):
            # Direct interaction and custom tasks (unprefixed)
            custom_tasks = preset_prompts.get("custom", ["Custom", "Question Answering", "Direct Chat", "Custom Instruction"]) 

            # Vision tasks shared by VLMs
            vision_tasks = preset_prompts.get("vision", [
                "Simple Description", "Detailed Description", "Ultra Detailed Description",
                "Cinematic Description", "Image Analysis", "Video Summary", "Short Story", "OCR",
                "Tags", "Detailed Analysis", "Tags to Natural Language", "Refine Prompt"
            ])

            # Detection tasks (region/grounding/detection)
            detection_tasks = preset_prompts.get("detection", [
                "Caption to Phrase Grounding", "Region Caption", "Dense Region Caption",
                "Region Proposal", "Referring Expression Segmentation", "OCR", "OCR With Region", "DocVQA"
            ])

            # Text-only LLM tasks
            text_tasks = preset_prompts.get("text", [
                "Expand Text", "Refine & Expand Prompt", "Rewrite Style",
                "Tags to Natural Language", "Natural Language to Tags", "Translate to English",
                "Short Story", "Summarize"
            ])
            florence_prompts_from_config = preset_prompts.get("florence", [])
        else:
            # Legacy format fallback
            custom_tasks = ["Custom", "Question Answering", "Direct Chat", "Custom Instruction"]
            vision_tasks = ["Simple Description", "Detailed Description", "Ultra Detailed Description",
                          "Cinematic Description", "Image Analysis", "Video Summary", "Short Story", "OCR",
                          "Tags", "Detailed Analysis", "Tags to Natural Language", "Refine Prompt"]
            detection_tasks = ["Caption to Phrase Grounding", "Region Caption", "Dense Region Caption", "Region Proposal", "Referring Expression Segmentation", "OCR", "OCR With Region", "DocVQA"]
            text_tasks = ["Custom Instruction", "Tags to Natural Language", "Expand Text", "Refine Prompt", "Direct Chat"]
            florence_prompts_from_config = []
        
        # Build unified task list:
        # - Common tasks (no prefix) - work with Qwen, Mistral, LLaVA
        # - Qwen-specific (prefixed) - detection/grounding only
        # - LLM-specific (prefixed) - text-only tasks
        # - Florence-specific (prefixed) - Florence tasks
        all_tasks = []

        # Helpers to extract display names and filter comments
        def _is_comment(entry):
            if not entry:
                return False
            if isinstance(entry, dict):
                name = (entry.get('name') or entry.get('id') or '')
                return str(name).strip().lower().startswith('_comment')
            return str(entry).strip().lower().startswith('_comment')

        def _display_name(entry):
            if isinstance(entry, dict):
                return entry.get('name') or entry.get('id') or str(entry)
            return str(entry)

        def _id_for_entry(entry):
            if isinstance(entry, dict):
                return entry.get('id') or entry.get('name')
            return str(entry)

        # Custom / direct interaction tasks (unprefixed, shown first)
        custom_list = [_display_name(t) for t in sorted(custom_tasks, key=lambda x: _display_name(x)) if not _is_comment(t)]
        all_tasks.extend(custom_list)

        # Vision tasks - no prefix (shared by VLMs)
        vision_list = [_display_name(t) for t in sorted(vision_tasks, key=lambda x: _display_name(x)) if not _is_comment(t)]
        all_tasks.extend(vision_list)

        # Detection tasks (region/grounding/detection) - show display names
        detection_list = [_display_name(t) for t in sorted(detection_tasks, key=lambda x: _display_name(x)) if not _is_comment(t)]
        all_tasks.extend(detection_list)

        # Text-only tasks - show display names (no family prefix)
        text_list = [_display_name(t) for t in sorted(text_tasks, key=lambda x: _display_name(x)) if not _is_comment(t)]
        all_tasks.extend(text_list)

        # Florence tasks - prefixed (different task format)
        if florence_prompts_from_config:
            # florence_prompts_from_config may be array of strings or dicts
            florence_list = []
            for t in florence_prompts_from_config:
                if _is_comment(t):
                    continue
                # Prefer the 'id' as stored machine key when available
                if isinstance(t, dict) and t.get('id'):
                    florence_list.append(t.get('id'))
                else:
                    florence_list.append(_id_for_entry(t))
        else:
            # Derive Florence task ids directly from authoritative TASK_DICT
            td = MODEL_CONFIGS.get("_task_dict", {}) or {}
            florence_list = [m.get("id") for name, m in td.items() if isinstance(m.get("families"), list) and "Florence" in m.get("families") and m.get("id")]

        # Ensure unique and sorted by id/display
        florence_list = sorted(set(fl for fl in florence_list if fl))

        # Map machine keys to human-friendly display names (no family prefixes in UI)
        # Use central resolver (will raise if mapping is invalid)
        from ..core.smartlm_templates import resolve_florence_display_from_id
        florence_display_list = [resolve_florence_display_from_id(mk) for mk in florence_list]
        all_tasks.extend(florence_display_list)

        # Sort the complete list alphabetically for easier navigation
        all_tasks.sort()
        
        mmproj_files = get_mmproj_list()
        
        return {"required": {
            # Model Selection
            "template_name": (templates, {"default": templates[0] if templates else "None", "tooltip": "Template for repo_id and paths"}),
            "model_family": (all_families, {"default": "Mistral", "tooltip": "Model architecture: Mistral/Qwen/Florence/LLM"}),
            "loading_method": (loading_methods, {"default": "Transformers", "tooltip": "Transformers/GGUF/vLLM"}),
            "model_source": (["Local", "HuggingFace"], {"default": "Local", "tooltip": "Local folder or HuggingFace download"}),
            "model_name": (all_model_names, {"default": "None", "tooltip": "Select from models/LLM/ folder"}),
            "repo_id": ("STRING", {"default": "", "tooltip": "HuggingFace repo ID or URL"}),
            "local_path": ("STRING", {"default": "", "tooltip": "Local filename after download"}),
            # GGUF mmproj
            "mmproj_source": (["Local", "HuggingFace"], {"default": "Local", "tooltip": "GGUF vision: mmproj source"}),
            "mmproj_url": ("STRING", {"default": "", "tooltip": "mmproj download URL"}),
            "mmproj_local": (mmproj_files, {"default": mmproj_files[0] if mmproj_files else "None", "tooltip": "Local mmproj file"}),
            "mmproj_path": ("STRING", {"default": "", "tooltip": "mmproj filename after download"}),
            # Transformers options
            "quantization": (QUANT_OPTIONS_V2, {"default": QUANT_OPTIONS_V2[0], "tooltip": "Precision/quantization"}),
            "attention_mode": (["auto", "flash_attention_2", "sdpa", "eager"], {"default": "auto", "tooltip": "Attention implementation"}),
            # vLLM options
            "auto_start_container": ("BOOLEAN", {"default": True, "tooltip": "Auto start Docker container when needed"}),
            "auto_stop_container": ("BOOLEAN", {"default": True, "tooltip": "Stop container after generation to free VRAM"}),
            # Multi-task mode
            "multi_task_mode": ("BOOLEAN", {"default": False, "tooltip": "Run multiple tasks sequentially, chaining output to input"}),
            "task_count": ("INT", {"default": 2, "min": 2, "max": 4, "tooltip": "Number of tasks to run (2-4)"}),
            "task": (all_tasks, {"default": "Detailed Description", "tooltip": "Task for selected model (Task 1 in multi-task mode)"}),
            "task_2": (all_tasks, {"default": "Tags to Natural Language", "tooltip": "Second task - receives output from task 1"}),
            "task_3": (all_tasks, {"default": "Expand Description", "tooltip": "Third task - receives output from task 2"}),
            "task_4": (all_tasks, {"default": "Refine Prompt", "tooltip": "Fourth task - receives output from task 3"}),
            # Florence detection options
            "detection_filter_threshold": ("FLOAT", {"default": 0.80, "min": 0.0, "max": 1.0, "step": 0.05, "tooltip": "Florence detection: Remove boxes covering more than X% of image (0.8=remove >80%, 1.0=keep all)"}),
            "nms_iou_threshold": ("FLOAT", {"default": 0.50, "min": 0.0, "max": 1.0, "step": 0.05, "tooltip": "Florence detection: Merge overlapping boxes (0.5=merge if >50% overlap, 1.0=no merging)"}),
            # LLM options

            # Universal options
            "user_prompt": ("STRING", {"default": "", "multiline": True, "tooltip": "Text input for all models"}),
            "context_size": ("INT", {"default": 8192, "min": 2048, "max": 131072, "step": 1024, "tooltip": "Context window size (GGUF: n_ctx, vLLM: max_model_len). VRAM: 8GB=2k-4k, 16GB=4k-8k, 24GB+=16k-32k. Model max: Qwen/Mistral=32k, Llama3=128k, Gemma2=8k"}),
            "max_tokens": ("INT", {"default": 1024, "min": 64, "max": 2048, "tooltip": "Maximum output tokens"}),
            "memory_cleanup": ("BOOLEAN", {"default": True, "tooltip": "Clear unused memory before loading"}),
            "keep_model_loaded": ("BOOLEAN", {"default": False, "tooltip": "Keep model in VRAM"}),
            "seed": ("INT", {"default": 0, "min": -3, "max": 2**64 - 1, "control_after_generate": True, "tooltip": "Random seed"}),
        }, "optional": {
            "images": ("IMAGE",),
            "text": ("STRING", {"forceInput": True, "tooltip": "Text input (overrides widgets)"}),
            "pipe_opt": ("SMARTLM_ADVANCED_PIPE", {"tooltip": "Advanced parameters pipe"}),
        }}

    CATEGORY = CATEGORY.MAIN.value + CATEGORY.LOADER.value
    RETURN_TYPES = ("IMAGE", "STRING", "JSON")
    RETURN_NAMES = ("image", "text", "data")
    FUNCTION = "execute"

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        # Allow template values even if not in dropdown (for portable workflows)
        return True

    def execute(
        self,
        model_family,
        loading_method,
        template_name,
        model_name,
        model_source,
        repo_id,
        local_path,
        mmproj_source,
        mmproj_url,
        mmproj_local,
        mmproj_path,
        quantization,
        attention_mode,
        auto_start_container,
        auto_stop_container,
        multi_task_mode,
        task_count,
        task,
        task_2,
        task_3,
        task_4,
        detection_filter_threshold,
        nms_iou_threshold,
        user_prompt,
        context_size,
        max_tokens,
        memory_cleanup,
        keep_model_loaded,
        seed,
        images=None,
        text=None,
        pipe_opt=None,
    ):
        import time
        import json
        import os
        import gc
        import torch
        from pathlib import Path
        import folder_paths
        
        start_time = time.time()
        
        # Log the seed for debugging
        log.debug(_LOG_PREFIX, f"Seed parameter received: {seed}")
        
        # Convert display name to internal quantization value
        quantization = QUANT_DISPLAY_V2.get(quantization, quantization)
        
        # Extract advanced parameters from pipe if provided
        device = "cuda"
        use_torch_compile = False
        temperature = 0.7
        top_p = 0.9
        num_beams = 3
        do_sample = True
        repetition_penalty = 1.0
        frame_count = 8
        
        convert_to_bboxes = True  # Default for Florence detection
        
        if pipe_opt is not None:
            device = pipe_opt.get("device", device)
            use_torch_compile = pipe_opt.get("use_torch_compile", use_torch_compile)
            temperature = pipe_opt.get("temperature", temperature)
            top_p = pipe_opt.get("top_p", top_p)
            top_k = pipe_opt.get("top_k", 50)
            num_beams = pipe_opt.get("num_beams", num_beams)
            do_sample = pipe_opt.get("do_sample", do_sample)
            repetition_penalty = pipe_opt.get("repetition_penalty", repetition_penalty)
            frame_count = pipe_opt.get("frame_count", frame_count)
            convert_to_bboxes = pipe_opt.get("convert_to_bboxes", convert_to_bboxes)
        else:
            top_k = 50
        
        # Build task list for multi-task mode
        def parse_task(t):
            # Parse task to extract task name (family prefixes are no longer used).
            # Tasks are stored as plain display names or Florence machine keys; return as-is
            return ("", t)
        
        # Build list of tasks to execute
        tasks_to_run = [task]
        if multi_task_mode:
            if task_count >= 2 and task_2:
                tasks_to_run.append(task_2)
            if task_count >= 3 and task_3:
                tasks_to_run.append(task_3)
            if task_count >= 4 and task_4:
                tasks_to_run.append(task_4)
        
        # If model family is Florence, convert human-readable display names to Florence machine keys (internal mapping)
        if model_family == "Florence":
            # Use authoritative task dict from MODEL_CONFIGS (built at startup)
            task_dict = MODEL_CONFIGS.get("_task_dict", {})
            id_to_display = MODEL_CONFIGS.get("_id_to_display", {})

            def _find_machine_key(value: str):
                if not value:
                    raise RuntimeError("Empty task value when resolving Florence machine key")
                # Direct id match
                if value in id_to_display:
                    return value
                # Exact display match
                meta = task_dict.get(value)
                if meta and meta.get("id"):
                    return meta.get("id")
                # Case-insensitive display match
                v_l = value.lower()
                for disp, m in task_dict.items():
                    if disp.lower() == v_l and m.get("id"):
                        return m.get("id")
                # Not found: raise to fail loudly
                raise RuntimeError(f"Could not resolve Florence machine key for task value: '{value}'")

            # Convert tasks_to_run entries to machine keys
            from ..core.smartlm_templates import resolve_florence_machine_key
            new_tasks = []
            for t in tasks_to_run:
                if isinstance(t, str):
                    mk = resolve_florence_machine_key(t)
                    new_tasks.append(mk)
                else:
                    raise RuntimeError("Invalid task type when resolving Florence task: expected string")
            tasks_to_run = new_tasks

            # Also convert the primary `task` variable if it is a human-readable name
            if isinstance(task, str):
                task = resolve_florence_machine_key(task)
            else:
                raise RuntimeError("Invalid primary task type when resolving Florence task: expected string")
        
        # Parse first task for initial setup
        task_family, task_name = parse_task(task)

        # Helper to get system instruction from task dict (uses get_system_prompt which consults _task_dict)
        def _get_system_instruction(name):
            # get_system_prompt handles exact match, case-insensitive match, and _task_dict lookup
            return get_system_prompt(name)
        
        if multi_task_mode:
            log.debug(_LOG_PREFIX, f"Multi-task mode: {len(tasks_to_run)} tasks to run")
            for i, t in enumerate(tasks_to_run):
                log.debug(_LOG_PREFIX, f"  Task {i+1}: {t}")
        
        log.debug(_LOG_PREFIX, f"execute: model_family={model_family}, loading_method={loading_method}")
        log.debug(_LOG_PREFIX, f"  task={task}, task_name={task_name}")
        log.debug(_LOG_PREFIX, f"  model_source={model_source}, template_name={template_name}, model_name={model_name}")
        log.debug(_LOG_PREFIX, f"  context_size={context_size} (from widget)")
        
        # Check if template is an Ollama registry model (loads template JSON to check model_source field)
        loaded_template = None
        if template_name and template_name != "None":
            loaded_template = load_template(template_name)
            
        is_ollama_registry = (
            loaded_template is not None and
            loaded_template.get("model_source") == "ollama" and
            loaded_template.get("ollama_model")
        )
        
        # Track the actual template name (may be created during download)
        actual_template_name = template_name if template_name and template_name != "None" else ""
        # Track if user explicitly selected a template (vs auto-created during model download)
        # Only explicitly selected templates should have widget settings auto-saved
        template_was_explicitly_selected = bool(actual_template_name)
        
        # Build model path based on source
        llm_base = get_llm_models_path()
        
        if is_ollama_registry:
            # Ollama registry model - no local path needed, use ollama_model name
            ollama_model_name = loaded_template.get("ollama_model")
            model_path = ollama_model_name  # Will be used as model identifier
            log.debug(_LOG_PREFIX, f"  Ollama registry model: {ollama_model_name}")
        elif model_source == "Local":
            if model_name and model_name != "None":
                # Check if model_name starts with a known subfolder of models_dir (e.g., "florence2/")
                # These models are in models/florence2/, not models/{llm_folder}/florence2/
                model_name_parts = model_name.replace('\\', '/').split('/')
                models_dir = Path(folder_paths.models_dir)
                
                # Get the configured LLM folder name (could be "LLM", "MyModels", or an absolute path)
                configured_llm_path = get_config_value("llm_models_path", "LLM")
                # Extract just the folder name (last component) for comparison
                llm_folder_name = Path(configured_llm_path).name
                
                # Check if first part of model_name is a folder under models_dir that ISN'T the LLM folder
                # This handles alternative model folders like "florence2/" that are siblings to LLM folder
                first_part = model_name_parts[0] if model_name_parts else ""
                first_part_is_models_subfolder = first_part and (models_dir / first_part).exists()
                first_part_is_llm_folder = first_part == llm_folder_name
                
                if first_part_is_models_subfolder and not first_part_is_llm_folder:
                    # Path is relative to models_dir (e.g., "florence2/model_name/")
                    # This handles models in models/florence2/, not models/{llm_folder}/florence2/
                    model_path = str(models_dir / model_name)
                    log.debug(_LOG_PREFIX, f"  Local model path (models/): {model_path}")
                else:
                    # Path is relative to LLM folder (llm_base from config)
                    model_path = str(llm_base / model_name)
                    log.debug(_LOG_PREFIX, f"  Local model path ({llm_folder_name}/): {model_path}")
            else:
                raise ValueError("No local model selected")
        else:  # HuggingFace
            # Check if a real template is selected (not "None")
            if template_name and template_name != "None":
                # Use the selected template directly - updates (local_path, vram) will persist
                log.debug(_LOG_PREFIX, f"  Using real template: {template_name}")
                model_path, model_folder, verified_repo_id = ensure_model_path_v2(template_name)
                model_path = str(model_path)
            else:
                # No template selected - create temporary template from manual inputs
                import json
                from ..core.smartlm_templates import get_template_dir, create_auto_template
                
                temp_template_info = {
                    "repo_id": repo_id.strip() if repo_id else "",
                    "local_path": local_path.strip() if local_path else "",
                    "model_family": model_family,
                    "loading_method": loading_method,
                    "mmproj_url": mmproj_url.strip() if mmproj_url else "",
                    "mmproj_path": "",
                }
                
                # Create a temporary template in the correct directory (respects dev_mode)
                temp_template_name = f"_temp_v2_{hash(repo_id + str(local_path))}"
                temp_template_path = get_template_dir() / f"{temp_template_name}.json"
                
                try:
                    # Write temporary template
                    temp_template_path.write_text(json.dumps(temp_template_info, indent=2))
                    
                    # Use standalone v2 ensure_model_path for download, verification, hash checking
                    model_path, model_folder, verified_repo_id = ensure_model_path_v2(temp_template_name)
                    model_path = str(model_path)
                    
                    # After successful download, create a permanent template
                    # Extract local_path relative to LLM folder or models folder
                    model_path_obj = Path(model_path)
                    relative_local_path = None
                    
                    # First try: relative to LLM folder (e.g., "LLM/model_name/")
                    try:
                        relative_local_path = model_path_obj.relative_to(llm_base).as_posix()
                        if model_path_obj.is_dir() and not relative_local_path.endswith('/'):
                            relative_local_path += '/'
                    except ValueError:
                        pass
                    
                    # Second try: relative to ComfyUI models folder (e.g., "florence2/model_name/")
                    # This handles models in models/florence2/ etc.
                    if relative_local_path is None:
                        try:
                            import folder_paths
                            models_dir = Path(folder_paths.models_dir)
                            relative_local_path = model_path_obj.relative_to(models_dir).as_posix()
                            if model_path_obj.is_dir() and not relative_local_path.endswith('/'):
                                relative_local_path += '/'
                        except ValueError:
                            # Fallback: use absolute path if all else fails
                            relative_local_path = model_path
                    
                    # Detect vision support based on family
                    has_vision = model_family in ("Qwen", "Mistral", "LLaVA", "Florence")
                    
                    # Build template context with all widget values
                    auto_ctx = TemplateContext()
                    auto_ctx.model_family = model_family
                    auto_ctx.loading_method = loading_method
                    auto_ctx.repo_id = repo_id.strip() if repo_id else ""
                    auto_ctx.local_path = relative_local_path
                    auto_ctx.has_vision = has_vision
                    auto_ctx.quantization = quantization
                    auto_ctx.attention_mode = attention_mode
                    auto_ctx.context_size = context_size
                    auto_ctx.max_tokens = max_tokens
                    # Preserve human-readable display name when creating auto templates
                    auto_task = task.split(": ", 1)[-1] if ": " in task else task
                    if model_family == "Florence":
                        # If auto_task looks like a machine key, map to display name using authoritative dict
                        from ..core.smartlm_templates import resolve_florence_display_from_id
                        if auto_task:
                            id_to_display = MODEL_CONFIGS.get("_id_to_display", {})
                            if auto_task in id_to_display:
                                auto_task = resolve_florence_display_from_id(auto_task)
                    auto_ctx.default_task = auto_task
                    # Use text input connection if provided, otherwise use user_prompt widget
                    # For Florence templates, only save default_text_input when the template's default task is a detection task
                    default_text_raw = (text.strip() if text else "") or (user_prompt.strip() if user_prompt else "")
                    if model_family == "Florence" and auto_task:
                        try:
                            from ..core.smartlm_templates import resolve_florence_machine_key
                            preset_prompts = MODEL_CONFIGS.get("_preset_prompts", {}) or {}
                            detection_section = preset_prompts.get("detection", [])
                            detection_ids = set()
                            for entry in detection_section:
                                if isinstance(entry, dict) and entry.get('id'):
                                    detection_ids.add(entry.get('id'))
                                else:
                                    try:
                                        detection_ids.add(resolve_florence_machine_key(entry))
                                    except Exception:
                                        pass
                            # Resolve auto_task to machine key and only keep default_text if it is a detection task
                            try:
                                auto_task_mk = resolve_florence_machine_key(auto_task)
                            except Exception:
                                auto_task_mk = None
                            if auto_task_mk not in detection_ids:
                                default_text_raw = ""
                        except Exception:
                            # If anything fails, err on the side of not saving Florence default text
                            default_text_raw = ""
                    auto_ctx.default_text_input = default_text_raw
                    # Include mmproj_url for vision models (GGUF/llama.cpp Docker)
                    auto_ctx.mmproj_url = mmproj_url.strip() if mmproj_url else ""
                    
                    # Generate template name from repo_id
                    # Handle different formats:
                    # - Full URL: "https://huggingface.co/owner/repo/resolve/main/file.gguf" -> "file" (without .gguf)
                    # - Repo ID: "owner/repo" -> "repo" (model name only, without owner prefix)
                    if repo_id:
                        repo_id_stripped = repo_id.strip()
                        if repo_id_stripped.startswith("http://") or repo_id_stripped.startswith("https://"):
                            # Full URL - extract filename without extension
                            url_path = repo_id_stripped.split("?")[0]  # Remove query params
                            filename = url_path.split("/")[-1]  # Get last part (filename)
                            # Remove .gguf extension if present
                            if filename.lower().endswith(".gguf"):
                                filename = filename[:-5]
                            template_model_name = filename
                        else:
                            # Standard repo_id format (owner/repo) -> use just the model name
                            template_model_name = repo_id_stripped.split("/")[-1]
                    else:
                        template_model_name = Path(model_path).name
                    
                    # Create permanent template (returns path if created, None if exists)
                    created_template = create_auto_template(
                        model_name=template_model_name,
                        loading_method=loading_method,
                        repo_id=repo_id.strip() if repo_id else "",
                        local_path=relative_local_path,
                        has_vision=has_vision,
                        widget_model_family=model_family,
                        force_overwrite=False,
                        ctx=auto_ctx,
                    )
                    if created_template:
                        actual_template_name = Path(created_template).stem
                        log.info(_LOG_PREFIX, f"✓ Created template: {actual_template_name}")
                    else:
                        # Template already exists - update its local_path if we have one
                        actual_template_name = template_model_name
                        log.info(_LOG_PREFIX, f"Template already exists: {template_model_name}")
                        
                        # Update existing template's local_path if it's missing or different
                        if relative_local_path:
                            update_template_settings(template_model_name, {"local_path": relative_local_path})
                    
                finally:
                    # Clean up temporary template
                    if temp_template_path.exists():
                        temp_template_path.unlink()
        
        # Build mmproj path for GGUF vision models (Qwen, LLaVA, Mistral with vision)
        # mmproj_file = resolved local path (for loading)
        # mmproj_url_for_download = URL to download from if local doesn't exist
        mmproj_file = None  # Local path only, never URL
        mmproj_url_for_download = None  # URL to download from
        is_gguf_method = loading_method in ("GGUF (llama-cpp-python)", "llama.cpp (Docker)")
        needs_mmproj = model_family in ("Qwen", "LLaVA", "Mistral")
        if is_gguf_method and needs_mmproj:
            if mmproj_source == "Local" and mmproj_local and mmproj_local != "None":
                # User selected a local file from dropdown
                mmproj_file = str(llm_base / mmproj_local)
            elif mmproj_source == "HuggingFace" and mmproj_url and mmproj_url.strip():
                # User provided a URL - check if we have a cached local copy
                mmproj_url_for_download = mmproj_url.strip()
                if mmproj_path and mmproj_path.strip():
                    local_mmproj = llm_base / mmproj_path.strip()
                    if local_mmproj.exists():
                        mmproj_file = str(local_mmproj)
                # If no local file, mmproj_file stays None - will be downloaded during load
            
            # Fallback: use mmproj info from loaded template if widget is empty
            if not mmproj_file and not mmproj_url_for_download and loaded_template:
                template_mmproj_url = loaded_template.get("mmproj_url", "")
                template_mmproj_path = loaded_template.get("mmproj_path", "")
                # First try local path from template
                if template_mmproj_path and template_mmproj_path.strip():
                    local_mmproj = llm_base / template_mmproj_path.strip()
                    if local_mmproj.exists():
                        mmproj_file = str(local_mmproj)
                        log.debug(_LOG_PREFIX, f"  Using mmproj from template path: {mmproj_file}")
                # If no local file, use URL for download
                if not mmproj_file and template_mmproj_url and template_mmproj_url.strip():
                    mmproj_url_for_download = template_mmproj_url.strip()
                    log.debug(_LOG_PREFIX, f"  Will download mmproj from template URL: {mmproj_url_for_download}")
        
        # Get values from template if available
        template_quantized = loaded_template.get("quantized", False) if loaded_template else False
        template_default_task = loaded_template.get("default_task", "") if loaded_template else ""
        template_model_type = loaded_template.get("model_type", "") if loaded_template else ""
        template_has_vision = loaded_template.get("has_vision", None) if loaded_template else None
        
        # Auto-detect vision support if not explicitly set in template
        # VL models (Qwen, Mistral, LLaVA) have vision unless explicitly set to False
        if template_has_vision is None:
            # Default to True for VLM families, False for text-only
            template_has_vision = model_family in ("Qwen", "Mistral", "LLaVA", "Florence")
        
        # Build TemplateContext from widget values + template values
        ctx = TemplateContext.from_widgets(
            model_family=model_family,
            model_type=template_model_type,
            loading_method=loading_method,
            quantization=quantization,
            attention_mode=attention_mode,
            template_name=actual_template_name,
            repo_id=repo_id if model_source == "HuggingFace" else "",
            local_path=model_name if model_source == "Local" else local_path,
            quantized=template_quantized,
            default_task=template_default_task,
            has_vision=template_has_vision,
        )
        
        # Add Ollama-specific fields if this is an Ollama registry model
        if is_ollama_registry and loaded_template:
            ctx.update(
                model_source="ollama",
                ollama_model=loaded_template.get("ollama_model", "")
            )
        
        # Set mmproj info in context ONLY for GGUF methods:
        # - mmproj_path: local file path ONLY (empty if not yet downloaded)
        # - mmproj_url: URL for downloading (kept for re-download capability)
        # Transformers models don't use mmproj - they load vision directly
        if is_gguf_method and needs_mmproj:
            if mmproj_file:
                # We have a resolved local file
                ctx.mmproj_path = mmproj_file
            if mmproj_url_for_download:
                # We have a URL for downloading (either from widget or template)
                ctx.mmproj_url = mmproj_url_for_download
            elif mmproj_source == "HuggingFace" and mmproj_url and mmproj_url.strip():
                # Preserve URL from widget for template saving
                ctx.mmproj_url = mmproj_url.strip()
        
        if loading_method in ("GGUF (llama-cpp-python)", "vLLM (Docker)", "vLLM (Native)", "SGLang (Docker)", "Ollama (Docker)", "llama.cpp (Docker)"):
            ctx.context_size = context_size
        
        log.debug(_LOG_PREFIX, f"Loading model: {model_path}")
        log.debug(_LOG_PREFIX, f"  ctx: {ctx.to_dict()}")
        
        # Load model
        supports_context_size = loading_method in ("GGUF (llama-cpp-python)", "vLLM (Docker)", "vLLM (Native)", "SGLang (Docker)", "Ollama (Docker)", "llama.cpp (Docker)")
        model, processor, model_type = load_model_with_backend(
            loading_method=loading_method,
            model_family=model_family,
            model_path=model_path,
            ctx=ctx,
            quantization=quantization,
            attention_mode=attention_mode,
            device=device,
            context_size=context_size if supports_context_size else None,
            memory_cleanup=memory_cleanup,
            keep_model_loaded=keep_model_loaded,
            use_torch_compile=use_torch_compile,
            auto_start_container=auto_start_container,
            auto_stop_container=auto_stop_container,
        )
        
        log.debug(_LOG_PREFIX, f"Model loaded: model_type={model_type}")
        
        # Update template with mmproj_path if it was discovered during loading
        # This ensures the template is updated even on first run when mmproj is auto-detected
        if actual_template_name and ctx.mmproj_path and not ctx.mmproj_path.startswith("http"):
            llm_dir = get_llm_models_path()
            mmproj_path_obj = Path(ctx.mmproj_path)
            try:
                relative_mmproj = mmproj_path_obj.relative_to(llm_dir).as_posix()
            except ValueError:
                relative_mmproj = mmproj_path_obj.name
            update_template_settings(actual_template_name, {"mmproj_path": relative_mmproj})
        
        # Check if model is already a wrapper (vLLM, SGLang, Ollama, or llama.cpp Docker)
        # Model persistence behavior:
        # - Docker backends (vLLM Docker, SGLang, Ollama, llama.cpp): controlled by auto_stop_container
        # - vLLM Native: has its own internal cache (_vllm_model_cache), always caches
        # - Transformers: uses keep_model_loaded for caching + offload control
        if hasattr(model, 'is_vllm') and model.is_vllm:
            # vLLM backend (Docker or Native) - use the wrapper directly
            # vLLM Native has its own internal cache, Docker uses container lifecycle
            instance = model
            instance.model_type = model_type
        elif hasattr(model, 'is_sglang') and model.is_sglang:
            # SGLang Docker backend - container lifecycle controls model
            instance = model
            instance.model_type = model_type
        elif hasattr(model, 'is_ollama') and model.is_ollama:
            # Ollama Docker backend - container lifecycle controls model
            instance = model
            instance.model_type = model_type
        elif hasattr(model, 'is_llamacpp_docker') and model.is_llamacpp_docker:
            # llama.cpp Docker backend - container lifecycle controls model
            instance = model
            instance.model_type = model_type
        else:
            # Create wrapper instance for generation functions
            # These functions expect a smart_lm_instance object with model, processor, etc.
            class _ModelWrapper:
                def __init__(self, model, processor, model_type, is_gguf, ctx, keep_loaded=False):
                    self.model = model
                    self.processor = processor
                    self.model_type = model_type
                    self.is_gguf = is_gguf
                    self.is_vllm = False  # Not vLLM
                    self.is_quantized = ctx.quantization not in [None, "auto", "fp16", "bf16", "fp32"]
                    self.keep_model_loaded = keep_loaded  # Preserve model in VRAM after generation
                    
                    # For Qwen models, tokenizer is inside the processor
                    if hasattr(processor, 'tokenizer'):
                        self.tokenizer = processor.tokenizer
                    else:
                        self.tokenizer = processor
                    
                    # Copy chat_handler reference for GGUF cleanup (v1 compatibility)
                    if hasattr(model, '_eclipse_chat_handler'):
                        self.chat_handler_ref = model._eclipse_chat_handler
                    else:
                        self.chat_handler_ref = None
                
                @staticmethod
                def tensor_to_pil(tensor):
                    # Convert ComfyUI image tensor to PIL Image
                    from PIL import Image
                    import numpy as np
                    
                    if tensor is None:
                        return None
                    if tensor.dim() == 4:
                        tensor = tensor[0]
                    array = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                    return Image.fromarray(array)
            
            is_gguf = loading_method == "GGUF (llama-cpp-python)"
            instance = _ModelWrapper(model, processor, model_type, is_gguf, ctx, keep_model_loaded)
        
        # Prepare input image
        input_image = None
        if images is not None and model_family in ["Qwen", "Florence", "Mistral", "LLaVA"]:
            input_image = images
        elif model_family not in ["LLM (Text-Only)"]:
            # Only warn for vision models that are missing images
            log.warning(_LOG_PREFIX, "No image provided for vision model")
        
        # Generate based on family
        log.debug(_LOG_PREFIX, f"Starting generation: model_family={model_family}")
        result = ""
        data = {}
        
        if model_family == "Qwen":
            # Qwen VL generation
            import json
            
            if instance.is_gguf:
                from ..core.smartlm_gguf import generate_gguf
                log.debug(_LOG_PREFIX, "  Using generate_gguf for Qwen (GGUF)")
            else:
                from ..core.smartlm_transformers import generate_transformers, _parse_qwen_detection_json
                log.debug(_LOG_PREFIX, "  Using generate_transformers for Qwen")
            
            # Text-only tasks that should NOT use images even if connected
            TEXT_ONLY_TASKS = [
                "Tags to Natural Language", "Natural Language to Tags",
                "Refine & Expand Prompt", "Expand Text",
                "Summarize", "Rewrite Style", "Translate to English"
            ]
            # Tasks that use images if connected, but also work with text-only
            FLEXIBLE_TASKS = ["Direct Chat", "Custom Instruction", "Question Answering"]
            has_text_input = text is not None or (user_prompt and user_prompt.strip())
            has_image_input = input_image is not None
            is_text_only_task = (task_name in TEXT_ONLY_TASKS and has_text_input) or \
                               (task_name in FLEXIBLE_TASKS and has_text_input and not has_image_input)
            
            if is_text_only_task:
                log.debug(_LOG_PREFIX, f"  Text-only task '{task_name}' with text input - skipping image")
            
            if is_text_only_task:
                # For text-only tasks, prepend system prompt to the text input
                text_content = text if text is not None else user_prompt
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{text_content}"
                else:
                    prompt = text_content
            elif task_name in FLEXIBLE_TASKS and has_image_input and user_prompt and user_prompt.strip():
                # Flexible task (Direct Chat, Custom Instruction, Question Answering) with image + user_prompt
                # User's prompt IS the instruction - use it directly without system prompt prefix
                prompt = user_prompt.strip() + "\n\n"
            elif text is not None and task_name == "Custom":
                # Custom task with text input - use text as-is (full control)
                prompt = text
            elif text is not None:
                # Text input with non-Custom task - combine system prompt with text as user message
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{text}"
                else:
                    prompt = text
            elif task_name == "Custom":
                # Custom task uses user_prompt directly
                base_prompt = user_prompt if user_prompt else "Describe this image in detail."
                # Format as: system instruction \n\n (required for parsing in generate_qwenvl)
                prompt = f"{base_prompt}\n\n"
            else:
                # Use system prompt from task mapping (_task_dict via get_system_prompt)
                base_prompt = _get_system_instruction(task_name)
                if not base_prompt:
                    log.warning(_LOG_PREFIX, f"No system prompt mapping for '{task_name}', using task name as prompt")
                    base_prompt = task_name or "Describe this image in detail."
                
                # Format as: system instruction \n\n [optional: \n\n Additional context: hints]
                prompt = base_prompt + "\n\n"
                
                # Add user_prompt as additional context/hints if provided
                if user_prompt and user_prompt.strip():
                    prompt += f"\n\nAdditional context: {user_prompt.strip()}"
            
            log.debug(_LOG_PREFIX, f"  Generation params: temp={temperature}, top_p={top_p}, top_k={top_k}, beams={num_beams}, sample={do_sample}, rep_pen={repetition_penalty}")
            
            # Check if using vLLM backend
            if hasattr(instance, 'is_vllm') and instance.is_vllm:
                is_vllm_native = hasattr(instance, 'is_vllm_native') and instance.is_vllm_native
                if is_vllm_native:
                    from ..core.smartlm_vllm_native import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Native) for Qwen")
                else:
                    from ..core.smartlm_vllm_docker import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Docker) for Qwen")
                
                # vLLM needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result = generate_vllm(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}
            elif hasattr(instance, 'is_sglang') and instance.is_sglang:
                # SGLang Docker generation path for Qwen
                from ..core.smartlm_sglang_docker import generate_sglang
                log.debug(_LOG_PREFIX, "  Using generate_sglang (Docker) for Qwen")
                
                # SGLang needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result = generate_sglang(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}
            elif hasattr(instance, 'is_ollama') and instance.is_ollama:
                # Ollama Docker generation path for Qwen
                from ..core.smartlm_ollama_docker import generate_ollama
                log.debug(_LOG_PREFIX, "  Using generate_ollama (Docker) for Qwen")
                
                # Ollama needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result, _ = generate_ollama(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}
            elif instance.is_gguf:
                # Skip image for text-only tasks
                effective_image = None if is_text_only_task else input_image
                
                result = generate_gguf(
                    smart_lm_instance=instance,
                    model_type="vision",
                    image=effective_image,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    frame_count=frame_count,
                )
                data = {}
            else:
                # Skip image for text-only tasks
                effective_image = None if is_text_only_task else input_image
                
                result, data = generate_transformers(
                    smart_lm_instance=instance,
                    model_family="QwenVL",
                    image=effective_image,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    num_beams=num_beams,
                    do_sample=do_sample,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    frame_count=frame_count,
                )
            
            # Parse detection JSON if present (only for transformers result)
            if not instance.is_gguf:
                parsed_data, cleaned_text = _parse_qwen_detection_json(result)
                if parsed_data:
                    result = cleaned_text
                    data = parsed_data
        
        elif model_family == "Florence":
            # Florence-2 generation - check v5 compatibility first
            from ..core.smartlm_types import FLORENCE_COMPATIBLE
            import transformers
            log.debug(_LOG_PREFIX, "  Using generate_florence2")
            
            if not FLORENCE_COMPATIBLE:
                raise RuntimeError(
                    f"Florence-2 is incompatible with transformers {transformers.__version__}.\n\n"
                    f"Solutions:\n"
                    f"  1. Downgrade transformers: pip install transformers==4.46.3\n"
                    f"  2. Use Qwen2.5-VL or Mistral for vision tasks (both support v5)\n\n"
                    f"Florence-2 requires transformers v4.x due to architecture changes in v5."
                )
            
            from ..core.smartlm_transformers import generate_transformers
            
            # Florence-2 doesn't support video (multiple frames) - warn if batch detected
            if input_image is not None and input_image.dim() == 4 and input_image.shape[0] > 1:
                log.warning("Florence-2", f"Video not supported ({input_image.shape[0]} frames), using first frame only")  # Keep Florence-2 prefix
            
            # For Florence, use text override if provided, otherwise fall back to template default.
            # user_prompt is only used for Florence *detection* tasks (search phrases), handled below.
            template_default_text = loaded_template.get("default_text_input", "") if loaded_template else ""

            # Helper to get system instruction from task dict (uses get_system_prompt which consults _task_dict)
            def _get_system_instruction(name):
                # get_system_prompt handles exact match, case-insensitive match, and _task_dict lookup
                return get_system_prompt(name)
            # Determine Florence detection tasks from loaded presets (do NOT hardcode)
            florence_detection_tasks = []
            try:
                preset_prompts = MODEL_CONFIGS.get("_preset_prompts", {}) or {}
                detection_section = preset_prompts.get("detection", [])
                # Helper to resolve display name or dict entry to Florence machine key
                from ..core.smartlm_templates import resolve_florence_machine_key
                for entry in detection_section:
                    if isinstance(entry, dict):
                        # Prefer explicit id when provided
                        if entry.get('id'):
                            florence_detection_tasks.append(entry.get('id'))
                        else:
                            # Fallback: try resolving by name or id field
                            name = entry.get('name') or entry.get('id') or ''
                            if name:
                                try:
                                    florence_detection_tasks.append(resolve_florence_machine_key(name))
                                except Exception:
                                    # Ignore entries that can't be resolved
                                    pass
                    else:
                        # Entry is a string - resolve to machine key
                        try:
                            florence_detection_tasks.append(resolve_florence_machine_key(entry))
                        except Exception:
                            # Ignore unresolved strings
                            pass
            except Exception:
                # Fallback to empty list if any error occurs
                florence_detection_tasks = []

            # Normalize to a set for faster membership tests
            florence_detection_set = set([s for s in florence_detection_tasks if s])
            is_florence_detection = task_name in florence_detection_set

            # Determine text input for Florence:
            # - If explicit `text` connection provided, use it always.
            # - Else, if this is a Florence detection task, use `user_prompt` (search phrase) or template default.
            # - Else (non-detection Florence tasks), ignore `user_prompt` and use template default only.
            if text is not None:
                # Explicit text connection takes precedence for Florence
                florence_text_input = text
            else:
                # For Florence detection tasks, use user_prompt or template default as search phrase
                # For non-detection Florence tasks, DO NOT pass any text input (Florence cannot handle text input for non-detection tasks)
                florence_text_input = (user_prompt if user_prompt else template_default_text) if is_florence_detection else ""

            # Parse multi-prompt: split by ";" or newlines, strip whitespace
            florence_prompts = []
            if florence_text_input and is_florence_detection and multi_task_mode:
                # Split by semicolon or newline
                raw_prompts = re.split(r'[;\n]', florence_text_input)
                florence_prompts = [p.strip() for p in raw_prompts if p.strip()]
                
                if len(florence_prompts) <= 1:
                    # No splitting occurred, treat as single prompt
                    florence_prompts = [florence_text_input] if florence_text_input else []
            
            if len(florence_prompts) > 1:
                # Multi-prompt mode: run each prompt separately, merge results
                log.info(_LOG_PREFIX, f"Florence multi-prompt: {len(florence_prompts)} phrases to detect")
                
                all_results = []
                merged_data = {
                    "bboxes": [],
                    "labels": [],
                    "quad_boxes": [],
                    "polygons": [],
                }
                
                for prompt_idx, search_phrase in enumerate(florence_prompts):
                    log.info(_LOG_PREFIX, f"  Phrase {prompt_idx + 1}/{len(florence_prompts)}: '{search_phrase}'")
                    
                    phrase_result, phrase_data = generate_transformers(
                        smart_lm_instance=instance,
                        model_family="Florence2",
                        image=input_image,
                        prompt=task_name,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        num_beams=num_beams,
                        do_sample=do_sample,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        text_input=search_phrase,
                        convert_to_bboxes=convert_to_bboxes,
                        detection_filter_threshold=detection_filter_threshold,
                        nms_iou_threshold=nms_iou_threshold,
                    )
                    
                    all_results.append(phrase_result)
                    
                    # Merge detection data
                    if phrase_data:
                        if "bboxes" in phrase_data:
                            merged_data["bboxes"].extend(phrase_data["bboxes"])
                            # Labels from phrase grounding are the search phrase itself
                            merged_data["labels"].extend(phrase_data.get("labels", [search_phrase] * len(phrase_data["bboxes"])))
                        if "quad_boxes" in phrase_data:
                            merged_data["quad_boxes"].extend(phrase_data["quad_boxes"])
                            if not merged_data["labels"]:
                                merged_data["labels"].extend(phrase_data.get("labels", [search_phrase] * len(phrase_data["quad_boxes"])))
                        if "polygons" in phrase_data:
                            merged_data["polygons"].extend(phrase_data["polygons"])
                            if not merged_data["labels"]:
                                merged_data["labels"].extend(phrase_data.get("labels", [search_phrase] * len(phrase_data["polygons"])))
                
                # Combine text results
                result = "\n".join(all_results)
                
                # Clean up empty lists from merged data
                data = {k: v for k, v in merged_data.items() if v}
                
                log.info(_LOG_PREFIX, f"  Merged: {len(data.get('bboxes', []))} bboxes, {len(data.get('labels', []))} labels")
            else:
                # Single prompt mode (original behavior)
                result, data = generate_transformers(
                    smart_lm_instance=instance,
                    model_family="Florence2",
                    image=input_image,
                    prompt=task_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    num_beams=num_beams,
                    do_sample=do_sample,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    text_input=florence_text_input,
                    convert_to_bboxes=convert_to_bboxes,
                    detection_filter_threshold=detection_filter_threshold,
                    nms_iou_threshold=nms_iou_threshold,
                )
        
        elif model_family == "Mistral":
            # Mistral VL generation - check if using vLLM or Transformers
            import json
            
            # Text-only tasks that should NOT use images even if connected
            TEXT_ONLY_TASKS = [
                "Tags to Natural Language", "Natural Language to Tags",
                "Refine & Expand Prompt", "Expand Text",
                "Summarize", "Rewrite Style", "Translate to English"
            ]
            # Tasks that use images if connected, but also work with text-only
            FLEXIBLE_TASKS = ["Direct Chat", "Custom Instruction", "Question Answering"]
            has_text_input = text is not None or (user_prompt and user_prompt.strip())
            has_image_input = input_image is not None
            is_text_only_task = (task_name in TEXT_ONLY_TASKS and has_text_input) or \
                               (task_name in FLEXIBLE_TASKS and has_text_input and not has_image_input)
            
            if is_text_only_task:
                log.debug(_LOG_PREFIX, f"  Text-only task '{task_name}' with text input - skipping image")
            
            if is_text_only_task:
                # For text-only tasks, prepend system prompt to the text input
                text_content = text if text is not None else user_prompt
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{text_content}"
                else:
                    prompt = text_content
            elif task_name in FLEXIBLE_TASKS and has_image_input and user_prompt and user_prompt.strip():
                # Flexible task (Direct Chat, Custom Instruction, Question Answering) with image + user_prompt
                # User's prompt IS the instruction - use it directly without system prompt prefix
                prompt = user_prompt.strip() + "\n\n"
            elif text is not None and task_name == "Custom":
                # Custom task with text input - use text as-is (full control)
                prompt = text
            elif text is not None:
                # Text input with non-Custom task - combine system prompt with text as user message
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{text}"
                else:
                    prompt = text
            elif task_name == "Custom":
                # Custom task uses user_prompt directly
                prompt = user_prompt if user_prompt else "Describe this image in detail."
            else:
                # Use system prompt from task mapping for vision tasks
                # user_prompt serves as hint/additional context (only visible when text is not connected)
                system_instruction = _get_system_instruction(task_name)
                user_hint = f"Additional context: {user_prompt.strip()}" if user_prompt and user_prompt.strip() else ""
                
                if system_instruction:
                    # Use proper format: system prompt + separator + (optional user hint)
                    prompt = f"{system_instruction}\n\n{user_hint}" if user_hint else f"{system_instruction}\n\n"
                else:
                    # Fallback to task name or default
                    log.warning(_LOG_PREFIX, f"No system prompt mapping for '{task_name}', using task name as prompt")
                    prompt = task_name or "Describe this image in detail."
                    if user_hint:
                        prompt += f"\n\n{user_hint}"
            
            log.debug(_LOG_PREFIX, f"  Prompt: {prompt[:100] if prompt else 'None'}...")
            log.debug(_LOG_PREFIX, f"  Generation params: temp={temperature}, top_p={top_p}, top_k={top_k}, beams={num_beams}, sample={do_sample}, rep_pen={repetition_penalty}")
            
            # Check if using vLLM backend
            if hasattr(instance, 'is_vllm') and instance.is_vllm:
                # Distinguish between vLLM Docker and Native
                is_vllm_native = hasattr(instance, 'is_vllm_native') and instance.is_vllm_native
                if is_vllm_native:
                    from ..core.smartlm_vllm_native import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Native)")
                else:
                    from ..core.smartlm_vllm_docker import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Docker)")
                
                # vLLM needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result = generate_vllm(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}  # vLLM doesn't return structured data
            elif hasattr(instance, 'is_sglang') and instance.is_sglang:
                # SGLang Docker generation path
                from ..core.smartlm_sglang_docker import generate_sglang
                log.debug(_LOG_PREFIX, "  Using generate_sglang (Docker) for Mistral")
                
                # SGLang needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result = generate_sglang(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}  # SGLang doesn't return structured data
            elif hasattr(instance, 'is_ollama') and instance.is_ollama:
                # Ollama Docker generation path
                from ..core.smartlm_ollama_docker import generate_ollama
                log.debug(_LOG_PREFIX, "  Using generate_ollama (Docker) for Mistral")
                
                # Ollama needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result, _ = generate_ollama(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}  # Ollama doesn't return structured data
            elif hasattr(instance, 'is_llamacpp_docker') and instance.is_llamacpp_docker:
                # llama.cpp Docker generation path
                from ..core.smartlm_llamacpp_docker import generate_llamacpp
                log.debug(_LOG_PREFIX, "  Using generate_llamacpp (Docker) for Mistral")
                
                # llama.cpp needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result, _ = generate_llamacpp(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}  # llama.cpp doesn't return structured data
            else:
                # Transformers generation path
                from ..core.smartlm_transformers import generate_transformers
                log.debug(_LOG_PREFIX, "  Using generate_transformers for Mistral")
                
                # Skip image for text-only tasks
                effective_image = None if is_text_only_task else input_image
                
                result, data = generate_transformers(
                    smart_lm_instance=instance,
                    model_family="Mistral3",
                    image=effective_image,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    num_beams=num_beams,
                    do_sample=do_sample,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
        
        elif model_family == "LLM (Text-Only)":
            # Text-only LLM generation
            import json
            
            text_content = text if text is not None else user_prompt
            
            # Check that we have a prompt to process
            if not text_content or not text_content.strip():
                raise ValueError("LLM requires a prompt. Please provide text via the 'text' input or enter a prompt in 'user_prompt'.")
            
            # Get system instruction for this task
            system_instruction = _get_system_instruction(task_name)
            

            
            # Convert task_name to llm_mode key (e.g., "Direct Chat" -> "direct_chat")
            llm_mode_key = task_name.lower().replace(" ", "_")
            
            # Build prompt with system instruction
            if system_instruction:
                prompt = f"{system_instruction}\n\n{text_content}"
            else:
                prompt = text_content
            
            log.debug(_LOG_PREFIX, f"  LLM task: {task_name}")
            log.debug(_LOG_PREFIX, f"  Generation params: temp={temperature}, top_p={top_p}, top_k={top_k}, rep_pen={repetition_penalty}")
            
            # Check if using vLLM Docker backend
            if hasattr(instance, 'is_vllm') and instance.is_vllm:
                is_vllm_native = hasattr(instance, 'is_vllm_native') and instance.is_vllm_native
                if is_vllm_native:
                    from ..core.smartlm_vllm_native import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Native) for LLM")
                else:
                    from ..core.smartlm_vllm_docker import generate_vllm
                    log.debug(_LOG_PREFIX, "  Using generate_vllm (Docker) for LLM")
                
                # System instruction is already prepended to prompt
                result, raw_output = generate_vllm(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=None,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    llm_mode=llm_mode_key,
                )
            elif hasattr(instance, 'is_sglang') and instance.is_sglang:
                # SGLang Docker generation path for LLM
                from ..core.smartlm_sglang_docker import generate_sglang
                log.debug(_LOG_PREFIX, "  Using generate_sglang (Docker) for LLM")
                
                # System instruction is already prepended to prompt
                result, raw_output = generate_sglang(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=None,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    llm_mode=llm_mode_key,
                )
            elif hasattr(instance, 'is_ollama') and instance.is_ollama:
                # Ollama Docker generation path for LLM
                from ..core.smartlm_ollama_docker import generate_ollama
                log.debug(_LOG_PREFIX, "  Using generate_ollama (Docker) for LLM")
                
                # System instruction is already prepended to prompt
                result, raw_output = generate_ollama(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=None,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    llm_mode=llm_mode_key,
                )
            elif hasattr(instance, 'is_llamacpp_docker') and instance.is_llamacpp_docker:
                # llama.cpp Docker generation path for LLM
                from ..core.smartlm_llamacpp_docker import generate_llamacpp
                log.debug(_LOG_PREFIX, "  Using generate_llamacpp (Docker) for LLM")
                
                result, raw_output = generate_llamacpp(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=None,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    llm_mode=llm_mode_key,
                )
            else:
                # Transformers/GGUF path
                if instance.is_gguf:
                    from ..core.smartlm_gguf import generate_gguf
                    log.debug(_LOG_PREFIX, "  Using generate_gguf for LLM (GGUF)")
                    
                    result = generate_gguf(
                        smart_lm_instance=instance,
                        model_type="text",
                        image=None,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                    )
                    raw_output = result
                else:
                    from ..core.smartlm_transformers import generate_transformers
                    log.debug(_LOG_PREFIX, "  Using generate_transformers for LLM")
                    
                    result, data = generate_transformers(
                        smart_lm_instance=instance,
                        model_family="LLM",
                        image=None,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        llm_mode=llm_mode_key,
                        instruction_template="",
                    )
                    raw_output = data.get("raw_output", result) if data else result
            # Store raw output (includes thinking tags) in data for debugging/analysis
            data = {"raw_output": raw_output} if raw_output != result else {}
        
        elif model_family == "LLaVA":
            # LLaVA family - generic vision models from Ollama registry
            # Currently only supported via Ollama Docker
            import json
            
            # Text-only tasks that should NOT use images even if connected
            TEXT_ONLY_TASKS = [
                "Tags to Natural Language", "Natural Language to Tags",
                "Refine & Expand Prompt", "Expand Text",
                "Summarize", "Rewrite Style", "Translate to English"
            ]
            # Tasks that use images if connected, but also work with text-only
            FLEXIBLE_TASKS = ["Direct Chat", "Custom Instruction", "Question Answering"]
            has_text_input = text is not None or (user_prompt and user_prompt.strip())
            has_image_input = input_image is not None
            is_text_only_task = (task_name in TEXT_ONLY_TASKS and has_text_input) or \
                               (task_name in FLEXIBLE_TASKS and has_text_input and not has_image_input)
            
            if is_text_only_task:
                log.debug(_LOG_PREFIX, f"  Text-only task '{task_name}' with text input - skipping image")
            
            if is_text_only_task:
                # For text-only tasks, prepend system prompt to the text input
                text_content = text if text is not None else user_prompt
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{text_content}"
                else:
                    prompt = text_content
            elif task_name in FLEXIBLE_TASKS and has_image_input and user_prompt and user_prompt.strip():
                # Flexible task (Direct Chat, Custom Instruction, Question Answering) with image + user_prompt
                # User's prompt IS the instruction - use it directly without system prompt prefix
                prompt = user_prompt.strip() + "\n\n"
            elif text is not None:
                # Text input overrides everything for vision tasks
                prompt = text
            elif task_name == "Custom":
                # Custom task uses user_prompt directly
                base_prompt = user_prompt if user_prompt else "Describe this image in detail."
                prompt = f"{base_prompt}\n\n"
            else:
                # Use system prompt from task mapping (_task_dict via get_system_prompt)
                base_prompt = _get_system_instruction(task_name)
                if not base_prompt:
                    log.warning(_LOG_PREFIX, f"No system prompt mapping for '{task_name}', using task name as prompt")
                    base_prompt = task_name or "Describe this image in detail."
                prompt = base_prompt + "\n\n"
                
                # Add user_prompt as additional context if provided
                if user_prompt and user_prompt.strip():
                    prompt += f"\n\nAdditional context: {user_prompt.strip()}"
            
            log.debug(_LOG_PREFIX, f"  Generation params: temp={temperature}, top_p={top_p}, top_k={top_k}, rep_pen={repetition_penalty}")
            log.debug(_LOG_PREFIX, f"  input_image is None: {input_image is None}")
            
            if hasattr(instance, 'is_ollama') and instance.is_ollama:
                # Ollama Docker generation path for LLaVA
                from ..core.smartlm_ollama_docker import generate_ollama
                log.debug(_LOG_PREFIX, "  Using generate_ollama (Docker) for LLaVA")
                
                # Ollama needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    log.debug(_LOG_PREFIX, f"  Converting input_image to temp files, shape: {input_image.shape}")
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result, _ = generate_ollama(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}
            elif hasattr(instance, 'is_llamacpp_docker') and instance.is_llamacpp_docker:
                # llama.cpp Docker generation path for LLaVA
                from ..core.smartlm_llamacpp_docker import generate_llamacpp
                log.debug(_LOG_PREFIX, "  Using generate_llamacpp (Docker) for LLaVA")
                
                # llama.cpp Docker needs image paths, not tensors - save temp images if needed
                # Skip images for text-only tasks
                image_paths = None
                if input_image is not None and not is_text_only_task:
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    log.debug(_LOG_PREFIX, f"  Converting input_image to temp files, shape: {input_image.shape}")
                    image_paths = []
                    # Handle batch of images
                    if input_image.dim() == 4:
                        for i in range(input_image.shape[0]):
                            img_tensor = input_image[i]
                            img_array = (img_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                            img_pil = PILImage.fromarray(img_array)
                            
                            # Save to ComfyUI temp folder (cleared on startup)
                            temp_path = get_comfyui_temp_image_path('.jpg')
                            img_pil.save(temp_path, 'JPEG', quality=95)
                            image_paths.append(temp_path)
                    else:
                        img_array = (input_image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
                        img_pil = PILImage.fromarray(img_array)
                        temp_path = get_comfyui_temp_image_path('.jpg')
                        img_pil.save(temp_path, 'JPEG', quality=95)
                        image_paths.append(temp_path)
                
                result, _ = generate_llamacpp(
                    smart_lm_instance=instance,
                    prompt=prompt,
                    image_paths=image_paths,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                )
                
                # Cleanup temp files
                if image_paths:
                    for path in image_paths:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
                
                data = {}
            elif instance.is_gguf:
                # GGUF generation path for LLaVA (llama-cpp-python with Llava16ChatHandler)
                from ..core.smartlm_gguf import generate_gguf
                log.debug(_LOG_PREFIX, "  Using generate_gguf for LLaVA (GGUF)")
                
                # Skip image for text-only tasks
                effective_image = None if is_text_only_task else input_image
                
                result = generate_gguf(
                    smart_lm_instance=instance,
                    model_type="vision",
                    image=effective_image,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    frame_count=frame_count,
                )
                data = {}
            else:
                # Transformers generation path for LLaVA (includes LLaVA 1.5, 1.6, and Mllama/Llama 3.2 Vision)
                from ..core.smartlm_transformers import generate_transformers
                log.debug(_LOG_PREFIX, "  Using generate_transformers for LLaVA")
                
                # Skip image for text-only tasks
                effective_image = None if is_text_only_task else input_image
                
                result, data = generate_transformers(
                    smart_lm_instance=instance,
                    model_family="LLaVA",
                    image=effective_image,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    num_beams=num_beams,
                    do_sample=do_sample,
                    seed=seed,
                    repetition_penalty=repetition_penalty,
                    frame_count=frame_count,
                )
        
        else:
            raise ValueError(f"Unknown model family: {model_family}")
        
        # Multi-task mode: run additional tasks (task chaining for LLMs)
        # Skip for Florence - it uses prompt splitting (handled above), not task chaining
        # Florence multi-task is: same task + different prompts, not different tasks chained together
        if multi_task_mode and len(tasks_to_run) > 1 and model_family == "Florence":
            # Florence already handled multi-prompt mode above (if applicable)
            # Don't run the task chaining logic below
            multi_task_mode = False
        
        if multi_task_mode and len(tasks_to_run) > 1:
            # Clear GGUF state after first task (which may have processed images)
            # This prevents VRAM accumulation when chaining to text-only tasks
            if hasattr(instance, 'is_gguf') and instance.is_gguf:
                from ..core.smartlm_gguf import clear_gguf_state_between_tasks
                clear_gguf_state_between_tasks(instance)
                log.debug(_LOG_PREFIX, "Cleared GGUF state after task 1 (before multi-task chain)")
            
            # Collect all task results
            all_task_results = [{
                "step": 1,
                "task": tasks_to_run[0],
                "result": result,
                "data": data if data else None
            }]
            
            current_text = result  # Chain output to next input
            
            # Run remaining tasks
            for task_idx in range(1, len(tasks_to_run)):
                current_task = tasks_to_run[task_idx]
                task_family, task_name = parse_task(current_task)
                
                log.info(_LOG_PREFIX, f"Multi-task step {task_idx + 1}/{len(tasks_to_run)}: {task_name}")
                
                # Clear GGUF model state between tasks to prevent VRAM accumulation
                # Clears KV cache and image embeddings but keeps model loaded
                if hasattr(instance, 'is_gguf') and instance.is_gguf:
                    from ..core.smartlm_gguf import clear_gguf_state_between_tasks
                    clear_gguf_state_between_tasks(instance)
                    log.debug(_LOG_PREFIX, f"  Cleared GGUF state before task {task_idx + 1}")
                
                # Check if previous result is empty - stop chain
                if not current_text or not current_text.strip():
                    log.warning(_LOG_PREFIX, f"Task {task_idx} returned empty, stopping chain")
                    break
                
                # For chained tasks, use text-only mode (previous output as input)
                # The image is still available but the task operates on text
                task_result = ""
                task_data = {}
                
                # Build prompt from previous result using system instruction
                system_instruction = _get_system_instruction(task_name)
                if system_instruction:
                    prompt = f"{system_instruction}\n\n{current_text}"
                else:
                    prompt = current_text
                
                # Convert task_name to llm_mode key for few-shot examples
                chained_llm_mode = task_name.lower().replace(" ", "_")
                
                # Generate based on backend type (reuse the instance)
                if hasattr(instance, 'is_vllm') and instance.is_vllm:
                    is_vllm_native = hasattr(instance, 'is_vllm_native') and instance.is_vllm_native
                    if is_vllm_native:
                        from ..core.smartlm_vllm_native import generate_vllm
                    else:
                        from ..core.smartlm_vllm_docker import generate_vllm
                    task_result = generate_vllm(
                        smart_lm_instance=instance,
                        prompt=prompt,
                        image_paths=None,  # Text-only for chained tasks
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        llm_mode=chained_llm_mode,
                    )
                elif hasattr(instance, 'is_sglang') and instance.is_sglang:
                    from ..core.smartlm_sglang_docker import generate_sglang
                    task_result = generate_sglang(
                        smart_lm_instance=instance,
                        prompt=prompt,
                        image_paths=None,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        llm_mode=chained_llm_mode,
                    )
                elif hasattr(instance, 'is_ollama') and instance.is_ollama:
                    from ..core.smartlm_ollama_docker import generate_ollama
                    task_result, _ = generate_ollama(
                        smart_lm_instance=instance,
                        prompt=prompt,
                        image_paths=None,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        llm_mode=chained_llm_mode,
                    )
                elif hasattr(instance, 'is_llamacpp_docker') and instance.is_llamacpp_docker:
                    from ..core.smartlm_llamacpp_docker import generate_llamacpp
                    task_result, _ = generate_llamacpp(
                        smart_lm_instance=instance,
                        prompt=prompt,
                        image_paths=None,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        llm_mode=chained_llm_mode,
                    )
                elif hasattr(instance, 'is_gguf') and instance.is_gguf:
                    from ..core.smartlm_gguf import generate_gguf
                    task_result = generate_gguf(
                        smart_lm_instance=instance,
                        model_type="text",  # Text-only for chained tasks
                        image=None,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        frame_count=frame_count,
                        llm_mode=chained_llm_mode,
                    )
                else:
                    # Transformers - text-only generation for chained tasks
                    from ..core.smartlm_transformers import generate_transformers
                    task_result, task_data = generate_transformers(
                        smart_lm_instance=instance,
                        model_family=model_family,  # Use actual model family
                        image=None,  # Text-only for chained tasks
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        num_beams=num_beams,
                        do_sample=do_sample,
                        seed=seed,
                        repetition_penalty=repetition_penalty,
                        frame_count=frame_count,
                        llm_mode=chained_llm_mode,
                    )
                
                # Collect result
                all_task_results.append({
                    "step": task_idx + 1,
                    "task": current_task,
                    "result": task_result,
                    "data": task_data if task_data else None
                })
                
                # Update for next iteration
                current_text = task_result
                result = task_result  # Update final result
            
            # Build final data output with all task results
            data = {
                "multi_task": True,
                "task_count": len(all_task_results),
                "tasks": all_task_results,
                "final_result": result
            }
            
            log.info(_LOG_PREFIX, f"✓ Multi-task complete: {len(all_task_results)} tasks executed")
        
        # Generate visualization for detection tasks
        output_image = None
        
        if data and ("bboxes" in data or "quad_boxes" in data or "polygons" in data):
            try:
                from ..core.smartlm_transformers import draw_bboxes
                output_image = draw_bboxes(input_image if input_image is not None else images, data)
            except Exception as e:
                log.warning(_LOG_PREFIX, f"Could not draw bounding boxes: {e}")
                output_image = input_image if input_image is not None else images
        else:
            if images is not None:
                output_image = images
            else:
                # Create blank image
                output_image = torch.zeros((1, 64, 64, 3))
        
        # Calculate elapsed time
        elapsed = time.time() - start_time
        char_count = len(result)
        log.info(_LOG_PREFIX, f"Generated {char_count} characters in {elapsed:.2f}s")
        
        # Auto-save changed settings to template using TemplateContext
        # Only save widget settings if the template was EXPLICITLY selected by user
        # Auto-created templates (during model download) should not have widget settings overwritten
        # Use actual_template_name which may have been updated during model download
        template_to_save = actual_template_name if actual_template_name else template_name
        if template_to_save and template_to_save != "None" and template_was_explicitly_selected:
            # Preserve human-readable display name when saving templates.
            task_to_save = task
            if ": " in task_to_save:
                # If task was prefixed for execution (e.g., "Florence: region_caption"), extract the token
                task_to_save = task_to_save.split(": ", 1)[1]

            # For Florence, ensure we save the human-friendly display name
            if model_family == "Florence":
                from ..core.smartlm_templates import resolve_florence_display_from_id
                # If it's a known machine key, map to display name
                id_to_display = MODEL_CONFIGS.get("_id_to_display", {})
                task_to_save = (task_to_save or '').strip()
                if task_to_save in id_to_display:
                    task_to_save = resolve_florence_display_from_id(task_to_save)
                else:
                    # Verify it's a known display name in the authoritative TASK_DICT
                    task_dict = MODEL_CONFIGS.get("_task_dict", {}) or {}
                    if task_to_save not in task_dict:
                        raise RuntimeError(f"Invalid Florence task when saving template: '{task_to_save}' not found as id or display")

            # Create context and save to template
            save_ctx = TemplateContext()
            save_ctx.template_name = template_to_save
            save_ctx.model_family = model_family
            save_ctx.loading_method = loading_method
            save_ctx.quantization = quantization
            save_ctx.attention_mode = attention_mode
            save_ctx.max_tokens = max_tokens
            save_ctx.default_task = task_to_save
            save_ctx.context_size = context_size
            save_ctx.save_to_template(auto_save=True)
        
        # Cleanup if not keeping model loaded
        # Note: GGUF models CAN now be cached with keep_model_loaded=True
        # We have proper KV cache clearing between calls to prevent VRAM accumulation
        is_gguf = loading_method == "GGUF (llama-cpp-python)"
        is_vllm_native = loading_method == "vLLM (Native)"
        is_vllm_docker = loading_method == "vLLM (Docker)"
        is_ollama_docker = loading_method == "Ollama (Docker)"
        is_llamacpp_docker = loading_method == "llama.cpp (Docker)"
        should_cleanup = not keep_model_loaded
        
        # Handle Docker container auto-stop (separate from keep_model_loaded)
        if is_vllm_docker and auto_stop_container:
            from ..core import smartlm_vllm_docker
            vllm_config = smartlm_vllm_docker.get_vllm_config()
            if vllm_config.get("stop_after_generation", False):
                log.info(_LOG_PREFIX, "Stopping vLLM container to free VRAM...")
                smartlm_vllm_docker.stop_vllm_container()
                log.info(_LOG_PREFIX, "✓ vLLM container stopped")
        
        if is_ollama_docker and auto_stop_container:
            from ..core import smartlm_ollama_docker
            log.info(_LOG_PREFIX, "Stopping Ollama container to free VRAM...")
            smartlm_ollama_docker.stop_ollama_container()
            log.info(_LOG_PREFIX, "✓ Ollama container stopped")
        
        if is_llamacpp_docker and auto_stop_container:
            from ..core import smartlm_llamacpp_docker
            log.info(_LOG_PREFIX, "Stopping llama.cpp container to free VRAM...")
            smartlm_llamacpp_docker.stop_llamacpp_container()
            log.info(_LOG_PREFIX, "✓ llama.cpp container stopped")
        
        # Determine if this is a Transformers model (not GGUF, not Docker, not vLLM)
        is_transformers = loading_method.lower() == "transformers"
        
        if should_cleanup:
            # For vLLM Native, use proper unload function to clear cache
            if is_vllm_native:
                from ..core import smartlm_vllm_native
                log.info(_LOG_PREFIX, "Unloading vLLM Native model from cache...")
                smartlm_vllm_native.unload_vllm(instance, model_path)
            
            # For GGUF models, use proper cleanup that handles chat_handler (CLIP model)
            # This calls the C-level cleanup functions (clip_free, llama_free)
            if is_gguf:
                from ..core.smartlm_gguf import cleanup_gguf_model, cleanup_chat_handler_vision
                from ..core.smartlm_base_v2 import clear_gguf_cache, is_gguf_cache_empty
                log.info(_LOG_PREFIX, "Cleaning up GGUF model and chat_handler...")
                
                # Check if model is in cache (keep_model_loaded=True case)
                if not is_gguf_cache_empty():
                    # Model was cached - clear cache will handle cleanup
                    clear_gguf_cache()
                else:
                    # Model was NOT cached (keep_model_loaded=False) - cleanup directly
                    # First cleanup the chat_handler (vision encoder) attached to the model
                    actual_model = instance.model if hasattr(instance, 'model') else instance
                    if actual_model is not None:
                        if hasattr(actual_model, '_eclipse_chat_handler') and actual_model._eclipse_chat_handler is not None:
                            log.debug(_LOG_PREFIX, "Cleaning up chat_handler from non-cached model")
                            cleanup_chat_handler_vision(actual_model._eclipse_chat_handler)
                            actual_model._eclipse_chat_handler = None
                        if hasattr(actual_model, 'chat_handler') and actual_model.chat_handler is not None:
                            log.debug(_LOG_PREFIX, "Cleaning up model.chat_handler")
                            cleanup_chat_handler_vision(actual_model.chat_handler)
                            actual_model.chat_handler = None
                        # Now close the model itself
                        if hasattr(actual_model, 'close') and callable(actual_model.close):
                            actual_model.close()
                
                # Null out references on the wrapper
                if hasattr(instance, 'model'):
                    instance.model = None
                if hasattr(instance, 'chat_handler_ref'):
                    instance.chat_handler_ref = None
            
            # For Transformers models, use proper cleanup
            # NOTE: Don't move to CPU - it's very slow for large models (10-30+ seconds for 7B+)
            # Instead, clear cached states and let GC + CUDA empty_cache() handle VRAM cleanup
            if is_transformers:
                from ..core.smartlm_base_v2 import clear_transformers_cache, is_transformers_cache_empty
                log.info(_LOG_PREFIX, "Cleaning up Transformers model...")
                
                if not is_transformers_cache_empty():
                    # Model was cached - clear cache will handle cleanup
                    clear_transformers_cache()
                else:
                    # Model was NOT cached - cleanup directly
                    actual_model = instance.model if hasattr(instance, 'model') else instance
                    if actual_model is not None:
                        # Clear cached states/gradients to help free memory
                        if hasattr(actual_model, 'eval'):
                            actual_model.eval()
                        if hasattr(actual_model, 'zero_grad'):
                            try:
                                actual_model.zero_grad(set_to_none=True)
                            except Exception:
                                pass
                
                # Null out references on the wrapper
                if hasattr(instance, 'model'):
                    instance.model = None
                if hasattr(instance, 'processor'):
                    instance.processor = None
            
            # Delete references to allow garbage collection
            try:
                del instance
            except Exception:
                pass
            try:
                del model
            except Exception:
                pass
            try:
                del processor
            except Exception:
                pass
            
            # Force garbage collection multiple times
            import gc
            for _ in range(3):
                gc.collect()
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                try:
                    torch.cuda.ipc_collect()
                except Exception:
                    pass
        
        return (output_image, result, data)

NODE_NAME = 'Smart Language Model Loader v2 [Eclipse]'
NODE_DESC = 'Smart Language Model Loader v2'

NODE_CLASS_MAPPINGS = {
    NODE_NAME: RvLoader_SmartLoader_LM_v2
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}
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

# Eclipse Server Endpoints
#
# Centralized REST API endpoints for all Eclipse functionality:
# - Wildcard management (list, refresh, process)
# - Template management (loader, smartlm, advanced defaults)
# - SmartLM model discovery and search
# - Smart Prompt folder/file access

import json
import os
import re
import shutil
from typing import Dict, Any, List, Optional

import folder_paths
from server import PromptServer
from aiohttp import web

from .wildcard_engine import (get_wildcard_list, wildcard_load, process)
from .logger import log
from .smartlm_templates import get_llm_models_path, get_config_value
from .regex_patterns import RE_LEADING_NUMBERS

# Module-level storage for wildcard path (set by WildcardEndpoints)
_wildcard_path: Optional[str] = None



def is_safe_filename(filename: str) -> bool:
    # Validate filename to prevent path traversal attacks.
    # Returns True if filename is safe (no path separators or traversal).
    if not filename:
        log.warning("Security", "Blocked empty filename")
        return False
    # Block path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        log.warning("Security", f"Blocked path traversal attempt in filename: {filename}")
        return False
    # Block null bytes
    if '\x00' in filename:
        log.warning("Security", f"Blocked null byte in filename: {repr(filename)}")
        return False
    return True


class WildcardEndpoints:
    # Manages wildcard server endpoints.

    def __init__(self, wildcard_path: Optional[str] = None):
        #nitialize endpoints.
        # 
        # Args:
        #     wildcard_path: Path to wildcard directory. If None, uses default.
        global _wildcard_path
        
        if wildcard_path is None:
            wildcard_path = self._get_default_wildcard_path()
        
        self.wildcard_path = wildcard_path
        _wildcard_path = wildcard_path  # Store at module level for reload_all
        
        # Load wildcards on initialization
        log.msg("Wildcard", f"Loading wildcards from: {wildcard_path}")
        wildcard_load(wildcard_path)
        
        self._register_endpoints()
    
    def _get_default_wildcard_path(self) -> str:
        # Determine the default wildcard path.
        # 
        # Priority:
        # 1. ComfyUI/models/wildcards (create if doesn't exist and copy examples)
        # 2. Extension's wildcards/ folder (fallback)
        # 
        # Returns:
        #     Path to wildcard directory
        # Extension's wildcard folder (fallback)
        extension_root = os.path.dirname(os.path.dirname(__file__))
        extension_wildcard_path = os.path.join(extension_root, "wildcards")
        
        # Try to find ComfyUI root (go up from custom_nodes/ComfyUI_Eclipse_X)
        comfyui_root = os.path.abspath(os.path.join(extension_root, "..", ".."))
        models_wildcard_path = os.path.join(comfyui_root, "models", "wildcards")
        
        # Check if we're actually in a ComfyUI installation
        if os.path.exists(os.path.join(comfyui_root, "models")):
            # Create models/wildcards directory if it doesn't exist
            if not os.path.exists(models_wildcard_path):
                try:
                    os.makedirs(models_wildcard_path, exist_ok=True)
                    log.msg("Wildcard", f"Created directory: {models_wildcard_path}")
                    
                    # Copy example files from extension's wildcards folder
                    if os.path.exists(extension_wildcard_path):
                        self._copy_example_wildcards(extension_wildcard_path, models_wildcard_path)
                except Exception as e:
                    log.error("Wildcard", f"Failed to create {models_wildcard_path}: {e}")
                    return extension_wildcard_path
            
            return models_wildcard_path
        else:
            # Not in a standard ComfyUI structure, use extension folder
            log.msg("Wildcard", "Using extension's wildcard folder (ComfyUI models dir not found)")
            return extension_wildcard_path
    
    def _copy_example_wildcards(self, source_dir: str, dest_dir: str) -> None:
        # Copy example wildcard files from source to destination.
        # 
        # Args:
        #     source_dir: Source directory with example wildcards
        #     dest_dir: Destination directory
        import shutil
        
        try:
            copied_count = 0
            for filename in os.listdir(source_dir):
                if filename.endswith(('.txt', '.yaml', '.yml')):
                    source_file = os.path.join(source_dir, filename)
                    dest_file = os.path.join(dest_dir, filename)
                    
                    # Only copy if destination doesn't exist
                    if not os.path.exists(dest_file):
                        shutil.copy2(source_file, dest_file)
                        copied_count += 1
            
            if copied_count > 0:
                log.msg("Wildcard", f"Copied {copied_count} example wildcard files to {dest_dir}")
        except Exception as e:
            log.error("Wildcard", f"Error copying example wildcards: {e}")

    def _register_endpoints(self):
        # Register all endpoints with PromptServer.
        
        @PromptServer.instance.routes.get("/eclipse/wildcards/list")
        async def handle_get_wildcard_list(request):
            # GET /eclipse/wildcards/list
            # 
            # Returns:
            #     JSON list of available wildcards in format: ['__keyword1__', '__keyword2__', ...]
            try:
                wildcard_list = get_wildcard_list()
                return web.json_response(wildcard_list)
            except Exception as e:
                log.error("Wildcard", f"Error getting wildcard list: {e}")
                return web.json_response([])

        @PromptServer.instance.routes.get("/eclipse/wildcards/refresh")
        async def handle_refresh_wildcards(request):
            # GET /eclipse/wildcards/refresh
            # 
            # Reloads wildcards from disk. Useful for discovering newly added wildcard files.
            # 
            # Returns:
            #     JSON with success status and count of loaded wildcards
            try:
                wildcard_load(self.wildcard_path)
                wildcard_list = get_wildcard_list()
                
                return web.json_response({
                    "success": True,
                    "message": f"Loaded {len(wildcard_list)} wildcard groups",
                    "count": len(wildcard_list)
                })
            except Exception as e:
                log.error("Wildcard", f"Error refreshing wildcards: {e}")
                return web.json_response({
                    "success": False,
                    "message": str(e),
                    "count": 0
                })

        @PromptServer.instance.routes.post("/eclipse/wildcards/process")
        async def handle_process_wildcards(request):
            # POST /eclipse/wildcards/process
            # 
            # Process text with wildcard expansion.
            # 
            # Request JSON:
            # {
            #     "text": "Text with __wildcards__ and {options|go|here}",
            #     "seed": 12345 (optional)
            # }
            # 
            # Returns:
            #     JSON with processed text
            try:
                # Parse request body
                if request.content_length:
                    body = await request.json()
                else:
                    body = {}

                text = body.get("text", "")
                seed = body.get("seed", None)

                if not isinstance(text, str):
                    return web.json_response({
                        "success": False,
                        "error": "Invalid text parameter"
                    })

                # Process the text
                result = process(text, seed=seed)

                return web.json_response({
                    "success": True,
                    "input": text,
                    "output": result,
                    "seed": seed
                })

            except Exception as e:
                log.error("Wildcard", f"Error processing wildcards: {e}")
                return web.json_response({
                    "success": False,
                    "error": str(e)
                })

        log.msg("Wildcard", "Registered server endpoints")


def onprompt_populate_wildcards(json_data):
    # Preprocess wildcard nodes before execution.
    # 
    # This runs BEFORE ComfyUI's execution engine, allowing us to:
    # 1. Detect seed connections in the prompt
    # 2. Extract actual seed values from connected nodes
    # 3. Process wildcards with the correct seed
    # 4. Update the prompt with processed text
    # 5. Does NOT switch mode or send UI feedback (for realtime preview support)
    prompt = json_data.get('prompt', {})
    
    for node_id, node_data in prompt.items():
        # Check if this is a Wildcard Processor node (old version)
        if 'class_type' not in node_data:
            continue
            
        if node_data['class_type'] != 'Wildcard Processor [Eclipse]':
            continue
        
        inputs = node_data.get('inputs', {})
        mode = inputs.get('mode', 'populate')
        
        # In fixed mode, normalize the seed to 0 to ensure caching works
        # The seed is not used for wildcard processing in fixed mode
        if mode == 'fixed':
            # Force seed to 0 in fixed mode so cache works regardless of seed changes
            inputs['seed'] = 0
            continue
        
        # Only process wildcards in populate mode
        if mode != 'populate':
            continue
        
        wildcard_text = inputs.get('wildcard_text', '')
        if not wildcard_text or not isinstance(wildcard_text, str):
            continue
        
        # Get seed - check if it's connected (list format) or widget value (int)
        seed_value = inputs.get('seed', 0)
        
        if isinstance(seed_value, list):
            # Seed is connected - extract actual value from connected node
            try:
                connected_node_id = str(seed_value[0])
                connected_node = prompt.get(connected_node_id)
                
                if not connected_node:
                    log.warning("Wildcard", f"Connected seed node {connected_node_id} not found")
                    continue
                
                class_type = connected_node.get('class_type', '')
                connected_inputs = connected_node.get('inputs', {})
                
                # Handle different seed node types (like Impact Pack does)
                if class_type == 'Seed (rgthree)':
                    input_seed = int(connected_inputs.get('seed', 0))
                elif class_type in ['ImpactInt', 'Primitive', 'PrimitiveNode']:
                    input_seed = int(connected_inputs.get('value', 0))
                else:
                    # Try common parameter names
                    input_seed = None
                    for key in ['seed', 'value', 'number', 'int']:
                        if key in connected_inputs:
                            value = connected_inputs[key]
                            if not isinstance(value, list):  # Not another connection
                                input_seed = int(value)
                                break
                    
                    if input_seed is None:
                        log.warning("Wildcard", f"Could not extract seed from node type: {class_type}")
                        continue
                
            except Exception as e:
                log.error("Wildcard", f"Error extracting seed from connection: {e}")
                continue
        else:
            # Seed is a direct value
            input_seed = int(seed_value)
        
        # Process wildcards with the determined seed
        try:
            processed_text = process(wildcard_text, seed=input_seed)
            
            # Update the populated_text in the prompt (this is what gets sent to execute)
            inputs['populated_text'] = processed_text
            
            # Also update the seed input so execute() receives the actual seed used
            # This ensures the seed is saved correctly in metadata
            inputs['seed'] = input_seed
            
        except Exception as e:
            log.error("Wildcard", f"Error processing wildcards for node {node_id}: {e}")
    
    # CRITICAL: Must return json_data for the handler chain to continue
    return json_data


class EclipseTemplateEndpoints:
    # Eclipse template and configuration server endpoints.
    
    def __init__(self):
        # Get paths
        self.extension_root = os.path.dirname(os.path.dirname(__file__))
        self.eclipse_dir = os.path.join(folder_paths.models_dir, "Eclipse")
        self.eclipse_prompt_dir = os.path.join(self.eclipse_dir, "smart_prompt")
        self.eclipse_loader_dir = os.path.join(self.eclipse_dir, "loader_templates")
        self.eclipse_smartlm_dir = os.path.join(self.eclipse_dir, "smartlm_templates")
        self.repo_prompt_dir = os.path.join(self.extension_root, "templates", "prompt")
        self.repo_loader_dir = os.path.join(self.extension_root, "templates", "loader_templates")
        self.repo_smartlm_dir = os.path.join(self.extension_root, "templates", "smartlm_templates")
        self.config_path = os.path.join(self.extension_root, "eclipse_config.json")
        
        self._register_endpoints()
    
    def _get_dev_mode(self) -> bool:
        # Check if dev mode is enabled.
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('dev_mode', False)
        except Exception:
            pass
        return False
    
    def _register_endpoints(self):
        # Register all template-related endpoints.
        
        # ==================== LOADER TEMPLATES ====================
        
        @PromptServer.instance.routes.get("/eclipse/loader_templates/{filename}")
        async def serve_loader_template(request):
            # Serve a loader template file.
            filename = request.match_info.get('filename', '')
            
            # Security: validate filename BEFORE path operations
            if not is_safe_filename(filename):
                return web.Response(status=400, text="Invalid filename")
            if not filename.endswith('.json'):
                return web.Response(status=400, text="Invalid file type")
            
            dev_mode = self._get_dev_mode()
            template_dir = self.repo_loader_dir if dev_mode else self.eclipse_loader_dir
            template_path = os.path.join(template_dir, filename)
            
            # Security: double-check path stays within template directory
            if not os.path.abspath(template_path).startswith(os.path.abspath(template_dir)):
                return web.Response(status=403, text="Access denied")
            
            if os.path.exists(template_path) and os.path.isfile(template_path):
                return web.FileResponse(template_path)
            else:
                return web.Response(status=404, text="Template not found")
        
        @PromptServer.instance.routes.get("/eclipse/loader_templates_list")
        async def get_loader_templates_list(request):
            # Get list of available loader templates.
            from .loader_templates import get_template_list
            templates = get_template_list()
            return web.json_response(templates)
        
        # ==================== MODEL FILE LISTS ====================
        
        @PromptServer.instance.routes.get("/eclipse/model_files/{folder_type}")
        async def get_model_files(request):
            # GET /eclipse/model_files/{folder_type}
            #
            # Returns list of model files for the specified folder type.
            # Supported folder types: checkpoints, diffusion_models, vae, loras, clip, text_encoders
            #
            # This forces a fresh scan of the folder (clears any cached file lists).
            folder_type = request.match_info.get('folder_type', '')
            
            # Allowed folder types for security
            allowed_folders = {
                "checkpoints", "diffusion_models", "diffusion_models_gguf",
                "vae", "loras", "clip", "text_encoders"
            }
            
            if folder_type not in allowed_folders:
                return web.json_response({"error": f"Invalid folder type: {folder_type}"}, status=400)
            
            # Check if folder is registered
            if folder_type not in folder_paths.folder_names_and_paths:
                return web.json_response(["None"])
            
            try:
                # Clear cached file list to force fresh scan
                if hasattr(folder_paths, 'filename_list_cache') and folder_type in folder_paths.filename_list_cache:
                    del folder_paths.filename_list_cache[folder_type]
                if hasattr(folder_paths, 'cache_helper'):
                    folder_paths.cache_helper.cache.pop(("get_filename_list", folder_type), None)
                
                # Get fresh file list
                files = folder_paths.get_filename_list(folder_type)
                return web.json_response(["None"] + list(files))
            except Exception as e:
                log.error("Model Files", f"Error getting {folder_type} files: {e}")
                return web.json_response(["None"])
        
        @PromptServer.instance.routes.get("/eclipse/model_files_all")
        async def get_all_model_files(request):
            # GET /eclipse/model_files_all
            #
            # Returns all model file lists in one request for efficiency.
            # Forces fresh scan of all folders.
            result = {}
            folders = ["checkpoints", "diffusion_models", "vae", "loras", "clip", "text_encoders"]
            
            # Add diffusion_models_gguf if registered
            if "diffusion_models_gguf" in folder_paths.folder_names_and_paths:
                folders.append("diffusion_models_gguf")
            
            for folder_type in folders:
                try:
                    # Clear cached file list
                    if hasattr(folder_paths, 'filename_list_cache') and folder_type in folder_paths.filename_list_cache:
                        del folder_paths.filename_list_cache[folder_type]
                    if hasattr(folder_paths, 'cache_helper'):
                        folder_paths.cache_helper.cache.pop(("get_filename_list", folder_type), None)
                    
                    # Get fresh file list
                    if folder_type in folder_paths.folder_names_and_paths:
                        files = folder_paths.get_filename_list(folder_type)
                        result[folder_type] = ["None"] + list(files)
                    else:
                        result[folder_type] = ["None"]
                except Exception as e:
                    result[folder_type] = ["None"]
            
            # Combine clip and text_encoders for convenience
            clip_combined = set(result.get("clip", ["None"]))
            clip_combined.update(result.get("text_encoders", []))
            result["clip_combined"] = sorted(list(clip_combined))
            
            return web.json_response(result)
        
        # ==================== SMARTLM TEMPLATES ====================
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_templates/{filename}")
        async def serve_smartlm_template(request):
            # Serve a SmartLM template file.
            filename = request.match_info.get('filename', '')
            
            # Security: validate filename BEFORE path operations
            if not is_safe_filename(filename):
                return web.Response(status=400, text="Invalid filename")
            if not filename.endswith('.json'):
                return web.Response(status=400, text="Invalid file type")
            
            dev_mode = self._get_dev_mode()
            
            eclipse_path = os.path.join(self.eclipse_smartlm_dir, filename)
            repo_path = os.path.join(self.repo_smartlm_dir, filename)
            
            # Security: double-check paths stay within template directories
            if not (os.path.abspath(eclipse_path).startswith(os.path.abspath(self.eclipse_smartlm_dir)) or
                    os.path.abspath(repo_path).startswith(os.path.abspath(self.repo_smartlm_dir))):
                return web.Response(status=403, text="Access denied")
            
            if dev_mode:
                if os.path.exists(repo_path) and os.path.isfile(repo_path):
                    return web.FileResponse(repo_path)
                return web.Response(status=404, text="Template not found in repo")
            
            # Production: Eclipse first, then repo fallback
            if os.path.exists(eclipse_path) and os.path.isfile(eclipse_path):
                return web.FileResponse(eclipse_path)
            elif os.path.exists(repo_path) and os.path.isfile(repo_path):
                return web.FileResponse(repo_path)
            else:
                return web.Response(status=404, text="Template not found")
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_templates_list")
        async def get_smartlm_templates_list(request):
            # Get list of available SmartLM templates.
            from .smartlm_templates import get_template_list
            templates = get_template_list()
            return web.json_response(templates)
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_v2/mmproj_list")
        async def get_mmproj_list_v2(request):
            # Get list of available mmproj files in models/LLM/ folder.
            from .smartlm_files import get_mmproj_list
            mmproj_files = get_mmproj_list()
            return web.json_response(mmproj_files)
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_v2/discover_models")
        async def discover_models_v2(request):
            # Discover available models in models/LLM/ folder with family detection.
            from .smartlm_files import discover_models_in_folder
            models = discover_models_in_folder()
            return web.json_response(models)
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_v2/method_support")
        async def get_method_support_v2(request):
            # Get method support matrix for v2 node.
            from .smartlm_types import METHOD_SUPPORT_V2, LoadingMethod, ModelFamily
            
            result = {}
            for method, families in METHOD_SUPPORT_V2.items():
                method_name = method.value
                result[method_name] = {}
                for family in ModelFamily:
                    result[method_name][family.value] = family in families
            
            return web.json_response(result)
        
        @PromptServer.instance.routes.post("/eclipse/smartlm_templates/{filename}")
        async def update_smartlm_template(request):
            # Update template settings from frontend.
            filename = request.match_info.get('filename', '')
            
            # Security: validate filename BEFORE any path operations
            if not is_safe_filename(filename):
                return web.Response(status=400, text="Invalid filename")
            if not filename.endswith('.json'):
                return web.Response(status=400, text="Invalid file type")
            
            dev_mode = self._get_dev_mode()
            
            eclipse_path = os.path.join(self.eclipse_smartlm_dir, filename)
            repo_path = os.path.join(self.repo_smartlm_dir, filename)
            
            # Security check
            if not (os.path.abspath(eclipse_path).startswith(os.path.abspath(self.eclipse_smartlm_dir)) or
                    os.path.abspath(repo_path).startswith(os.path.abspath(self.repo_smartlm_dir))):
                return web.Response(status=403, text="Access denied")
            
            # Determine which path to use
            if dev_mode:
                if os.path.exists(repo_path):
                    template_path = repo_path
                else:
                    return web.Response(status=404, text="Template not found in repo")
            else:
                if os.path.exists(eclipse_path):
                    template_path = eclipse_path
                elif os.path.exists(repo_path):
                    # Copy to Eclipse folder first
                    os.makedirs(self.eclipse_smartlm_dir, exist_ok=True)
                    shutil.copy2(repo_path, eclipse_path)
                    template_path = eclipse_path
                    log.msg("SmartLM", f"Copied template to Eclipse folder for editing: {filename}")
                else:
                    return web.Response(status=404, text="Template not found")
            
            try:
                updates = await request.json()
                
                with open(template_path, 'r') as f:
                    template_data = json.load(f)
                
                changes = []
                for key, value in updates.items():
                    # Save default_task exactly as provided by the frontend (do not convert Florence display names)
                    # The frontend is responsible for mapping legacy machine keys to display names when loading.
                    if template_data.get(key) != value:
                        template_data[key] = value
                        changes.append(f"{key}={value}")
                
                if changes:
                    with open(template_path, 'w') as f:
                        json.dump(template_data, f, indent=2)
                    template_name = filename.replace('.json', '')
                    log.msg("SmartLM", f"✓ Auto-saved template '{template_name}': {', '.join(changes)}")
                    return web.json_response({"success": True, "changes": changes})
                else:
                    return web.json_response({"success": True, "changes": []})
            
            except Exception as e:
                log.error("SmartLM", f"Error updating template {filename}: {e}")
                return web.Response(status=500, text=str(e))
        
        # ==================== ADVANCED DEFAULTS ====================
        
        @PromptServer.instance.routes.get("/eclipse/smartlml_advanced_defaults")
        async def get_smartlml_advanced_defaults(request):
            # Get advanced defaults config.
            dev_mode = self._get_dev_mode()
            eclipse_config = os.path.join(self.eclipse_dir, 'config', 'smartlm_advanced_defaults.json')
            repo_config = os.path.join(self.extension_root, 'templates', 'config', 'smartlm_advanced_defaults.json')
            
            config_path = repo_config if dev_mode else (eclipse_config if os.path.exists(eclipse_config) else repo_config)
            
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    return web.json_response(config_data)
                else:
                    return web.json_response({})
            except Exception as e:
                log.error("SmartLM", f"Error loading advanced defaults: {e}")
                return web.Response(status=500, text=str(e))

        @PromptServer.instance.routes.get("/eclipse/smartlm_prompt_defaults")
        async def get_smartlm_prompt_defaults(request):
            # Serve processed prompt defaults (authoritative task dict)
            try:
                # Import processed configs from core module (build_task_dict runs at import)
                from ..core import smartlm_templates as st
                task_dict = st.MODEL_CONFIGS.get("_task_dict", None)
                id_to_display = st.MODEL_CONFIGS.get("_id_to_display", {})
                preset_prompts = st.MODEL_CONFIGS.get("_preset_prompts", {})

                if task_dict is None:
                    raise RuntimeError("Task dict not available; prompt defaults may be invalid")

                return web.json_response({"_task_dict": task_dict, "_id_to_display": id_to_display, "_preset_prompts": preset_prompts})
            except Exception as e:
                log.error("SmartLM", f"Error loading processed prompt defaults: {e}")
                return web.Response(status=500, text=str(e))
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_reload_configs")
        async def reload_smartlm_configs(request):
            # Reload prompt defaults and few-shot configs from disk
            # Call this when user edits config files and refreshes the page
            try:
                from ..core import smartlm_templates as st
                result = st.reload_prompt_configs()
                return web.json_response(result)
            except Exception as e:
                log.error("SmartLM", f"Error reloading configs: {e}")
                return web.json_response({"success": False, "error": str(e)})
        
        @PromptServer.instance.routes.get("/eclipse/reload_all")
        async def reload_all_configs(request):
            # GET /eclipse/reload_all
            #
            # Reloads ALL Eclipse configs and caches from disk:
            # - SmartLM prompt defaults and few-shot training
            # - Wildcards
            # - Styles
            #
            # Templates and folder contents are read fresh each request (no cache).
            results = {"success": True, "reloaded": []}
            
            # 1. Reload SmartLM configs
            try:
                from ..core import smartlm_templates as st
                config_result = st.reload_prompt_configs()
                if config_result.get("success"):
                    results["reloaded"].append(f"SmartLM configs ({config_result.get('tasks', 0)} tasks)")
                    results["smartlm"] = config_result
                else:
                    results["smartlm_error"] = config_result.get("error")
            except Exception as e:
                results["smartlm_error"] = str(e)
            
            # 2. Reload wildcards
            try:
                from .wildcard_engine import wildcard_load, get_wildcard_list
                if _wildcard_path:
                    wildcard_load(_wildcard_path)
                    wc_count = len(get_wildcard_list())
                    results["reloaded"].append(f"Wildcards ({wc_count} groups)")
                    results["wildcards"] = {"count": wc_count}
                else:
                    results["wildcards_error"] = "Wildcard path not initialized"
            except Exception as e:
                results["wildcards_error"] = str(e)
            
            # 3. Reload styles
            try:
                from .styles import reload_styles as core_reload_styles
                style_result = core_reload_styles()
                if style_result.get("success"):
                    results["reloaded"].append(f"Styles ({style_result.get('total_styles', 0)} styles)")
                    results["styles"] = style_result
                else:
                    results["styles_error"] = style_result.get("error")
            except Exception as e:
                results["styles_error"] = str(e)
            
            log.msg("Eclipse", f"Reload all: {', '.join(results['reloaded'])}")
            return web.json_response(results)
        
        @PromptServer.instance.routes.post("/eclipse/smartlml_advanced_defaults")
        async def post_smartlml_advanced_defaults(request):
            # Save advanced defaults config.
            try:
                updates = await request.json()
                
                if not updates or 'model_type' not in updates:
                    return web.Response(status=400, text="Missing model_type in request")
                
                model_type = updates.pop('model_type')
                params = updates
                
                eclipse_config = os.path.join(self.eclipse_dir, 'config', 'smartlm_advanced_defaults.json')
                os.makedirs(os.path.dirname(eclipse_config), exist_ok=True)
                
                repo_config = os.path.join(self.extension_root, 'templates', 'config', 'smartlm_advanced_defaults.json')
                config_read_path = eclipse_config if os.path.exists(eclipse_config) else repo_config
                
                current_config = {}
                if os.path.exists(config_read_path):
                    with open(config_read_path, 'r', encoding='utf-8') as f:
                        current_config = json.load(f)
                
                if model_type not in current_config:
                    current_config[model_type] = {}
                
                current_config[model_type].update(params)
                
                with open(eclipse_config, 'w', encoding='utf-8') as f:
                    json.dump(current_config, f, indent=2)
                
                changes = [f"{key}={value}" for key, value in params.items()]
                log.msg("SmartLM", f"✓ Auto-saved advanced defaults for {model_type}: {', '.join(changes)}")
                
                return web.json_response({"success": True, "changes": changes})
            
            except Exception as e:
                log.error("SmartLM", f"Error saving advanced defaults: {e}")
                return web.Response(status=500, text=str(e))
        
        # ==================== SMART PROMPT / FOLDER FILES ====================
        
        @PromptServer.instance.routes.get("/eclipse/folder_files/{folder}")
        async def get_folder_files(request):
            # Get files from a smart prompt folder.
            folder = request.match_info.get('folder', '')
            if not folder:
                return web.json_response({})
            
            # Primary: check Eclipse smart_prompt
            folder_path = os.path.join(self.eclipse_prompt_dir, folder)
            if not os.path.isdir(folder_path):
                folder_path = os.path.join(self.repo_prompt_dir, folder)
            
            files = {}
            if os.path.isdir(folder_path):
                folder_name = os.path.basename(folder_path)
                clean_folder_name = RE_LEADING_NUMBERS.sub('', folder_name)
                
                folder_files = []
                for fname in os.listdir(folder_path):
                    if fname.lower().endswith('.txt') and fname.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                        try:
                            number = int(fname.split('_')[0])
                            folder_files.append((number, fname))
                        except ValueError:
                            continue
                folder_files.sort(key=lambda x: x[0])
                
                for number, fname in folder_files:
                    base = os.path.splitext(fname)[0]
                    clean_base = RE_LEADING_NUMBERS.sub('', base).replace('_', ' ')
                    display = f"{clean_folder_name} {clean_base}"
                    fpath = os.path.join(folder_path, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            lines = [line.strip() for line in f if line.strip()]
                            files[display] = lines
                    except Exception:
                        files[display] = []
            
            return web.json_response(files)
        
        @PromptServer.instance.routes.get("/eclipse/widget_folder_mapping")
        async def get_widget_folder_mapping(request):
            # Get widget-to-folder mapping for smart prompt.
            prompt_dir = self.eclipse_prompt_dir
            if not os.path.isdir(prompt_dir):
                prompt_dir = self.repo_prompt_dir
            
            mapping = {}
            if os.path.isdir(prompt_dir):
                for item in os.listdir(prompt_dir):
                    item_path = os.path.join(prompt_dir, item)
                    if os.path.isdir(item_path):
                        folder_name = os.path.basename(item_path)
                        clean_folder_name = RE_LEADING_NUMBERS.sub('', folder_name)
                        
                        folder_files = []
                        for fname in os.listdir(item_path):
                            if fname.lower().endswith('.txt') and fname.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                                try:
                                    number = int(fname.split('_')[0])
                                    folder_files.append((number, fname))
                                except ValueError:
                                    continue
                        folder_files.sort(key=lambda x: x[0])
                        
                        for number, fname in folder_files:
                            base = os.path.splitext(fname)[0]
                            clean_base = RE_LEADING_NUMBERS.sub('', base).replace('_', ' ')
                            display = f"{clean_folder_name} {clean_base}"
                            mapping[display] = clean_folder_name
            
            return web.json_response(mapping)
        
        log.msg("SmartLM", "Registered template and config endpoints")


class LoadImageFolderEndpoints:
    # Manages Load Image From Folder server endpoints.
    
    # Supported image extensions (must match RvImage_LoadImageFromFolder.py)
    SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')
    
    def __init__(self):
        self._register_endpoints()
    
    def _resolve_folder_path(self, folder_path: str) -> str:
        # Resolve folder path - can be absolute or relative to input directory.
        if not folder_path:
            return folder_paths.get_input_directory()
        
        # Strip quotes from path
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
        comfyui_root = os.path.dirname(os.path.dirname(folder_paths.get_input_directory()))
        root_relative = os.path.join(comfyui_root, folder_path)
        if os.path.exists(root_relative):
            return root_relative
        
        return folder_path
    
    def _count_images(self, folder_path: str, include_subfolders: bool) -> int:
        # Count image files in folder.
        count = 0
        
        if not os.path.exists(folder_path):
            return 0
        
        if include_subfolders:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(self.SUPPORTED_EXTENSIONS):
                        count += 1
        else:
            for file in os.listdir(folder_path):
                filepath = os.path.join(folder_path, file)
                if os.path.isfile(filepath) and file.lower().endswith(self.SUPPORTED_EXTENSIONS):
                    count += 1
        
        return count
    
    def _register_endpoints(self):
        @PromptServer.instance.routes.post("/eclipse/load_image_folder/count")
        async def get_image_count(request):
            # POST /eclipse/load_image_folder/count
            #
            # Returns the total image count for given folder path(s).
            # Request body: {"folder_path": "...", "include_subfolders": false}
            # folder_path can contain multiple paths separated by newlines.
            try:
                data = await request.json()
                folder_path = data.get("folder_path", "")
                include_subfolders = data.get("include_subfolders", False)
                
                # Parse multiple folders (one per line)
                folder_lines = [f.strip() for f in folder_path.strip().split('\n') if f.strip()]
                
                total_count = 0
                folder_counts = []
                
                for folder_line in folder_lines:
                    resolved_path = self._resolve_folder_path(folder_line)
                    if os.path.exists(resolved_path):
                        count = self._count_images(resolved_path, include_subfolders)
                        total_count += count
                        folder_counts.append({"path": folder_line, "count": count})
                    else:
                        folder_counts.append({"path": folder_line, "count": 0, "error": "not_found"})
                
                return web.json_response({
                    "total_count": total_count,
                    "folders": folder_counts
                })
            except Exception as e:
                log.error("LoadImageFolder", f"Error getting image count: {e}")
                return web.json_response({"error": str(e), "total_count": 0}, status=500)
        
        @PromptServer.instance.routes.post("/eclipse/load_image_folder/invalidate_cache")
        async def invalidate_cache(request):
            # POST /eclipse/load_image_folder/invalidate_cache
            #
            # Invalidates the file list cache for a folder.
            # Request body: {"folder_path": "..."}
            try:
                data = await request.json()
                folder_path = data.get("folder_path", "")
                
                # Import FileListCache from the core module
                try:
                    from .file_cache import FileListCache
                    resolved_path = self._resolve_folder_path(folder_path)
                    FileListCache.invalidate(resolved_path)
                    return web.json_response({"success": True, "path": resolved_path})
                except ImportError:
                    return web.json_response({"success": False, "error": "FileListCache not available"})
            except Exception as e:
                log.error("LoadImageFolder", f"Error invalidating cache: {e}")
                return web.json_response({"error": str(e), "success": False}, status=500)
        
        log.msg("LoadImageFolder", "Registered folder endpoints")


class PromptStylerEndpoints:
    # Manages Prompt Styler server endpoints.
    
    def __init__(self):
        self._register_endpoints()
    
    def _register_endpoints(self):
        @PromptServer.instance.routes.get("/eclipse/prompt_styler/styles/{mode}")
        async def get_styles_for_mode(request):
            # GET /eclipse/prompt_styler/styles/{mode}
            #
            # Returns styles for the specified mode (tag_based or natural_language).
            try:
                mode = request.match_info.get('mode', 'tag_based')
                
                # Import from core styles module
                from .styles import get_styles_for_mode as core_get_styles_for_mode
                
                # Get styles for the requested mode
                styles = core_get_styles_for_mode(mode)
                
                return web.json_response({
                    "mode": mode,
                    "styles": styles,
                    "count": len(styles)
                })
            except Exception as e:
                log.error("PromptStyler", f"Error getting styles for mode {mode}: {e}")
                return web.json_response({"error": str(e), "styles": []}, status=500)
        
        @PromptServer.instance.routes.get("/eclipse/prompt_styler/reload")
        async def reload_styles(request):
            # GET /eclipse/prompt_styler/reload
            #
            # Reloads styles from disk. Useful for discovering newly added style files.
            try:
                from .styles import reload_styles as core_reload_styles
                result = core_reload_styles()
                log.msg("PromptStyler", f"Reloaded styles: {result['total_styles']} total")
                return web.json_response(result)
            except Exception as e:
                log.error("PromptStyler", f"Error reloading styles: {e}")
                return web.json_response({"success": False, "error": str(e)}, status=500)
        
        log.msg("PromptStyler", "Registered style endpoints")


# Initialize endpoints when module is imported
def initialize_endpoints(wildcard_path: Optional[str] = None):
    # Initialize all Eclipse server endpoints.
    #
    # Args:
    #     wildcard_path: Path to wildcard directory. If None, uses default.
    try:
        WildcardEndpoints(wildcard_path)
        EclipseTemplateEndpoints()
        LoadImageFolderEndpoints()
        PromptStylerEndpoints()
        
        # Register prompt handler for wildcard preprocessing
        PromptServer.instance.add_on_prompt_handler(onprompt_populate_wildcards)
        
        log.msg("Endpoints", "All server endpoints initialized successfully")
    except Exception as e:
        log.error("Endpoints", f"Failed to initialize endpoints: {e}")




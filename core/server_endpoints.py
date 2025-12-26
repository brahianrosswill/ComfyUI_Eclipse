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


# Local logging helpers
def msg_log(prefix: str, message: str):
    # Print regular message (always shown).
    log.msg(prefix, message)


def warning_log(prefix: str, message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning(prefix, message)


def error_log(prefix: str, message: str):
    # Print error message (always shown).
    log.error(prefix, message)


class WildcardEndpoints:
    # Manages wildcard server endpoints.

    def __init__(self, wildcard_path: Optional[str] = None):
        #nitialize endpoints.
        # 
        # Args:
        #     wildcard_path: Path to wildcard directory. If None, uses default.
        if wildcard_path is None:
            wildcard_path = self._get_default_wildcard_path()
        
        self.wildcard_path = wildcard_path
        
        # Load wildcards on initialization
        msg_log("Wildcard", f"Loading wildcards from: {wildcard_path}")
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
                    msg_log("Wildcard", f"Created directory: {models_wildcard_path}")
                    
                    # Copy example files from extension's wildcards folder
                    if os.path.exists(extension_wildcard_path):
                        self._copy_example_wildcards(extension_wildcard_path, models_wildcard_path)
                except Exception as e:
                    error_log("Wildcard", f"Failed to create {models_wildcard_path}: {e}")
                    return extension_wildcard_path
            
            return models_wildcard_path
        else:
            # Not in a standard ComfyUI structure, use extension folder
            msg_log("Wildcard", "Using extension's wildcard folder (ComfyUI models dir not found)")
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
                msg_log("Wildcard", f"Copied {copied_count} example wildcard files to {dest_dir}")
        except Exception as e:
            error_log("Wildcard", f"Error copying example wildcards: {e}")

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
                error_log("Wildcard", f"Error getting wildcard list: {e}")
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
                error_log("Wildcard", f"Error refreshing wildcards: {e}")
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
                error_log("Wildcard", f"Error processing wildcards: {e}")
                return web.json_response({
                    "success": False,
                    "error": str(e)
                })

        msg_log("Wildcard", "Registered server endpoints")


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
                    warning_log("Wildcard", f"Connected seed node {connected_node_id} not found")
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
                        warning_log("Wildcard", f"Could not extract seed from node type: {class_type}")
                        continue
                
            except Exception as e:
                error_log("Wildcard", f"Error extracting seed from connection: {e}")
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
            error_log("Wildcard", f"Error processing wildcards for node {node_id}: {e}")
    
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
        except:
            pass
        return False
    
    def _register_endpoints(self):
        # Register all template-related endpoints.
        
        # ==================== LOADER TEMPLATES ====================
        
        @PromptServer.instance.routes.get("/eclipse/loader_templates/{filename}")
        async def serve_loader_template(request):
            # Serve a loader template file.
            filename = request.match_info.get('filename', '')
            if not filename.endswith('.json'):
                return web.Response(status=400, text="Invalid file type")
            
            dev_mode = self._get_dev_mode()
            template_dir = self.repo_loader_dir if dev_mode else self.eclipse_loader_dir
            template_path = os.path.join(template_dir, filename)
            
            # Security: prevent directory traversal
            if not os.path.abspath(template_path).startswith(os.path.abspath(template_dir)):
                return web.Response(status=403, text="Access denied")
            
            if os.path.exists(template_path) and os.path.isfile(template_path):
                return web.FileResponse(template_path)
            else:
                return web.Response(status=404, text="Template not found")
        
        @PromptServer.instance.routes.get("/eclipse/loader_templates_list")
        async def get_loader_templates_list(request):
            # Get list of available loader templates.
            # Import here to avoid circular imports
            from ..py.RvLoader_SmartLoader import get_template_list
            templates = get_template_list()
            return web.json_response(templates)
        
        # ==================== SMARTLM TEMPLATES ====================
        
        @PromptServer.instance.routes.get("/eclipse/smartlm_templates/{filename}")
        async def serve_smartlm_template(request):
            # Serve a SmartLM template file.
            filename = request.match_info.get('filename', '')
            if not filename.endswith('.json'):
                return web.Response(status=400, text="Invalid file type")
            
            dev_mode = self._get_dev_mode()
            
            eclipse_path = os.path.join(self.eclipse_smartlm_dir, filename)
            repo_path = os.path.join(self.repo_smartlm_dir, filename)
            
            # Security: prevent directory traversal
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
                    msg_log("SmartLM", f"Copied template to Eclipse folder for editing: {filename}")
                else:
                    return web.Response(status=404, text="Template not found")
            
            try:
                updates = await request.json()
                
                with open(template_path, 'r') as f:
                    template_data = json.load(f)
                
                changes = []
                for key, value in updates.items():
                    if template_data.get(key) != value:
                        template_data[key] = value
                        changes.append(f"{key}={value}")
                
                if changes:
                    with open(template_path, 'w') as f:
                        json.dump(template_data, f, indent=2)
                    template_name = filename.replace('.json', '')
                    msg_log("SmartLM", f"✓ Auto-saved template '{template_name}': {', '.join(changes)}")
                    return web.json_response({"success": True, "changes": changes})
                else:
                    return web.json_response({"success": True, "changes": []})
            
            except Exception as e:
                error_log("SmartLM", f"Error updating template {filename}: {e}")
                return web.Response(status=500, text=str(e))
        
        # ==================== ADVANCED DEFAULTS ====================
        
        @PromptServer.instance.routes.get("/eclipse/smartlml_advanced_defaults")
        async def get_smartlml_advanced_defaults(request):
            # Get advanced defaults config.
            eclipse_config = os.path.join(self.eclipse_dir, 'config', 'smartlm_advanced_defaults.json')
            repo_config = os.path.join(self.extension_root, 'templates', 'config', 'smartlm_advanced_defaults.json')
            
            config_path = eclipse_config if os.path.exists(eclipse_config) else repo_config
            
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    return web.json_response(config_data)
                else:
                    return web.json_response({})
            except Exception as e:
                error_log("SmartLM", f"Error loading advanced defaults: {e}")
                return web.Response(status=500, text=str(e))
        
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
                msg_log("SmartLM", f"✓ Auto-saved advanced defaults for {model_type}: {', '.join(changes)}")
                
                return web.json_response({"success": True, "changes": changes})
            
            except Exception as e:
                error_log("SmartLM", f"Error saving advanced defaults: {e}")
                return web.Response(status=500, text=str(e))
        
        # ==================== LOAD IMAGE FROM FOLDER ====================
        
        @PromptServer.instance.routes.post("/eclipse/load_image_folder/invalidate_cache")
        async def invalidate_load_image_folder_cache(request):
            """Invalidate file list cache for LoadImageFromFolder node."""
            try:
                data = await request.json()
                folder_path = data.get("folder_path", "")
                
                if folder_path:
                    # Import and call the cache invalidation
                    from ..py.RvImage_LoadImageFromFolder import FileListCache
                    FileListCache.invalidate(folder_path)
                    msg_log("LoadImageFromFolder", f"Cache invalidated for: {folder_path}")
                    return web.json_response({"success": True, "folder": folder_path})
                else:
                    # Invalidate all caches if no specific folder
                    from ..py.RvImage_LoadImageFromFolder import FileListCache
                    FileListCache.invalidate()
                    msg_log("LoadImageFromFolder", "All caches invalidated")
                    return web.json_response({"success": True, "folder": "all"})
                    
            except Exception as e:
                error_log("LoadImageFromFolder", f"Error invalidating cache: {e}")
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
                clean_folder_name = re.sub(r'^[0-9_]+', '', folder_name)
                
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
                    clean_base = re.sub(r'^[0-9_]+', '', base).replace('_', ' ')
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
                        clean_folder_name = re.sub(r'^[0-9_]+', '', folder_name)
                        
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
                            clean_base = re.sub(r'^[0-9_]+', '', base).replace('_', ' ')
                            display = f"{clean_folder_name} {clean_base}"
                            mapping[display] = clean_folder_name
            
            return web.json_response(mapping)
        
        msg_log("SmartLM", "Registered template and config endpoints")


class PromptStylerEndpoints:
    """Manages Prompt Styler server endpoints."""
    
    def __init__(self):
        self._register_endpoints()
    
    def _register_endpoints(self):
        @PromptServer.instance.routes.get("/eclipse/prompt_styler/styles/{mode}")
        async def get_styles_for_mode(request):
            """
            GET /eclipse/prompt_styler/styles/{mode}
            
            Returns styles for the specified mode (tag_based or natural_language).
            """
            try:
                mode = request.match_info.get('mode', 'tag_based')
                
                # Import here to avoid circular imports
                from ..py.RvTools_PromptStyler import RvTools_PromptStyler
                
                # Get styles for the requested mode
                styles = RvTools_PromptStyler.names_by_mode.get(mode, [])
                
                return web.json_response({
                    "mode": mode,
                    "styles": styles,
                    "count": len(styles)
                })
            except Exception as e:
                error_log("PromptStyler", f"Error getting styles for mode {mode}: {e}")
                return web.json_response({"error": str(e), "styles": []}, status=500)
        
        msg_log("PromptStyler", "Registered style endpoints")


# Initialize endpoints when module is imported
def initialize_endpoints(wildcard_path: Optional[str] = None):
    # Initialize all Eclipse server endpoints.
    #
    # Args:
    #     wildcard_path: Path to wildcard directory. If None, uses default.
    try:
        WildcardEndpoints(wildcard_path)
        EclipseTemplateEndpoints()
        PromptStylerEndpoints()
        
        # Register prompt handler for wildcard preprocessing
        PromptServer.instance.add_on_prompt_handler(onprompt_populate_wildcards)
        
        msg_log("Endpoints", "All server endpoints initialized successfully")
    except Exception as e:
        error_log("Endpoints", f"Failed to initialize endpoints: {e}")



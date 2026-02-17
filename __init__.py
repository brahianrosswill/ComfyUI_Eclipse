# ComfyUI_Eclipse Extension Loader
# Initializes and loads all custom nodes for ComfyUI_Eclipse using the ComfyUI V3 extension API.
WEB_DIRECTORY = "./js"

import os
import json
from .core import version
from .core.logger import log, cstr

log.msg("", f"Version: {version}")

# Early check of wrappers (for consistent startup logging)
try:
    from .core import gguf_wrapper
except Exception as e:
    log.warning("GGUF Wrapper", f"Failed to load: {e}")

try:
    from .core import nunchaku_wrapper
except Exception as e:
    log.warning("Nunchaku Wrapper", f"Failed to load: {e}")

def get_ext_dir(subpath=None, mkdir=False):
    dir = os.path.dirname(__file__)
    if subpath is not None:
        dir = os.path.join(dir, subpath)
    dir = os.path.abspath(dir)
    if mkdir and not os.path.exists(dir):
        os.makedirs(dir)
    return dir

# Initialize Eclipse folder structure with templates (one-time copy on first run)
from .core.common import copy_prompt_files_once, create_junction, migrate_old_folders
import sys

comfyui_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
eclipse_dir = os.path.join(comfyui_root, 'models', 'Eclipse')

# Migrate user files from old locations (one-time migration)
migrate_old_folders(comfyui_root)

# Copy templates to models/Eclipse/ structure
repo_templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
repo_prompt_dir = os.path.join(repo_templates_dir, 'prompt')
repo_loader_dir = os.path.join(repo_templates_dir, 'loader_templates')
repo_styles_dir = os.path.join(repo_templates_dir, 'styles')
repo_patterns_dir = os.path.join(repo_templates_dir, 'patterns')

eclipse_prompt_dir = os.path.join(eclipse_dir, 'smart_prompt')
eclipse_loader_dir = os.path.join(eclipse_dir, 'loader_templates')
eclipse_styles_dir = os.path.join(eclipse_dir, 'styles')
eclipse_patterns_dir = os.path.join(eclipse_dir, 'patterns')

# Check if force_update or dev_mode is enabled in config
force_update = False
dev_mode = False
config_file = os.path.join(os.path.dirname(__file__), 'eclipse_config.json')
if os.path.exists(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            force_update = config_data.get('_force_update', False)
            dev_mode = config_data.get('dev_mode', False)
    except Exception:
        pass

def is_folder_empty_or_missing(folder_path):
    if not os.path.exists(folder_path):
        return True
    try:
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json') and os.path.isfile(os.path.join(folder_path, f))]
        return len(json_files) == 0
    except Exception:
        return True

# Dev mode: skip all template copying (work directly with repo templates)
if dev_mode:
    log.msg("", "Dev mode enabled - using repo templates directly")
else:
    # One-time copy of templates to Eclipse folder
    if not os.path.exists(eclipse_prompt_dir) and os.path.exists(repo_prompt_dir):
        copy_prompt_files_once(repo_prompt_dir, eclipse_prompt_dir)

    if not os.path.exists(eclipse_loader_dir) and os.path.exists(repo_loader_dir):
        copy_prompt_files_once(repo_loader_dir, eclipse_loader_dir)

    # Styles folder: copy on first run (user can add custom styles that persist across updates)
    if not os.path.exists(eclipse_styles_dir) and os.path.exists(repo_styles_dir):
        copy_prompt_files_once(repo_styles_dir, eclipse_styles_dir)
        log.msg("", "Style files copied to models/Eclipse/styles/")

    # Patterns folder: copy if missing/empty OR force_update
    patterns_folder_empty = is_folder_empty_or_missing(eclipse_patterns_dir)
    if patterns_folder_empty and os.path.exists(repo_patterns_dir):
        copy_prompt_files_once(repo_patterns_dir, eclipse_patterns_dir, force=True)
        log.msg("", "Pattern files copied to models/Eclipse/patterns/")
    elif force_update and os.path.exists(repo_patterns_dir):
        import shutil
        repo_pattern_files = {f for f in os.listdir(repo_patterns_dir) 
                             if os.path.isfile(os.path.join(repo_patterns_dir, f)) and f.endswith('.json')}
        os.makedirs(eclipse_patterns_dir, exist_ok=True)
        for item in repo_pattern_files:
            src = os.path.join(repo_patterns_dir, item)
            dst = os.path.join(eclipse_patterns_dir, item)
            shutil.copy2(src, dst)
        log.msg("", f"Force updated {len(repo_pattern_files)} pattern file(s)")

    # Reset force_update flag after updates are complete
    if force_update:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            config_data['_force_update'] = False
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            log.warning("", f"Could not reset _force_update flag: {e}")

# Create junction for wildcards/smart_prompt → Eclipse/smart_prompt (no duplication)
wildcards_smartprompt_dir = os.path.join(comfyui_root, 'models', 'wildcards', 'smart_prompt')
if not os.path.exists(wildcards_smartprompt_dir) and os.path.exists(eclipse_prompt_dir):
    create_junction(eclipse_prompt_dir, wildcards_smartprompt_dir)

# Update references to use Eclipse folder
models_smartprompt_dir = eclipse_prompt_dir
models_loader_dir = eclipse_loader_dir
repo_prompt_dir = eclipse_prompt_dir

# Initialize server endpoints
try:
    from .core.server_endpoints import initialize_endpoints
    initialize_endpoints()
except Exception as e:
    log.warning("", f"Failed to initialize server endpoints: {e}")

# V3 Extension Registration
from comfy_api.latest import ComfyExtension, io #type: ignore

class EclipseExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        # Conversion nodes
        from .py.RvConversion_ConcatMulti import RvConversion_ConcatMulti
        from .py.RvConversion_ConvertPrimitive import RvConversion_ConvertPrimitive
        from .py.RvConversion_ConvertToBatch import RvConversion_ConvertToBatch
        from .py.RvConversion_ConvertToList import RvConversion_ConvertToList
        from .py.RvConversion_DetectionToBboxes import RvConversion_DetectionToBboxes
        from .py.RvConversion_ImageConvert import RvConversion_ImageConvert
        from .py.RvConversion_Join import RvConversion_Join
        from .py.RvConversion_LoraStackToString import RvConversion_LoraStackToString
        from .py.RvConversion_MergeStrings import RvConversion_MergeStrings
        from .py.RvConversion_StringFromList import RvConversion_StringFromList
        from .py.RvConversion_WidgetToString import RvConversion_WidgetToString
        # Folder nodes
        from .py.RvFolder_AddFolder import RvFolder_AddFolder
        from .py.RvFolder_FilenamePrefix import RvFolder_FilenamePrefix
        from .py.RvFolder_SmartFolder import RvFolder_SmartFolder
        # Image nodes
        from .py.RvImage_AddWatermarkImage import RvImage_AddWatermarkImage
        from .py.RvImage_LoadImage import RvImage_LoadImage
        from .py.RvImage_LoadImageFromFolder import RvImage_LoadImageFromFolder
        from .py.RvImage_LoadImagePath import RvImage_LoadImagePath
        from .py.RvImage_LoadImagePath_Pipe import RvImage_LoadImagePath_Pipe
        from .py.RvImage_Preview_Image import RvImage_Preview_Image
        from .py.RvImage_Preview_Mask import RvImage_Preview_Mask
        from .py.RvImage_SaveImages import RvImage_SaveImages
        # Loader nodes
        from .py.RvLoader_Checkpoint_Loader_Small import RvLoader_Checkpoint_Loader_Small
        from .py.RvLoader_Checkpoint_Loader_Small_Pipe import RvLoader_Checkpoint_Loader_Small_Pipe
        from .py.RvLoader_SmartLoader import RvLoader_SmartLoader
        from .py.RvLoader_SmartLoader_Basic import RvLoader_SmartLoader_Basic
        from .py.RvLoader_SmartLoader_Plus import RvLoader_SmartLoader_Plus
        # Logic nodes
        from .py.RvLogic_Boolean import RvLogic_Boolean
        from .py.RvLogic_Float import RvLogic_Float
        from .py.RvLogic_Integer import RvLogic_Integer
        from .py.RvLogic_Integer_Gen import RvLogic_IntegerGen
        from .py.RvLogic_String import RvLogic_String
        # Pipe IO nodes
        from .py.RvPipe_IO_12CH_Any import RvPipe_IO_12CH_Any
        from .py.RvPipe_IO_Context_Image import RvPipe_IO_Context_Image
        from .py.RvPipe_IO_Context_Video import RvPipe_IO_Context_Video
        from .py.RvPipe_IO_Context_WanVideoWrapper import RvPipe_IO_Context_WanVideoWrapper
        from .py.RvPipe_IO_Generation_Data import RvPipe_IO_Generation_Data
        from .py.RvPipe_IO_Sampler_Settings import RvPipe_IO_Sampler_Settings
        # Pipe Out nodes
        from .py.RvPipe_Out_CheckpointLoader import RvPipe_Out_CheckpointLoader
        from .py.RvPipe_Out_LoadDirectorySettings import RvPipe_Out_LoadDirectorySettings
        from .py.RvPipe_Out_LoadImage import RvPipe_Out_LoadImage
        from .py.RvPipe_Out_Sampler_Settings import RvPipe_Out_Sampler_Settings
        from .py.RvPipe_Out_SmartFolder import RvPipe_Out_SmartFolder
        from .py.RvPipe_Out_VCNameGen import RvPipe_Out_VCNameGen
        from .py.RvPipe_Out_WanVideo_Setup import RvPipe_Out_WanVideo_Setup
        # Router nodes
        from .py.RvRouter_Any_DualSwitch import RvRouter_Any_DualSwitch
        from .py.RvRouter_Any_DualSwitch_purge import RvRouter_Any_DualSwitch_purge
        from .py.RvRouter_Any_MultiSwitch import RvRouter_Any_MultiSwitch
        from .py.RvRouter_Any_MultiSwitch_purge import RvRouter_Any_MultiSwitch_purge
        from .py.RvRouter_Any_Passer import RvRouter_Any_Passer
        from .py.RvRouter_Any_Passer_purge import RvRouter_Any_Passer_purge
        from .py.RvRouter_IfExecute import RvSwitch_IfExecute
        # Settings nodes
        from .py.RvSettings_ControlNetUnionType import RvSettings_ControlNetUnionType
        from .py.RvSettings_CustomSize import RvSettings_CustomSize
        from .py.RvSettings_Image_Resolution import RvSettings_Image_Resolution
        from .py.RvSettings_LoadDirectorySettings import RvSettings_LoadDirectorySettings
        from .py.RvSettings_Sampler_Selection import RvSettings_Sampler_Selection
        from .py.RvSettings_Sampler_Settings import RvSettings_Sampler_Settings
        from .py.RvSettings_Sampler_Settings_NI import RvSettings_Sampler_Settings_NI
        from .py.RvSettings_Sampler_Settings_NI_Seed import RvSettings_Sampler_Settings_NI_Seed
        from .py.RvSettings_Sampler_Settings_Seed import RvSettings_Sampler_Settings_Seed
        from .py.RvSettings_Sampler_Settings_Small import RvSettings_Sampler_Settings_Small
        from .py.RvSettings_Sampler_Settings_Small_Seed import RvSettings_Sampler_Settings_Small_Seed
        from .py.RvSettings_VCNameGen_v1 import RvSettings_VCNameGen_v1
        from .py.RvSettings_VCNameGen_v2 import RvSettings_VCNameGen_v2
        from .py.RvSettings_WanVideo_Setup import RvSettings_WanVideo_Setup
        # Text nodes
        from .py.RvText_DualText import RvText_DualText
        from .py.RvText_Multiline import RvText_Multiline
        from .py.RvText_PromptStyler import RvText_PromptStyler
        from .py.RvText_ReadPromptFiles import RvText_ReadPromptFiles
        from .py.RvText_ReplaceString import RvText_ReplaceString
        from .py.RvText_ReplaceStringV2 import RvText_ReplaceStringV2
        from .py.RvText_ReplaceStringV3 import RvText_ReplaceStringV3
        from .py.RvText_SavePrompt import RvText_SavePrompt
        from .py.RvText_SmartPrompt import RvText_SmartPrompt_All
        from .py.RvText_WildcardProcessor import RvText_WildcardProcessor
        # Tools nodes
        from .py.RvTools_LoopCalc import RvTools_LoopCalc
        from .py.RvTools_LoopKeepCalc import RvTools_LoopKeepCalc
        from .py.RvTools_LoraStack import RvTools_LoraStack
        from .py.RvTools_LoraStack_Apply import RvTools_LoraStack_Apply
        from .py.RvTools_RAMCleanup import RvTools_RAMCleanup
        from .py.RvTools_ShowAny import RvTools_ShowAny
        from .py.RvTools_Stop import RvTools_Stop
        from .py.RvTools_VideoClips_Combine import RvTools_VideoClips_Combine
        from .py.RvTools_VideoClips_SeamlessJoin import RvTools_VideoClips_SeamlessJoin
        from .py.RvTools_VRAMCleanUp import RvTools_VRAMCleanUp

        return [
            # Conversion
            RvConversion_ConcatMulti,
            RvConversion_ConvertPrimitive,
            RvConversion_ConvertToBatch,
            RvConversion_ConvertToList,
            RvConversion_DetectionToBboxes,
            RvConversion_ImageConvert,
            RvConversion_Join,
            RvConversion_LoraStackToString,
            RvConversion_MergeStrings,
            RvConversion_StringFromList,
            RvConversion_WidgetToString,
            # Folder
            RvFolder_AddFolder,
            RvFolder_FilenamePrefix,
            RvFolder_SmartFolder,
            # Image
            RvImage_AddWatermarkImage,
            RvImage_LoadImage,
            RvImage_LoadImageFromFolder,
            RvImage_LoadImagePath,
            RvImage_LoadImagePath_Pipe,
            RvImage_Preview_Image,
            RvImage_Preview_Mask,
            RvImage_SaveImages,
            # Loader
            RvLoader_Checkpoint_Loader_Small,
            RvLoader_Checkpoint_Loader_Small_Pipe,
            RvLoader_SmartLoader,
            RvLoader_SmartLoader_Basic,
            RvLoader_SmartLoader_Plus,
            # Logic
            RvLogic_Boolean,
            RvLogic_Float,
            RvLogic_Integer,
            RvLogic_IntegerGen,
            RvLogic_String,
            # Pipe IO
            RvPipe_IO_12CH_Any,
            RvPipe_IO_Context_Image,
            RvPipe_IO_Context_Video,
            RvPipe_IO_Context_WanVideoWrapper,
            RvPipe_IO_Generation_Data,
            RvPipe_IO_Sampler_Settings,
            # Pipe Out
            RvPipe_Out_CheckpointLoader,
            RvPipe_Out_LoadDirectorySettings,
            RvPipe_Out_LoadImage,
            RvPipe_Out_Sampler_Settings,
            RvPipe_Out_SmartFolder,
            RvPipe_Out_VCNameGen,
            RvPipe_Out_WanVideo_Setup,
            # Router
            RvRouter_Any_DualSwitch,
            RvRouter_Any_DualSwitch_purge,
            RvRouter_Any_MultiSwitch,
            RvRouter_Any_MultiSwitch_purge,
            RvRouter_Any_Passer,
            RvRouter_Any_Passer_purge,
            RvSwitch_IfExecute,
            # Settings
            RvSettings_ControlNetUnionType,
            RvSettings_CustomSize,
            RvSettings_Image_Resolution,
            RvSettings_LoadDirectorySettings,
            RvSettings_Sampler_Selection,
            RvSettings_Sampler_Settings,
            RvSettings_Sampler_Settings_NI,
            RvSettings_Sampler_Settings_NI_Seed,
            RvSettings_Sampler_Settings_Seed,
            RvSettings_Sampler_Settings_Small,
            RvSettings_Sampler_Settings_Small_Seed,
            RvSettings_VCNameGen_v1,
            RvSettings_VCNameGen_v2,
            RvSettings_WanVideo_Setup,
            # Text
            RvText_DualText,
            RvText_Multiline,
            RvText_PromptStyler,
            RvText_ReadPromptFiles,
            RvText_ReplaceString,
            RvText_ReplaceStringV2,
            RvText_ReplaceStringV3,
            RvText_SavePrompt,
            RvText_SmartPrompt_All,
            RvText_WildcardProcessor,
            # Tools
            RvTools_LoopCalc,
            RvTools_LoopKeepCalc,
            RvTools_LoraStack,
            RvTools_LoraStack_Apply,
            RvTools_RAMCleanup,
            RvTools_ShowAny,
            RvTools_Stop,
            RvTools_VideoClips_Combine,
            RvTools_VideoClips_SeamlessJoin,
            RvTools_VRAMCleanUp,
        ]

async def comfy_entrypoint() -> EclipseExtension:
    return EclipseExtension()
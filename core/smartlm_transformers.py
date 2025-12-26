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

# Unified Transformers Loading Module
#
# This module consolidates all HuggingFace Transformers model loading functions
# for vision-language and text-only models. It provides a single entry point
# (load_transformers_model) that routes to family-specific loaders.
#
# Supported model families:
# - Mistral3: Ministral 3B/8B/14B, Mistral Small 24B (vision-language)
# - QwenVL: Qwen2.5-VL, Qwen3-VL (vision-language)
# - Florence2: Florence-2 base/large (vision-language, requires transformers < 5.0)
# - LLM: Text-only models (Mistral, Llama, Qwen, etc.)
#
# For GGUF models, see smartlm_gguf.py (to be created)
# For vLLM/Docker inference, see smartlm_vllm_docker.py

import json
import shutil
import torch
from pathlib import Path
from typing import Any, Optional

from .logger import log
from .smartlm_templates import get_dev_mode


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

def debug_log(message: str):
    # Print debug message only when dev_mode is enabled
    if get_dev_mode():
        log.debug("Transformers", message)


def msg_log(message: str):
    # Print regular message
    log.msg("Transformers", message)


def warning_log(message: str):
    # Print warning message
    log.warning("Transformers", message)


def error_log(message: str):
    # Print error message
    log.error("Transformers", message)


# ==============================================================================
# TRANSFORMERS VERSION DETECTION
# ==============================================================================

import transformers
transformers_version = tuple(map(int, transformers.__version__.split('.')[:2])) if transformers.__version__[0].isdigit() else (4, 0)
# Handle RC versions like "5.0.0rc1"
if 'rc' in transformers.__version__.lower():
    transformers_version = (5, 0)


# ==============================================================================
# NOTE: v1 loading functions (load_transformers_model, _load_mistral3, _load_qwenvl,
# _load_florence2, _load_llm) have been removed as they are no longer used.
# v2 uses smartlm_base_v2.py for model loading which delegates to Docker backends.
# The generation functions below are still used by v2.
# ==============================================================================


# ==============================================================================
# FLORENCE-2 TASK CONFIGURATIONS
# ==============================================================================

# Florence-2 task prompts (hardcoded to match official implementation)
FLORENCE_PROMPTS = {
    'region_caption': '<OD>',
    'dense_region_caption': '<DENSE_REGION_CAPTION>',
    'region_proposal': '<REGION_PROPOSAL>',
    'caption': '<CAPTION>',
    'detailed_caption': '<DETAILED_CAPTION>',
    'more_detailed_caption': '<MORE_DETAILED_CAPTION>',
    'caption_to_phrase_grounding': '<CAPTION_TO_PHRASE_GROUNDING>',
    'referring_expression_segmentation': '<REFERRING_EXPRESSION_SEGMENTATION>',
    'ocr': '<OCR>',
    'ocr_with_region': '<OCR_WITH_REGION>',
    'docvqa': '<DocVQA>',
    'prompt_gen_tags': '<GENERATE_TAGS>',
    'prompt_gen_mixed_caption': '<MIXED_CAPTION>',
    'prompt_gen_analyze': '<ANALYZE>',
    'prompt_gen_mixed_caption_plus': '<MIXED_CAPTION_PLUS>',
}

# Florence-2 tasks configuration (loaded from config)
FLORENCE_TASKS = {
    "region_caption": {"prompt": "<OD>", "description": "Object detection with captions"},
    "dense_region_caption": {"prompt": "<DENSE_REGION_CAPTION>", "description": "Dense captioning with multiple regions"},
    "region_proposal": {"prompt": "<REGION_PROPOSAL>", "description": "Generate region proposals for objects"},
    "caption": {"prompt": "<CAPTION>", "description": "Short single-sentence caption"},
    "detailed_caption": {"prompt": "<DETAILED_CAPTION>", "description": "Detailed paragraph description"},
    "more_detailed_caption": {"prompt": "<MORE_DETAILED_CAPTION>", "description": "Very detailed rich description"},
    "caption_to_phrase_grounding": {"prompt": "<CAPTION_TO_PHRASE_GROUNDING>", "description": "Detect and locate specific objects/phrases in image"},
    "referring_expression_segmentation": {"prompt": "<REFERRING_EXPRESSION_SEGMENTATION>", "description": "Segment objects based on text description"},
    "ocr": {"prompt": "<OCR>", "description": "Extract text from image"},
    "ocr_with_region": {"prompt": "<OCR_WITH_REGION>", "description": "Extract text with bounding boxes"},
    "docvqa": {"prompt": "<DocVQA>", "description": "Document visual question answering"},
    "prompt_gen_tags": {"prompt": "<GENERATE_TAGS>", "description": "Generate comma-separated tags (PromptGen models)"},
    "prompt_gen_mixed_caption": {"prompt": "<MIXED_CAPTION>", "description": "Mixed-style caption for prompt generation"},
    "prompt_gen_analyze": {"prompt": "<ANALYZE>", "description": "Analytical description"},
    "prompt_gen_mixed_caption_plus": {"prompt": "<MIXED_CAPTION_PLUS>", "description": "Enhanced mixed caption"},
}


_florence_tasks_loaded = False

def get_florence_tasks():
    # Get Florence-2 tasks configuration
    global _florence_tasks_loaded
    
    # Lazy load from config if not yet loaded
    if not _florence_tasks_loaded:
        try:
            from .smartlm_templates import MODEL_CONFIGS
            florence_config = MODEL_CONFIGS.get("_florence_tasks_config")
            if florence_config:
                update_florence_tasks(florence_config)
        except Exception:
            pass  # Use default FLORENCE_TASKS
        _florence_tasks_loaded = True
    
    return FLORENCE_TASKS


def update_florence_tasks(tasks: dict):
    # Update Florence-2 tasks from config file
    global FLORENCE_TASKS
    # Filter out _comment keys
    FLORENCE_TASKS = {k: v for k, v in tasks.items() if not k.startswith("_")}


# ==============================================================================
# FLORENCE-2 HELPER FUNCTIONS
# ==============================================================================

import re
import numpy as np
from typing import Tuple, List
from PIL import Image, ImageDraw, ImageFont


def nms_filter(bboxes: List[List[float]], labels: List[str], iou_threshold: float = 0.5, containment_threshold: float = 0.7) -> Tuple[List[List[float]], List[str]]:
    # Apply Non-Maximum Suppression to remove overlapping bounding boxes.
    # Uses area-based sorting (smaller boxes preferred) and containment-based suppression.
    #
    # Args:
    #     bboxes: List of bounding boxes in [x1, y1, x2, y2] format
    #     labels: List of labels corresponding to each bbox
    #     iou_threshold: IoU threshold for suppression (default: 0.5)
    #     containment_threshold: If smaller box is contained this much in larger box, suppress larger (default: 0.7)
    #
    # Returns:
    #     Tuple of (filtered_bboxes, filtered_labels)
    if not bboxes or len(bboxes) == 0:
        return [], []
    
    # Convert to numpy for easier computation
    boxes = np.array(bboxes)
    
    # Calculate areas
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    
    # Sort by area ascending (smaller boxes first = preferred, more specific detections)
    order = np.argsort(areas)
    
    keep = []
    suppressed = set()
    
    while len(order) > 0:
        i = order[0]
        
        if i in suppressed:
            order = order[1:]
            continue
            
        keep.append(i)
        
        if len(order) == 1:
            break
        
        # Calculate IoU and containment with remaining boxes
        remaining = order[1:]
        xx1 = np.maximum(x1[i], x1[remaining])
        yy1 = np.maximum(y1[i], y1[remaining])
        xx2 = np.minimum(x2[i], x2[remaining])
        yy2 = np.minimum(y2[i], y2[remaining])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        intersection = w * h
        
        # Standard IoU calculation
        iou = intersection / (areas[i] + areas[remaining] - intersection + 1e-6)
        
        # Containment: what fraction of the current (smaller) box is inside each remaining (larger) box?
        # If a large box mostly contains this small box, suppress the large box
        containment = intersection / (areas[i] + 1e-6)
        
        # Suppress boxes that either:
        # 1. Have high IoU with current box (standard NMS)
        # 2. Mostly contain the current smaller box (containment-based suppression)
        suppress_mask = (iou > iou_threshold) | (containment > containment_threshold)
        
        for idx, should_suppress in enumerate(suppress_mask):
            if should_suppress:
                suppressed.add(remaining[idx])
        
        order = order[1:]
    
    # Filter bboxes and labels
    filtered_bboxes = [bboxes[i] for i in keep]
    filtered_labels = [labels[i] for i in keep] if labels else []
    
    return filtered_bboxes, filtered_labels


def parse_florence_location_tokens(text: str, width: int, height: int) -> dict:
    # Parse Florence-2 location tokens manually when processor doesn't parse properly.
    #
    # Supports multiple formats:
    # - Bboxes: "label<loc_x1><loc_y1><loc_x2><loc_y2>" (4 tokens)
    # - Polygons: "label<loc_x1><loc_y1><loc_x2><loc_y2>...<loc_xn><loc_yn>" (4+ tokens, multiples of 2)
    # - Quad boxes: "label<loc_x1><loc_y1><loc_x2><loc_y2><loc_x3><loc_y3><loc_x4><loc_y4>" (8 tokens for OCR)
    #
    # Location tokens are normalized to 0-999 range.
    #
    # Args:
    #     text: Raw model output with location tokens
    #     width: Image width in pixels
    #     height: Image height in pixels
    #
    # Returns:
    #     Dict with 'bboxes'/'quad_boxes'/'polygons' and 'labels'
    # Pattern to match label followed by location tokens
    # Captures label and all subsequent <loc_###> tokens
    pattern = r'([^<]+?)((?:<loc_\d+>)+)'
    matches = re.findall(pattern, text)
    
    if not matches:
        return {}
    
    bboxes = []
    labels = []
    polygons = []
    quad_boxes = []
    
    for match in matches:
        label = match[0].strip()
        loc_tokens = match[1]
        
        # Extract all location values
        locs = [int(x) for x in re.findall(r'<loc_(\d+)>', loc_tokens)]
        
        if len(locs) < 4:
            continue  # Invalid
        
        # Denormalize from 0-999 to pixel coordinates
        coords = []
        for i, loc in enumerate(locs):
            if i % 2 == 0:  # x coordinate
                coords.append((loc / 999.0) * width)
            else:  # y coordinate
                coords.append((loc / 999.0) * height)
        
        # Classify by coordinate count
        if len(coords) == 4:
            # Regular bbox: [x1, y1, x2, y2]
            bboxes.append(coords)
            labels.append(label)
        elif len(coords) == 8:
            # Quad box (OCR): [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            quad = [[coords[i], coords[i+1]] for i in range(0, 8, 2)]
            quad_boxes.append(quad)
            labels.append(label)
        elif len(coords) > 4 and len(coords) % 2 == 0:
            # Polygon: [[x1,y1], [x2,y2], ...]
            poly = [[coords[i], coords[i+1]] for i in range(0, len(coords), 2)]
            polygons.append(poly)
            labels.append(label)
    
    # Return appropriate format based on what was found
    result = {}
    if bboxes:
        result['bboxes'] = bboxes
        result['labels'] = labels
    if quad_boxes:
        result['quad_boxes'] = quad_boxes
        if 'labels' not in result:
            result['labels'] = labels
    if polygons:
        result['polygons'] = polygons
        if 'labels' not in result:
            result['labels'] = labels
    
    return result


def draw_bboxes(image: Any, data: dict) -> Any:
    # Draw bounding boxes, quad boxes, and polygons on image and return as tensor.
    #
    # Args:
    #     image: Input image tensor
    #     data: Detection data dict with 'bboxes'/'quad_boxes'/'polygons' and 'labels'
    #
    # Returns:
    #     Image tensor with drawn annotations
    debug_log(f"draw_bboxes: data keys={list(data.keys()) if data else 'None'}")
    
    # Convert tensor to PIL
    if image is None:
        raise ValueError("Image required for drawing")
    
    if isinstance(image, torch.Tensor):
        if image.dim() == 4:
            image = image[0]  # Take first from batch
        array = (image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        pil_image = Image.fromarray(array)
    else:
        pil_image = image
    
    # Handle empty data - just return original image as tensor
    if not data:
        debug_log("  No detection data, returning original image")
        img_array = np.array(pil_image).astype(np.float32) / 255.0
        return torch.from_numpy(img_array).unsqueeze(0)
    
    # Create a copy to draw on
    draw_image = pil_image.copy()
    draw = ImageDraw.Draw(draw_image)
    
    # Get detection data
    bboxes = data.get("bboxes", []) or []
    quad_boxes = data.get("quad_boxes", []) or []
    polygons = data.get("polygons", []) or []
    labels = data.get("labels", []) or []
    
    debug_log(f"  bboxes={len(bboxes)}, quad_boxes={len(quad_boxes)}, polygons={len(polygons)}, labels={len(labels)}")
    
    # If all are empty, return original image
    if not bboxes and not quad_boxes and not polygons:
        debug_log("  All detection lists empty, returning original image")
        img_array = np.array(pil_image).astype(np.float32) / 255.0
        return torch.from_numpy(img_array).unsqueeze(0)
    
    # Color palette for labels - vibrant colors with good visibility
    colormap = ['red', 'lime', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 
                'green', 'pink', 'gold', 'turquoise', 'coral', 'violet', 'springgreen', 
                'deeppink', 'dodgerblue', 'tomato', 'limegreen', 'hotpink']
    
    # Try to load font once
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Draw regular bounding boxes
    for i, bbox in enumerate(bboxes):
        # Validate bbox has 4 elements
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            debug_log(f"  Skipping invalid bbox[{i}]: {bbox}")
            continue
        
        try:
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            # Use fixed red color for bboxes (original behavior)
            color = 'red'
            
            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Draw label if available (format: "index.label" like "0.eye", "1.face")
            if i < len(labels):
                indexed_label = f"{i}.{labels[i]}"  # Match florence2 format: "0.label"
                # Get text bbox for background
                text_bbox = draw.textbbox((x1, y1), indexed_label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                # Draw background rectangle (black, not red - so labels don't appear in red mask extraction)
                draw.rectangle([x1, y1 - text_height - 4, x1 + text_width + 4, y1], fill='black')
                # Draw text
                draw.text((x1 + 2, y1 - text_height - 2), indexed_label, fill='white', font=font)
        except Exception as e:
            debug_log(f"  Error drawing bbox[{i}]: {e}")
    
    # Draw quad boxes (for OCR/text detection)
    for i, quad_box in enumerate(quad_boxes):
        try:
            # quad_box format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            if not quad_box or len(quad_box) < 4:
                continue
            if isinstance(quad_box[0], (list, tuple)):
                points = [(float(pt[0]), float(pt[1])) for pt in quad_box]
            else:
                # Flat list format [x1,y1,x2,y2,...]
                points = [(float(quad_box[j]), float(quad_box[j+1])) for j in range(0, len(quad_box), 2)]
            
            color = colormap[i % len(colormap)]
            draw.polygon(points, outline=color, width=3)
            
            # Draw index label
            if points:
                label = str(i) if i >= len(labels) else str(labels[i])
                text_bbox = draw.textbbox(points[0], label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                draw.rectangle([points[0][0], points[0][1] - text_height - 4, 
                               points[0][0] + text_width + 4, points[0][1]], fill=color)
                draw.text((points[0][0] + 2, points[0][1] - text_height - 2), label, fill='white', font=font)
        except Exception as e:
            debug_log(f"  Error drawing quad_box[{i}]: {e}")
    
    # Draw polygons
    for i, polygon in enumerate(polygons):
        try:
            # polygon format: [[x1,y1], [x2,y2], ...] or [x1,y1,x2,y2,...]
            if not polygon or len(polygon) < 3:
                continue
            if isinstance(polygon[0], (list, tuple)):
                points = [(float(pt[0]), float(pt[1])) for pt in polygon]
            else:
                # Flat list format
                points = [(float(polygon[j]), float(polygon[j+1])) for j in range(0, len(polygon), 2)]
            
            color = colormap[i % len(colormap)]
            draw.polygon(points, outline=color, width=3)
            
            # Draw label
            if points:
                label = str(i) if i >= len(labels) else str(labels[i])
                text_bbox = draw.textbbox(points[0], label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                draw.rectangle([points[0][0], points[0][1] - text_height - 4,
                               points[0][0] + text_width + 4, points[0][1]], fill=color)
                draw.text((points[0][0] + 2, points[0][1] - text_height - 2), label, fill='white', font=font)
        except Exception as e:
            debug_log(f"  Error drawing polygon[{i}]: {e}")
    
    # Convert back to tensor format
    img_array = np.array(draw_image).astype(np.float32) / 255.0
    tensor_out = torch.from_numpy(img_array).unsqueeze(0)  # Add batch dimension
    
    return tensor_out


# ==============================================================================
# UNIFIED GENERATION ENTRY POINT
# ==============================================================================

def generate_transformers(smart_lm_instance, model_family: str, image: Any, prompt: str,
                          max_tokens: int, temperature: float, top_p: float, top_k: int,
                          seed: Optional[int], repetition_penalty: float, num_beams: int = 1, 
                          do_sample: bool = True, **kwargs) -> Tuple[str, dict]:
    # Route to family-specific generator based on model_family.
    #
    # This is the main entry point for generating with any transformers-based model.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance with loaded model
    #     model_family: Model family (Mistral3, QwenVL, Florence2, LLM)
    #     image: Input image (PIL or tensor) - can be None for text-only models
    #     prompt: Text prompt
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Nucleus sampling parameter
    #     top_k: Top-k sampling parameter
    #     seed: Random seed for reproducibility
    #     repetition_penalty: Penalty for token repetition
    #     num_beams: Number of beams for beam search
    #     do_sample: Whether to use sampling
    #     **kwargs: Additional family-specific arguments
    #
    # Returns:
    #     Tuple of (generated_text, parsed_data_dict)
    #
    # Raises:
    #     ValueError: Unknown model family
    #     RuntimeError: Generation errors
    
    # Import ModelType for checking model_type attribute
    from .smartlm_types import ModelType
    
    if model_family == "Mistral3":
        return _generate_mistral3(smart_lm_instance, image, prompt, max_tokens, temperature,
                                  top_p, top_k, num_beams, do_sample, seed, repetition_penalty)
    elif model_family == "QwenVL":
        frame_count = kwargs.get("frame_count", 8)
        return _generate_qwenvl(smart_lm_instance, image, prompt, max_tokens, temperature,
                                top_p, top_k, num_beams, do_sample, seed, repetition_penalty, frame_count)
    elif model_family == "Florence2":
        text_input = kwargs.get("text_input")
        convert_to_bboxes = kwargs.get("convert_to_bboxes", True)
        detection_filter_threshold = kwargs.get("detection_filter_threshold", 0.80)
        nms_iou_threshold = kwargs.get("nms_iou_threshold", 0.50)
        return _generate_florence2(smart_lm_instance, image, prompt, max_tokens, num_beams,
                                   do_sample, seed, repetition_penalty, text_input,
                                   convert_to_bboxes, detection_filter_threshold, nms_iou_threshold)
    elif model_family == "LLM":
        llm_mode = kwargs.get("llm_mode", "direct_chat")
        instruction_template = kwargs.get("instruction_template", "")
        return _generate_llm(smart_lm_instance, prompt, max_tokens, temperature, top_p,
                             top_k, seed, repetition_penalty, llm_mode, instruction_template)
    elif model_family == "LLaVA":
        # Check if the actual model_type is Mllama (Llama 3.2 Vision)
        # LLaVA family includes both LLaVA and Mllama models, need to route correctly
        actual_model_type = getattr(smart_lm_instance, 'model_type', None)
        debug_log(f"  LLaVA routing: actual_model_type={actual_model_type}, type={type(actual_model_type)}")
        
        # Handle both enum and string comparison
        is_mllama = (
            actual_model_type == ModelType.MLLAMA or 
            str(actual_model_type).lower() in ('mllama', 'modeltype.mllama')
        )
        
        if is_mllama:
            debug_log("  Routing to _generate_mllama (Llama 3.2 Vision)")
            return _generate_mllama(smart_lm_instance, image, prompt, max_tokens, temperature,
                                    top_p, top_k, num_beams, do_sample, seed, repetition_penalty)
        debug_log("  Routing to _generate_llava (standard LLaVA)")
        return _generate_llava(smart_lm_instance, image, prompt, max_tokens, temperature,
                               top_p, top_k, num_beams, do_sample, seed, repetition_penalty)
    elif model_family == "Mllama" or model_family == "Llama-Vision":
        return _generate_mllama(smart_lm_instance, image, prompt, max_tokens, temperature,
                                top_p, top_k, num_beams, do_sample, seed, repetition_penalty)
    else:
        raise ValueError(f"Unknown model family: {model_family}")


# ==============================================================================
# MISTRAL3 GENERATION
# ==============================================================================

def _generate_mistral3(smart_lm_instance, image: Any, prompt: str, max_tokens: int, 
                       temperature: float, top_p: float, top_k: int, num_beams: int, 
                       do_sample: bool, seed: Optional[int], repetition_penalty: float = 1.0) -> Tuple[str, dict]:
    # Generate with Mistral3 vision model using Transformers.
    #
    # This function uses HuggingFace Transformers for local inference.
    # If vLLM is being used, generation is handled in smartlm_vllm_docker.py
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance
    #     image: Input image (PIL or tensor)
    #     prompt: Text prompt (can include system prompt separated by double newline)
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Nucleus sampling parameter
    #     top_k: Top-k sampling parameter
    #     num_beams: Number of beams for beam search
    #     do_sample: Whether to use sampling
    #     seed: Random seed for reproducibility
    #     repetition_penalty: Penalty for token repetition
    #
    # Returns:
    #     Tuple of (generated_text, empty_dict)
    debug_log(f"_generate_mistral3: prompt={prompt[:100] if prompt else 'None'}...")
    
    # Parse prompt to extract system instruction and user message
    # Format: "System instruction\n\n<optional user message or Additional context>" or just "user message"
    system_prompt = None
    user_message = prompt
    
    if "\n\n" in prompt:
        parts = prompt.split("\n\n", 1)
        if len(parts) >= 2:
            # First part is system instruction, rest is user message (if any)
            system_prompt = parts[0].strip()
            remaining = parts[1].strip() if parts[1].strip() else None
            
            # Check if remaining has "Additional context:"
            if remaining and remaining.startswith("Additional context:"):
                user_message = remaining.replace("Additional context:", "").strip()
            elif remaining:
                user_message = remaining
            else:
                # Just system instruction, no user message - use empty string
                # The system prompt already contains the full instruction
                # The image placeholder in user content is enough context
                user_message = ""
    
    debug_log(f"  System: {system_prompt[:50] if system_prompt else 'None'}...")
    debug_log(f"  User: {user_message[:50] if user_message else '(empty)'}...")
    
    # Set seed if provided
    if seed is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    
    # Handle image tensor - Mistral3 expects PIL image
    if image is None:
        raise ValueError("Mistral3 requires an image input for vision tasks")
    
    # Convert tensor to PIL - handle batch dimension
    if isinstance(image, torch.Tensor):
        if image.ndim == 4:  # Batch dimension
            image = image[0]
        # Convert from CHW to HWC and ensure proper range
        if image.shape[0] in [1, 3, 4]:  # Channel first
            image = image.permute(1, 2, 0)
        image_np = (image.cpu().numpy() * 255).astype('uint8')
        from PIL import Image as PILImage
        image_pil = PILImage.fromarray(image_np)
    else:
        image_pil = image
    
    if not image_pil:
        raise ValueError("Failed to process image for Mistral3")
    
    # Build messages using chat template format
    # Use AutoProcessor (PixtralProcessor) which supports images properly
    messages = []
    
    # Add system message if provided (Mistral supports system role)
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })
    
    # Add user message with image
    # If user_message is empty, just include the image (system prompt has full instruction)
    user_content = [{"type": "image"}]
    if user_message:
        user_content.append({"type": "text", "text": user_message})
    
    messages.append({
        "role": "user",
        "content": user_content
    })
    
    # Apply chat template and tokenize using AutoProcessor
    try:
        # Get formatted text from chat template
        # Try processor first, fall back to tokenizer if processor doesn't have chat template
        text = None
        if hasattr(smart_lm_instance.processor, 'chat_template') and smart_lm_instance.processor.chat_template:
            text = smart_lm_instance.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        elif hasattr(smart_lm_instance.processor, 'tokenizer') and hasattr(smart_lm_instance.processor.tokenizer, 'chat_template') and smart_lm_instance.processor.tokenizer.chat_template:
            # Use tokenizer's chat template
            debug_log("  Using tokenizer's chat_template (processor has none)")
            text = smart_lm_instance.processor.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # Fallback: manually construct Mistral chat format
            debug_log("  Using fallback Mistral chat template")
            # Mistral format: [INST] {system}\n{user_message} [/INST]
            if system_prompt and user_message:
                text = f"[INST] {system_prompt}\n\n[IMG]{user_message} [/INST]"
            elif system_prompt:
                text = f"[INST] {system_prompt}\n\n[IMG] [/INST]"
            else:
                text = f"[INST] [IMG]{user_message} [/INST]"
        
        # Process text and image together - this returns image_sizes
        tokenized = smart_lm_instance.processor(
            text=text,
            images=image_pil,
            return_tensors="pt"
        )
        
        # Move all tensors to device with correct dtype
        device = next(smart_lm_instance.model.parameters()).device
        # Get actual model dtype from first float parameter, not from stored attribute
        model_dtype = None
        for param in smart_lm_instance.model.parameters():
            if param.dtype in (torch.float16, torch.bfloat16, torch.float32):
                model_dtype = param.dtype
                break
        if model_dtype is None:
            model_dtype = smart_lm_instance.dtype if hasattr(smart_lm_instance, 'dtype') else torch.bfloat16
        debug_log(f"  Model dtype detected: {model_dtype}")
        
        for key in tokenized:
            if isinstance(tokenized[key], torch.Tensor):
                if tokenized[key].dtype in (torch.float32, torch.float64, torch.bfloat16, torch.float16):
                    # Convert floating point tensors (pixel_values) to model dtype
                    tokenized[key] = tokenized[key].to(dtype=model_dtype, device=device)
                else:
                    # Integer tensors (input_ids, attention_mask, image_sizes)
                    tokenized[key] = tokenized[key].to(device=device)
        
        debug_log(f"  Tokenized keys: {list(tokenized.keys())}")
        for k, v in tokenized.items():
            if isinstance(v, torch.Tensor):
                debug_log(f"    {k}: shape={v.shape}, dtype={v.dtype}")
        
    except Exception as e:
        error_log(f"Error processing Mistral3 inputs: {e}")
        raise
    
    # Generation parameters
    # Mistral recommends temperature < 0.1 for production
    gen_kwargs = {
        "max_new_tokens": max_tokens,
        "temperature": max(temperature, 0.01),  # Avoid zero temperature
        "top_p": top_p,
        "top_k": top_k if top_k > 0 else None,
        "do_sample": do_sample and temperature > 0.01,
        "num_beams": num_beams if num_beams > 1 else 1,
        "repetition_penalty": repetition_penalty,
    }
    
    # Generate - tokenized already includes image_sizes from AutoProcessor
    try:
        with torch.inference_mode():
            output_ids = smart_lm_instance.model.generate(**tokenized, **gen_kwargs)
        
        # Decode output (remove input tokens)
        input_len = tokenized["input_ids"].shape[1]
        generated_ids = output_ids[0][input_len:]
        
        # Use processor.tokenizer for decoding with cleanup
        response = smart_lm_instance.processor.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True
        )
        
        # Clean up any remaining byte-level BPE artifacts (Ġ = space, Ċ = newline)
        response = response.replace('Ġ', ' ').replace('Ċ', '\n').strip()
        
        # Fix common UTF-8 encoding artifacts (mojibake)
        # These occur when UTF-8 smart quotes are decoded as Latin-1/Windows-1252
        encoding_fixes = {
            'âĢĻ': "'",   # Right single quotation mark (U+2019)
            'âĢľ': '"',   # Left double quotation mark (U+201C)
            'âĢĿ': '"',   # Right double quotation mark (U+201D)
            'âĢĺ': "'",   # Left single quotation mark (U+2018)
            'âĢ"': '—',   # Em dash (U+2014)
            'âĢ"': '–',   # En dash (U+2013)
            'âĢ¦': '…',   # Horizontal ellipsis (U+2026)
            'Ã©': 'é',    # e with acute
            'Ã¨': 'è',    # e with grave
            'Ã¢': 'â',    # a with circumflex
            'Ã´': 'ô',    # o with circumflex
            'Ã®': 'î',    # i with circumflex
            'Ã»': 'û',    # u with circumflex
            'Ã§': 'ç',    # c with cedilla
            'Ã ': 'à',    # a with grave
            'Ãª': 'ê',    # e with circumflex
        }
        for wrong, correct in encoding_fixes.items():
            response = response.replace(wrong, correct)
        
        # Return (result, data) tuple like other generators
        return response, {}
        
    except Exception as e:
        error_log(f"Generation error: {e}")
        raise


# ==============================================================================
# QWENVL GENERATION (TRANSFORMERS ONLY)
# ==============================================================================

def _generate_qwenvl(smart_lm_instance, image: Any, prompt: str, max_tokens: int, 
                     temperature: float, top_p: float, top_k: int, num_beams: int, 
                     do_sample: bool, seed: Optional[int], repetition_penalty: float = 1.0, 
                     frame_count: int = 8) -> Tuple[str, dict]:
    # Generate with QwenVL using transformers (NOT GGUF).
    #
    # For GGUF models, use smartlm_qwenvl.generate_qwenvl_gguf() directly.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance
    #     image: Input image tensor (can be video with multiple frames)
    #     prompt: Text prompt
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Nucleus sampling parameter
    #     top_k: Top-k sampling parameter
    #     num_beams: Number of beams for beam search
    #     do_sample: Whether to use sampling
    #     seed: Random seed for reproducibility
    #     repetition_penalty: Penalty for token repetition
    #     frame_count: Maximum number of frames to process for video
    #
    # Returns:
    #     Tuple of (generated_text, parsed_detection_data)
    # Parse prompt to extract system instruction and optional user message/hints
    # Format: "system_instruction\n\nuser_message" or "system_instruction\n\n\n\nAdditional context: hints"
    system_prompt = None
    user_message = ""
    
    if "\n\n" in prompt:
        parts = prompt.split("\n\n", 1)  # Split only on first \n\n
        system_prompt = parts[0].strip()
        if len(parts) > 1:
            remaining = parts[1].strip()
            # Check if it's user hints or actual user message
            if remaining.startswith("Additional context:"):
                user_message = remaining.replace("Additional context:", "").strip()
            elif remaining:
                user_message = remaining
    else:
        # No separator - use entire prompt as user message (Custom task)
        user_message = prompt
    
    # HYBRID APPROACH: Handle device management based on quantization
    # Set defaults first to ensure variables are always defined
    device = next(smart_lm_instance.model.parameters()).device
    offload_device = device
    
    if hasattr(smart_lm_instance, 'is_quantized') and not smart_lm_instance.is_quantized:
        # Non-quantized: Use ComfyUI device management
        try:
            import comfy.model_management as mm
            device = mm.get_torch_device()
            offload_device = mm.unet_offload_device()
            smart_lm_instance.model.to(device)
        except:
            # ComfyUI not available, use model's current device
            pass
    # Quantized: Model stays where device_map placed it (uses defaults set above)
    
    # Handle video frames if input has multiple frames
    frames = None
    if image is not None and len(image.shape) == 4 and image.shape[0] > 1:
        # This is a video (multiple frames) - limit to frame_count
        total_frames = image.shape[0]
        actual_frame_count = min(frame_count, total_frames)
        frames = [smart_lm_instance.tensor_to_pil(image[i]) for i in range(actual_frame_count)]
    
    image_pil = smart_lm_instance.tensor_to_pil(image) if image is not None else None
    
    # Build conversation like ComfyUI-QwenVL does:
    # - NO system role (FP8 models don't handle it well)
    # - All content (image + instruction text) goes in user role
    conversation: list[dict[str, Any]] = []
    user_content = []
    
    # Add image if single frame
    if image_pil and frames is None:
        user_content.append({"type": "image", "image": image_pil})
    
    # Add video if multiple frames
    if frames and len(frames) > 1:
        user_content.append({"type": "video", "video": frames})
    
    # Combine system_prompt and user_message into the text content
    # This matches how ComfyUI-QwenVL does it
    prompt_text = system_prompt or ""
    if user_message:
        if prompt_text:
            prompt_text = f"{prompt_text}\n\n{user_message}"
        else:
            prompt_text = user_message
    
    # Ensure we have some text prompt
    if not prompt_text:
        prompt_text = "Describe this image in detail."
    
    user_content.append({"type": "text", "text": prompt_text})
    conversation.append({"role": "user", "content": user_content})
    
    chat = smart_lm_instance.processor.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)
    
    images = [image_pil] if (image_pil and frames is None) else None
    videos = [frames] if frames and len(frames) > 1 else None
    
    processed = smart_lm_instance.processor(text=chat, images=images or None, videos=videos, return_tensors="pt")
    
    # Get model dtype
    model_dtype = next(smart_lm_instance.model.parameters()).dtype
    
    model_inputs = {
        key: value.to(device) if torch.is_tensor(value) else value
        for key, value in processed.items()
    }
    
    # Convert float tensors to model dtype (needed for FP8 dequantized to BF16, or regular fp16/bf16 models)
    # Skip int tensors (input_ids, attention_mask, etc.) - they stay as int
    # This handles pixel_values, pixel_values_videos, image_embeds, etc.
    if model_dtype in (torch.float16, torch.bfloat16):
        for key, value in model_inputs.items():
            if torch.is_tensor(value) and value.dtype in (torch.float32, torch.float16, torch.bfloat16):
                if value.dtype != model_dtype:
                    model_inputs[key] = value.to(model_dtype)
    
    stop_tokens: list[int] = [smart_lm_instance.tokenizer.eos_token_id]
    if hasattr(smart_lm_instance.tokenizer, "eot_id") and smart_lm_instance.tokenizer.eot_id is not None:
        stop_tokens.append(smart_lm_instance.tokenizer.eot_id)
    
    # Beam search is incompatible with video in Qwen2.5-VL/Qwen3-VL (transformers bug)
    # Force num_beams=1 for video to avoid split_with_sizes error
    has_video = videos is not None and len(videos) > 0
    effective_beams = 1 if has_video else num_beams
    
    if has_video and num_beams > 1:
        msg_log("Note: Beam search disabled for video (using sampling instead)")
    
    kwargs = {
        "max_new_tokens": max_tokens,
        "repetition_penalty": repetition_penalty if repetition_penalty > 0 else 1.0,
        "num_beams": effective_beams,
        "eos_token_id": stop_tokens,
        "pad_token_id": smart_lm_instance.tokenizer.pad_token_id,
    }
    
    if effective_beams == 1:
        kwargs.update({"do_sample": do_sample, "temperature": temperature, "top_p": top_p})
    else:
        kwargs["do_sample"] = False
    
    outputs = smart_lm_instance.model.generate(**model_inputs, **kwargs)
    
    # Synchronize CUDA to ensure generation is complete
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    input_len = model_inputs["input_ids"].shape[-1]
    
    # Decode output
    text = smart_lm_instance.tokenizer.decode(outputs[0, input_len:], skip_special_tokens=True)
    
    # Strip reasoning/thinking tags from "Thinker" models (e.g., Qwen3-VL-Thinking)
    # These models output <think>...</think> before the actual response
    raw_text = text.strip()
    cleaned_text = re.sub(r'<think>.*?</think>\s*', '', raw_text, flags=re.DOTALL).strip()
    
    # Handle models that output untagged thinking (no <think> tags)
    # Models with few-shot examples or reasoning prompts may output thinking-like text
    # Pattern: "Okay, let me think about this..." followed by actual output
    thinking_start_patterns = [
        r'^(?:Okay|Alright|Let me|Let\'s|First|I\'ll|I need to|I should|I will|I want to|Hmm|So|Now|Got it|Start with|Wait|Check)[,\s]',
    ]
    is_thinking_output = any(re.match(p, cleaned_text, re.IGNORECASE) for p in thinking_start_patterns)
    
    if is_thinking_output:
        # Method 1: Look for the LAST substantial paragraph that looks like final output
        # Thinking models often end with the clean result as the last paragraph
        paragraphs = re.split(r'\n\n+|\n(?=[A-Z][a-z])', cleaned_text)
        
        # Find the last paragraph that looks like actual output (not thinking)
        for para in reversed(paragraphs):
            para = para.strip()
            # Check if it's substantial and doesn't start with thinking patterns
            if len(para) > 80 and not re.match(r'^(?:Okay|Alright|Let me|Let\'s|First|I\'ll|I need to|I should|I will|I want to|Hmm|So|Now|Got it|Start with|Wait|Check|Yes|Yep|Now,)[,\.\s]', para, re.IGNORECASE):
                # Also check it's not a "Let me draft/check" type statement
                if not re.search(r'^(?:Let me draft|Let me check|Wait,|Check if|So:|Yes\.|Yep\.)', para, re.IGNORECASE):
                    # Looks like actual output
                    cleaned_text = para
                    break
        
        # Method 2: If still has thinking patterns, try to find content after transition markers
        if re.match(r'^(?:Okay|Alright|Let me|Let\'s|First)[,\s]', cleaned_text, re.IGNORECASE):
            # Look for explicit transition patterns
            transition_patterns = [
                r'(?:Final version[:\s]*|Alright[,\s]+actual[^:]*:|Proceed\.\s*|[Bb]egin fresh[^:]*:|Starting[:\s]+|Here(?:\'s| is) (?:the|my) (?:refined|expanded|improved|final)[^:]*:)',
                r'(?:^|\n)(?:The |A |An )(?=[A-Z]?[a-z]{2,})',  # Sentence starting with article
            ]
            for pattern in transition_patterns:
                match = re.search(pattern, cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
                if match:
                    potential_output = cleaned_text[match.end():].strip()
                    # For article matches, include the article
                    if 'The |A |An ' in pattern:
                        potential_output = cleaned_text[match.start():].strip()
                        # Get from the match to end
                        potential_output = re.split(r'\n\n+', potential_output)[0] if '\n\n' in potential_output else potential_output
                    if len(potential_output) > 50:
                        cleaned_text = potential_output
                        break
    
    # HYBRID APPROACH: Offload non-quantized models back (only if not keeping model loaded)
    keep_loaded = getattr(smart_lm_instance, 'keep_model_loaded', False)
    if not keep_loaded and hasattr(smart_lm_instance, 'is_quantized') and not smart_lm_instance.is_quantized and offload_device != device:
        try:
            smart_lm_instance.model.to(offload_device)
            import comfy.model_management as mm
            mm.soft_empty_cache()
        except:
            pass
    
    # Try to parse detection JSON from output (use cleaned text without thinking)
    parsed_data, final_text = _parse_qwen_detection_json(cleaned_text)
    
    # If not a detection task (no bboxes found), output raw text to data
    if not parsed_data:
        parsed_data = {"raw_output": raw_text}
    
    return final_text, parsed_data


def _parse_qwen_detection_json(text: str) -> Tuple[dict, str]:
    # Parse Qwen detection JSON output and convert to Florence-2 format.
    #
    # Handles multiple Qwen formats:
    # 1. Object format (current): {"bboxes": [[x1,y1,x2,y2], ...], "labels": ["obj1", ...]}
    # 2. Array format (legacy): [{"bbox_2d": [x1,y1,x2,y2], "label": "obj1"}, ...]
    #
    # Florence-2 format:
    # {
    #     "bboxes": [[x1, y1, x2, y2], [x1, y1, x2, y2], ...],
    #     "labels": ["object1", "object2", ...]
    # }
    #
    # Returns (parsed_dict, cleaned_text) tuple.
    # - If detection found: (dict with bboxes/labels, text with JSON removed)
    # - If no detection: ({}, original text)
    import json as json_module
    
    # Try to find JSON object or array in the text
    # First try object format: {...}
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            json_str = json_match.group(0)
            data = json_module.loads(json_str)
            
            # Check if it's already in Florence-2 format
            if isinstance(data, dict) and 'bboxes' in data and 'labels' in data:
                bboxes = data['bboxes']
                labels = data['labels']
                
                # Validate format
                if isinstance(bboxes, list) and isinstance(labels, list) and len(bboxes) == len(labels):
                    debug_log(f"Found Qwen detection JSON: {len(bboxes)} boxes")
                    # Remove JSON from text and return cleaned version
                    cleaned_text = text.replace(json_str, '').strip()
                    if not cleaned_text:
                        cleaned_text = f"Detected {len(bboxes)} object(s): {', '.join(labels)}"
                    return (data, cleaned_text)
        except (json_module.JSONDecodeError, KeyError, IndexError, TypeError):
            pass
    
    # Try array format: [...]
    json_match = re.search(r'\[[\s\S]*\]', text)
    if not json_match:
        return ({}, text)
    
    try:
        json_str = json_match.group(0)
        data = json_module.loads(json_str)
        
        # Check if it's Qwen detection format (list of objects with bbox_2d)
        if not isinstance(data, list) or len(data) == 0:
            return ({}, text)
        
        # Check if first item has bbox_2d and label keys
        if not isinstance(data[0], dict) or 'bbox_2d' not in data[0]:
            return ({}, text)
        
        # Convert to Florence-2 format
        bboxes = []
        labels = []
        
        for item in data:
            if 'bbox_2d' in item and 'label' in item:
                bboxes.append(item['bbox_2d'])
                labels.append(item['label'])
        
        if bboxes and labels:
            converted = {
                'bboxes': bboxes,
                'labels': labels
            }
            debug_log(f"Converted Qwen detection JSON: {len(bboxes)} boxes")
            # Remove JSON from text and return cleaned version
            cleaned_text = text.replace(json_str, '').strip()
            if not cleaned_text:
                cleaned_text = f"Detected {len(bboxes)} object(s): {', '.join(labels)}"
            return (converted, cleaned_text)
        
    except (json_module.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        warning_log(f"Failed to parse Qwen detection JSON: {e}")
    
    return ({}, text)


# ==============================================================================
# FLORENCE2 GENERATION
# ==============================================================================

def _generate_florence2(base_instance, image: Any, task_or_prompt: str, max_tokens: int,
                        num_beams: int, do_sample: bool, seed: Optional[int], 
                        repetition_penalty: float = 1.0, text_input: Optional[str] = None,
                        convert_to_bboxes: bool = True, detection_filter_threshold: float = 0.80,
                        nms_iou_threshold: float = 0.50) -> Tuple[str, dict]:
    # Generate with Florence-2 - returns (text, parsed_data).
    #
    # Args:
    #     base_instance: SmartLM instance with loaded model
    #     image: Input image tensor
    #     task_or_prompt: Task name or custom prompt
    #     max_tokens: Maximum tokens to generate
    #     num_beams: Number of beams for beam search
    #     do_sample: Whether to use sampling
    #     seed: Random seed
    #     repetition_penalty: Penalty for repetition
    #     text_input: Additional text input for specific tasks
    #     convert_to_bboxes: Convert detections to bboxes format
    #     detection_filter_threshold: Filter threshold for oversized detections
    #     nms_iou_threshold: IoU threshold for NMS filtering (0.0-1.0)
    #
    # Returns:
    #     Tuple of (generated_text, parsed_data_dict)
    debug_log(f"_generate_florence2: task={task_or_prompt}")
    debug_log(f"  max_tokens={max_tokens}, num_beams={num_beams}, do_sample={do_sample}")
    
    if seed is not None:
        # Use hash for better randomization (Florence-2 seeds can be full uint32)
        import hashlib
        seed_bytes = str(seed).encode('utf-8')
        hash_seed = int(hashlib.sha256(seed_bytes).hexdigest()[:8], 16)
        torch.manual_seed(hash_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(hash_seed)
    
    # Handle image tensor - Florence-2 expects PIL image
    if image is None:
        raise ValueError("Florence-2 requires an image input")
    
    # Convert tensor to PIL - handle batch dimension
    if isinstance(image, torch.Tensor):
        if image.dim() == 4:
            # Take first image from batch
            image = image[0]
        # Convert to PIL
        array = (image.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        image_pil = Image.fromarray(array)
    else:
        image_pil = image
    
    if not image_pil:
        raise ValueError("Failed to convert image to PIL format")
    
    # Get task prompt token
    task_prompt = FLORENCE_PROMPTS.get(task_or_prompt, task_or_prompt)
    
    # Tasks that require text input after the task token
    tasks_requiring_text = [
        "caption_to_phrase_grounding",
        "referring_expression_segmentation",
        "docvqa"
    ]
    
    # Build full prompt for generation (task token + text input only for tasks that need it)
    if task_or_prompt in tasks_requiring_text and text_input and text_input.strip():
        # Task token + text input (e.g., "<CAPTION_TO_PHRASE_GROUNDING>person")
        prompt = task_prompt + text_input
        debug_log(f"Task: {task_or_prompt} | Prompt: {prompt}")
    else:
        # Just task token (e.g., "<CAPTION>")
        prompt = task_prompt
        debug_log(f"Task: {task_or_prompt} | Prompt: {prompt}")
    
    # Get current device - Florence-2 uses standard PyTorch device management
    device = next(base_instance.model.parameters()).device
    
    # For non-quantized models, ensure model is on correct device
    if hasattr(base_instance, 'is_quantized') and not base_instance.is_quantized:
        # Move to CUDA if available and not already there
        if torch.cuda.is_available() and device.type != "cuda":
            base_instance.model = base_instance.model.to("cuda")
            device = next(base_instance.model.parameters()).device
    # Quantized: Model stays where device_map placed it
    
    dtype = base_instance.dtype if hasattr(base_instance, 'dtype') else torch.float16
    
    # Process image with do_rescale=False (ComfyUI images are already 0-1)
    inputs = base_instance.processor(text=prompt, images=image_pil, return_tensors="pt", do_rescale=False)
    inputs = {k: v.to(dtype).to(device) if torch.is_tensor(v) and v.dtype.is_floating_point else v.to(device)
              for k, v in inputs.items()}
    
    generated_ids = base_instance.model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=max_tokens,
        do_sample=do_sample,
        num_beams=num_beams,
        repetition_penalty=repetition_penalty if repetition_penalty and repetition_penalty > 0 else 1.0,
        # Note: use_cache=False for Florence2 because comfyui-florence2's modeling code
        # has a bug in prepare_inputs_for_generation that doesn't handle None past_key_values
        use_cache=False,
    )
    
    # Decode with skip_special_tokens=True to get clean text first
    results_clean = base_instance.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    # Also decode with skip_special_tokens=False for spatial tasks that need location tokens
    results = base_instance.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    
    # Define tasks that produce spatial data (bboxes, polygons, etc.)
    spatial_tasks = [
        "region_caption",  # Object detection with captions
        "dense_region_caption",
        "region_proposal",
        "caption_to_phrase_grounding",
        "ocr_with_region",
        "referring_expression_segmentation"
    ]
    
    # Parse structured output (bounding boxes, labels, etc.) ONLY for spatial tasks
    parsed_data = {}
    is_spatial_task = task_or_prompt in spatial_tasks
    
    if is_spatial_task:
        # Try to parse with processor's post_process method
        try:
            parsed_answer = base_instance.processor.post_process_generation(
                results,
                task=task_prompt,
                image_size=(image_pil.width, image_pil.height)
            )
            
            # Extract bboxes and labels
            if task_prompt in parsed_answer:
                task_result = parsed_answer[task_prompt]
                
                # Handle different result formats
                if 'bboxes' in task_result and 'labels' in task_result:
                    parsed_data['bboxes'] = task_result['bboxes']
                    parsed_data['labels'] = task_result['labels']
                elif 'quad_boxes' in task_result and 'labels' in task_result:
                    # OCR with region returns quad boxes (4 corners)
                    parsed_data['quad_boxes'] = task_result['quad_boxes']
                    parsed_data['labels'] = task_result['labels']
                elif 'polygons' in task_result and 'labels' in task_result:
                    # Segmentation returns polygons
                    parsed_data['polygons'] = task_result['polygons']
                    parsed_data['labels'] = task_result['labels']
                
        except Exception as e:
            # Fallback: Manual parsing if processor fails
            warning_log(f"Processor parsing failed, using manual parser: {e}")
            parsed_data = parse_florence_location_tokens(
                results, image_pil.width, image_pil.height
            )
        
        # Convert quad boxes to regular bboxes if needed
        if 'quad_boxes' in parsed_data and convert_to_bboxes:
            quad_boxes = parsed_data['quad_boxes']
            bboxes = []
            for quad in quad_boxes:
                # Quad format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                # Convert to bbox: [min_x, min_y, max_x, max_y]
                if isinstance(quad[0], (list, tuple)):
                    # Nested list format
                    xs = [pt[0] for pt in quad]
                    ys = [pt[1] for pt in quad]
                else:
                    # Flat list format [x1,y1,x2,y2,...]
                    xs = [quad[i] for i in range(0, len(quad), 2)]
                    ys = [quad[i] for i in range(1, len(quad), 2)]
                
                bbox = [min(xs), min(ys), max(xs), max(ys)]
                bboxes.append(bbox)
            
            parsed_data['bboxes'] = bboxes
            del parsed_data['quad_boxes']
        
        # Convert polygons to bboxes if needed
        if 'polygons' in parsed_data and convert_to_bboxes:
            polygons = parsed_data['polygons']
            bboxes = []
            for poly in polygons:
                # Polygon format: [[x1,y1], [x2,y2], ...] or [x1,y1,x2,y2,...]
                if isinstance(poly[0], (list, tuple)):
                    xs = [pt[0] for pt in poly]
                    ys = [pt[1] for pt in poly]
                else:
                    xs = [poly[i] for i in range(0, len(poly), 2)]
                    ys = [poly[i] for i in range(1, len(poly), 2)]
                
                bbox = [min(xs), min(ys), max(xs), max(ys)]
                bboxes.append(bbox)
            
            parsed_data['bboxes'] = bboxes
            del parsed_data['polygons']
        
        # Filter out oversized detections (likely errors)
        if 'bboxes' in parsed_data and parsed_data['bboxes']:
            img_area = image_pil.width * image_pil.height
            filtered_bboxes = []
            filtered_labels = []
            
            for i, bbox in enumerate(parsed_data['bboxes']):
                x1, y1, x2, y2 = bbox
                bbox_area = (x2 - x1) * (y2 - y1)
                bbox_ratio = bbox_area / img_area if img_area > 0 else 0
                
                # Filter out detections that cover > threshold of image (likely errors)
                if bbox_ratio <= detection_filter_threshold:
                    filtered_bboxes.append(bbox)
                    if 'labels' in parsed_data and i < len(parsed_data['labels']):
                        filtered_labels.append(parsed_data['labels'][i])
            
            parsed_data['bboxes'] = filtered_bboxes
            if filtered_labels:
                parsed_data['labels'] = filtered_labels
            
            # Apply NMS to remove overlapping detections (skip if threshold is 1.0)
            if len(parsed_data['bboxes']) > 1 and nms_iou_threshold < 1.0:
                nms_bboxes, nms_labels = nms_filter(
                    parsed_data['bboxes'], 
                    parsed_data.get('labels', []), 
                    iou_threshold=nms_iou_threshold
                )
                if nms_bboxes:
                    parsed_data['bboxes'] = nms_bboxes
                    if nms_labels:
                        parsed_data['labels'] = nms_labels
    
    # Clean up special tokens for text output
    # Special handling for ocr_with_region to preserve line breaks
    if task_or_prompt == 'ocr_with_region':
        # For OCR with region, clean text but preserve structure
        clean_results = results_clean.strip()
    elif is_spatial_task:
        # For other spatial tasks, use clean version (skip_special_tokens=True already removed tokens)
        clean_results = results_clean.strip()
    else:
        # For non-spatial tasks, just use clean version
        clean_results = results_clean.strip()
        # Remove any remaining special tokens manually
        for token in ['<s>', '</s>', '<pad>', '<|endoftext|>']:
            clean_results = clean_results.replace(token, '')
        clean_results = clean_results.strip()
    
    # Debug: Log parsed data before returning
    if parsed_data:
        debug_log(f"Parsed data keys: {list(parsed_data.keys())}")
        if 'bboxes' in parsed_data:
            debug_log(f"  bboxes count: {len(parsed_data['bboxes'])}")
            if parsed_data['bboxes']:
                debug_log(f"  first bbox: {parsed_data['bboxes'][0]}")
        if 'labels' in parsed_data:
            debug_log(f"  labels: {parsed_data['labels'][:5]}...")  # First 5 labels
    else:
        debug_log("No parsed data returned")
    
    return (clean_results, parsed_data)


# ==============================================================================
# LLAVA GENERATION
# ==============================================================================

def _generate_llava(smart_lm_instance, image: Any, prompt: str, max_tokens: int,
                    temperature: float, top_p: float, top_k: int, num_beams: int,
                    do_sample: bool, seed: Optional[int], repetition_penalty: float) -> Tuple[str, dict]:
    """Generate with LLaVA vision-language model using Transformers.
    
    LLaVA models use a similar interface to other VLMs - processor handles
    image + text inputs, model generates from the combined representation.
    
    Args:
        smart_lm_instance: The SmartLM instance with loaded model
        image: Input image (PIL or tensor)
        prompt: Text prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        num_beams: Number of beams for beam search
        do_sample: Whether to use sampling
        seed: Random seed for reproducibility
        repetition_penalty: Penalty for token repetition
        
    Returns:
        Tuple of (generated_text, empty_dict)
    """
    debug_log(f"_generate_llava: prompt={prompt[:100] if prompt else 'None'}...")
    
    model = smart_lm_instance.model
    processor = smart_lm_instance.processor
    
    # Set seed if provided
    if seed is not None:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    
    # Convert image to PIL if needed
    pil_image = None
    if image is not None:
        if hasattr(image, 'convert'):
            pil_image = image
        elif isinstance(image, torch.Tensor):
            import numpy as np
            from PIL import Image
            if image.dim() == 4:
                image = image[0]
            if image.dim() == 3:
                img_np = (image.cpu().numpy() * 255).astype(np.uint8)
                if img_np.shape[0] in [1, 3, 4]:
                    img_np = np.transpose(img_np, (1, 2, 0))
                if img_np.shape[-1] == 1:
                    img_np = img_np.squeeze(-1)
                pil_image = Image.fromarray(img_np)
    
    # Build conversation for LLaVA
    # LLaVA typically expects conversation format with image placeholder
    if pil_image is not None:
        # Vision mode - include image in prompt
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    else:
        # Text-only mode
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    
    try:
        # Apply chat template
        text_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
        
        # Process inputs
        if pil_image is not None:
            inputs = processor(images=pil_image, text=text_prompt, return_tensors="pt")
        else:
            inputs = processor(text=text_prompt, return_tensors="pt")
        
        # For BitsAndBytes quantized models with device_map, model.device may be unreliable
        # Use cuda:0 directly since that's where device_map={"":0} places the model
        target_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        
        # Move inputs to device with proper dtype handling
        processed_inputs = {}
        for k, v in inputs.items():
            if not hasattr(v, 'to'):
                processed_inputs[k] = v
            elif k == "pixel_values":
                # pixel_values should be float16 for quantized models
                processed_inputs[k] = v.to(device=target_device, dtype=torch.float16)
            elif v.dtype in (torch.float32, torch.float64):
                # Convert other float tensors to float16
                processed_inputs[k] = v.to(device=target_device, dtype=torch.float16)
            else:
                # Integer tensors (input_ids, attention_mask, etc.)
                processed_inputs[k] = v.to(device=target_device)
        inputs = processed_inputs
        
        # Clear any cached past_key_values from previous generations to avoid conflicts
        # between different images. This is safer than use_cache=False which disables
        # KV caching entirely and significantly slows down generation.
        if hasattr(model, '_past_key_values'):
            model._past_key_values = None
        
        # Build generation kwargs - use_cache=True for fast autoregressive generation
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample and temperature > 0,
            "pad_token_id": processor.tokenizer.pad_token_id or processor.tokenizer.eos_token_id,
            "use_cache": True,  # Enable KV cache for faster generation
        }
        
        if do_sample and temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
            if top_k > 0:
                gen_kwargs["top_k"] = top_k
        
        if num_beams > 1:
            gen_kwargs["num_beams"] = num_beams
        
        if repetition_penalty != 1.0:
            gen_kwargs["repetition_penalty"] = repetition_penalty
        
        # Generate
        output_ids = model.generate(**inputs, **gen_kwargs)
        
        # Decode only the new tokens
        input_len = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0][input_len:]
        text = processor.decode(generated_ids, skip_special_tokens=True).strip()
        
        # Strip thinking tags from "Thinker" models (e.g., reasoning models)
        from .common import strip_thinking_tags
        text, _ = strip_thinking_tags(text)
        
        debug_log(f"  Generated: {text[:200]}...")
        return text, {}
        
    except Exception as e:
        error_log(f"LLaVA generation error: {e}")
        import traceback
        traceback.print_exc()
        raise


# ==============================================================================
# MLLAMA (LLAMA 3.2 VISION) GENERATION
# ==============================================================================

def _generate_mllama(smart_lm_instance, image: Any, prompt: str, max_tokens: int,
                     temperature: float, top_p: float, top_k: int, num_beams: int,
                     do_sample: bool, seed: Optional[int], repetition_penalty: float) -> Tuple[str, dict]:
    """Generate with Llama 3.2 Vision (Mllama) model using Transformers.
    
    Mllama uses a cross-attention architecture where the text model attends to
    image features from the vision encoder. The processor handles image+text inputs.
    
    Args:
        smart_lm_instance: The SmartLM instance with loaded model
        image: Input image (PIL or tensor)
        prompt: Text prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        num_beams: Number of beams for beam search
        do_sample: Whether to use sampling
        seed: Random seed for reproducibility
        repetition_penalty: Penalty for token repetition
        
    Returns:
        Tuple of (generated_text, empty_dict)
    """
    debug_log(f"_generate_mllama: prompt={prompt[:100] if prompt else 'None'}...")
    
    model = smart_lm_instance.model
    processor = smart_lm_instance.processor
    
    # Set seed if provided
    if seed is not None:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    
    # Convert image to PIL if needed
    pil_image = None
    if image is not None:
        if hasattr(image, 'convert'):
            pil_image = image
        elif isinstance(image, torch.Tensor):
            import numpy as np
            from PIL import Image
            if image.dim() == 4:
                image = image[0]
            if image.dim() == 3:
                img_np = (image.cpu().numpy() * 255).astype(np.uint8)
                if img_np.shape[0] in [1, 3, 4]:
                    img_np = np.transpose(img_np, (1, 2, 0))
                if img_np.shape[-1] == 1:
                    img_np = img_np.squeeze(-1)
                pil_image = Image.fromarray(img_np)
    
    # Build conversation for Mllama
    # Mllama uses a specific format with <|image|> token
    if pil_image is not None:
        # Vision mode - include image in prompt
        # Mllama expects the image token to be placed where the image should be attended to
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    else:
        # Text-only mode
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
    
    try:
        # Apply chat template
        input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        
        # Process inputs
        if pil_image is not None:
            inputs = processor(images=pil_image, text=input_text, return_tensors="pt")
        else:
            inputs = processor(text=input_text, return_tensors="pt")
        
        # For BitsAndBytes quantized models with device_map, model.device may be unreliable
        # Use cuda:0 directly since that's where device_map={"":0} places the model
        target_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        
        # Move inputs to device with proper dtype handling for Mllama
        # pixel_values need to be float16/bfloat16, cross_attention_mask needs proper handling
        processed_inputs = {}
        for k, v in inputs.items():
            if not hasattr(v, 'to'):
                processed_inputs[k] = v
            elif k == "pixel_values":
                # pixel_values should be float16 for quantized models
                processed_inputs[k] = v.to(device=target_device, dtype=torch.float16)
            elif v.dtype in (torch.float32, torch.float64):
                # Convert other float tensors to float16
                processed_inputs[k] = v.to(device=target_device, dtype=torch.float16)
            else:
                # Integer tensors (input_ids, attention_mask, etc.)
                processed_inputs[k] = v.to(device=target_device)
        inputs = processed_inputs
        
        debug_log(f"  Mllama inputs: {list(inputs.keys())}")
        for k, v in inputs.items():
            if hasattr(v, 'shape'):
                debug_log(f"    {k}: shape={v.shape}, dtype={v.dtype}, device={v.device}")
        
        # Clear any cached past_key_values from previous generations to avoid conflicts
        # between different images. This is safer than use_cache=False which disables
        # KV caching entirely and significantly slows down generation.
        if hasattr(model, '_past_key_values'):
            model._past_key_values = None
        # Also try to clear the language_model's cache for Mllama
        if hasattr(model, 'language_model') and hasattr(model.language_model, '_past_key_values'):
            model.language_model._past_key_values = None
        
        # Build generation kwargs - use_cache=True for fast autoregressive generation
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample and temperature > 0,
            "pad_token_id": processor.tokenizer.pad_token_id or processor.tokenizer.eos_token_id,
            "use_cache": True,  # Enable KV cache for faster generation
        }
        
        if do_sample and temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
            if top_k > 0:
                gen_kwargs["top_k"] = top_k
        
        if num_beams > 1:
            gen_kwargs["num_beams"] = num_beams
        
        if repetition_penalty != 1.0:
            gen_kwargs["repetition_penalty"] = repetition_penalty
        
        # Generate
        output_ids = model.generate(**inputs, **gen_kwargs)
        
        # Decode only the new tokens
        input_len = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0][input_len:]
        text = processor.decode(generated_ids, skip_special_tokens=True).strip()
        
        # Strip thinking tags from "Thinker" models (e.g., reasoning models)
        from .common import strip_thinking_tags
        text, _ = strip_thinking_tags(text)
        
        debug_log(f"  Generated: {text[:200]}...")
        return text, {}
        
    except Exception as e:
        error_log(f"Mllama generation error: {e}")
        import traceback
        traceback.print_exc()
        raise


# ==============================================================================
# LLM (TEXT-ONLY) GENERATION
# ==============================================================================

def _generate_llm(smart_lm_instance, prompt: str, max_tokens: int, temperature: float,
                  top_p: float, top_k: int, seed: Optional[int], repetition_penalty: float,
                  llm_mode: str, instruction_template: str) -> Tuple[str, dict]:
    # Generate text-only completion with LLM (no images) - transformers path only.
    #
    # For GGUF models, use smartlm_llm.generate_llm() which handles both.
    #
    # Args:
    #     smart_lm_instance: The SmartLM instance
    #     prompt: Text prompt
    #     max_tokens: Maximum tokens to generate
    #     temperature: Sampling temperature
    #     top_p: Nucleus sampling parameter
    #     top_k: Top-k sampling parameter
    #     seed: Random seed for reproducibility
    #     repetition_penalty: Penalty for token repetition
    #     llm_mode: Few-shot mode selection
    #     instruction_template: Custom instruction template
    #
    # Returns:
    #     Tuple of (cleaned_text, data_dict_with_raw_output)
    debug_log(f"_generate_llm: llm_mode={llm_mode}")
    
    # Use getter function to get the latest loaded config (not stale import reference)
    from .smartlm_templates import get_llm_few_shot_examples
    LLM_FEW_SHOT_EXAMPLES = get_llm_few_shot_examples()
    
    debug_log(f"  Available modes: {list(LLM_FEW_SHOT_EXAMPLES.keys())}")
    
    # Set seed if provided
    if seed is not None:
        from transformers import set_seed
        import hashlib
        seed_bytes = str(seed).encode('utf-8')
        hash_object = hashlib.sha256(seed_bytes)
        hashed_seed = int(hash_object.hexdigest(), 16) % (2**32)
        set_seed(hashed_seed)
    
    # Load configuration for the selected mode
    config = LLM_FEW_SHOT_EXAMPLES.get(llm_mode, LLM_FEW_SHOT_EXAMPLES.get("direct_chat", {}))
    
    # Warn only if mode not found (fallback to direct_chat)
    if llm_mode not in LLM_FEW_SHOT_EXAMPLES:
        warning_log(f"Mode '{llm_mode}' not found, using direct_chat")
    else:
        debug_log(f"  Found mode config: system_prompt={config.get('system_prompt', '')[:50]}...")
    
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    examples = config.get("examples", [])
    debug_log(f"  Using {len(examples)} few-shot examples")
    
    # Get instruction template (custom or from config)
    if instruction_template:
        # Custom instruction provided
        template = instruction_template
    else:
        # Use template from config
        template = config.get("instruction_template", "")
    
    # Build messages based on mode
    if llm_mode != "direct_chat" and template:
        # Apply instruction template with few-shot examples
        req = template.replace("{prompt}", prompt) if "{prompt}" in template else f"{template} {prompt}"
        
        # Build messages: system + examples + user request
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(examples)
        messages.append({"role": "user", "content": req})
    else:
        # Direct chat mode - no instruction wrapper or examples
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    
    # Generate response with transformers
    try:
        # Apply chat template to convert messages to text
        input_text = smart_lm_instance.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize and generate
        inputs = smart_lm_instance.processor(input_text, return_tensors="pt").to(smart_lm_instance.model.device)
        
        outputs = smart_lm_instance.model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            do_sample=temperature > 0,
            pad_token_id=smart_lm_instance.processor.eos_token_id
        )
        
        # Decode only the generated tokens (skip input)
        generated_tokens = outputs[0][inputs['input_ids'].shape[1]:]
        text = smart_lm_instance.processor.decode(generated_tokens, skip_special_tokens=True)
        
        # Keep raw output for data (includes thinking tags)
        raw_text = text.strip()
        
        # Strip reasoning/thinking tags from "Thinker" models (e.g., MiroThinker, DeepSeek-R1)
        # These models output <think>...</think> before the actual response
        cleaned_text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()
        
        # Handle models that output untagged thinking (no <think> tags)
        # MiroThinker and similar models output reasoning like "Okay, let's tackle this..."
        # then have the actual output after double newlines
        
        # Method 1: Look for common thinking start patterns and find the actual output after
        thinking_start_patterns = [
            r'^(?:Okay|Alright|Let me|Let\'s|First|I\'ll|I need to|I should|I will|I want to|Hmm|So|Now)[,\s]',
        ]
        is_thinking_output = any(re.match(p, cleaned_text, re.IGNORECASE) for p in thinking_start_patterns)
        
        if is_thinking_output:
            # Look for double newline followed by substantial content
            # The actual output often starts with "A/An/The" or a descriptive phrase
            double_newline_match = re.search(r'\n\n+([A-Z][^\n]{50,})', cleaned_text)
            if double_newline_match:
                potential_output = double_newline_match.group(1)
                # Get the rest of the text after this point
                rest_start = double_newline_match.start(1)
                potential_output = cleaned_text[rest_start:].strip()
                # Verify it's substantial and looks like actual output (not more thinking)
                if len(potential_output) > 100 and not re.match(r'^(?:Okay|Alright|Let me|Let\'s|First|I\'ll|I need to|I should)[,\s]', potential_output, re.IGNORECASE):
                    cleaned_text = potential_output
        
        # Method 2: Look for explicit transition markers
        thinking_end_patterns = [
            r'(?:Final version[:\s]*|Alright[,\s]+actual[^:]*:|Proceed\.\s*|[Bb]egin fresh[^:]*:|Starting[:\s]+|Here(?:\'s| is) (?:the|my) (?:refined|expanded|improved)[^:]*:)',
        ]
        for pattern in thinking_end_patterns:
            match = re.search(pattern, cleaned_text, flags=re.IGNORECASE)
            if match:
                # Keep only content after the thinking marker
                potential_output = cleaned_text[match.end():].strip()
                # Only use if substantial content remains (>50 chars)
                if len(potential_output) > 50:
                    cleaned_text = potential_output
                    break
        
        # Return tuple: (cleaned_text, data_dict) - data dict includes raw output for data output
        return cleaned_text, {"raw_output": raw_text}

    except Exception as e:
        error_log(f"LLM generation error: {e}")
        raise


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Loading functions
    "load_transformers_model",
    "_load_mistral3",
    "_load_qwenvl", 
    "_load_florence2",
    "_load_llm",
    # Generation functions
    "generate_transformers",
    "_generate_mistral3",
    "_generate_qwenvl",
    "_generate_florence2",
    "_generate_llava",
    "_generate_mllama",
    "_generate_llm",
    # Florence2 utilities
    "FLORENCE_PROMPTS",
    "FLORENCE_TASKS",
    "get_florence_tasks",
    "update_florence_tasks",
    "nms_filter",
    "parse_florence_location_tokens",
    "draw_bboxes",
    # Helper functions
    "_parse_qwen_detection_json",
]

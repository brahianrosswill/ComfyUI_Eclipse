# Smart Language Model Loader v2 Guide

A comprehensive guide to the **Smart Language Model Loader v2** node for ComfyUI Eclipse.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Node Overview](#node-overview)
  - [Inputs](#inputs)
  - [Outputs](#outputs)
- [Model Families](#model-families)
  - [Mistral](#mistral)
  - [Qwen](#qwen)
  - [LLaVA](#llava)
  - [Florence](#florence)
  - [LLM (Text-Only)](#llm-text-only)
- [Loading Methods (Backends)](#loading-methods-backends)
  - [Transformers](#transformers)
  - [GGUF (llama-cpp-python)](#gguf-llama-cpp-python)
  - [vLLM (Docker)](#vllm-docker)
  - [vLLM (Native)](#vllm-native)
  - [SGLang (Docker)](#sglang-docker)
  - [Ollama (Docker)](#ollama-docker)
  - [llama.cpp (Docker)](#llamacpp-docker)
- [Compatibility Matrix](#compatibility-matrix)
- [Tasks Reference](#tasks-reference)
- [Templates](#templates)
- [Quantization Options](#quantization-options)
- [Docker Configuration](#docker-configuration)
- [Quick Start Examples](#quick-start-examples)
- [Multi-Task Mode](#multi-task-mode)
- [Troubleshooting](#troubleshooting)

---

## Overview

The **Smart Language Model Loader v2** is a unified node for loading and running vision-language and text-only language models in ComfyUI. It uses a **template-first workflow** where selecting a template auto-configures all settings, making it easy to switch between models.

### What Can This Node Do?

- **Image Analysis**: Describe, analyze, and extract information from images
- **Object Detection**: Detect and locate objects in images (Qwen, Florence)
- **OCR**: Extract text from images (Florence, vision models)
- **Text Generation**: Chat, expand prompts, translate, summarize (LLM mode)
- **Video Analysis**: Summarize video sequences (Qwen)
- **Prompt Generation**: Convert tags to natural language, refine prompts

---

## Key Features

| Feature | Description |
|---------|-------------|
| **🎯 Template-First Workflow** | Select a template to auto-configure model family, loading method, and paths |
| **🔍 Auto-Discovery** | Models in your LLM folder automatically appear in dropdowns |
| **🐳 Docker Integration** | Auto-start/stop Docker containers for vLLM, SGLang, Ollama, llama.cpp |
| **⚡ Multiple Backends** | 7 loading methods: Transformers, GGUF, vLLM, SGLang, Ollama, llama.cpp |
| **📦 Pre-Quantized Support** | Auto-detects FP8, AWQ, GPTQ models |
| **🎬 Video Support** | Process video frames with Qwen-VL models |
| **💾 Model Caching** | Keep models loaded between runs for faster inference |
| **🔄 Multi-Task Mode** | Chain 2-4 sequential tasks with output→input flow |
| **🧹 VRAM Management** | Auto cleanup and container stop to free VRAM |

---

## Node Overview

### Inputs

#### Core Settings

| Input | Type | Description |
|-------|------|-------------|
| **template_name** | Dropdown | Pre-configured template (auto-populates all settings) |
| **model_family** | Dropdown | Model architecture: Mistral, Qwen, Florence, LLaVA, LLM (Text-Only) |
| **loading_method** | Dropdown | Backend: Transformers, GGUF, vLLM, SGLang, Ollama, llama.cpp |
| **model_source** | Dropdown | "Local" (from LLM folder) or "HuggingFace" (download) |
| **model_name** | Dropdown | Auto-discovered models from your LLM folder |

#### Model Source Settings

| Input | Type | Description |
|-------|------|-------------|
| **repo_id** | String | HuggingFace repository ID (e.g., `Qwen/Qwen2.5-VL-7B-Instruct`) |
| **local_path** | String | Local path within LLM folder after download |

#### GGUF Vision Settings (mmproj)

| Input | Type | Description |
|-------|------|-------------|
| **mmproj_source** | Dropdown | "Local" or "HuggingFace" for vision adapter |
| **mmproj_url** | String | URL for mmproj GGUF file download |
| **mmproj_local** | Dropdown | Select local mmproj file |
| **mmproj_path** | String | mmproj filename after download |

#### Model Configuration

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| **quantization** | Dropdown | Auto | Precision: Auto, 4-bit, 8-bit, FP16, BF16, FP32 |
| **attention_mode** | Dropdown | auto | Attention: auto, flash_attention_2, sdpa, eager |
| **context_size** | Integer | 8192 | Context window (2048-131072 tokens) |
| **max_tokens** | Integer | 1024 | Maximum output tokens (64-2048) |

#### Docker Settings

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| **auto_start_container** | Boolean | True | Auto-start Docker container when needed |
| **auto_stop_container** | Boolean | True | Stop container after generation (frees VRAM) |

#### Task & Prompt

| Input | Type | Description |
|-------|------|-------------|
| **task** | Dropdown | Task type (filtered by model family) - Task 1 in multi-task mode |
| **user_prompt** | String | Text input / question for the model |
| **llm_custom_instruction** | String | Custom instruction template for LLM tasks |

#### Multi-Task Mode

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| **multi_task_mode** | Boolean | False | Enable sequential task chaining |
| **task_count** | Integer | 2 | Number of tasks to run (2-4) |
| **task_2** | Dropdown | - | Second task - receives output from task 1 |
| **task_3** | Dropdown | - | Third task - receives output from task 2 |
| **task_4** | Dropdown | - | Fourth task - receives output from task 3 |

#### Florence-Specific

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| **detection_filter_threshold** | Float | 0.80 | Remove boxes larger than X% of image |
| **nms_iou_threshold** | Float | 0.50 | Merge overlapping boxes (NMS) |

#### Memory & Caching

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| **memory_cleanup** | Boolean | True | Clear unused memory before loading |
| **keep_model_loaded** | Boolean | False | Keep model in VRAM between runs |
| **seed** | Integer | 0 | Random seed for generation |

#### Optional Inputs (Connectable)

| Input | Type | Description |
|-------|------|-------------|
| **images** | IMAGE | Image input for vision models |
| **text** | STRING | Text input (overrides user_prompt widget) |
| **pipe_opt** | SMARTLM_ADVANCED_PIPE | Advanced parameters (temperature, top_p, etc.) |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| **image** | IMAGE | Passthrough image (same as input) |
| **text** | STRING | Generated text response |
| **data** | JSON | Detection data with bboxes and labels (Florence, Qwen detection) |

---

## Model Families

### Mistral

**Vision-language models from Mistral AI** including Ministral-3 (3B, 8B, 14B) and Mistral Small 3 (24B).

| Property | Value |
|----------|-------|
| **Vision Support** | ✅ Yes |
| **Video Support** | ❌ No |
| **Best For** | High-quality image descriptions, analysis |
| **Transformers Version** | Requires v5.0+ |
| **VRAM (3B model)** | ~7 GB (FP16) |

**Recommended Models:**
- `Ministral-3-3B-Instruct-2512` - Fastest, lowest VRAM
- `Ministral-3-8B-Instruct-2512` - Balanced quality/speed
- `Ministral-3-14B-Instruct-2512` - Best quality

---

### Qwen

**Vision-language models from Alibaba** including Qwen2.5-VL and Qwen3-VL series.

| Property | Value |
|----------|-------|
| **Vision Support** | ✅ Yes |
| **Video Support** | ✅ Yes (multi-frame) |
| **Best For** | Object detection, video analysis, grounding |
| **Transformers Version** | Any (Qwen3-VL needs v4.57.1+) |
| **VRAM (3B model)** | ~7 GB (FP16), ~4 GB (4-bit) |

**Unique Features:**
- **Object Detection**: Returns JSON with bounding boxes
- **Grounding**: Locate specific objects by description
- **Video Summary**: Process multiple frames

**Recommended Models:**
- `Qwen2.5-VL-3B-Instruct` - Lightweight, excellent quality
- `Qwen2.5-VL-7B-Instruct` - Best balance
- `Qwen3-VL-4B` - Latest generation

---

### LLaVA

**LLaVA (Large Language and Vision Assistant)** family including LLaVA 1.5, LLaVA 1.6 (NeXT), and Llama 3.2 Vision.

| Property | Value |
|----------|-------|
| **Vision Support** | ✅ Yes |
| **Video Support** | ❌ No |
| **Best For** | General vision tasks, conversation |
| **Transformers Version** | Any |
| **VRAM (7B model)** | ~14 GB (FP16), ~6 GB (4-bit) |

**Supported Architectures:**
- **LLaVA 1.5/1.6**: Standard LLaVA models (`llava-hf/llava-v1.6-mistral-7b-hf`)
- **Llama 3.2 Vision (Mllama)**: Meta's multimodal Llama (`meta-llama/Llama-3.2-11B-Vision-Instruct`)

> **Note**: The node auto-detects LLaVA vs Mllama architecture from `config.json`

**Recommended Models:**
- `llava-v1.6-mistral-7b-hf` - Good quality, well-supported
- `llava-v1.6-vicuna-13b-hf` - Higher quality
- `Llama-3.2-11B-Vision-Instruct` - Latest from Meta

---

### Florence

**Microsoft Florence-2** specialized vision models with 15+ task types.

| Property | Value |
|----------|-------|
| **Vision Support** | ✅ Yes |
| **Video Support** | ❌ No |
| **Best For** | OCR, object detection, segmentation, DocVQA |
| **Transformers Version** | ⚠️ Requires v4.x (incompatible with v5+) |
| **VRAM (base model)** | ~4 GB |

**Unique Features:**
- **Specialized Tasks**: 15 task types with specific prompt codes
- **Region Detection**: Dense region captioning, region proposals
- **OCR**: Text extraction with optional bounding boxes
- **Segmentation**: Referring expression segmentation

> ⚠️ **Version Warning**: Florence-2 is **incompatible with transformers v5+**. If you have v5, either downgrade (`pip install transformers==4.46.3`) or use Qwen-VL instead.

**Recommended Models:**
- `Florence-2-base` - Lightweight (0.2B)
- `Florence-2-large` - Better quality (0.7B)
- `Florence-2-base-PromptGen-v2.0` - Optimized for prompt generation

---

### LLM (Text-Only)

**Text-only language models** without vision capability.

| Property | Value |
|----------|-------|
| **Vision Support** | ❌ No (text only) |
| **Best For** | Text expansion, translation, summarization |
| **Transformers Version** | Any |
| **VRAM (7B model)** | ~14 GB (FP16), ~5 GB (4-bit) |

**Use Cases:**
- Expand/refine prompts
- Convert tags to natural language or natural language to tags
- Translate text to English
- Summarize text
- Custom instructions

**Recommended Models:**
- `Mistral-7B-Instruct-v0.3` - High quality
- `Llama-3.2-3B-Instruct` - Fast, lightweight
- Any GGUF quantized model for lower VRAM

---

## Loading Methods (Backends)

### Transformers

**HuggingFace Transformers library** - Direct Python loading.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ❌ No |
| **Quantization** | BitsAndBytes (4-bit, 8-bit) |
| **Best For** | Simplest setup, all model families |

**Pros:**
- No Docker required
- Supports all model families
- Easy quantization with BitsAndBytes

**Cons:**
- Slower than vLLM/SGLang for batch processing
- Model stays in VRAM (no auto-unload)

---

### GGUF (llama-cpp-python)

**llama-cpp-python** for GGUF format models.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ❌ No |
| **Quantization** | Built into GGUF file (Q4_K_M, Q5_K_M, etc.) |
| **Best For** | Pre-quantized models, lower VRAM usage |

**Pros:**
- Excellent VRAM efficiency
- Quantization baked in
- Supports CPU offloading

**Cons:**
- Requires mmproj file for vision models
- Not all architectures supported (no Mistral3)

---

### vLLM (Docker)

**vLLM via Docker** - High-performance inference server.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ✅ Yes |
| **Quantization** | Auto-detects FP8/AWQ/GPTQ, BitsAndBytes 4-bit |
| **Best For** | Pre-quantized FP8 models, continuous batching |

**Pros:**
- Fast inference once loaded
- Auto container management
- Works on all platforms
- Native FP8 support

**Cons:**
- Requires Docker Desktop
- Slow model loading (~1-3 min for large models)
- Higher VRAM usage (Mistral3 uses mixed precision: FP8 for LLM backbone + BF16 for vision encoder)
- Container startup overhead

---

### vLLM (Native)

**Native vLLM installation** - Fastest option, Linux only.

| Property | Value |
|----------|-------|
| **Platform** | 🐧 Linux only |
| **Docker Required** | ❌ No |
| **Quantization** | FP8/AWQ/GPTQ, BitsAndBytes 4-bit |
| **Best For** | Maximum performance on Linux |

**Pros:**
- Fastest inference
- No Docker overhead
- Native GPU access

**Cons:**
- Linux only
- Requires `pip install vllm`

> ⚠️ **Note**: Only tested in WSL2 environment. Native Linux installation is untested.

---

### SGLang (Docker)

**SGLang via Docker** - Alternative to vLLM with RadixAttention.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ✅ Yes |
| **Quantization** | FP8/AWQ/GPTQ (no runtime quantization) |
| **Best For** | Better throughput for repeated requests |

**Pros:**
- RadixAttention for KV cache reuse
- Better batch throughput than vLLM

**Cons:**
- No runtime quantization (model must be pre-quantized)
- Container startup time

---

### Ollama (Docker)

**Ollama via Docker** - Easy model management with registry.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ✅ Yes |
| **Quantization** | Pre-quantized from Ollama registry |
| **Best For** | Fastest batch processing, easiest setup |

**Pros:**
- **Fastest for batch processing** (quick model loading)
- Auto-downloads models from registry
- Simple `ollama_model` name (e.g., `qwen2.5vl:7b`)
- Good Mistral3 support
- Lower VRAM usage than vLLM

**Cons:**
- Limited to Ollama registry models
- Less control over quantization
- No GGUF vision projector (mmproj) support; local GGUF only for text-only models

---

### llama.cpp (Docker)

**llama.cpp server via Docker** - Reference GGUF engine.

| Property | Value |
|----------|-------|
| **Platform** | Windows, Linux, macOS |
| **Docker Required** | ✅ Yes |
| **Quantization** | Built into GGUF file |
| **Best For** | GGUF models with vision support |

**Pros:**
- Best GGUF support
- Auto-detects mmproj files
- Flexible GPU layer offloading

**Cons:**
- Requires Docker
- Container startup time

---

## Compatibility Matrix

### Model Family × Loading Method Support

| Loading Method | Mistral | Qwen | Florence | LLaVA | LLM (Text) |
|---------------|:-------:|:----:|:--------:|:-----:|:----------:|
| **Transformers** | ✅¹ | ✅ | ✅² | ✅ | ✅ |
| **GGUF (llama-cpp-python)** | ❌³ | ✅ | ❌ | ✅⁴ | ✅ |
| **vLLM (Docker)** | ✅ | ✅ | ❌ | ❌ | ✅ |
| **vLLM (Native)** | ✅ | ✅ | ❌ | ❌ | ✅ |
| **SGLang (Docker)** | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Ollama (Docker)** | ✅ | ✅ | ❌ | ✅ | ✅ |
| **llama.cpp (Docker)** | ✅ | ✅ | ❌ | ✅ | ✅ |

**Notes:**
1. ¹ Mistral requires transformers v5.0+
2. ² Florence requires transformers v4.x (incompatible with v5+)
3. ³ Mistral3 architecture not supported by llama-cpp-python
4. ⁴ LLaVA GGUF requires mmproj file; Mllama not supported in GGUF

### Platform Availability

| Loading Method | Windows | Linux | macOS |
|---------------|:-------:|:-----:|:-----:|
| **Transformers** | ✅ | ✅ | ✅ |
| **GGUF (llama-cpp-python)** | ✅ | ✅ | ✅ |
| **vLLM (Docker)** | ✅ | ✅ | ✅ |
| **vLLM (Native)** | ❌ | ✅ | ❌ |
| **SGLang (Docker)** | ✅ | ✅ | ✅ |
| **Ollama (Docker)** | ✅ | ✅ | ✅ |
| **llama.cpp (Docker)** | ✅ | ✅ | ✅ |

---

## Tasks Reference

### Common Tasks (All Vision Models)

These tasks work with Mistral, Qwen, LLaVA, and Florence (where applicable):

| Task | Description |
|------|-------------|
| **Custom** | Use your own prompt in `user_prompt` |
| **Simple Description** | Brief one-sentence description |
| **Detailed Description** | Paragraph-length description |
| **Ultra Detailed Description** | Very comprehensive description |
| **Cinematic Description** | Film/cinematography style description |
| **Detailed Analysis** | Analytical breakdown of the image |
| **Image Analysis** | Technical analysis |
| **OCR** | Extract text from image |
| **Tags** | Generate comma-separated tags |
| **Tags to Natural Language** | Convert tags to flowing text |
| **Question Answering** | Answer questions about the image |
| **Refine & Expand Prompt** | Improve and expand a prompt |
| **Short Story** | Generate a short story from image |
| **Video Summary** | Summarize video frames (Qwen only) |

### Qwen-Specific Tasks

| Task | Description |
|------|-------------|
| **Qwen: Object Detection** | Detect all objects, returns JSON bboxes |
| **Qwen: Grounding** | Locate specific objects by description |

### Florence-Specific Tasks

| Task | Prompt Code | Description |
|------|-------------|-------------|
| **Florence: caption** | `<CAPTION>` | Short single-sentence caption |
| **Florence: detailed_caption** | `<DETAILED_CAPTION>` | Detailed paragraph |
| **Florence: more_detailed_caption** | `<MORE_DETAILED_CAPTION>` | Very detailed description |
| **Florence: dense_region_caption** | `<DENSE_REGION_CAPTION>` | Caption multiple regions |
| **Florence: region_proposal** | `<REGION_PROPOSAL>` | Generate region proposals |
| **Florence: region_caption** | `<OD>` | Object detection with captions |
| **Florence: caption_to_phrase_grounding** | `<CAPTION_TO_PHRASE_GROUNDING>` | Object detection by text description |
| **Florence: referring_expression_segmentation** | `<REFERRING_EXPRESSION_SEGMENTATION>` | Segment by text description |
| **Florence: ocr** | `<OCR>` | Extract text |
| **Florence: ocr_with_region** | `<OCR_WITH_REGION>` | Extract text with bboxes |
| **Florence: docvqa** | `<DocVQA>` | Document Q&A |
| **Florence: prompt_gen_tags** | `<GENERATE_TAGS>` | Generate tags (PromptGen models) |
| **Florence: prompt_gen_mixed_caption** | `<MIXED_CAPTION>` | Mixed-style caption |
| **Florence: prompt_gen_analyze** | `<ANALYZE>` | Analytical description |

### LLM (Text-Only) Tasks

| Task | Description |
|------|-------------|
| **LLM: Custom Instruction** | Use custom instruction template |
| **LLM: Tags to Natural Language** | Convert tags to sentences |
| **LLM: Natural Language to Tags** | Convert sentences to tags |
| **LLM: Refine & Expand Prompt** | Improve prompts |
| **LLM: Expand Text** | Expand input text into detailed |
| **LLM: Short Story** | Generate a short story from tags or description |
| **LLM: Summarize** | Summarize text |
| **LLM: Rewrite Style** | Rewrite in different style |
| **LLM: Translate to English** | Translate to English |

---

## Templates

Templates are pre-configured JSON files that auto-populate all node settings.

### Using Templates

1. Select a template from the **template_name** dropdown
2. All settings (model_family, loading_method, repo_id, etc.) auto-populate
3. Adjust individual settings if needed
4. Run the workflow

### Template Format

```json
{
  "model_family": "Qwen",
  "model_type": "qwenvl",
  "loading_method": "Transformers",
  "repo_id": "Qwen/Qwen2.5-VL-7B-Instruct",
  "local_path": "",
  "ollama_model": "",
  "mmproj_path": "",
  "mmproj_url": "",
  "quantization": "auto",
  "attention_mode": "auto",
  "context_size": 8192,
  "max_tokens": 1024,
  "default_task": "Detailed Description",
  "has_vision": true
}
```

### Template Naming Convention

- **Standard models**: `Model-Name.json` (e.g., `Qwen2.5-VL-7B-Instruct.json`)
- **Ollama models**: `ollama--model-name.json` (e.g., `ollama--qwen2.5-vl-7b.json`)
- **GGUF models**: `Model-Name.Q4_K_M.json` (includes quantization)

### Auto-Created Templates

Templates are automatically created when:
1. **Downloading from HuggingFace**: A template is created with your current widget settings
2. **Loading a local model**: If no matching template exists, one is auto-created

> **💡 Note:** Templates are only created when no matching template exists. If a template with the same name already exists, you'll see "Template already exists" - your customizations are safe!

**Creating Multiple Custom Templates from One Model:**

You can create specialized templates for different use cases from the same model:

1. **Set up widgets** - Configure task, user_prompt, and other settings for your use case
2. **Run workflow** - Model downloads (first time) or loads from cache, template auto-created
3. **Rename the template** - Give it a descriptive name (e.g., `Florence-2-PromptGen-Eyes.json`)
4. **Standard template recreated** - Next time you load the model, a new standard template is auto-created
5. **Repeat** - Change widgets for a different use case → run again → rename → repeat

**Example: Creating Multiple Florence-2 Detection Templates**

1. **First template (eye detection):**
   - Set `repo_id`: `microsoft/Florence-2-large` (or select existing local model)
   - Set `task`: "caption_to_phrase_grounding"
   - Set `user_prompt`: "eye"
   - Run workflow → Template `Florence-2-large.json` auto-created or updated if it exists
   - Rename to `Florence-2-large-Eye-Detection.json`

2. **Second template (face detection):**
   - Load the same model (with widgets configured for face detection)
   - Set `task`: "caption_to_phrase_grounding"
   - Set `user_prompt`: "face"
   - Run workflow → Standard template `Florence-2-large.json` recreated
   - Rename to `Florence-2-large-Face-Detection.json`

3. **Third template (captions):**
   - Set `task`: "detailed_caption"
   - Clear `user_prompt`
   - Run workflow → Standard template recreated
   - Keep as `Florence-2-large.json` for general use

**Result:** Multiple specialized templates sharing the same model files:
- `Florence-2-large-Eye-Detection.json` - Pre-configured for eye detection
- `Florence-2-large-Face-Detection.json` - Pre-configured for face detection
- `Florence-2-large.json` - Default for general captions

> **💡 Tip:** This workflow works for any model family. The template captures all widget values (task, user_prompt, quantization, max_tokens, etc.) so you can create presets for different use cases.

---

## Quantization Options

| Option | Description | Backend Support |
|--------|-------------|-----------------|
| **Auto (Best for VRAM)** | Auto-select based on model size vs VRAM | All |
| **4-bit (Lowest VRAM)** | BitsAndBytes 4-bit quantization | Transformers |
| **8-bit (Balanced)** | BitsAndBytes 8-bit quantization | Transformers only |
| **None (FP16)** | Half precision, no quantization | All |
| **None (BF16)** | BFloat16 precision | All |
| **None (FP32)** | Full precision | All |

### Pre-Quantized Models

For vLLM and SGLang, pre-quantized models are auto-detected:
- **FP8**: Fastest, best quality for quantized
- **AWQ**: Good quality, widely supported
- **GPTQ**: Compatible with many tools

### GGUF Quantization

GGUF files have quantization built-in (e.g., `Q4_K_M`, `Q5_K_M`):
- `Q4_K_M` - Good balance of quality/size
- `Q5_K_M` - Better quality, larger
- `Q8_0` - Near-lossless

---

## Docker Configuration

Docker backends are configured in `docker_config.json`:

### vLLM Settings

```json
"vllm": {
  "enabled": true,
  "url": "http://localhost:8000/v1",
  "auto_start": true,
  "stop_after_generation": true,
  "startup_timeout": 600,
  "request_timeout": 300
}
```

### SGLang Settings

```json
"sglang": {
  "enabled": true,
  "url": "http://localhost:30000/v1",
  "gpu_memory_utilization": 0.55,
  "startup_timeout": 300,
  "request_timeout": 600
}
```

### Ollama Settings

```json
"ollama": {
  "enabled": false,
  "port": 11434,
  "auto_pull": true,
  "startup_timeout": 120,
  "pull_timeout": 1800
}
```

### llama.cpp Settings

```json
"llamacpp": {
  "enabled": false,
  "port": 8080,
  "n_gpu_layers": -1,
  "ctx_size": 8192
}
```

---

## Quick Start Examples

### Example 1: Image Description with Qwen (Transformers)

1. Add **Smart Language Model Loader v2 [Eclipse]** node
2. Connect an image to `images` input
3. Set:
   - `template_name`: "Qwen2.5-VL-7B-Instruct"
   - `task`: "Detailed Description"
4. Click **Queue Prompt**

### Example 2: Object Detection with Florence

1. Add the node
2. Connect an image
3. Set:
   - `template_name`: "Florence-2-large"
   - `task`: "Florence: region_caption"
4. Check `data` output for bboxes

### Example 3: Fast Inference with vLLM Docker

1. Ensure Docker Desktop is running
2. Add the node
3. Set:
   - `model_family`: "Mistral"
   - `loading_method`: "vLLM (Docker)"
   - `model_name`: Select your local Ministral model
   - `auto_start_container`: True
   - `auto_stop_container`: True
4. First run starts container (~1-2 min), subsequent runs are fast

### Example 4: Text Expansion (LLM Mode)

1. Add the node (no image needed)
2. Set:
   - `model_family`: "LLM (Text-Only)"
   - `template_name`: Select a text-only model
   - `task`: "LLM: Expand Text"
   - `user_prompt`: "A cat sitting on a windowsill"
4. Output: Expanded, detailed description

---

## Troubleshooting

### Missing Dependencies / Import Errors

**Issue**: Node fails to load or shows import errors

**Solution**: Install the required dependencies from the requirements file:

```bash
# Navigate to the Eclipse node folder
cd ComfyUI/custom_nodes/ComfyUI_Eclipse

# Install requirements
pip install -r requirements.txt
```

> **💡 Tip**: After installing requirements, restart ComfyUI for changes to take effect.

### Florence-2 Not Loading

**Error**: `Florence-2 incompatible with transformers v5`

**Solution**: Downgrade transformers:
```bash
pip install transformers==4.46.3
```
Or use Qwen-VL as an alternative.

### Mistral3 Not Loading

**Error**: `Mistral3ForConditionalGeneration not found`

**Solution**: Upgrade transformers:
```bash
pip install transformers>=5.0.0
```

### Docker Container Won't Start

**Checks**:
1. Is Docker Desktop running? (`docker info`)
2. Check GPU access: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
3. Check `docker_config.json` settings
4. Ensure `llm_models_absolute_path` is set in `eclipse_config.json`
5. Review container logs: `docker logs <container_id>`

### Out of Memory (OOM)

**Solutions**:
1. Enable `memory_cleanup`: True
2. Use 4-bit quantization
3. Enable `auto_stop_container`: True
4. Reduce `context_size` for GGUF/vLLM
5. Disable `keep_model_loaded`
6. Use a smaller model

### Model Not Appearing in Dropdown

**Checks**:
1. Is model in your LLM folder? (Check `llm_models_path` in `eclipse_config.json`)
2. Does model have `config.json`? (Required for auto-discovery)
3. Is model family correct? (Models filtered by selected family)
4. Folder name should indicate family (e.g., `Ministral-*`, `Qwen-*`)
5. GGUF files should end in `.gguf`
6. Try refreshing the node (right-click → Reload Node)

### GGUF Vision Not Working

**Solution**: Ensure mmproj file is available:
1. Set `mmproj_source`: "Local" or "HuggingFace"
2. Select or download the matching mmproj GGUF file
3. mmproj files usually named `*-mmproj*.gguf`, `*projector*.gguf`, or `*-clip-*.gguf`
4. Place mmproj in same folder as the main GGUF model

### vLLM Fails for Mistral3/Pixtral

**Checks**:
1. Ensure model has `consolidated.safetensors` (Mistral native format)
2. Node auto-detects and uses `--load-format mistral`
3. `--enforce-eager` is auto-applied to prevent CUDA graph crashes
4. Custom/fine-tuned HF-only models may not work - use Transformers (v5) instead

### Ollama Vision Not Working with Local GGUF

**Issue**: Ollama doesn't support mmproj for local GGUF imports

**Solutions**:
1. Use `llama.cpp (Docker)` instead for local GGUF + vision
2. Or use Ollama registry models (e.g., `ministral-3:8b`, `llava:7b`)

### llama.cpp Docker Vision Not Working

**Checks**:
1. Ensure mmproj file is in same folder as GGUF model
2. Check mmproj filename matches patterns: `*mmproj*.gguf`, `*projector*.gguf`
3. Verify with: `curl http://localhost:8080/props` (should show `"vision": true`)
4. Check container logs: `docker logs eclipse-llamacpp`

### FP8 Model Crashes ("Cannot copy out of meta tensor")

**Issue**: Transformers v4.x does NOT support FP8 models

**Solutions**:
1. Switch to **vLLM (Docker)** or **SGLang (Docker)** - both have full FP8 support
2. Pre-configured FP8 templates auto-select the correct backend

### SGLang Container Not Starting

**Checks**:
1. Check Docker is running: `docker info`
2. Check GPU access: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
3. Check container logs: `docker logs eclipse_sglang_<model-name>`
4. Ensure sufficient VRAM for the model

---

### Docker Backend Troubleshooting Commands

**vLLM (Docker):**
```powershell
# Check Docker is running
docker info

# Check GPU access
docker run --gpus all nvidia/cuda:12.0-base nvidia-smi

# Check vLLM containers
docker ps -a | findstr vllm

# View container logs
docker logs <container_id>
```

**SGLang (Docker):**
```powershell
# Check Docker is running
docker info

# Check GPU access
docker run --gpus all nvidia/cuda:12.0-base nvidia-smi

# Check SGLang containers
docker ps -a | findstr sglang

# View container logs
docker logs eclipse_sglang_<model-name>
```

**Ollama (Docker):**
```powershell
# Check container status
docker ps -a | findstr eclipse-ollama

# View container logs
docker logs eclipse-ollama

# List imported models
docker exec eclipse-ollama ollama list
```

**llama.cpp (Docker):**
```powershell
# Check container status
docker ps -a | findstr eclipse-llamacpp

# View container logs
docker logs eclipse-llamacpp

# Test API (check if vision is enabled)
curl http://localhost:8080/props
# Should show "vision": true if mmproj loaded
```

---

### Debug Logging

Enable debug logging in `eclipse_config.json`:
```json
{
  "log_level": "debug"
}
```

**Key log prefixes:**
- `SmartLM`: Main node operations
- `vLLM Docker`: vLLM container management
- `SGLang Docker`: SGLang container management
- `Ollama Docker`: Ollama container management
- `llama.cpp Docker`: llama.cpp container management
- `Transformers`: Model loading
- `GGUF`: llama.cpp native operations

---

## Multi-Task Mode

Multi-task mode allows you to **chain 2-4 sequential tasks** where each task's output becomes the input for the next task. This is powerful for building prompt refinement pipelines without needing multiple nodes.

### How It Works

1. **Task 1** runs with your original input (image + user_prompt or text)
2. **Task 2** receives the output from Task 1 as its text input
3. **Task 3** receives the output from Task 2 (if enabled)
4. **Task 4** receives the output from Task 3 (if enabled)
5. Final output is returned

### Enabling Multi-Task Mode

1. Set **multi_task_mode**: `True`
2. Set **task_count**: Number of tasks (2, 3, or 4)
3. Configure each task dropdown (task, task_2, task_3, task_4)
4. The additional task widgets appear based on task_count

### Example: Image Tags to Refined Prompt

A common workflow for generating high-quality prompts from images:

| Step | Task | Input | Output |
|------|------|-------|--------|
| 1 | **Tags** | Image | `1girl, long hair, blue eyes, dress...` |
| 2 | **Tags to Natural Language** | Tags from step 1 | `A girl with long hair and blue eyes wearing a dress...` |
| 3 | **Expand Text** | Natural text from step 2 | `A beautiful young woman with flowing long hair and striking blue eyes...` |
| 4 | **Refine Prompt** | Expanded text from step 3 | Final polished prompt |

**Configuration:**
- `multi_task_mode`: True
- `task_count`: 4
- `task`: Tags
- `task_2`: Tags to Natural Language
- `task_3`: Expand Text
- `task_4`: Refine Prompt

### Example: LLM Text Processing Pipeline

For text-only models (no image input):

| Step | Task | Description |
|------|------|-------------|
| 1 | **LLM: Tags to Natural Language** | Convert input tags to sentences |
| 2 | **LLM: Expand Text** | Add more detail and description |

**Configuration:**
- `model_family`: LLM (Text-Only)
- `multi_task_mode`: True
- `task_count`: 2
- `task`: Tags to Natural Language
- `task_2`: Expand Text
- Connect tags via `text` input

### Notes

- **Task filtering**: All task dropdowns are filtered by the selected model family
- **VRAM efficiency**: Model is loaded once and reused for all tasks
- **KV cache clearing**: Between tasks, the KV cache is automatically cleared to prevent VRAM accumulation
- **Image handling**: Only Task 1 uses the image input; subsequent tasks are text-only
- **Performance**: Multi-task is faster than chaining multiple nodes since the model stays loaded

---

## Advanced Parameters

Connect the **LM Advanced Pipe [Eclipse]** node to `pipe_opt` for fine-tuned control:

| Parameter | Default | Description |
|-----------|---------|-------------|
| **temperature** | 0.7 | Randomness (0 = deterministic, 1+ = creative) |
| **top_p** | 0.9 | Nucleus sampling threshold |
| **top_k** | 50 | Top-k sampling |
| **repetition_penalty** | 1.0 | Penalize repeated tokens (>1 = less repetition) |
| **num_beams** | 1 | Beam search (>1 for better quality, slower) |
| **do_sample** | True | Enable sampling (False = greedy decoding) |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `eclipse_config.json` | Main config: LLM folder path, log level, HF token |
| `docker_config.json` | Docker backend settings: ports, timeouts, auto-start |
| `templates/smartlm_templates/*.json` | Model templates |
| `templates/config/smartlm_advanced_defaults.json` | Default advanced parameters per family |
| `templates/config/smartlm_prompt_defaults.json` | Task lists and system prompts |

# Smart Language Model Loader v2 Guide

**Template-First Workflow with Multi-Backend Support**

The Smart Language Model Loader v2 (Smart LML v2) provides a streamlined, template-first approach to loading and running vision-language and text-only models in ComfyUI. This new version supports seven distinct backends: **Transformers**, **GGUF (llama-cpp-python)**, **vLLM (Docker)**, **vLLM (Native)**, **SGLang (Docker)**, **Ollama (Docker)**, and **llama.cpp (Docker)** - giving you flexibility to choose the best balance of quality, speed, and VRAM usage for your workflow.

## What's New in v2?

### Key Improvements Over v1

| Feature | v1 | v2 |
|---------|----|----|
| **Workflow** | Template-first (select template, then run) | Template-first with multi-backend support |
| **Model Discovery** | Manual template creation | Auto-discovery from LLM models folder |
| **vLLM Support** | Not available | Full Docker and Native vLLM support |
| **Ollama Support** | Not available | Ollama Docker with registry models |
| **llama.cpp Docker** | Not available | Local GGUF with vision (mmproj) support |
| **Backend Selection** | Auto-detected from template | Explicit loading method dropdown |
| **Model Families** | QwenVL, Florence, LLM | Mistral, Qwen, Florence, LLaVA, LLM (Text-Only) |
| **Task Organization** | Per-family widgets | Unified task dropdown with family prefixes |
| **Docker Integration** | None | Auto-start/stop containers, VRAM management |

### New Features

- **🚀 vLLM Backend**: High-performance inference via Docker or native Linux installation
- **⚡ SGLang Backend**: Alternative high-performance inference with RadixAttention (Docker)
- **🦙 Ollama Docker**: Easy model management with Ollama registry (vision via registry models)
- **⚡ llama.cpp Docker**: Local GGUF files with vision support via mmproj auto-detection
- **🔥 FP8 Support**: Pre-quantized FP8 models for vLLM and SGLang (faster, lower VRAM than FP16)
- **🦙 LLaVA Family**: Support for generic vision models from Ollama registry (LLaVA, Moondream, etc.)
- **🔍 Auto-Discovery**: Models in your LLM folder automatically appear in dropdown
- **👨‍👩‍👧‍👦 Model Families**: Clear separation of Mistral, Qwen, Florence, LLaVA, and LLM models
- **🎯 Unified Tasks**: Single task dropdown, auto-filtered by selected model family
- **🐳 Docker Management**: Auto-start/stop containers to free VRAM
- **⚡ Mistral3/Pixtral**: Full support for Mistral vision models with automatic format detection

---

## Table of Contents

- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Model Families](#model-families)
- [Loading Methods](#loading-methods)
- [Mistral3 Compatibility Matrix](#mistral3-compatibility-matrix)
- [Node Overview](#node-overview)
- [Workflow Examples](#workflow-examples)
- [Parameters Guide](#parameters-guide)
- [Docker Backend Setup](#docker-backend-setup)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Your First Image Analysis (5 Minutes)

**Goal:** Get a detailed description of an image using a pre-configured template.

**Steps:**
1. Add **Smart Language Model Loader v2 [Eclipse]** node to your workflow
2. Connect an **IMAGE** output to the `images` input
3. Configure the node:
   - `template_name`: Select a template (e.g., `Ministral-3-3B-Instruct-2512`)
   - `task`: **Detailed Description**
4. Click **Queue Prompt**

**Expected Result:**
```
The image shows a young woman standing in a sunlit garden. She has long 
brown hair and wears a flowing white dress. Cherry blossoms bloom on 
nearby trees, their delicate pink petals creating a beautiful contrast 
with the bright blue sky behind her.
```

### Fast Auto-Tagging with Florence-2

**Goal:** Generate SD/Flux tags quickly.

**Steps:**
1. Add **Smart Language Model Loader v2 [Eclipse]** node
2. Connect image to `images` input
3. Configure:
   - `template_name`: Select `Florence-2-base-PromptGen-v2.0`
   - `task`: **prompt_gen_tags**
4. Run workflow

**Expected Result:**
```
1girl, long hair, brown hair, white dress, outdoors, garden, cherry blossoms, blue sky, smile
```

### High-Performance vLLM (Docker)

**Goal:** Maximum inference speed with vLLM.

**Requirements:** Docker Desktop installed and running

**Steps:**
1. Add **Smart Language Model Loader v2 [Eclipse]** node
2. Connect image to `images` input
3. Configure:
   - `template_name`: Select a vLLM template (e.g., `Ministral-3-3B-Instruct-2512`)
   - `auto_start_container`: ✅ (enabled)
   - `auto_stop_container`: ✅ (enabled)
   - `task`: **Detailed Description**
4. Run workflow

The Docker container starts automatically, serves the model, and stops after generation to free VRAM.

### Local GGUF with Vision (llama.cpp Docker)

**Goal:** Run local GGUF files with vision support (mmproj).

**Requirements:** Docker Desktop, GGUF model + mmproj file in same folder

**Option 1: Use a Template (Auto-Download)**
1. Select a GGUF template from `template_name` dropdown (e.g., `Qwen2.5-VL-3B-Instruct-Q4_K_M`)
2. Files download automatically from HuggingFace on first run
3. Run workflow!

**Option 2: Manual Download**
1. Download GGUF model (e.g., `Ministral-3-8B-Instruct-Q4_K_M.gguf`)
2. Download matching mmproj file (e.g., `Ministral-3-8B-Instruct-BF16-mmproj.gguf`)
3. Place both in your LLM models folder (e.g., `<llm_folder>/Ministral-3-8B-Instruct-GGUF/`)
4. Add **Smart Language Model Loader v2 [Eclipse]** node
5. Connect image to `images` input
6. Configure:
   - `loading_method`: **llama.cpp (Docker)**
   - `model_source`: **Local**
   - `model_name`: Select the GGUF file
   - `task`: **Detailed Description**
7. Run workflow

The mmproj file is auto-detected and vision is enabled automatically.

### Easy Setup with Ollama (Docker)

**Goal:** Use Ollama's pre-built vision models.

**Requirements:** Docker Desktop installed

**Steps:**
1. Add **Smart Language Model Loader v2 [Eclipse]** node
2. Connect image to `images` input
3. Configure:
   - `template_name`: Select an Ollama template (e.g., `ollama--ministral-3-8b`)
   - `task`: **Detailed Description**
4. Run workflow

Ollama automatically pulls and caches the model. Vision works out of the box with registry models.

### LLaVA Vision Models (Ollama)

**Goal:** Use LLaVA family models for image descriptions.

**Requirements:** Docker Desktop installed

**Steps:**
1. Add **Smart Language Model Loader v2 [Eclipse]** node
2. Connect image to `images` input
3. Configure:
   - `template_name`: Select `ollama--llava-llama3-8b` (or other LLaVA template)
   - `task`: **Ultra Detailed Description**
4. Run workflow

**Model Options by Quality/Speed:**
| Template | Model | Quality | Speed |
|----------|-------|---------|-------|
| `ollama--moondream-1.8b` | moondream:1.8b | Basic | ⚡ Fast |
| `ollama--llava-7b` | llava:7b | Good | Medium |
| `ollama--llava-llama3-8b` | llava-llama3:8b | Good | Medium |
| `ollama--llava-13b` | llava:13b | Best | Slower |

Models auto-pull from Ollama registry on first use.

---

## Core Concepts

#### Folder Configuration

The folder location is configured in `eclipse_config.json` with two settings:

| Setting | Purpose | Used By |
|---------|---------|---------|
| `llm_models_path` | Path for Python file scanning | All backends |
| `llm_models_absolute_path` | Full path for Docker volume mounts | Docker backends only |

**How `llm_models_path` is resolved:**

| Config Value | Resolution | Result |
|--------------|------------|--------|
| `"LLM"` (relative) | `ComfyUI/models/` + `LLM` | `ComfyUI/models/LLM/` |
| `"MyVLMs"` (relative) | `ComfyUI/models/` + `MyVLMs` | `ComfyUI/models/MyVLMs/` |
| `"AI/vision-models"` (relative) | `ComfyUI/models/` + `AI/vision-models` | `ComfyUI/models/AI/vision-models/` |
| `"D:/AI/models/LLM"` (absolute) | Used directly | `D:/AI/models/LLM/` |
| `"/home/user/models"` (absolute) | Used directly | `/home/user/models/` |

**Configuration Examples:**

```json
// Example 1: Default - models inside ComfyUI folder
{
  "llm_models_path": "LLM",
  "llm_models_absolute_path": "C:/ComfyUI/models/LLM"
}
// → Python scans: C:/ComfyUI/models/LLM/
// → Docker mounts: C:/ComfyUI/models/LLM/

// Example 2: Custom subfolder
{
  "llm_models_path": "vision/VLMs",
  "llm_models_absolute_path": "C:/ComfyUI/models/vision/VLMs"
}
// → Python scans: C:/ComfyUI/models/vision/VLMs/
// → Docker mounts: C:/ComfyUI/models/vision/VLMs/

// Example 3: External folder (outside ComfyUI)
{
  "llm_models_path": "D:/AI/SharedModels/LLM",
  "llm_models_absolute_path": "D:/AI/SharedModels/LLM"
}
// → Python scans: D:/AI/SharedModels/LLM/ (absolute path used directly)
// → Docker mounts: D:/AI/SharedModels/LLM/
```

> ⚠️ **Important for Docker backends:** The `llm_models_absolute_path` **must** be set correctly for vLLM, SGLang, Ollama, and llama.cpp Docker backends. Docker containers require the full absolute path to mount the folder as a volume. If not set, Eclipse will try to derive it from `llm_models_path`, but this may fail for relative paths.


### Template-First Workflow

v2 uses a **template-first** approach where you:

1. **Select Template** → Choose a pre-configured template that sets model, family, loading method, and defaults
2. **Pick Task** → What to generate (auto-filtered based on template's model family)
3. **Customize (Optional)** → Override model_source, model_name, or other settings if needed

This is intuitive because:
- Templates provide working configurations out of the box
- Selecting a template auto-configures: model_family, loading_method, repo_id, quantization, etc.
- Tasks are filtered automatically based on the template's model family
- You can still override settings for advanced use cases

### Auto-Discovery

Models placed in your **LLM models folder** are automatically discovered and appear in the `model_name` dropdown.

The node detects:

- **Model Family**: From folder/file naming (e.g., `Mistral-*`, `Qwen-*`, `Florence-*`)
- **Format**: GGUF files vs. folders with safetensors
- **Compatibility**: Filters models based on selected family and method

### Pre-configured Templates

For Ollama Docker, pre-configured templates are available in the `template_name` dropdown. These templates point to Ollama registry models that auto-pull on first use:

- **Mistral/Qwen templates**: `ollama--ministral-3-8b`, `ollama--qwen2.5-vl-7b`, etc.
- **LLaVA templates**: `ollama--llava-7b`, `ollama--llava-llama3-8b`, `ollama--moondream-1.8b`, etc.
- **Text-only templates**: `ollama--mistral-7b`, `ollama--llama3.1-8b`, `ollama--deepseek-r1-7b`, etc.

💡 **Tip:** When using Ollama Docker with `model_source: Local`, select a template from the `template_name` dropdown. The template contains the Ollama registry model name (e.g., `llava-llama3:8b`) which will be auto-pulled.

### Automatic Template Creation (repo_id Workflow)

When you download a model from HuggingFace using `repo_id`, a template is **automatically created** with all your current widget values. This is the easiest way to add new models to your library:

**How It Works:**
1. **Configure the node manually:**
   - Set `model_source`: **HuggingFace**
   - Set `model_family`: Match the model type (e.g., Qwen, Mistral)
   - Set `loading_method`: Your preferred backend
   - Enter `repo_id`: The HuggingFace repository (e.g., `Qwen/Qwen2.5-VL-3B-Instruct`)
   - Configure other settings (task, user_prompt, quantization, max_tokens, etc.)

2. **Execute the workflow:**
   - The model downloads automatically from HuggingFace
   - Files are saved to your LLM models folder (configured in `eclipse_config.json`)

3. **Template is auto-created:**
   - A template file is saved (e.g., `Qwen2.5-VL-3B-Instruct.json`)
   - All your widget settings are preserved (task, quantization, max_tokens, context_size, etc.)
   - **Quantization is auto-detected**: FP8, AWQ, GPTQ, and other pre-quantized formats are detected from the model files and saved to the template
   - The template appears in the `template_name` dropdown

4. **Next time - just select the template!**
   - No need to re-enter repo_id or configure settings
   - Model loads from local cache instantly

**Example: Adding a New Qwen Model**
```
1. model_source: HuggingFace
2. model_family: Qwen
3. loading_method: Transformers
4. repo_id: Qwen/Qwen2.5-VL-7B-Instruct
5. quantization: 4-bit (Lowest VRAM)
6. max_tokens: 1024
7. → Execute workflow
8. → Model downloads (~5-10 min first time)
9. → Template "Qwen2.5-VL-7B-Instruct.json" auto-created
10. → Next time: just select template from dropdown!
```

**Creating Multiple Custom Templates:**

You can create specialized templates for different use cases from the same model:

1. **Set up widgets** - Configure task, user_prompt, and other settings for your use case
2. **Run with no template selected** - Model downloads (first time) or loads from cache, template auto-created
3. **Rename the template** - Give it a descriptive name (e.g., `Qwen-7B-detailed-tags.json`)
4. **Change widgets and repeat** - Different task/settings → run again → new default template created
5. **Result** - Multiple specialized templates sharing the same model files

> **💡 Example:** Create `Qwen-7B-tags.json` (task: Tags), `Qwen-7B-story.json` (task: Short Story), and `Qwen-7B-analysis.json` (task: Image Analysis) - all from one `Qwen2.5-VL-7B-Instruct` download.

💡 **Tips:**
- Templates are only created when no matching template exists. If a template with the same name already exists, you'll see "Template already exists" - your customizations are safe!
- Pre-quantized models (FP8, AWQ, GPTQ) are automatically detected and the quantization type is saved in the template

### Unified Task System

Tasks are automatically filtered based on your selected `model_family`. When you select a family, only relevant tasks appear in the dropdown:

**Mistral/Qwen/LLaVA Tasks:**
- Custom, Simple Description, Detailed Description
- Ultra Detailed Description, Cinematic Description
- Image Analysis, Question Answering, Video Summary (Qwen only)
- OCR, Tags, Short Story, Detailed Analysis

**Florence Tasks:**
- caption, detailed_caption, more_detailed_caption
- prompt_gen_tags, ocr, caption_to_phrase_grounding

**LLM Tasks:**
- Custom Instruction, Refine & Expand Prompt
- Tags to Natural Language, Natural Language to Tags
- Summarize, Rewrite Style, Translate to English

The dropdown shows clean task names (e.g., "Detailed Description") without family prefixes - filtering happens automatically in the background.

---

## Model Families

### Mistral (Vision-Language)

**Supports:** Images, vLLM Docker/Native, Transformers

**Models:**
| Model | Size | VRAM (FP8) | Description |
|-------|------|------------|-------------|
| Ministral-3-3B-Instruct-2512 | 3B | ~4 GB | Fast, efficient vision |
| Ministral-3-8B-Instruct-2512 | 8B | ~6 GB | Higher quality |
| Pixtral-12B | 12B | ~8 GB | Best quality Mistral vision |

**Strengths:**
- ✅ Excellent vision understanding
- ✅ Fast inference with vLLM
- ✅ FP8 pre-quantized models available
- ✅ Native Mistral format support

**Tasks:**
- Custom, Simple Description, Detailed Description
- Ultra Detailed Description, Cinematic Description
- Image Analysis, Question Answering

### Qwen (Vision-Language)

**Supports:** Images, Videos, Transformers, GGUF

**Models:**
| Model | Size | VRAM | Video | Description |
|-------|------|------|-------|-------------|
| Qwen2.5-VL-3B-Instruct | 3B | 6 GB | ✅ | Good balance |
| Qwen2.5-VL-7B-Instruct | 7B | 14 GB | ✅ | High quality |
| Qwen3-VL-2B-Instruct | 2B | 4 GB | ✅ | Fastest |
| Qwen3-VL-8B-Instruct | 8B | 12 GB | ✅ | Best quality |

**Strengths:**
- ✅ Video analysis with multiple frames
- ✅ GGUF support for low VRAM
- ✅ Excellent at detailed descriptions
- ✅ Natural language understanding

**Tasks:**
- Custom, Tags, Simple/Detailed/Ultra Detailed Description
- Cinematic Description, Detailed Analysis
- Video Summary, Short Story, Prompt Refine

### Florence (Vision-Language)

**Supports:** Images only, Transformers only

> **💡 Model Reuse:** If you already have Florence2 models downloaded by other nodes (e.g., comfyui-florence2) in `models/florence2/`, Eclipse will automatically detect and use them - no duplicate downloads needed!

**Models:**
| Model | Size | Disk | VRAM | Best For |
|-------|------|------|------|----------|
| Florence-2-base | 230M | ~0.5 GB | ~1.5 GB | General captions |
| Florence-2-base-PromptGen-v2.0 | 230M | ~1.0 GB | ~2 GB | SD/Flux tags |
| Florence-2-large-PromptGen-v2.0 | 770M | ~3.0 GB | ~4 GB | High-quality tags |

**Strengths:**
- ✅ Extremely fast (<1 second)
- ✅ Very low VRAM (~1-3 GB)
- ✅ Specialized detection tasks
- ✅ Object detection with bounding boxes

**Tasks:**
- caption, detailed_caption, more_detailed_caption
- prompt_gen_tags, ocr, ocr_with_region
- caption_to_phrase_grounding, region_proposal
- dense_region_caption, referring_expression_segmentation

**Creating Custom Templates (e.g., for specific detection tasks):**

When you download a model via `repo_id`, a template is auto-created with your current widget values. You can use this to create multiple specialized templates:

1. **Set up widgets** - Configure the node with your desired settings:
   - Enter `repo_id` (e.g., `MiaoshouAI/Florence-2-base-PromptGen-v1.5`)
   - Set `task` to your detection task (e.g., `caption_to_phrase_grounding`)
   - Set `user_prompt` to your detection target (e.g., `eyes`)
   - Leave `template_name` as "None"

2. **First run** - Execute the workflow:
   - Model downloads to your LLM models folder (or uses existing from `models/florence2/` if found)
   - Template `Florence-2-base-PromptGen-v1.5.json` is auto-created with your widget values

3. **Rename template** - Rename to describe its purpose:
   - `Florence-2-base-PromptGen-v1.5.json` → `Florence-2-PromptGen-eyes.json`

4. **Repeat for other tasks** - Change widget values and run again:
   - Set `task` to `detailed_caption`, clear `user_prompt`
   - Run → New `Florence-2-base-PromptGen-v1.5.json` created (no re-download, model exists)
   - Keep as default, or rename to `Florence-2-PromptGen-captions.json`

5. **Result** - Multiple specialized templates, one model:
   - `Florence-2-PromptGen-eyes.json` - Pre-configured for eye detection
   - `Florence-2-PromptGen-captions.json` - Pre-configured for detailed captions
   - All using the same downloaded model files

> **💡 Tip:** This workflow works for any model family. The template captures all widget values (task, user_prompt, temperature, etc.) so you can create presets for different use cases.

### LLM (Text-Only)

**Supports:** Text only, Transformers, GGUF, vLLM

**Models:**
| Model | Size | VRAM | Description |
|-------|------|------|-------------|
| Mistral-7B-Instruct-v0.3 | 7B | 14 GB (fp16) | General purpose |
| Llama-3-8B-Instruct | 8B | 16 GB (fp16) | Strong reasoning |
| Any GGUF LLM | Varies | 3-8 GB | Low VRAM option |

**Strengths:**
- ✅ Fast text processing
- ✅ Prompt refinement
- ✅ Tags to natural language
- ✅ All backends supported

**Tasks:**
- Custom Instruction, Refine & Expand Prompt
- Tags to Natural Language, Natural Language to Tags
- Summarize, Rewrite Style, Translate to English

### LLaVA (Generic Vision Models)

**Supports:** Images, GGUF (llama-cpp-python), Ollama Docker, llama.cpp Docker

The LLaVA family provides access to generic vision models that don't fit into Mistral/Qwen categories. This includes models like LLaVA, Moondream, MiniCPM-V, and other community vision models. LLaVA models can be loaded via Ollama registry or as local GGUF files with mmproj vision support.

**Models (via Ollama Registry):**
| Model | Size | VRAM | Speed | Description |
|-------|------|------|-------|-------------|
| moondream:1.8b | 1.8B | ~2 GB | Fast | Lightweight, basic descriptions |
| llava:7b | 7B | ~5 GB | Medium | Good balance of quality/speed |
| llava:13b | 13B | ~9 GB | Slower | Higher quality descriptions |
| llava-llama3:8b | 8B | ~6 GB | Medium | LLaVA with Llama 3 backbone |
| minicpm-v:8b | 8B | ~6 GB | Medium | MiniCPM vision model |

**Strengths:**
- ✅ Easy setup via Ollama Docker or local GGUF
- ✅ Auto-pull from Ollama registry
- ✅ Local GGUF with vision via llama-cpp-python or llama.cpp Docker
- ✅ Variety of model sizes and architectures
- ✅ Good for general image descriptions
- ✅ Pre-configured templates available

**Limitations:**
- ❌ No Transformers support (use GGUF or Docker backends)
- ❌ Quality varies significantly by model size
- ❌ No structured output (detection, grounding)

**Pre-configured Templates:**
- `ollama--moondream-1.8b` - Fast, lightweight (1.8B)
- `ollama--llava-7b` - Good balance (7B)
- `ollama--llava-13b` - Higher quality (13B)
- `ollama--llava-llama3-8b` - LLaVA + Llama 3 (8B)
- `ollama--minicpm-v-8b` - MiniCPM-V (8B)

**Tasks:**
- Custom, Simple Description, Detailed Description
- Ultra Detailed Description, Cinematic Description
- Image Analysis, Question Answering
- OCR, Tags, Short Story, Detailed Analysis

---

## Loading Methods

### Overview Table

| Method | Platform | Model Format | Vision | VRAM | Speed | Setup |
|--------|----------|--------------|--------|------|-------|-------|
| **Transformers** | All | Safetensors | ✅ | High | Medium | Easy |
| **GGUF (llama-cpp-python)** | All | GGUF | ✅ (Qwen) | Low | Medium | Easy |
| **vLLM (Docker)** | Win/Linux | Safetensors/FP8 | ✅ | High | Fast | Medium |
| **vLLM (Native)** | Linux | Safetensors/FP8 | ✅ | High | Fastest | Hard |
| **SGLang (Docker)** | Win/Linux | Safetensors/FP8 | ✅ | High | Fast | Medium |
| **Ollama (Docker)** | All | Registry/GGUF | ✅* | Medium | Fast | Easy |
| **llama.cpp (Docker)** | All | GGUF + mmproj | ✅ | Low | Fast | Easy |

*Ollama vision only works with registry models (e.g., `ministral-3:8b`, `llava:7b`), not local GGUF imports.

### Family Support by Loading Method

| Family | Transformers | GGUF | vLLM Docker | vLLM Native | SGLang Docker | Ollama Docker | llama.cpp Docker |
|--------|--------------|------|-------------|-------------|---------------|---------------|------------------|
| **Mistral** | ✅ Vision | ❌ | ✅ Vision | ✅ Vision | ✅ Vision | ✅ Registry | ✅ mmproj |
| **Qwen** | ✅ Vision* | ✅ Vision | ✅ Vision | ✅ Vision | ✅ Vision | ✅ Registry | ✅ mmproj |
| **Florence** | ✅ Vision | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **LLaVA** | ❌ | ✅ Vision | ❌ | ❌ | ❌ | ✅ Vision | ✅ mmproj |
| **LLM (Text)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

*Qwen FP8 models require vLLM or SGLang (Docker) - Transformers v4.x does NOT support FP8.

---

### Transformers

**Best For:** Simplicity, automatic downloads, full quality

**Pros:**
- ✅ Auto-downloads from HuggingFace
- ✅ Auto-quantization (4bit/8bit) based on VRAM
- ✅ Full model quality
- ✅ Works on all platforms

**Cons:**
- ❌ Higher VRAM usage than GGUF
- ❌ Slower than vLLM for batch inference
- ❌ Mistral3 requires Transformers v5 (breaks Florence-2)

**When to Use:**
- First-time users
- When you want automatic model management
- For Florence-2 (requires Transformers v4.x)

**Supported Families:** Mistral (v5 only), Qwen, Florence (v4 only), LLM

⚠️ **Version Conflict:**
- **Mistral3/Ministral3** requires `transformers>=5.0.0`
- **Florence-2** requires `transformers==4.46.3` (incompatible with v5)
- You cannot use both Mistral3 and Florence-2 with Transformers in the same environment
- **Solution:** Use vLLM/llama.cpp Docker for Mistral3, keep Transformers v4 for Florence-2

---

### GGUF (llama-cpp-python)

**Best For:** Low VRAM, pre-quantized models, CPU inference

**Pros:**
- ✅ Lowest VRAM usage
- ✅ Pre-quantized (Q4, Q5, Q8)
- ✅ Fast loading
- ✅ Works on CPU
- ✅ Auto-download via templates (HuggingFace)

**Cons:**
- ❌ Slightly lower quality than full models
- ❌ Requires mmproj file for vision

**When to Use:**
- 8GB VRAM or less
- Running multiple models
- CPU inference
- Qwen, LLaVA, or generic LLM models

**Supported Families:** Qwen (with vision), LLaVA (with vision), LLM (text-only)  
**NOT Supported:** Mistral3, Florence (use llama.cpp Docker or other methods for Mistral3)

---

### vLLM (Docker)

**Best For:** Maximum performance, official Mistral models

**Pros:**
- ✅ Highest inference speed (continuous batching)
- ✅ Auto-start/stop containers
- ✅ Works on Windows (via Docker Desktop)
- ✅ Full vision support for official Mistral3 models

**Cons:**
- ❌ Requires Docker Desktop + NVIDIA Container Toolkit
- ❌ Initial container startup time (~30-60s)
- ❌ High VRAM usage (full precision)
- ❌ Mistral3: Only official models with native format (not custom/fine-tuned HF models)

**When to Use:**
- High-throughput workflows
- When speed is critical
- Official Mistral3 models (from mistral.ai)
- Windows users wanting vLLM

**Supported Families:** Mistral (official only), Qwen, LLM

⚠️ **Mistral3 Format Requirement:**
- vLLM requires Mistral's **native format** (`consolidated.safetensors` + `params.json`)
- Official models from `mistralai/` have this format
- Custom/fine-tuned models (e.g., community models) often only have HuggingFace format
- HF-format-only models will NOT work with vLLM Docker
- **Solution:** Use Transformers (v5) or llama.cpp Docker for custom Mistral3 models

---

### vLLM (Native)

**Best For:** Linux users, direct vLLM installation, official models

**Pros:**
- ✅ Fastest option (no Docker overhead)
- ✅ Direct GPU access
- ✅ Lower latency

**Cons:**
- ❌ Linux only (or WSL2 on Windows)
- ❌ Requires vLLM pip installation
- ❌ Manual setup required
- ❌ Mistral3: Only official models with native format

**When to Use:**
- Linux systems (native or WSL2)
- When Docker overhead is unacceptable
- Server deployments
- Official Mistral3 models only

**Supported Families:** Mistral (official only), Qwen, LLM

⚠️ **Note:** vLLM Native has only been tested with WSL2 (Windows Subsystem for Linux). Native Linux installations should work but are untested.

---

### SGLang (Docker) 🆕

**Best For:** High-performance inference, FP8 models, RadixAttention optimization

**Pros:**
- ✅ High inference speed (RadixAttention for KV cache reuse)
- ✅ Full FP8 model support (pre-quantized models work out of the box)
- ✅ Auto-start/stop containers
- ✅ Works on Windows (via Docker Desktop)
- ✅ Full vision support for Qwen and Mistral
- ✅ OpenAI-compatible API

**Cons:**
- ❌ Requires Docker Desktop + NVIDIA Container Toolkit
- ❌ Initial container startup time (~30-60s)
- ❌ High VRAM usage for non-quantized models

**When to Use:**
- FP8 pre-quantized models (Qwen3-VL-*-FP8, etc.)
- High-throughput workflows
- Alternative to vLLM with better FP8 support
- RadixAttention benefits (repeated prompts)

**Supported Families:** Mistral, Qwen (including FP8), LLM

**Container Settings:**

| Setting | Description |
|---------|-------------|
| `auto_start_container` | Start container when model not loaded |
| `auto_stop_container` | Stop container after generation |

---

### Ollama (Docker) 🆕

**Best For:** Easy setup, Ollama registry models, beginners

**Pros:**
- ✅ Super easy setup (one Docker container)
- ✅ Automatic model pulling from Ollama registry
- ✅ Vision works with registry models (e.g., `llava:7b`, `pixtral`, `qwen2.5-vl`)
- ✅ **Pre-configured templates** for popular models - just select and run!
- ✅ Can import local Mistral3 GGUF for text generation
- ✅ Model caching and management
- ✅ OpenAI-compatible API

**Cons:**
- ❌ Vision does NOT work with local GGUF imports (no mmproj support)
- ❌ Mistral3 local GGUF = text-only (no vision)
- ❌ Requires Docker Desktop

**When to Use:**
- Want easiest possible setup
- Using Ollama registry models with built-in vision
- Mistral3 text-only tasks (captioning without images)

**Supported Families:** Mistral (text-only for local GGUF), Qwen, LLaVA, LLM

💡 **Use Preset Templates (Easiest!):**
Select from pre-configured templates in the `template_name` dropdown:

**Vision Models (Mistral/Qwen):**
- `ollama--ministral-3-8b` - Ministral 3 8B vision (6GB, 256K context)
- `ollama--ministral-3-3b` - Ministral 3 3B vision (3GB, smaller/faster)
- `ollama--mistral-small3.1-24b` - Mistral Small 3.1 (15GB, best quality)
- `ollama--llama3.2-vision-11b` - Llama 3.2 Vision 11B
- `ollama--qwen2.5-vl-7b` - Qwen2.5 Vision-Language 7B

**LLaVA Family Vision Models:**
- `ollama--moondream-1.8b` - Fast, lightweight (1.8B, ~2GB)
- `ollama--llava-7b` - Good balance (7B, ~5GB)
- `ollama--llava-13b` - Higher quality (13B, ~9GB)
- `ollama--llava-llama3-8b` - LLaVA + Llama 3 backbone (8B, ~6GB)
- `ollama--minicpm-v-8b` - MiniCPM-V vision (8B, ~6GB)

**Text-Only Models:**
- `ollama--mistral-7b` - Mistral 7B
- `ollama--llama3.1-8b` - Llama 3.1 8B
- `ollama--qwen2.5-7b` / `ollama--qwen2.5-14b` - Qwen 2.5
- `ollama--deepseek-r1-7b` - DeepSeek R1 reasoning
- `ollama--phi4-14b` - Microsoft Phi-4
- `ollama--gemma3-4b` - Google Gemma 3

**Registry Models with Vision:**
- `ministral-3:8b` / `ministral-3:3b` / `ministral-3:14b` - Ministral 3 vision family
- `mistral-small3.1:24b` - Mistral Small 3.1 vision (best quality)
- `llama3.2-vision:11b` - Meta's vision model  
- `qwen2.5-vl:7b` - Qwen vision-language
- `llava:7b`, `llava:13b` - LLaVA vision models
- `llava-llama3:8b` - LLaVA with Llama 3 backbone
- `moondream:1.8b` - Lightweight vision model
- `minicpm-v:8b` - MiniCPM-V vision

**Local GGUF (Text-Only):**
- Mistral3/Ministral3 GGUF files - imported for text generation only
- No vision support for local imports (Ollama limitation)

💡 **Local GGUF Import Note:** When using Ollama Docker with local GGUF files, Ollama performs a **one-time import** to create an Ollama model from your GGUF file. This process may take a moment on first use:
```
Eclipse: [Ollama Docker] Importing GGUF file into Ollama: Mistral-7B-Instruct-v0.3-Q5_K_M.gguf
Eclipse: [Ollama Docker]   → Creating model: local_mistral_7b_instruct_v0.3
Eclipse: [Ollama Docker] Creating Ollama model from GGUF (this may take a moment)...
Eclipse: [Ollama Docker] ✓ Model local_mistral_7b_instruct_v0.3 created successfully
Eclipse: [Ollama Docker] ✓ Template created - you can now select it from the template dropdown
```
Once imported:
- Subsequent runs use the cached Ollama model directly (fast inference)
- A **template file** is auto-generated (e.g., `ollama--local--Mistral-7B-Instruct-v0.3-Q5_K_M.json`)
- Select the template from the dropdown instead of manually configuring the GGUF path

---

### llama.cpp (Docker) 🆕

**Best For:** Local GGUF files with vision support (mmproj)

**Pros:**
- ✅ Full vision support for local GGUF + mmproj files
- ✅ Auto-detects mmproj files in model folder
- ✅ Low VRAM (quantized GGUF)
- ✅ Fast inference
- ✅ OpenAI-compatible API
- ✅ GPU acceleration via CUDA

**Cons:**
- ❌ Requires Docker Desktop
- ❌ Must download both GGUF and mmproj files
- ❌ Initial container startup time

**When to Use:**
- Local GGUF files that need vision
- Want quantized models with vision capability
- Prefer Docker isolation

**Supported Families:** Mistral (with mmproj), Qwen (with mmproj), LLaVA (with mmproj), LLM (text-only)

**mmproj Auto-Detection:**
Place the mmproj file in the same folder as your GGUF model:
```
<llm_models_folder>/Ministral-3-8B-Instruct-GGUF/
  ├── Ministral-3-8B-Instruct-Q4_K_M.gguf      # Main model
  └── Ministral-3-8B-Instruct-BF16-mmproj.gguf # Vision projector (auto-detected)
```

---

## Mistral3 Compatibility Matrix

Mistral3/Ministral3 models come in different formats. Here's what works with each loading method:

### Model Formats Explained

| Format | Files | Vision | Example |
|--------|-------|--------|----------|
| **Safetensors** | `consolidated.safetensors` + `params.json` | ✅ Built-in | `Ministral-3-8B-Instruct-2512/` folder |
| **GGUF** | Single `.gguf` file | ❌ No | `Ministral-3-8B-Q4_K_M.gguf` |
| **GGUF + mmproj** | `.gguf` + `*mmproj*.gguf` | ✅ Yes | Model + projector files |
| **Ollama Registry** | Pulled from ollama.com | ✅ Built-in | `ministral-3:8b` |

### Compatibility by Loading Method

| Loading Method | Safetensors | GGUF | GGUF + mmproj | Ollama Registry | Mistral3 Support |
|----------------|-------------|------|---------------|------------------|------------------|
| **Transformers** | ✅ Vision | ❌ | ❌ | ❌ | ✅ Vision (v5 only)* |
| **GGUF (llama-cpp-python)** | ❌ | ✅ Text | ❌ | ❌ | ❌ Not yet |
| **vLLM (Docker)** | ✅ Vision | ❌ | ❌ | ❌ | ✅ Official only** |
| **vLLM (Native)** | ✅ Vision | ❌ | ❌ | ❌ | ✅ Official only** |
| **Ollama (Docker)** | ❌ | ✅ Text* | ❌ No vision** | ✅ Vision | ✅ Text only*** |
| **llama.cpp (Docker)** | ❌ | ✅ Text | ✅ Vision | ❌ | ✅ Vision |

\* Transformers v5 required for Mistral3 (breaks Florence-2 compatibility)  
\*\* vLLM requires Mistral native format (`consolidated.safetensors`), custom/fine-tuned HF-only models won't work  
\*\*\* Ollama can import local GGUF but only for text generation  
\*\*\*\* Ollama's Modelfile format doesn't support mmproj/PROJECTOR directive  
\*\*\*\*\* Ollama can load Mistral3 GGUF for text, but no vision (use llama.cpp Docker for Mistral3 vision)


## Node Overview

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `images` | IMAGE | Optional | Image(s) to analyze (required for vision models) |
| `text` | STRING | Optional | Text input (overrides `user_prompt` widget) |
| `pipe_opt` | SMARTLM_ADVANCED_PIPE | Optional | Advanced parameters from companion node |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | Original or annotated image (detection tasks show boxes) |
| `text` | STRING | Generated text/description/tags |
| `data` | JSON | Structured data (bounding boxes, labels for detection) |

### Main Parameters

#### Model Selection

| Parameter | Description |
|-----------|-------------|
| `model_family` | Mistral, Qwen, Florence, LLaVA, or LLM (Text-Only) |
| `loading_method` | Transformers, GGUF (llama-cpp-python), vLLM (Docker), vLLM (Native)*, SGLang (Docker), Ollama (Docker), llama.cpp (Docker) |
| `template_name` | Optional template for HuggingFace downloads or Ollama registry models |
| `model_source` | Local (auto-discovered) or HuggingFace |
| `model_name` | Select from discovered models |
| `repo_id` | HuggingFace repo ID (when source=HuggingFace) |
| `local_path` | Local filename after download |

*vLLM (Native) has only been tested with WSL2

#### GGUF Options (GGUF method only)

| Parameter | Description |
|-----------|-------------|
| `mmproj_source` | Local or HuggingFace for vision projector |
| `mmproj_local` | Select local mmproj file |
| `mmproj_url` | HuggingFace URL for mmproj |
| `mmproj_path` | Mmproj filename after download |

#### Transformers Options

| Parameter | Description |
|-----------|-------------|
| `quantization` | Auto, 4-bit, 8-bit, None (FP16/BF16/FP32) |
| `attention_mode` | auto, flash_attention_2, sdpa, eager |

#### Docker Options (Docker only)

| Parameter | Description |
|-----------|-------------|
| `auto_start_container` | Automatically start Docker container |
| `auto_stop_container` | Stop container after generation (frees VRAM) |

#### Task & Generation

| Parameter | Description |
|-----------|-------------|
| `task` | Task for selected family (auto-filtered, e.g., "Detailed Description") |
| `user_prompt` | Custom prompt text |
| `llm_custom_instruction` | Template for LLM custom instructions |
| `context_size` | Context window (GGUF/llama.cpp Docker, vision models only) |
| `max_tokens` | Maximum output tokens |

#### Florence Detection Options

| Parameter | Description |
|-----------|-------------|
| `detection_filter_threshold` | Remove boxes covering >X% of image |
| `nms_iou_threshold` | Merge overlapping boxes threshold |

#### Memory Management

| Parameter | Description |
|-----------|-------------|
| `memory_cleanup` | Clear VRAM before loading |
| `keep_model_loaded` | Keep model in memory after generation |
| `seed` | Random seed for reproducibility |

---

## Workflow Examples

### Example 1: Batch Image Tagging

**Goal:** Generate tags for multiple images efficiently.

```
Load Images → Smart LML v2 → Save Text
              ├── template_name: Florence-2-base-PromptGen-v2.0
              └── task: prompt_gen_tags
```

Florence-2 processes images in ~1 second each, perfect for batch workflows.

### Example 2: Video Analysis

**Goal:** Summarize video content.

```
Load Video → Video to Frames → Smart LML v2 → Display Text
                               ├── template_name: Qwen2.5-VL-7B-Instruct
                               └── task: Video Summary
```

Qwen models support multiple frames for video understanding.

### Example 3: High-Performance vLLM Pipeline

**Goal:** Maximum speed image captioning.

```
Load Image → Smart LML v2 → Text Output
             ├── template_name: Ministral-3-3B-Instruct-2512
             ├── auto_start_container: ✅
             ├── auto_stop_container: ✅
             └── task: Detailed Description
```

vLLM provides 2-3x faster inference than Transformers.

### Example 4: Low VRAM Setup

**Goal:** Run on 8GB VRAM GPU.

```
Load Image → Smart LML v2 → Text Output
             ├── template_name: (select a Qwen GGUF template or set manually)
             ├── loading_method: GGUF (llama-cpp-python)
             ├── model_name: Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf
             └── task: Detailed Description
```

GGUF Q4 models typically use 3-5GB VRAM.

### Example 5: Object Detection

**Goal:** Detect faces in image.

```
Load Image → Smart LML v2 → Preview Image (shows boxes)
             ├── template_name: Florence-2-large     ↓
             ├── task: caption_to_phrase_grounding   JSON output (coordinates)
             └── user_prompt: "face"
```

The `data` output contains bounding box coordinates.

### Example 6: Prompt Refinement Pipeline

**Goal:** Enhance simple prompts for image generation.

```
Text Input → Smart LML v2 → Enhanced Prompt → Image Generation
             ├── template_name: ollama--mistral-7b (or any LLM template)
             └── task: Refine & Expand Prompt or Expand Text
```

LLM models can refine and expand prompts without images.

---

## Docker Backend Setup

All Docker backends share common prerequisites:

### Common Prerequisites

1. **Install Docker Desktop**
   - Windows: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   - Linux: `curl -fsSL https://get.docker.com | sh`
   - macOS: [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

2. **Enable GPU Support** (required for CUDA acceleration)
   - Windows/Linux: Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
   - Verify: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`

---

### vLLM (Docker)

**Image:** `vllm/vllm-openai:latest`  
**Port:** `8000`  
**Best For:** Highest throughput, safetensors models

**Pull Image** (optional, auto-pulled on first use):
```bash
docker pull vllm/vllm-openai:latest
```

**Container Settings:**

| Setting | Description |
|---------|-------------|
| `auto_start_container` | Start container when model not loaded |
| `auto_stop_container` | Stop container after generation |

**Container Lifecycle:**
1. First run: Container starts, model loads (~30-120s depending on model)
2. Generation: Fast inference (~1-5s per image)
3. After generation: Container stops if `auto_stop_container` enabled
4. Next run: Container restarts (faster, model cached)

**Troubleshooting vLLM:**
```powershell
# Check Docker is running
docker info

# Check GPU access
docker run --gpus all nvidia/cuda:12.0-base nvidia-smi

# Check vLLM containers
docker ps -a | findstr vllm
```

---

### SGLang (Docker) 🆕

**Image:** `lmsysorg/sglang:latest`  
**Port:** `30000`  
**Container Name:** `eclipse_sglang_<model-name>`  
**Best For:** FP8 models, high-performance inference, RadixAttention

**Pull Image** (optional, auto-pulled on first use):
```bash
docker pull lmsysorg/sglang:latest
```

**How It Works:**
1. Container starts automatically when you select SGLang (Docker)
2. Model is loaded with RadixAttention for efficient KV cache reuse
3. FP8 models are auto-detected and loaded with optimal settings
4. Container stops automatically after generation if `auto_stop_container` enabled

**Container Settings:**

| Setting | Description |
|---------|-------------|
| `auto_start_container` | Start container when model not loaded |
| `auto_stop_container` | Stop container after generation (frees VRAM) |

**FP8 Model Example:**
```
loading_method: SGLang (Docker)
template_name: Qwen3-VL-2B-Instruct-FP8
auto_start_container: ✅
auto_stop_container: ✅
→ FP8 model loads, ~4GB VRAM, fast inference
```

**SGLang vs vLLM:**

| Feature | SGLang | vLLM |
|---------|--------|------|
| FP8 Support | ✅ Excellent | ✅ Good |
| RadixAttention | ✅ Yes | ❌ No |
| Startup Time | ~30-60s | ~30-60s |
| Inference Speed | Fast | Fast |
| Memory Management | Static allocation | Dynamic allocation |
| Default GPU Memory | 60% | 60% |

💡 **Note:** SGLang allocates memory statically at startup (controlled by `gpu_memory_utilization` in docker_config.json). vLLM uses more dynamic allocation. Both default to 60% to leave room for other applications.

**Troubleshooting SGLang:**
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

---

### Ollama (Docker) 🆕

**Image:** `ollama/ollama:latest`  
**Port:** `11434`  
**Container Name:** `eclipse-ollama`  
**Best For:** Easy setup, Ollama registry models

**Pull Image** (optional, auto-pulled on first use):
```bash
docker pull ollama/ollama:latest
```

**How It Works:**
1. Container starts automatically when you select Ollama (Docker)
2. For registry models (e.g., `pixtral`): Ollama pulls the model automatically
3. For local GGUF: Creates a Modelfile and imports the model

💡 **Easiest Method: Use Preset Templates!**

Select a pre-configured template from the `template_name` dropdown:

| Template | Model | Type | Size |
|----------|-------|------|------|
| `ollama--ministral-3-8b` | Ministral 3 8B | Vision | ~6GB |
| `ollama--ministral-3-3b` | Ministral 3 3B | Vision | ~3GB |
| `ollama--mistral-small3.1-24b` | Mistral Small 3.1 | Vision | ~15GB |
| `ollama--llama3.2-vision-11b` | Llama 3.2 Vision | Vision | ~7GB |
| `ollama--qwen2.5-vl-7b` | Qwen2.5-VL | Vision | ~5GB |
| `ollama--mistral-7b` | Mistral 7B | Text | ~4GB |
| `ollama--llama3.1-8b` | Llama 3.1 8B | Text | ~5GB |
| `ollama--qwen2.5-7b` | Qwen 2.5 7B | Text | ~5GB |
| `ollama--deepseek-r1-7b` | DeepSeek R1 | Reasoning | ~5GB |
| `ollama--phi4-14b` | Phi-4 14B | Text | ~9GB |

Just select a template and run - the model downloads automatically!

**Manual Registry Models:**
```
model_name: ministral-3:8b      # Vision model (recommended), auto-pulled
model_name: ministral-3:3b      # Vision model (smaller), auto-pulled
model_name: mistral-small3.1:24b # Vision model (best quality), auto-pulled
model_name: llama3.2-vision:11b # Vision model, auto-pulled  
model_name: llama3.1:8b         # Text-only, auto-pulled
model_name: qwen2.5:7b          # Text-only, auto-pulled
```

**Local GGUF Import:**
```
model_name: path/to/model.gguf  # Imported as "eclipse-{filename}"
```

⚠️ **Note:** Local GGUF imports do NOT support vision (Ollama limitation). Use llama.cpp (Docker) for local GGUF + vision.

**Troubleshooting Ollama:**
```powershell
# Check container status
docker ps -a | findstr eclipse-ollama

# View container logs
docker logs eclipse-ollama

# List imported models
docker exec eclipse-ollama ollama list
```

---

### llama.cpp (Docker) 🆕

**Image:** `ghcr.io/ggml-org/llama.cpp:server-cuda`  
**Port:** `8080`  
**Container Name:** `eclipse-llamacpp`  
**Best For:** Local GGUF files with vision (mmproj)

**Pull Image** (optional, auto-pulled on first use):
```bash
docker pull ghcr.io/ggml-org/llama.cpp:server-cuda
```

**How It Works:**
1. Point to your GGUF file in your LLM models folder
2. If mmproj file exists in same folder, it's auto-detected
3. Container starts with model and mmproj loaded
4. Vision works immediately!

**mmproj Auto-Detection Patterns:**
- `mmproj*.gguf`
- `*-mmproj.gguf`
- `*_mmproj.gguf`
- `*projector*.gguf`
- `*-clip-*.gguf`

**Example Folder Structure:**
```
<llm_models_folder>/Ministral-3-8B-Instruct-GGUF/
  ├── Ministral-3-8B-Instruct-Q4_K_M.gguf        # Main model (required)
  └── Ministral-3-8B-Instruct-BF16-mmproj.gguf   # Vision projector (auto-detected)
```

> 💡 Your LLM models folder is configured in `eclipse_config.json` (`llm_models_path` and `llm_models_absolute_path`)

**Usage:**
```
loading_method: llama.cpp (Docker)
model_name: Ministral-3-8B-Instruct-GGUF/Ministral-3-8B-Instruct-Q4_K_M.gguf
→ mmproj auto-detected, vision enabled
```

**Troubleshooting llama.cpp:**
```powershell
# Check container status
docker ps -a | findstr eclipse-llamacpp

# View container logs
docker logs eclipse-llamacpp

# Test API
curl http://localhost:8080/props
# Should show "vision": true if mmproj loaded
```

---

### Port Summary

| Backend | Default Port | Container Name |
|---------|--------------|----------------|
| vLLM | 8000 | eclipse-vllm-* |
| SGLang | 30000 | eclipse_sglang_* |
| Ollama | 11434 | eclipse-ollama |
| llama.cpp | 8080 | eclipse-llamacpp-* |

---

## FP8 Models

### What is FP8?

FP8 (8-bit floating point) is a quantization format that reduces model size to ~50% of FP16 while maintaining near-full quality. FP8 models are pre-quantized and optimized for inference.

### FP8 Compatibility

| Backend | FP8 Support | Notes |
|---------|-------------|-------|
| **Transformers** | ❌ NO | Crashes with "Cannot copy out of meta tensor" error |
| **vLLM (Docker)** | ✅ YES | Full support, recommended |
| **vLLM (Native)** | ✅ YES | Full support |
| **SGLang (Docker)** | ✅ YES | Full support, recommended |
| **GGUF** | ❌ NO | Use Q4/Q8 GGUF instead |
| **Ollama** | ❌ NO | Use registry models instead |
| **llama.cpp** | ❌ NO | Use Q4/Q8 GGUF instead |

### Available FP8 Models

| Model | Size | VRAM | Description |
|-------|------|------|-------------|
| Qwen3-VL-2B-Instruct-FP8 | 2B | ~4 GB | Fastest, good quality |
| Qwen3-VL-4B-Instruct-FP8 | 4B | ~6 GB | Good balance |
| Qwen3-VL-8B-Instruct-FP8 | 8B | ~10 GB | High quality |
| Qwen3-VL-32B-Instruct-FP8 | 32B | ~36 GB | Best quality |
| Qwen3-VL-*-Thinking-FP8 | Various | Various | Reasoning variants |

### Using FP8 Models

1. Download an FP8 model (e.g., `Qwen3-VL-2B-Instruct-FP8`) to your LLM models folder
2. Select template: `Qwen3-VL-2B-Instruct-FP8` (or similar)
3. Loading method will auto-set to **vLLM (Docker)** or **SGLang (Docker)**
4. Enable `auto_start_container` and run!

⚠️ **Important:** Do NOT use Transformers with FP8 models - it will crash with a meta tensor error. The node will show an error message if you try.

### FP8 vs Other Quantization

| Format | Quality | Speed | VRAM | Supported By |
|--------|---------|-------|------|---------------|
| FP16 | 100% | Baseline | High | All |
| FP8 | ~99% | Faster | ~50% | vLLM, SGLang |
| INT8 | ~98% | Similar | ~50% | Transformers |
| INT4 | ~95% | Similar | ~25% | Transformers |
| GGUF Q8 | ~98% | Medium | ~50% | llama.cpp, GGUF |
| GGUF Q4 | ~93% | Medium | ~25% | llama.cpp, GGUF |

---

## Troubleshooting

### Common Issues

**"No local model selected"**
- Ensure models are in your LLM models folder (check `eclipse_config.json` → `llm_models_path`)
- Check model name matches selected family
- Try refreshing the node (right-click → Refresh)

**"CUDA out of memory"**
- Reduce `context_size` for GGUF/vLLM
- Use lower quantization (4-bit)
- Enable `memory_cleanup`
- Disable `keep_model_loaded`

**"Florence-2 is incompatible"**
- Florence requires transformers v4.x
- Run: `pip install transformers==4.57.3`
- Or use Qwen/Mistral for vision tasks

**"Docker container exits immediately"**
- Check GPU access: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
- Check model compatibility with vLLM
- Review container logs: `docker logs <container_id>`

**"vLLM fails for Mistral3/Pixtral"**
- Ensure model has `consolidated.safetensors` (Mistral format)
- Node auto-detects and uses `--load-format mistral`
- `--enforce-eager` is auto-applied to prevent CUDA graph crashes

**"Ollama vision not working with local GGUF"**
- Ollama doesn't support mmproj for local GGUF imports
- Use `llama.cpp (Docker)` instead for local GGUF + vision
- Or use Ollama registry models (e.g., `ministral-3:8b`)

**"llama.cpp Docker vision not working"**
- Ensure mmproj file is in same folder as GGUF model
- Check mmproj filename matches patterns: `*mmproj*.gguf`, `*projector*.gguf`
- Verify with: `curl http://localhost:8080/props` (should show `"vision": true`)
- Check container logs: `docker logs eclipse-llamacpp`

**"Model not found in dropdown"**
- Place models in your LLM models folder (check `eclipse_config.json` → `llm_models_path`)
- Folder name should indicate family (e.g., `Ministral-*`, `Qwen-*`)
- GGUF files should end in `.gguf`
- For Ollama registry: use exact model name (e.g., `ministral-3:8b`)

**"Cannot copy out of meta tensor" (FP8 models)**
- Transformers v4.x does NOT support FP8 models
- Switch to **vLLM (Docker)** or **SGLang (Docker)**
- These backends have full FP8 support
- Pre-configured FP8 templates auto-select the correct backend

**"SGLang container not starting"**
- Check Docker is running: `docker info`
- Check GPU access: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
- Check container logs: `docker logs eclipse_sglang_<model-name>`
- Ensure sufficient VRAM for the model

### Log Messages

Enable debug logging in `eclipse_config.json`:
```json
{
  "log_level": "debug"
}
```

Key log prefixes:
- `SmartLM`: Main node operations
- `vLLM Docker`: vLLM container management
- `SGLang Docker`: SGLang container management
- `Ollama Docker`: Ollama container management
- `llama.cpp Docker`: llama.cpp container management
- `Transformers`: Model loading
- `GGUF`: llama.cpp native operations

---

*For HuggingFace repository URLs, see [Model_Repos_Reference.md](Model_Repos_Reference.md)*

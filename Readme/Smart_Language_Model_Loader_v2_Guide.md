# Smart Language Model Loader v2 Guide

**Template-First Workflow with Multi-Backend Support**

The Smart Language Model Loader v2 (Smart LML v2) provides a streamlined, template-first approach to loading and running vision-language and text-only models in ComfyUI. This new version supports six distinct backends: **Transformers**, **GGUF (llama-cpp-python)**, **vLLM (Docker)**, **vLLM (Native)**, **Ollama (Docker)**, and **llama.cpp (Docker)** - giving you flexibility to choose the best balance of quality, speed, and VRAM usage for your workflow.

## What's New in v2?

### Key Improvements Over v1

| Feature | v1 | v2 |
|---------|----|----|
| **Workflow** | Template-first (select template, then run) | Template-first with multi-backend support |
| **Model Discovery** | Manual template creation | Auto-discovery from `models/LLM/` folder |
| **vLLM Support** | Not available | Full Docker and Native vLLM support |
| **Ollama Support** | Not available | Ollama Docker with registry models |
| **llama.cpp Docker** | Not available | Local GGUF with vision (mmproj) support |
| **Backend Selection** | Auto-detected from template | Explicit loading method dropdown |
| **Model Families** | QwenVL, Florence, LLM | Mistral, Qwen, Florence, LLaVA, LLM (Text-Only) |
| **Task Organization** | Per-family widgets | Unified task dropdown with family prefixes |
| **Docker Integration** | None | Auto-start/stop containers, VRAM management |

### New Features

- **🚀 vLLM Backend**: High-performance inference via Docker or native Linux installation
- **🦙 Ollama Docker**: Easy model management with Ollama registry (vision via registry models)
- **⚡ llama.cpp Docker**: Local GGUF files with vision support via mmproj auto-detection
- **🦙 LLaVA Family**: Support for generic vision models from Ollama registry (LLaVA, Moondream, etc.)
- **🔍 Auto-Discovery**: Models in `models/LLM/` automatically appear in dropdown
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
- [Performance & VRAM](#performance--vram)
- [Troubleshooting](#troubleshooting)
- [Migration from v1](#migration-from-v1)

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
   - `template_name`: Select a vLLM template (e.g., `vllm--Ministral-3-3B-Instruct-2512`)
   - `auto_start_container`: ✅ (enabled)
   - `auto_stop_container`: ✅ (enabled)
   - `task`: **Detailed Description**
4. Run workflow

The Docker container starts automatically, serves the model, and stops after generation to free VRAM.

### Local GGUF with Vision (llama.cpp Docker)

**Goal:** Run local GGUF files with vision support (mmproj).

**Requirements:** Docker Desktop, GGUF model + mmproj file in same folder

**Steps:**
1. Download GGUF model (e.g., `Ministral-3-8B-Instruct-Q4_K_M.gguf`)
2. Download matching mmproj file (e.g., `Ministral-3-8B-Instruct-BF16-mmproj.gguf`)
3. Place both in `ComfyUI/models/LLM/Ministral-3-8B-Instruct-GGUF/`
4. Add **Smart Language Model Loader v2 [Eclipse]** node
5. Connect image to `images` input
6. Configure:
   - `template_name`: Select a llama.cpp template or set manually:
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

Models placed in `ComfyUI/models/LLM/` are automatically discovered and appear in the `model_name` dropdown. The node detects:

- **Model Family**: From folder/file naming (e.g., `Mistral-*`, `Qwen-*`, `Florence-*`)
- **Format**: GGUF files vs. folders with safetensors
- **Compatibility**: Filters models based on selected family and method

### Pre-configured Templates

For Ollama Docker, pre-configured templates are available in the `template_name` dropdown. These templates point to Ollama registry models that auto-pull on first use:

- **Mistral/Qwen templates**: `ollama--ministral-3-8b`, `ollama--qwen2.5-vl-7b`, etc.
- **LLaVA templates**: `ollama--llava-7b`, `ollama--llava-llama3-8b`, `ollama--moondream-1.8b`, etc.
- **Text-only templates**: `ollama--mistral-7b`, `ollama--llama3.1-8b`, `ollama--deepseek-r1-7b`, etc.

💡 **Tip:** When using Ollama Docker with `model_source: Local`, select a template from the `template_name` dropdown. The template contains the Ollama registry model name (e.g., `llava-llama3:8b`) which will be auto-pulled.

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

**Models:**
| Model | Size | VRAM | Best For |
|-------|------|------|----------|
| Florence-2-base | 230M | 0.5 GB | General captions |
| Florence-2-base-PromptGen-v2.0 | 230M | 1.2 GB | SD/Flux tags |
| Florence-2-large-PromptGen-v2.0 | 770M | 3.7 GB | High-quality tags |

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
| **vLLM (Docker)** | Win/Linux | Safetensors | ✅ | High | Fast | Medium |
| **vLLM (Native)** | Linux | Safetensors | ✅ | High | Fastest | Hard |
| **Ollama (Docker)** | All | Registry/GGUF | ✅* | Medium | Fast | Easy |
| **llama.cpp (Docker)** | All | GGUF + mmproj | ✅ | Low | Fast | Easy |

*Ollama vision only works with registry models (e.g., `ministral-3:8b`, `llava:7b`), not local GGUF imports.

### Family Support by Loading Method

| Family | Transformers | GGUF | vLLM Docker | vLLM Native | Ollama Docker | llama.cpp Docker |
|--------|--------------|------|-------------|-------------|---------------|------------------|
| **Mistral** | ✅ Vision | ❌ | ✅ Vision | ✅ Vision | ✅ Registry | ✅ mmproj |
| **Qwen** | ✅ Vision | ✅ Vision | ✅ Vision | ✅ Vision | ✅ Registry | ✅ mmproj |
| **Florence** | ✅ Vision | ❌ | ❌ | ❌ | ❌ | ❌ |
| **LLaVA** | ❌ | ✅ Vision | ❌ | ❌ | ✅ Vision | ✅ mmproj |
| **LLM (Text)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

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

**Cons:**
- ❌ Must manually download GGUF files
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
models/LLM/Ministral-3-8B-Instruct-GGUF/
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

### Recommended Setup by Use Case

| Use Case | Recommended Method | Model Format | Notes |
|----------|-------------------|--------------|-------|
| **Mistral3 vision (recommended)** | llama.cpp (Docker) | GGUF + mmproj | Low VRAM, no version conflicts |
| **Mistral3 vision (fastest)** | vLLM (Docker) | Native safetensors | Official models only, high VRAM |
| **Mistral3 vision (no Docker)** | Transformers (v5) | HuggingFace repo | Breaks Florence-2! |
| **Mistral3 text-only** | Ollama (Docker) | Local GGUF | Easy import, no vision |
| **Florence-2** | Transformers (v4) | HuggingFace repo | Keep v4.x for Florence |
| **Qwen vision (fast load)** | Transformers | HuggingFace repo | Faster loading, works with v4 |
| **Qwen vision (low VRAM)** | GGUF (llama-cpp-python) | GGUF + mmproj | Lower VRAM, slower Docker startup |
| **Text-only, low VRAM** | GGUF (llama-cpp-python) | GGUF | Lowest VRAM, Qwen/LLM only |
| **Text-only, fastest** | vLLM (Docker) | Safetensors | Continuous batching |

### Example: Ministral-3-8B Vision Setup

**Option 1: Ollama (Text-Only, Easiest for local GGUF)**
```
loading_method: Ollama (Docker)
model_name: path/to/Ministral-3-8B-Q4_K_M.gguf
→ Imports GGUF, text generation only (no vision)
```

**Option 2: llama.cpp Docker (Low VRAM)**
```
loading_method: llama.cpp (Docker)
model_name: Ministral-3-8B-Instruct-GGUF/Ministral-3-8B-Instruct-Q4_K_M.gguf

Folder structure:
models/LLM/Ministral-3-8B-Instruct-GGUF/
  ├── Ministral-3-8B-Instruct-Q4_K_M.gguf        # ~5GB
  └── Ministral-3-8B-Instruct-BF16-mmproj.gguf  # ~860MB (auto-detected)
→ Vision works with ~6GB VRAM
```

**Option 3: vLLM Docker (Fastest, Official Models Only)**
```
loading_method: vLLM (Docker)
model_name: Ministral-3-8B-Instruct-2512/

Folder structure (must have native Mistral format):
models/LLM/Ministral-3-8B-Instruct-2512/
  ├── consolidated.safetensors   # Native format (required)
  ├── params.json                # Native format (required)
  └── tekken.json
→ Vision works, ~12GB VRAM, fastest inference
⚠️ Only works with official mistralai/ models!
⚠️ Custom/fine-tuned models with HF format won't work
```

**Option 4: Transformers (No Docker, requires v5)**
```
loading_method: Transformers
model_source: HuggingFace
repo_id: mistralai/Ministral-3-8B-Instruct-2512
→ Auto-downloads, vision works, ~12GB VRAM (or less with 4-bit)
⚠️ Requires: pip install transformers>=5.0.0
⚠️ WARNING: This breaks Florence-2 compatibility!
```

---

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
| `loading_method` | Transformers, GGUF (llama-cpp-python), vLLM (Docker), vLLM (Native)*, Ollama (Docker), llama.cpp (Docker) |
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

#### vLLM Options (Docker only)

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
             ├── template_name: vllm--Ministral-3-3B-Instruct-2512
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
             └── task: Refine & Expand Prompt
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
1. Point to your GGUF file in `models/LLM/`
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
models/LLM/Ministral-3-8B-Instruct-GGUF/
  ├── Ministral-3-8B-Instruct-Q4_K_M.gguf        # Main model (required)
  └── Ministral-3-8B-Instruct-BF16-mmproj.gguf   # Vision projector (auto-detected)
```

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
| Ollama | 11434 | eclipse-ollama |
| llama.cpp | 8080 | eclipse-llamacpp |

---

## Performance & VRAM

### VRAM Requirements by Method

| Method | Overhead | Model VRAM | Total | Vision | Mistral3 |
|--------|----------|------------|-------|--------|----------|
| Transformers (FP16) | ~1 GB | Full size | High | ✅ | ✅ (v5)* |
| Transformers (8-bit) | ~1 GB | ~50% size | Medium | ✅ | ✅ (v5)* |
| Transformers (4-bit) | ~1 GB | ~25% size | Low | ✅ | ✅ (v5)* |
| GGUF Q4 (llama-cpp-python) | ~0.5 GB | ~25% size | Lowest | Qwen only | ❌ |
| GGUF Q8 (llama-cpp-python) | ~0.5 GB | ~50% size | Low | Qwen only | ❌ |
| vLLM (Docker) | ~2 GB | Full size | High | ✅ | ✅ Official* |
| vLLM (Native) | ~2 GB | Full size | High | ✅ | ✅ Official* |
| Ollama (Docker) | ~1 GB | Varies | Medium | Registry only | ✅ Text only* |
| llama.cpp (Docker) | ~0.5 GB | ~25-50% | Low | ✅ (with mmproj) | ✅ |

### Speed Comparison

| Method | Tokens/sec (8B model) | First Load | Vision | Mistral3 |
|--------|----------------------|------------|--------|----------|
| Transformers | 30-50 | Fast | ✅ | ✅ (v5 only)* |
| GGUF (llama-cpp-python) | 20-40 | Fast | Qwen only | ❌ |
| vLLM (Docker) | 60-100 | Slow (~60s) | ✅ | ✅ Official* |
| vLLM (Native) | 80-120 | Fast | ✅ | ✅ Official* |
| Ollama (Docker) | 40-60 | Medium (~30s) | Registry only | ✅ Text only* |
| llama.cpp (Docker) | 30-50 | Medium (~20s) | ✅ (with mmproj) | ✅ |

\* Transformers v5 required for Mistral3 (breaks Florence-2 which needs v4.46.3)  
\*\* Ollama can load Mistral3 GGUF but only for text generation (no mmproj/vision support)

### Recommended Configurations

**6-8GB VRAM:**
- Florence-2 (any) + Transformers (v4)
- Qwen 3B GGUF Q4 (llama-cpp-python)
- Ministral3 8B Q4_K_M + llama.cpp (Docker) ✅ Vision
- Ollama + Mistral3 GGUF (text-only)

**12GB VRAM:**
- Qwen 7B with 8-bit quantization
- Official Mistral3 8B with vLLM (Docker) ✅ Vision
- Ministral3 8B + Transformers v5 (4-bit) ✅ Vision (breaks Florence!)
- Any Florence-2 model (keep Transformers v4)
- Custom Mistral3 models: use llama.cpp Docker

**16GB+ VRAM:**
- Qwen 7B FP16
- Mistral3 8B FP8 with vLLM (Docker) ✅ Vision
- Multiple models with `keep_model_loaded: false`

**24GB+ VRAM:**
- Qwen 32B with 4-bit
- Full-size models with vLLM (Docker)
- Mistral3 full precision
- Keep models loaded for speed

---

## Troubleshooting

### Common Issues

**"No local model selected"**
- Ensure models are in `ComfyUI/models/LLM/`
- Check model name matches selected family
- Try refreshing the node (right-click → Refresh)

**"CUDA out of memory"**
- Reduce `context_size` for GGUF/vLLM
- Use lower quantization (4-bit)
- Enable `memory_cleanup`
- Disable `keep_model_loaded`

**"Florence-2 is incompatible"**
- Florence requires transformers v4.x
- Run: `pip install transformers==4.46.3`
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
- Place models in `ComfyUI/models/LLM/`
- Folder name should indicate family (e.g., `Ministral-*`, `Qwen-*`)
- GGUF files should end in `.gguf`
- For Ollama registry: use exact model name (e.g., `ministral-3:8b`)

### Log Messages

Enable debug logging in `config/log_config.json`:
```json
{
  "log_level": "debug"
}
```

Key log prefixes:
- `SmartLM v2`: Main node operations
- `vLLM Docker`: vLLM container management
- `Ollama Docker`: Ollama container management
- `llama.cpp Docker`: llama.cpp container management
- `Transformers`: Model loading
- `GGUF`: llama.cpp native operations

---

## Migration from v1

### Key Differences

| Aspect | v1 | v2 |
|--------|----|----|
| Node name | Smart Language Model Loader | Smart Language Model Loader v2 |
| First step | Select template | Select template (same, but more templates!) |
| Loading methods | Transformers, GGUF | 6 methods (+ vLLM, Ollama, llama.cpp Docker) |
| Model discovery | Manual templates only | Auto-discovery + templates |
| Task widgets | Per-family (qwen_preset_prompt, etc.) | Unified `task` dropdown |
| Mistral | Limited support | Full Mistral3/Pixtral support |
| Docker backends | None | vLLM, Ollama, llama.cpp |
| Local GGUF + Vision | Not supported | ✅ via llama.cpp (Docker) |

### Migrating Workflows

1. **Replace Node**: Delete v1 node, add v2 node
2. **Select Template**: Choose matching template from `template_name` dropdown
3. **Set Task**: Find equivalent in unified dropdown
4. **(Optional) Override Settings**: Adjust model_source, model_name if needed

### Template Compatibility

v1 templates work in v2 - select from `template_name` dropdown:
- Template auto-configures: model_family, loading_method, repo_id, quantization
- Just select template and task, then run!

### Feature Mapping

| v1 Feature | v2 Equivalent |
|------------|---------------|
| `qwen_preset_prompt` | `task` (filtered when Qwen selected) |
| `florence_task` | `task` (filtered when Florence selected) |
| `llm_instruction_mode` | `task` (filtered when LLM selected) |
| `qwen_custom_prompt` | `user_prompt` |
| `florence_text_input` | `user_prompt` |
| `llm_prompt` | `text` input or `user_prompt` |

---

## Tips & Best Practices

### Performance Tips

1. **Use vLLM for batch processing** - 2-3x faster than Transformers
2. **Enable `auto_stop_container`** - Frees VRAM between batches
3. **Use Florence-2 for quick tagging** - <1 second per image
4. **Match context_size to needs** - Larger = more VRAM

### Quality Tips

1. **Mistral for vision quality** - Excellent image understanding
2. **Qwen for video** - Only family with multi-frame support
3. **Higher temperature** - More creative descriptions (0.8-1.0)
4. **Lower temperature** - More factual/consistent (0.3-0.5)

### VRAM Management

1. **One model at a time** - Unload before loading another
2. **Use `memory_cleanup: true`** - Clears cache before loading
3. **4-bit for large models** - Mistral-7B fits in 8GB with 4-bit
4. **GGUF for lowest VRAM** - Q4_K_M typically uses 25% of FP16

### Workflow Organization

1. **Name models clearly** - Family + size in folder name
2. **Use templates for HuggingFace** - Auto-download management
3. **Local for speed** - No download checks on each run
4. **Separate workflows** - Different model families in different workflows

---

## Appendix: Supported Model Architectures

### vLLM Compatible

| Architecture | Family | Notes |
|--------------|--------|-------|
| Mistral3ForConditionalGeneration | Mistral | Vision, auto-format detection |
| Pixtral | Mistral | Vision, needs `--load-format mistral` |
| LlamaForCausalLM | LLM | Text-only |
| MistralForCausalLM | LLM | Text-only |
| Qwen2ForCausalLM | LLM | Text-only |

### Transformers Compatible

| Architecture | Family | Notes |
|--------------|--------|-------|
| Qwen2VLForConditionalGeneration | Qwen | Vision, video support |
| Florence2ForConditionalGeneration | Florence | Vision, detection |
| AutoModelForCausalLM | LLM | Text-only, any HF model |

### GGUF Compatible

| Format | Family | Notes |
|--------|--------|-------|
| Qwen2-VL GGUF | Qwen | Requires mmproj file |
| LLaVA GGUF | LLaVA | Requires mmproj file |
| LLaMA GGUF | LLM | Text-only |
| Mistral GGUF | LLM | Text-only |

---

*For HuggingFace repository URLs, see [Model_Repos_Reference.md](Model_Repos_Reference.md)*

# Save Prompt

Save text, prompts, or captions to files in txt, csv, or json format. Perfect for batch captioning workflows with automatic filename matching.

## Overview

The **Save Prompt** node saves text content to files with flexible naming and output options. Designed for:

- **Batch Captioning**: Save captions alongside source images
- **Training Data Preparation**: Export prompts in various formats
- **Prompt Logging**: Keep records of generated prompts
- **Dataset Annotation**: Create tag files for training

## Features

- 📝 **Multiple formats**: TXT, CSV, JSON
- 📂 **Source folder integration**: Save alongside source images
- 🏷️ **Placeholder system**: Dynamic filenames with `%source_name`, `%date`, etc.
- 🔢 **Auto-numbering**: Sequential file naming with padding
- ➕ **Append mode**: Add to existing files
- 🔞 **NSFW detection**: Auto-detect and tag content levels (JSON)

---

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | STRING | (required) | The text/prompt to save. Connected from upstream node. |
| `output_path` | STRING | "" | Output folder. Empty + `use_source_folder` = save with source. Supports placeholders. |
| `use_source_folder` | BOOLEAN | False | Save in same folder as source image (from pipe). |
| `filename_prefix` | STRING | "%source_name" | Filename prefix. Supports placeholders like `%source_name`. |
| `filename_delimiter` | STRING | "_" | Delimiter between prefix and counter (new mode only). |
| `filename_number_padding` | INT | 4 | Counter digits (e.g., 4 = 0001). Only used in 'new' mode. |
| `extension` | COMBO | "txt" | File format: `txt`, `csv`, `json` |
| `write_mode` | COMBO | "overwrite" | `new`: numbered files, `overwrite`: replace each time, `append`: add to file |
| `nsfw_level` | COMBO | "disabled" | NSFW tagging for JSON: `disabled`, `auto`, `None`, `Mature`, `X` |
| `pipe_opt` | PIPE | (optional) | Pipe from Load Image From Folder for source filename placeholders. |

---

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `text` | STRING | The original input text (passthrough for chaining) |

---

## Write Modes

### New Mode (`new`)

Creates numbered files with auto-incrementing counter:
```
my_prompt_0001.txt
my_prompt_0002.txt
my_prompt_0003.txt
```

- Scans folder for existing files to continue numbering
- Uses `filename_delimiter` between prefix and counter
- Uses `filename_number_padding` for counter width

### Overwrite Mode (`overwrite`)

Single file, replaced each execution:
```
my_prompt.txt  (always same file)
```

- No counter in filename
- Each run overwrites previous content
- Good for "latest prompt" workflows

### Append Mode (`append`)

Single file, content added each execution:
```
my_prompt.txt  (grows with each run)
```

- No counter in filename
- Each run adds to the file
- TXT: New line between entries
- CSV: New row per entry
- JSON: Added to array/dict

---

## File Formats

### TXT Format

Plain text, one prompt per file (new/overwrite) or multiple lines (append):

```
a beautiful landscape, mountains, sunset, golden hour
```

**Append behavior**: Each entry on a new line.

### CSV Format

Comma-separated values with header:

```csv
prompt
"a beautiful landscape, mountains, sunset, golden hour"
"portrait of a woman, professional lighting"
```

**Features**:
- Automatic header row: `prompt`
- Proper CSV escaping for commas and quotes
- Each entry is a new row

### JSON Format

Structured data, two formats depending on `nsfw_level`:

**Without NSFW (nsfw_level = disabled)**:
```json
{
  "prompts": [
    "a beautiful landscape, mountains, sunset",
    "portrait of a woman, professional lighting"
  ]
}
```

**With NSFW (nsfw_level ≠ disabled)**:
```json
{
  "photo_001.png": {
    "prompt": "a beautiful landscape, mountains, sunset",
    "nsfwLevel": "None"
  },
  "photo_002.png": {
    "prompt": "portrait of a woman, professional lighting",
    "nsfwLevel": "Mature"
  }
}
```

Uses source filename as key for easy dataset management.

---

## Placeholder System

### Available Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `%source_name` | Source filename without extension | `photo_001` |
| `%source_filename` | Full source filename | `photo_001.png` |
| `%date` / `%today` | Current date (YYYY-MM-DD) | `2025-12-24` |
| `%time` | Current time (HHMMSS) | `143052` |
| `%Y` | Year (4 digits) | `2025` |
| `%m` / `%M` | Month (2 digits) | `12` |
| `%d` / `%D` | Day (2 digits) | `24` |
| `%H` | Hour (2 digits) | `14` |
| `%S` | Second (2 digits) | `52` |
| `%counter` | Execution counter | `1`, `2`, `3`... |
| `%source_folder` | Immediate parent folder name | `portraits` |
| `%source_base_folder` | Root folder from input list | `portraits` |

### Folder Placeholders Explained

When processing `D:/datasets/portraits/subfolder/img.png` from input folder `D:/datasets/portraits`:

| Placeholder | Value | Use Case |
|-------------|-------|----------|
| `%source_folder` | `subfolder` | Immediate parent of the file |
| `%source_base_folder` | `portraits` | The folder from the input list |

This is useful for multi-folder workflows:
```
filename_prefix: %source_base_folder_%source_name
```
Result: `portraits_img.txt`, `landscapes_photo.txt`

### Placeholder Usage

**In filename_prefix**:
```
%source_name          → photo_001.txt
%date_%source_name    → 2025-12-24_photo_001.txt
caption_%counter      → caption_1.txt, caption_2.txt, ...
%source_base_folder_%source_name → portraits_photo_001.txt
```

**In output_path**:
```
%date/captions        → 2025-12-24/captions/
tagged/%model         → tagged/sd_xl_base/
%source_base_folder   → portraits/ (organize by source folder)
```

---

## Source Folder Integration

The most powerful feature for batch captioning workflows.

### How It Works

When `use_source_folder` is enabled:

1. Node reads `filepath` from `pipe_opt` (from Load Image From Folder)
2. Extracts the folder containing the source image
3. Saves output in that folder (or relative to it)

### Examples

**Source**: `D:/datasets/images/photo_001.png`

| output_path | Result |
|-------------|--------|
| (empty) | `D:/datasets/images/photo_001.txt` |
| `captions` | `D:/datasets/captions/photo_001.txt` |
| `../captions` | `D:/datasets/captions/photo_001.txt` |
| `./captions` | Auto-corrected to `../captions` |

### Typical Batch Captioning Setup

```
Load Image From Folder
    ↓ (image)
Vision Model (generates caption)
    ↓ (text)
Save Prompt
    ├─ use_source_folder: True
    ├─ filename_prefix: %source_name
    ├─ write_mode: overwrite
    └─ pipe_opt: connected from Load Image From Folder
```

Result: Each image gets a matching `.txt` file in the same folder.

---

## NSFW Detection (JSON Only)

Automatic content level detection for dataset annotation.

### Detection Levels

| Level | Keywords Detected |
|-------|------------------|
| **X** | sex, nude, nsfw, porn, hentai, explicit, penetration, genitals, etc. |
| **Mature** | sexy, seductive, lingerie, bikini, cleavage, suggestive, etc. |
| **None** | No NSFW keywords detected |

### Settings

| nsfw_level | Behavior |
|------------|----------|
| `disabled` | No NSFW tagging, simple array format |
| `auto` | Automatically detect from prompt text |
| `None` | Force "None" level for all entries |
| `Mature` | Force "Mature" level for all entries |
| `X` | Force "X" level for all entries |

### Output Format

With `nsfw_level` enabled, JSON uses filename-keyed format:
```json
{
  "image_001.png": {
    "prompt": "...",
    "nsfwLevel": "None"
  }
}
```

---

## Usage Examples

### Basic Prompt Saving

Save prompts with date prefix:
```
output_path: prompts
filename_prefix: %date_prompt
write_mode: new
extension: txt
```
Result: `prompts/2025-12-24_prompt_0001.txt`

### Batch Captioning

Save captions alongside source images:
```
use_source_folder: True
filename_prefix: %source_name
write_mode: overwrite
extension: txt
pipe_opt: connected from Load Image From Folder
```
Source: `images/cat_photo.png` → Output: `images/cat_photo.txt`

### Training Dataset (CSV)

Collect all prompts in a single CSV:
```
output_path: datasets
filename_prefix: training_prompts
write_mode: append
extension: csv
```
Result: `datasets/training_prompts.csv` with all prompts as rows

### Civitai-Style JSON

Create JSON with NSFW ratings:
```
output_path: metadata
filename_prefix: dataset
write_mode: append
extension: json
nsfw_level: auto
pipe_opt: connected
```
Result: `metadata/dataset.json` with filenames as keys and NSFW levels

### Separate Folders by Date

Organize captions by date:
```
output_path: %Y/%m/%d
filename_prefix: caption_%counter
write_mode: new
extension: txt
```
Result: `2025/12/24/caption_0001.txt`

---

## Path Handling

### Absolute Paths

Full paths are used directly (allows saving outside ComfyUI):
```
output_path: D:/my_datasets/captions
```

### Relative Paths (Without Source Folder)

Resolved inside ComfyUI's output directory:
```
output_path: captions/daily
→ ComfyUI/output/captions/daily/
```

### Relative Paths (With Source Folder)

Resolved relative to source image folder:
```
use_source_folder: True
output_path: captions
source: D:/images/photo.png
→ D:/images/captions/
```

### Auto-Correction

Single dot paths are auto-corrected to go up one level:
```
output_path: .\captions  →  ..\captions
output_path: ./captions  →  ../captions
```

This matches the common expectation that `.\folder` means "outside the current folder".

---

## Text Processing

The node automatically cleans input text:

1. **Removes line breaks**: `\r\n`, `\r`, `\n` → space
2. **Collapses spaces**: Multiple spaces → single space
3. **Trims whitespace**: Leading/trailing spaces removed

This ensures captions are single-line for compatibility with training tools.

---

## Pipe Integration

### From Load Image From Folder

```
Load Image From Folder (pipe) → Save Prompt (pipe_opt)
```

Enables:
- `%source_name` - filename without extension
- `%source_filename` - full filename
- `%source_folder` - immediate parent folder name
- `%source_base_folder` - root folder from input list

---

## Troubleshooting

### File Not Saving

1. Check `output_path` is valid/writable
2. Verify folder exists (node creates it if needed)
3. Check for permission issues

### Wrong Filename

1. Verify `filename_prefix` with placeholders
2. Check `pipe_opt` is connected for source placeholders
3. Empty placeholders fall back to placeholder name without `%`

### Append Not Working

1. Ensure `write_mode` is set to "append"
2. Check file permissions
3. For JSON, verify existing file is valid JSON

### Source Folder Not Used

1. Enable `use_source_folder`
2. Connect `pipe_opt` from Load Image From Folder
3. Verify pipe contains `filepath` or `path`

---

## Related Nodes

- **[Load Image From Folder](Load_Image_From_Folder.md)** - Load images sequentially for batch processing
- **[Save Images](Save_Images.md)** - Save images with metadata
- **[Replace String v3](Replace_String_v3.md)** - Clean up captions before saving
- **[Smart Language Model Loader v2](Smart_Language_Model_Loader_v2_Guide.md)** - Generate captions with vision models

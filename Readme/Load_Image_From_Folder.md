# Load Image From Folder

A powerful node for batch processing workflows like captioning, tagging, or analyzing images. Loads images sequentially from one or more folders with metadata extraction support.

## Overview

The **Load Image From Folder** node is designed for workflows that need to process multiple images in sequence. Perfect for:

- **Batch Captioning**: Generate captions for entire image collections
- **Auto-Tagging**: Create tags for training datasets
- **Dataset Preparation**: Process images for fine-tuning
- **Metadata Extraction**: Retrieve generation data from existing images

## Features

- 📁 **Multi-folder support** - process multiple folders in one run
- 📁 **Subfolder recursion** - optionally include nested folders
- 🔢 **Cumulative index** - single index spans all folders
- 📊 **Multiple sort options**: name, date modified, date created, file size
- 🔄 **Per-folder caching** - efficient cache management
- 📋 **Metadata extraction** from ComfyUI, Auto1111, NovelAI, and more
- ⏹️ **Auto-stop** at end of all folders (disables auto-queue)
- 🎭 **Mask extraction** from images with alpha channels

---

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `folder_path` | STRING (multiline) | "" | Path(s) to folder(s) containing images. **One folder per line.** Can be absolute or relative to ComfyUI input folder. Index spans across all folders. |
| `include_subfolders` | BOOLEAN | False | Include images from subfolders recursively. |
| `index` | INT | 0 | Current image index (0-based). Use with `control_after_generate` to auto-increment. |
| `sort_by` | COMBO | "name" | How to sort: `name`, `date_modified`, `date_created`, `size` |
| `sort_order` | COMBO | "ascending" | Sort direction: `ascending` or `descending` |
| `stop_at_end` | BOOLEAN | True | Stop workflow and disable auto-queue when reaching end of list. |
| `extract_metadata` | BOOLEAN | False | Extract generation metadata from images (slower). Disable for faster loading. |
| `refresh_list` | BOOLEAN | False | Force refresh of cached file list. Enable once after adding/removing files. |

---

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | The loaded image as a tensor (RGB) |
| `mask` | MASK | Alpha channel mask if present, otherwise empty mask |
| `pipe` | PIPE | Metadata dictionary with generation data and file info |

### Pipe Output Contents

The `pipe` output contains all extracted metadata:

```python
{
    # File information (always populated)
    "filepath": "C:/images/photo.png",      # Full path to file
    "filename": "photo.png",                 # Filename with extension
    "source_name": "photo",                  # Filename without extension
    "path": "C:/images/photo.png",          # Alias for filepath
    "width": 1024,                           # Image width
    "height": 768,                           # Image height
    "current_index": 5,                      # Global position across all folders
    "total_count": 225,                      # Total images across all folders
    
    # Multi-folder fields
    "folder_index": 1,                       # Current folder (0-based)
    "folder_count": 3,                       # Total number of folders
    "folder_path": "C:/images/setB",         # Root folder from input list (full path)
    "local_index": 5,                        # Position within current folder
    "local_count": 50,                       # Images in current folder
    
    # Generation metadata (when extract_metadata=True)
    "text_pos": "a beautiful landscape...",  # Positive prompt
    "text_neg": "blurry, low quality",       # Negative prompt
    "seed": 12345,                            # Generation seed
    "steps": 30,                              # Sampling steps
    "cfg": 7.5,                               # CFG scale
    "sampler_name": "euler_ancestral",       # Sampler used
    "scheduler": "karras",                   # Scheduler used
    "model_name": "sd_xl_base_1.0",          # Model name from hashes
}
```

---

## Multi-Folder Support

Process multiple folders in a single workflow run by entering one folder path per line:

```
D:/datasets/portraits
D:/datasets/landscapes  
D:/datasets/animals
```

### How It Works

The index is **cumulative** across all folders:

```
Folder 1: portraits   (100 images) → index 0-99
Folder 2: landscapes  (50 images)  → index 100-149
Folder 3: animals     (75 images)  → index 150-224
─────────────────────────────────────────────────
Total: 225 images
```

- Just keep incrementing the index - folder transitions happen automatically
- Each folder is cached separately for efficiency
- Adding/removing a folder only affects that folder's cache
- Invalid or empty folders are skipped with a warning

### Multi-Folder Pipe Fields

When using multiple folders, extra fields are added to the pipe:

| Field | Description |
|-------|-------------|
| `folder_index` | Current folder number (0-based) |
| `folder_count` | Total number of folders |
| `folder_path` | Full path of current folder |
| `local_index` | Position within current folder |
| `local_count` | Number of images in current folder |

---

## Supported Image Formats

| Extension | Metadata Support |
|-----------|-----------------|
| `.png` | ✅ Full metadata extraction |
| `.webp` | ✅ Full metadata extraction |
| `.tiff`, `.tif` | ✅ Full metadata extraction |
| `.jpg`, `.jpeg` | Image only |
| `.bmp` | Image only |
| `.gif` | Image only |

---

## Metadata Sources

The node can extract generation parameters from images created by:

| Source | Prompt | Negative | Seed | Steps | CFG | Sampler |
|--------|--------|----------|------|-------|-----|---------|
| ComfyUI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Auto1111 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| NovelAI | ✅ | ✅ | - | - | - | - |
| EasyDiffusion | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| InvokeAI | ✅ | ✅ | - | - | - | - |
| Draw Things | ✅ | ✅ | - | - | - | - |

---

## Usage Examples

### Basic Batch Processing

1. Add **Load Image From Folder** node
2. Set `folder_path` to your image folder
3. Enable `stop_at_end` to automatically stop when done
4. Set index `control_after_generate` to "increment"
5. Connect to your processing workflow
6. Enable Auto Queue and run

### Captioning Workflow

```
Load Image From Folder → Vision Model → Save Prompt
       ↓
   (pipe output)  →  Save Prompt (use %source_name)
```

The `pipe` output provides `source_name` which can be used by **Save Prompt** to save captions with matching filenames.

### With Subfolder Organization

```
folder_path: "D:/datasets/training_images"
include_subfolders: True
sort_by: name
```

This loads all images from the folder and all subfolders, sorted alphabetically by full path for consistent ordering.

### Multi-Folder Batch Processing

Process images from multiple locations in one run:

```
folder_path:
D:/datasets/portraits
D:/datasets/landscapes
C:/projects/my_images
```

The workflow will process all folders sequentially. When folder 1 is done, it automatically continues to folder 2, etc.

### Resume After Interruption

The file list is cached to ensure consistent ordering. If you stop mid-way and restart:

1. Keep the same folder/sort settings
2. Set `index` to where you left off
3. The cached list ensures the same ordering

To force a fresh scan (after adding/removing files):
1. Enable `refresh_list` once
2. Run the workflow
3. Disable `refresh_list`

---

## Index Control

The `index` input works with ComfyUI's control system:

| Control After Generate | Behavior |
|----------------------|----------|
| `fixed` | Same image every run |
| `increment` | Next image each run (recommended for batch) |
| `decrement` | Previous image each run |
| `randomize` | Random image each run |

### Auto-Stop Behavior

When `stop_at_end` is enabled and `index >= total_count`:
1. Sends "stop-iteration" signal to frontend
2. Disables auto-queue to prevent infinite loops
3. Interrupts workflow execution

This makes batch processing "fire and forget" - just enable auto-queue and let it process the entire folder.

---

## Sorting Details

All sort modes use the **full file path** as a secondary sort key to ensure deterministic ordering. This prevents issues where files with identical timestamps could appear in random order.

| Sort Mode | Primary Key | Secondary Key |
|-----------|-------------|---------------|
| `name` | Full path (case-insensitive) | - |
| `date_modified` | File modification time | Full path |
| `date_created` | File creation time* | Full path |
| `size` | File size in bytes | Full path |

*Note: On Windows, `date_created` is the actual creation time. On Unix/Linux, it's the last metadata change time.

---

## Performance Tips

### Fast Loading (Metadata Disabled)

For workflows that don't need generation metadata:
- Set `extract_metadata` to False
- Only `filepath`, `filename`, `source_name`, dimensions, and counts are populated
- Significantly faster for large batches

### Caching

The file list is cached per unique combination of:
- folder_path
- include_subfolders
- sort_by
- sort_order

This means:
- First run: Scans folder, caches list
- Subsequent runs: Uses cached list (instant)
- Changing any setting: Re-scans folder

### Large Folders

For folders with thousands of images:
1. Use `sort_by: name` (fastest to sort)
2. Disable `extract_metadata` unless needed
3. Consider processing in batches by using index ranges

---

## Error Handling

### Folder Not Found

If the folder path doesn't exist, the node will:
1. Try as absolute path
2. Try relative to ComfyUI input folder
3. Try relative to ComfyUI root
4. Raise error with the path that was attempted

### Unreadable Images

If an image fails to load:
1. Warning is logged
2. Node automatically tries the next image
3. Continues until a valid image is found or all fail

### No Images Found

If the folder contains no supported image files:
- Raises error: "No images found in folder: [path]"

---

## Pipe Integration

The `pipe` output is designed to work seamlessly with other Eclipse nodes:

### Save Prompt Integration

```
Load Image From Folder (pipe) → Save Prompt
                                 └─ filename_prefix: %source_name
                                 └─ use_source_folder: True
```

This saves captions alongside source images with matching names.

### Available Placeholders

When using the pipe with Save Prompt:

| Placeholder | Value |
|-------------|-------|
| `%source_name` | Filename without extension (e.g., "photo_001") |
| `%source_filename` | Full filename (e.g., "photo_001.png") |
| `%seed` | Generation seed (if extracted) |
| `%steps` | Sampling steps (if extracted) |
| `%cfg` | CFG scale (if extracted) |

---

## Troubleshooting

### Images Loading in Wrong Order

1. Check `sort_by` and `sort_order` settings
2. Try `refresh_list` to re-scan the folder
3. Ensure no files were added/removed mid-process

### Metadata Not Extracted

1. Verify `extract_metadata` is enabled
2. Check file format supports metadata (PNG, WebP, TIFF)
3. Verify the image was saved with metadata

### Workflow Won't Stop

1. Ensure `stop_at_end` is enabled
2. Check that index is actually incrementing
3. Verify `control_after_generate` is set to "increment"

### Cache Issues

If the cached list seems stale:
1. Enable `refresh_list`
2. Run once
3. Disable `refresh_list`

---

## Related Nodes

- **[Save Prompt](Save_Prompt.md)** - Save captions/tags with matching filenames
- **[Save Images](Save_Images.md)** - Save processed images with metadata
- **[Smart Language Model Loader v2](Smart_Language_Model_Loader_v2_Guide.md)** - Generate captions with vision models

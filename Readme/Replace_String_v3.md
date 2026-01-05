# Replace String v3 [Eclipse]

A powerful text manipulation node for processing LLM outputs and prompt strings. Designed for advanced prompt engineering workflows, especially when working with AI-generated descriptions.

![Eclipse](icon_eclipse.png)

## Table of Contents
- [Overview](#overview)
- [Basic Features](#basic-features)
- [Removal Options](#removal-options)
  - [Remove Subject](#remove-subject)
  - [Remove Background](#remove-background)
  - [Remove Mood](#remove-mood)
  - [Remove Image](#remove-image)
  - [Remove Shot Style](#remove-shot-style)
- [Age Adjustment](#age-adjustment)
- [List Processing](#list-processing)
- [Custom Regex](#custom-regex)
- [Cleanup](#cleanup)
- [Usage Examples](#usage-examples)
- [Tips & Best Practices](#tips--best-practices)

---

## Overview

Replace String v3 is a versatile text processing node that can:
- Extract and filter specific parts of prompts
- Remove unwanted description types (subject, background, mood, etc.)
- Process LLM outputs (extract choices, convert lists)
- Apply custom regex replacements
- Adjust age references automatically
- Clean up formatting artifacts

**Key Use Case:** Processing captions/descriptions from vision models (like Florence2) or LLM outputs before using them as prompts for image generation.

---

## Basic Features

### Inputs

| Input | Type | Description |
|-------|------|-------------|
| `string` | STRING | The input text to process |
| `regex` | STRING | Regular expression pattern to match |
| `replace_with` | STRING | Replacement string for regex matches |

### Toggle Options

All toggles are `BOOLEAN` (default: `False`):

| Option | Purpose |
|--------|---------|
| `remove_instructions` | Extract content from quotes or remove text before `:` |
| `list_select_first` | Extract the first numbered choice from LLM output |
| `list_to_string` | Convert numbered list to single-line prompt |
| `remove_background` | Remove background/setting descriptions |
| `remove_subject` | Remove subject (person) descriptions |
| `remove_mood` | Remove mood/atmosphere descriptions |
| `remove_image` | Remove image type descriptions |
| `remove_shot_style` | Remove camera angles and shot types |
| `adjust_age` | Replace age references with target age |
| `remove_nsfw` | Remove explicit NSFW content |
| `cleanup` | Clean up formatting and whitespace |

---

## Removal Options

### Remove Subject

**Purpose:** Focus on the background/setting by removing subject (person) descriptions. Useful when you have an image of a landscape with people and want to extract just the environment.

#### How It Works

The node auto-detects **two prompt formats**:

##### 1. Tags Format (Danbooru-style)
Detected when: Contains tags like `1girl`, `1boy`, or has 3+ commas without sentence punctuation.

**Subject tags removed:**
- Count: `1girl`, `2boys`, `solo`, `duo`, `group`
- Hair: `blonde_hair`, `long_hair`, `ponytail`, `bangs`
- Eyes: `blue_eyes`, `red_eyes`
- Body: `large_breasts`, `slim`, `muscular`
- Expressions: `smile`, `blush`, `open_mouth`
- Poses: `sitting`, `standing`, `kneeling`
- Clothing: `dress`, `uniform`, `bikini`
- Viewpoint: `looking_at_viewer`, `from_behind`
- Framing: `portrait`, `cowboy_shot`, `upper_body`

**Background tags preserved:**
- Locations: `forest`, `beach`, `city`, `bedroom`
- Time: `day`, `night`, `sunset`
- Weather: `rain`, `snow`, `clouds`
- Quality: `realistic`, `masterpiece`, `detailed`
- Lighting: `dramatic_lighting`, `bokeh`

**Example:**
```
Input:  1girl, solo, long hair, blue eyes, smile, standing, forest, day, realistic
Output: forest, day, realistic
```

##### 2. Prose Format
For descriptive sentences, extracts the setting portion.

**Example:**
```
Input:  A beautiful woman reclines in a moonlit garden surrounded by flowers.
Output: in a moonlit garden surrounded by flowers
```

**Structured prompts:**
```
Input:  Subject: A young warrior. Background: A stormy battlefield at dawn.
Output: Background: A stormy battlefield at dawn.
```

#### Safety Feature
If removal leaves nothing meaningful, the **original text is returned unchanged**.

```
Input:  1girl, solo, blue_eyes, blonde_hair  (no background tags)
Output: 1girl, solo, blue_eyes, blonde_hair  (unchanged)
```

---

### Remove Background

Removes background, environment, setting, and scene descriptions.

**Patterns matched:**
- `Background: ...`
- `The background is...`
- `In the background...`
- `Environment/Setting/Scene: ...`

**Example:**
```
Input:  A woman stands in a garden. The background shows mountains at sunset.
Output: A woman stands in a garden.
```

---

### Remove Mood

Removes mood, atmosphere, feeling, and vibe descriptions.

**Patterns matched:**
- `Mood: ...`
- `The atmosphere is...`
- `Overall feeling...`
- `The vibe of...`

**Example:**
```
Input:  A portrait of a woman. The mood is serene and contemplative. She wears blue.
Output: A portrait of a woman. She wears blue.
```

---

### Remove Image

Removes image type descriptions and prefixes. Smart handling preserves subject information.

**Patterns matched:**
- `The image is...`
- `A digital illustration of...`
- `A photo-realistic render of...`
- `Close-up portrait of...`

**Example:**
```
Input:  A highly detailed digital illustration of a menacing warrior
Output: a menacing warrior

Input:  A semi-realistic photo shoot from a close-up angle about a portrait of a young woman
Output: a young woman
```

---

### Remove Shot Style

Removes camera angles, shot types, and framing descriptions.

**Prose patterns removed:**
- `shoot from a close-up angle about`
- `captured from a side angle`
- `shot from behind view`

**Tag patterns removed:**
- `close-up`, `portrait`, `cowboy shot`
- `from above`, `from behind`, `from side`
- `looking at viewer`, `looking back`
- `upper body`, `full body`, `pov`

**Example:**
```
Input:  A photo shoot from a close-up camera angle about a portrait of a woman smiling
Output: A shoot about a woman smiling

Input:  1girl, close-up, smile, blue eyes, looking at viewer, garden
Output: 1girl, smile, blue eyes, garden
```

---

## Remove NSFW

Removes explicit NSFW content from prompts while preserving non-explicit descriptors. Useful for cleaning vision model outputs or sanitizing prompts.

### What Gets Removed

**Nudity tags:**
- `nude`, `naked`, `topless`, `bottomless`
- `bare-breasted`, `completely nude`

**Explicit body parts:**
- `nipples`, `areola`
- `pussy`, `vagina`, `penis`, `genitals`
- `pubic hair`, `anus`

**Sexual content:**
- `sex`, `intercourse`, `penetration`
- `masturbation`, `oral sex`, `orgasm`
- `erection`, `aroused`

**Explicit poses/states:**
- `spread legs` (in explicit context)
- `uncensored`, `cameltoe`
- `no panties`, `no bra`

**Fetish/Other:**
- `bdsm`, `bondage`, `fetish`
- `hentai`, `ahegao`
- `loli`, `shota`

### What is NOT Removed

These are preserved because they can appear in non-explicit contexts:

- **Breast sizes:** `large breasts`, `medium breasts`, `small breasts`
- **Cleavage:** Can be clothed/formal wear
- **Underwear:** `panties`, `bra`, `lingerie` (modeling context)
- **Swimwear:** `bikini`, `swimsuit`

### Examples

**Tags:**
```
Input:  1girl, solo, large breasts, topless, nipples, bedroom, realistic
Output: 1girl, solo, large breasts, bedroom, realistic
REMOVED: topless, nipples

Input:  1girl, bikini, beach, cleavage, summer
Output: 1girl, bikini, beach, cleavage, summer  (unchanged - all safe)
```

**Prose:**
```
Input:  A nude woman with long blonde hair stands in a forest, her nipples visible.
Output: A woman with long blonde hair stands in a forest, her visible.
```

---

## Age Adjustment

Enable `adjust_age` and set the `age` parameter (18-99) to replace all age references.

**Patterns replaced:**
- `young woman` → `25-year-old woman`
- `appears to be in her mid-twenties` → `is 25-year-old`
- `teenage girl` → `25-year-old girl`
- `17 years old` → `25-year-old`
- `20-year-old` → `25-year-old`
- `10yr`, `17yo` → `25yr`, `25yo`

**Example:**
```
Input:  A young woman who appears to be in her late teens or early twenties
Output: A 25-year-old woman is 25-year-old
(with age=25)
```

---

## List Processing

### Remove Instructions
Extracts content from quotes at the start, or removes everything before `:`.

```
Input:  Prompt: "A beautiful landscape with mountains"
Output: A beautiful landscape with mountains

Input:  Description: The image shows a sunset
Output: The image shows a sunset
```

### List Select First
Extracts the first numbered quoted choice from LLM output.

```
Input:  Here are some options:
        1. "A serene mountain lake at dawn"
        2. "A bustling city street at night"
Output: A serene mountain lake at dawn
```

### List to String
Converts numbered tip lists to single-line prompts, removing labels.

```
Input:  Photography tips:
        1. **Lighting:** Use soft natural light
        2. **Composition:** Follow rule of thirds
        3. **Focus:** Keep eyes sharp
Output: Use soft natural light, Follow rule of thirds, Keep eyes sharp
```

---

## Custom Regex

The `regex` and `replace_with` fields allow custom pattern matching.

**Examples:**

| Regex | Replace | Effect |
|-------|---------|--------|
| `\bcat\b` | `dog` | Replace whole word "cat" with "dog" |
| `\s+` | ` ` | Collapse multiple spaces |
| `(?i)anime` | `realistic` | Case-insensitive replace |
| `\d+` | `X` | Replace all numbers |
| `,\s*,` | `,` | Remove double commas |

---

## Cleanup

When enabled, performs final cleanup:
- Normalizes whitespace and newlines
- Removes surrounding quotes
- Fixes punctuation artifacts (`. ,` → `. `)
- Removes trailing punctuation
- Collapses multiple periods/commas

---

## Usage Examples

### Example 1: Extract Background from Tagged Prompt
```
Settings:
  remove_subject: ✓
  
Input:  1girl, solo, blonde_hair, blue_eyes, dress, standing, forest, sunlight, masterpiece
Output: forest, sunlight, masterpiece
```

### Example 2: Clean LLM Caption for Re-prompting
```
Settings:
  remove_image: ✓
  adjust_age: ✓
  age: 30
  cleanup: ✓
  
Input:  A photo-realistic digital illustration of a young woman in her early twenties, 
        with long brown hair, wearing a red dress, standing in a garden.
Output: a 30-year-old woman, with long brown hair, wearing a red dress, standing in a garden
```

### Example 3: Process Vision Model Output
```
Settings:
  remove_instructions: ✓
  remove_mood: ✓
  cleanup: ✓
  
Input:  Caption: "A dramatic portrait of a warrior. The mood is intense and foreboding. 
        He holds a sword."
Output: A dramatic portrait of a warrior He holds a sword
```

### Example 4: Focus on Setting Only
```
Settings:
  remove_subject: ✓
  remove_mood: ✓
  cleanup: ✓
  
Input:  Subject: A beautiful woman with flowing hair. 
        Background: A mystical forest with glowing mushrooms.
        Mood: Ethereal and magical.
Output: Background: A mystical forest with glowing mushrooms
```

---

## Tips & Best Practices

### 💡 Order of Operations
Options are applied in this order:
1. `remove_instructions` / `list_select_first` / `list_to_string`
2. `remove_background`
3. `remove_subject`
4. `remove_mood`
5. `remove_image`
6. `remove_shot_style`
7. `adjust_age`
8. `remove_nsfw`
9. Custom `regex` replacement
9. `cleanup`

### 💡 Combine with Smart Prompt
Works great with [Smart Prompt](Smart_Prompt.md) - use Replace String v3 to clean LLM outputs before feeding them to image generation.

### 💡 Safe Defaults
If `remove_subject` would result in empty output, the original is preserved. Test with your specific prompt format first.

### 💡 Tags vs Prose
The node auto-detects format based on:
- Presence of `1girl`/`1boy` patterns
- Comma count (3+ suggests tags)
- Presence of sentence punctuation (`.!?`)

### 💡 Chaining Multiple Nodes
For complex processing, chain multiple Replace String v3 nodes with different settings.

### 💡 Use with Florence2/LLaVA
Caption outputs from vision models often need:
- `remove_image` to remove "The image shows..."
- `adjust_age` for age-appropriate prompts
- `cleanup` for formatting

---

## Related Documentation

- [Smart Prompt](Smart_Prompt.md) - AI-powered prompt enhancement
- [Smart Language Model Loader v2](Smart_Language_Model_Loader_v2_Guide.md) - LLM integration
- [Wildcard Processor](Wildcard_Processor.md) - Dynamic prompt generation
- [Smart Loaders](Smart_Loaders.md) - Model loading nodes

---

*Part of [ComfyUI Eclipse](README.md) - Advanced nodes for ComfyUI*

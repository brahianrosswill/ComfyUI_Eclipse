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

import re
from typing import List


def is_tags_format(text: str) -> bool:
    """
    Detect if text is tag-based prompt format (Danbooru/NAI style).
    Checks for: underscore tags, weight syntax, double parentheses,
    common quality tags, count tags (1girl, 2boys).
    
    Args:
        text: Text to analyze
        
    Returns:
        True if text appears to be tag-based format
    """
    if not text:
        return False
    
    # Import patterns to avoid circular imports
    from .regex_patterns import (
        RE_TAG_UNDERSCORE, RE_TAG_WEIGHT, RE_TAG_DOUBLE_PARENS,
        RE_TAG_QUALITY, RE_TAG_COUNT
    )
    
    return any([
        RE_TAG_UNDERSCORE.search(text),
        RE_TAG_WEIGHT.search(text),
        RE_TAG_DOUBLE_PARENS.search(text),
        RE_TAG_QUALITY.search(text),
        RE_TAG_COUNT.search(text),
    ])


def smart_phrase_removal(text: str, removal_patterns: List[str], pattern_type: str = "content") -> str:
    """
    Intelligently remove phrases from prose while maintaining grammatical integrity.
    
    This approach:
    1. Detects if text is tags vs prose
    2. For prose: removes entire sentences containing problematic phrases
    3. For tags: removes individual tags
    
    Args:
        text: Input text
        removal_patterns: List of regex patterns to remove
        pattern_type: Type of content being removed (for logging)
        
    Returns:
        Text with patterns removed while maintaining grammar
    """
    if not text:
        return text
    
    # For tag format, use simple tag removal
    if is_tags_format(text):
        tags = [t.strip() for t in text.split(',')]
        kept_tags = []
        for tag in tags:
            tag_lower = tag.lower().strip()
            is_target = any(re.search(pat, tag_lower, re.I) for pat in removal_patterns)
            if not is_target:
                kept_tags.append(tag)
        return ', '.join(kept_tags) if kept_tags else text
    
    # For prose format, remove entire sentences containing target phrases
    sentences = re.split(r'([.!?]+)', text)
    cleaned_sentences = []
    
    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        
        # Check if this sentence contains any target patterns
        contains_target = False
        if sentence.strip():  # Skip empty/punctuation-only parts
            for pattern in removal_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    contains_target = True
                    break
        
        if contains_target:
            # Skip this sentence (and its punctuation if present)
            if i + 1 < len(sentences) and sentences[i + 1].strip() in '.!?':
                i += 2  # Skip sentence + punctuation
            else:
                i += 1  # Skip just sentence
        else:
            # Keep this sentence
            cleaned_sentences.append(sentence)
            # Also keep the following punctuation if it exists
            if i + 1 < len(sentences) and sentences[i + 1].strip() in '.!?':
                i += 1
                cleaned_sentences.append(sentences[i])
            i += 1
    
    result = ''.join(cleaned_sentences)
    
    # Clean up spacing and punctuation artifacts
    result = re.sub(r'\s+', ' ', result)  # Multiple spaces
    result = re.sub(r'([.!?])\s*\1+', r'\1', result)  # Double punctuation
    result = re.sub(r'\.([A-Z])', r'. \1', result)  # Add space after period before capital letter
    result = result.strip()
    
    return result


def detect_nsfw_level(text: str) -> str:
    """
    Detect NSFW level from text content.
    
    Args:
        text: Text content to analyze
        
    Returns:
        'X' for explicit content, 'Mature' for suggestive content, or 'None' for safe content
    """
    if not text:
        return 'None'
    
    # Import patterns to avoid circular imports
    from .regex_patterns import NSFW_KEYWORDS_X, NSFW_KEYWORDS_MATURE
    
    text_lower = text.lower()
    
    # Check for X-rated keywords first
    for keyword in NSFW_KEYWORDS_X:
        if keyword in text_lower:
            return 'X'
    
    # Check for Mature keywords
    for keyword in NSFW_KEYWORDS_MATURE:
        if keyword in text_lower:
            return 'Mature'
    
    return 'None'


def clean_text_whitespace(text: str) -> str:
    """
    Clean and normalize whitespace in text.
    Collapses newlines to spaces and multiple spaces to single space.
    
    Args:
        text: Text to clean
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    from .regex_patterns import RE_NEWLINES, RE_MULTI_SPACE
    
    text = RE_NEWLINES.sub(' ', text)
    text = RE_MULTI_SPACE.sub(' ', text)
    return text.strip()


def clean_punctuation(text: str) -> str:
    """
    Clean up common punctuation issues in prompts.
    Handles double punctuation, trailing punctuation, etc.
    
    Args:
        text: Text to clean
        
    Returns:
        Text with cleaned punctuation
    """
    if not text:
        return ""
    
    from .regex_patterns import (
        RE_DOUBLE_PUNCT, RE_COMMA_PERIOD, RE_PERIOD_COMMA, 
        RE_MULTI_PERIOD, RE_TRAILING_PUNCT
    )
    
    # Fix double punctuation
    while RE_DOUBLE_PUNCT.search(text):
        text = RE_DOUBLE_PUNCT.sub(',', text)
    # Fix comma-period combinations
    text = RE_COMMA_PERIOD.sub('.', text)
    text = RE_PERIOD_COMMA.sub('.', text)
    # Fix multiple periods
    text = RE_MULTI_PERIOD.sub('.', text)
    # Remove trailing punctuation
    text = RE_TRAILING_PUNCT.sub('', text)
    return text.strip()


def extract_json_object(text: str) -> str | None:
    """
    Extract first JSON object {...} from text.
    
    Args:
        text: Text to search
        
    Returns:
        First JSON object found or None
    """
    from .regex_patterns import RE_JSON_OBJECT
    
    match = RE_JSON_OBJECT.search(text)
    return match.group(0) if match else None


def extract_json_array(text: str) -> str | None:
    """
    Extract first JSON array [...] from text.
    
    Args:
        text: Text to search
        
    Returns:
        First JSON array found or None
    """
    from .regex_patterns import RE_JSON_ARRAY
    
    match = RE_JSON_ARRAY.search(text)
    return match.group(0) if match else None


def strip_code_fences(text: str) -> str:
    """
    Remove markdown code fences from text.
    
    Args:
        text: Text to process
        
    Returns:
        Text without code fences
    """
    if not text:
        return ""
    
    from .regex_patterns import RE_CODE_FENCE_OPEN, RE_CODE_FENCE_CLOSE
    
    text = RE_CODE_FENCE_OPEN.sub('', text)
    text = RE_CODE_FENCE_CLOSE.sub('', text)
    return text.strip()


def clean_nsfw_prose(text: str) -> str:
    """
    Clean NSFW content from prose text by removing entire sentences/clauses
    instead of individual words to avoid broken grammar.
    
    Args:
        text: Input prose text
        
    Returns:
        Cleaned text with NSFW sentences/clauses removed
    """
    if not text:
        return text
    
    if is_tags_format(text):
        return text
    
    from .regex_patterns import NSFW_PROSE_SENTENCE_PATTERNS
    
    # First pass: Remove entire sentences containing explicit content
    for pattern in NSFW_PROSE_SENTENCE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Clean up artifacts
    text = re.sub(r'\s*\.\s*\.', '.', text)  # Double periods
    text = re.sub(r'\s*,\s*,', ',', text)    # Double commas  
    text = re.sub(r'\s*,\s*\.', '.', text)   # Comma before period
    text = re.sub(r'\s+', ' ', text)         # Multiple spaces
    text = re.sub(r'^\s*[,.]\s*', '', text)  # Leading punctuation
    text = text.strip()
    
    return text
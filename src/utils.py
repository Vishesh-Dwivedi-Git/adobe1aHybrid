import re
from typing import List, Dict, NamedTuple
from collections import Counter

# A simple data class to hold style information for a font.
class Style(NamedTuple):
    size: float
    bold: bool
    italic: bool
    font: str

# A data class to hold all the extracted features for a single text block (line).
class TextBlock(NamedTuple):
    text: str
    bbox: tuple
    page_num: int
    size: float
    font: str
    bold: bool
    italic: bool

def normalize_text(text: str) -> str:
    """
    Normalizes text for comparison by removing non-alphanumeric characters
    and converting to lowercase.
    """
    return re.sub(r'[^a-z0-9]', '', text.lower())

def get_font_styles(blocks: List[TextBlock]) -> Dict[str, Style]:
    """
    Analyzes all text blocks to determine the primary styles used in the document,
    such as body text and different heading levels. This version is more robust.
    """
    if not blocks:
        return {}

    # Filter out very short text (likely artifacts) for style analysis
    meaningful_blocks = [b for b in blocks if len(b.text.strip()) >= 3]
    if not meaningful_blocks:
        meaningful_blocks = blocks  # Fallback

    # Heuristic: Assume body text is the most common style in blocks with more than 4 words.
    body_candidate_blocks = [b for b in meaningful_blocks if len(b.text.split()) > 4 and not b.bold]
    if not body_candidate_blocks:
        # Fallback: try non-bold blocks with at least 2 words
        body_candidate_blocks = [b for b in meaningful_blocks if len(b.text.split()) >= 2 and not b.bold]
    if not body_candidate_blocks:
        body_candidate_blocks = meaningful_blocks  # Final fallback

    style_counts = Counter(
        Style(b.size, b.bold, b.italic, b.font) for b in body_candidate_blocks
    )
    if not style_counts:
        # If still no candidates, find the most common style overall.
        style_counts = Counter(Style(b.size, b.bold, b.italic, b.font) for b in meaningful_blocks)
        if not style_counts:
            return {'body': Style(12.0, False, False, 'Unknown')}  # Absolute fallback

    body_style = style_counts.most_common(1)[0][0]

    # Identify potential heading styles as unique styles that are larger or bolder than body text.
    # Use a slightly more generous size threshold
    size_threshold = max(0.5, body_style.size * 0.05)  # At least 0.5pt or 5% larger
    
    heading_styles = sorted(
        list({
            Style(b.size, b.bold, b.italic, b.font) 
            for b in meaningful_blocks 
            if (b.size > body_style.size + size_threshold) or 
               (b.bold and not body_style.bold) or
               (b.size >= body_style.size and b.bold and len(b.text.split()) <= 8)  # Short bold text
        }),
        key=lambda s: (s.size, s.bold),  # Sort by size first, then bold
        reverse=True
    )

    # Remove duplicates and body style from heading styles
    heading_styles = [s for s in heading_styles if s != body_style]

    # Assign H1, H2, H3 based on descending font size and formatting.
    styles = {'body': body_style}
    if len(heading_styles) > 0:
        styles['h1'] = heading_styles[0]
    if len(heading_styles) > 1:
        styles['h2'] = heading_styles[1]
    if len(heading_styles) > 2:
        styles['h3'] = heading_styles[2]

    return styles

def is_likely_artifact(text: str) -> bool:
    """
    Additional utility to check if text is likely an artifact (page numbers, etc.)
    This can be used as an extra filter in the main extractor.
    """
    text = text.strip()
    
    # Common artifact patterns
    artifact_patterns = [
        r'^\s*\d+\s*$',  # Standalone numbers
        r'^\s*page\s+\d+\s*$',  # Page numbers
        r'^\s*\d+\s*[-/]\s*\d+\s*$',  # Number ranges
        r'^\s*[ivxlcdm]+\s*$',  # Roman numerals alone
        r'^\s*\([a-z]\)\s*$',  # Single letters in parentheses
        r'^\s*[.\-_–—]+\s*$',  # Just punctuation
    ]
    
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in artifact_patterns)
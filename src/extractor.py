import fitz  # PyMuPDF
import logging
import re
import os
from collections import Counter
from typing import List, Dict, Any, Tuple
import numpy as np

# Make sure utils.py is in the same directory
from utils import Style, TextBlock, normalize_text, get_font_styles

# Setup logging
logger = logging.getLogger(__name__)


class AdvancedPDFOutlineExtractor:
    """
    A robust PDF outline extractor using a document-adaptive scoring model
    to identify titles and hierarchical headings with high precision.
    """

    def __init__(self):
        """Initializes the extractor with refined patterns for filtering."""
        self.artifact_patterns = [
            re.compile(r'^\s*(page\s+)?\d+\s*$', re.IGNORECASE),
            re.compile(r'^\s*table\s+\d+|figure\s+\d+', re.IGNORECASE),
            re.compile(r'copyright|©|all rights reserved', re.IGNORECASE),
            re.compile(r'^[.\-_–—\s]+$'),
            re.compile(r'^\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*$'),
            # Enhanced patterns to filter out standalone numbers and common non-heading patterns
            re.compile(r'^\s*\d+\s*$'),  # Standalone numbers
            re.compile(r'^\s*\d+\.\s*$'),  # Numbers with just a dot
            re.compile(r'^\s*\([a-z]\)\s*$', re.IGNORECASE),  # Single letters in parentheses
            re.compile(r'^\s*[ivxlcdm]+\s*$', re.IGNORECASE),  # Roman numerals alone
        ]
        self.heading_keywords = {'abstract', 'introduction', 'summary', 'conclusion', 'references', 'acknowledgements',
                                 'contents', 'background', 'methodology', 'results', 'discussion', 'appendix', 'preamble',
                                 'timeline', 'outlook'}

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Main processing pipeline for a single PDF."""
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"Could not open or read PDF {pdf_path}: {e}")
            return {"title": f"Error reading {os.path.basename(pdf_path)}", "outline": []}

        if len(doc) == 0:
            return {"title": "Empty Document", "outline": []}

        all_blocks = self._extract_text_blocks(doc)
        if not all_blocks:
            doc.close()
            return {"title": "Document has no text", "outline": []}

        doc_type = self._classify_document_type(all_blocks)

        headers, footers = self._detect_headers_footers(all_blocks, doc)
        content_blocks = [
            b for b in all_blocks
            if normalize_text(b.text) not in headers and normalize_text(b.text) not in footers
        ]

        font_styles = get_font_styles(content_blocks)
        body_style = font_styles.get('body')

        title = self._extract_title(content_blocks, font_styles, doc_type)

        scored_blocks = self._score_blocks_for_headings(content_blocks, body_style, doc_type)

        # **RECALIBRATED THRESHOLD**
        headings = [b for b in scored_blocks if b['score'] > 30]

        final_outline = self._classify_and_clean(headings, font_styles)

        doc.close()
        return {"title": title, "outline": final_outline}

    def _classify_document_type(self, blocks: List[TextBlock]) -> str:
        """Classifies the document as 'text_heavy' or 'sparse'."""
        # Heuristic: A document is text-heavy if it has a reasonable number of blocks
        # and the average line length is not extremely short.
        if len(blocks) > 15:
            avg_len = sum(len(b.text) for b in blocks) / len(blocks)
            if avg_len > 30:
                return 'text_heavy'
        return 'sparse'

    def _is_meaningful_heading(self, text: str) -> bool:
        """Enhanced check to determine if text could be a meaningful heading."""
        text = text.strip()
        
        # Must have some alphabetic content
        if not re.search(r'[a-zA-Z]', text):
            return False
        
        # Check for meaningful numbered headings (number + text)
        numbered_heading = re.match(r'^\s*(\d{1,2}(?:\.\d{1,2})*)\s*[\.\:\-\s]*(.+)', text)
        if numbered_heading:
            number_part, text_part = numbered_heading.groups()
            # Must have substantial text after the number
            return len(text_part.strip()) >= 3 and bool(re.search(r'[a-zA-Z]', text_part))
        
        # For non-numbered text, it should be substantial
        words = text.split()
        if len(words) == 1:
            # Single word should be at least 3 characters and not just numbers
            return len(text) >= 3 and not text.isdigit()
        
        return True

    def _extract_text_blocks(self, doc: fitz.Document) -> List[TextBlock]:
        """Extracts text blocks from the document."""
        blocks = []
        for page_num, page in enumerate(doc):
            page_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_LIGATURES)
            for block in page_dict.get("blocks", []):
                if block['type'] == 0:
                    for line in block.get("lines", []):
                        if not line.get('spans'): continue
                        text = " ".join(span.get('text', '') for span in line['spans']).strip()
                        if not text: continue

                        spans = line['spans']
                        sizes = [s['size'] for s in spans]
                        fonts = [s['font'] for s in spans]
                        flags = [s['flags'] for s in spans]

                        is_bold, is_italic = False, False
                        if flags:
                            most_common_flag = Counter(flags).most_common(1)[0][0]
                            is_bold = bool(most_common_flag & (1 << 4))
                            is_italic = bool(most_common_flag & (1 << 1))

                        blocks.append(TextBlock(
                            text=text, bbox=line['bbox'], page_num=page_num,
                            size=round(np.mean(sizes), 2) if sizes else 0,
                            font=Counter(fonts).most_common(1)[0][0] if fonts else "Unknown",
                            bold=is_bold, italic=is_italic
                        ))
        return blocks

    def _detect_headers_footers(self, all_blocks: List[TextBlock], doc: fitz.Document) -> Tuple[set, set]:
        """Detects repeating text at the top and bottom of pages."""
        page_count = doc.page_count
        if page_count < 3: return set(), set()

        headers, footers = Counter(), Counter()
        page_heights = [page.rect.height for page in doc]

        for block in all_blocks:
            if block.page_num < len(page_heights):
                page_height = page_heights[block.page_num]
                if block.bbox[1] < page_height * 0.12: headers[normalize_text(block.text)] += 1
                elif block.bbox[3] > page_height * 0.88: footers[normalize_text(block.text)] += 1

        min_occurrences = max(2, page_count // 2)
        final_headers = {text for text, count in headers.items() if count >= min_occurrences}
        final_footers = {text for text, count in footers.items() if count >= min_occurrences}
        return final_headers, final_footers

    def _extract_title(self, blocks: List[TextBlock], font_styles: Dict[str, Style], doc_type: str) -> str:
        """Extracts the document title based on prominence and document type."""
        candidates = []
        page_one_blocks = sorted([b for b in blocks if b.page_num == 0], key=lambda b: b.bbox[1])

        for i, block in enumerate(page_one_blocks):
            if i > 10: break
            if any(p.search(block.text) for p in self.artifact_patterns): continue
            
            text_len = len(block.text)
            if text_len < 4 or text_len > 150: continue

            score = 0
            largest_font = font_styles.get('h1', Style(1, False, False, ''))
            if largest_font.size > 0: score += (block.size / largest_font.size) * 60
            
            score += (1 - (block.bbox[1] / 800)) * 20
            if block.bold: score += 20
            
            candidates.append({'text': block.text, 'score': score})

        if not candidates: return ""
        best_candidate = max(candidates, key=lambda x: x['score'])

        if doc_type == 'sparse':
            return best_candidate['text']
        
        return best_candidate['text'] if best_candidate['score'] > 50 else ""

    def _score_blocks_for_headings(self, blocks: List[TextBlock], body_style: Style, doc_type: str) -> List[Dict]:
        """Scores each block using a scoring model adapted to the document type."""
        scored_blocks = []
        if not body_style: return []

        for i, block in enumerate(blocks):
            # Enhanced artifact pattern filtering
            if any(p.search(block.text) for p in self.artifact_patterns): continue
            
            # Check if this could be a meaningful heading
            if not self._is_meaningful_heading(block.text): continue
            
            word_count = len(block.text.split())
            if not (1 <= word_count <= 35): continue

            score = 0
            
            if doc_type == 'text_heavy':
                if block.text.endswith('.') and word_count > 12: continue

                # **IMPROVED SCORING WITH BETTER NUMBER DETECTION**
                # Font Size: Give points even for small increases.
                if block.size > body_style.size:
                    score += (block.size - body_style.size) * 15
                # Bold Style: Very strong signal.
                if block.bold and not body_style.bold:
                    score += 30
                # Space Above: Good signal.
                if i > 0 and (block.bbox[1] - blocks[i-1].bbox[3] > 8):
                    score += 15
                
                # **IMPROVED NUMBERED PATTERN DETECTION**
                # Only give high scores to meaningful numbered headings (number + substantial text)
                numbered_match = re.match(r'^\s*(\d{1,2}(?:\.\d{1,2})*)\s*[\.\:\-\s]*(.+)', block.text)
                if numbered_match:
                    number_part, text_part = numbered_match.groups()
                    if len(text_part.strip()) >= 3:  # Must have substantial text after number
                        score += 50
                    else:
                        score -= 20  # Penalize number-only or minimal text
                
                # Keyword Match
                if any(kw in block.text.lower() for kw in self.heading_keywords):
                    score += 25
                    
                # Capitalization patterns (common in headings)
                if block.text.isupper() and len(block.text) > 3:
                    score += 15
                elif block.text.istitle():
                    score += 10
            
            elif doc_type == 'sparse':
                # For sparse docs, any distinct text is a candidate.
                score += block.size * 3
                if block.bold: score += 20
                if block.text.isupper(): score += 15
                if block.text.endswith(':'): score -= 30
                
                # Even in sparse docs, be careful with standalone numbers
                if re.match(r'^\s*\d+\s*$', block.text):
                    score -= 50

            scored_blocks.append({'block': block, 'score': score})
        return scored_blocks

    def _classify_and_clean(self, headings: List[Dict], font_styles: Dict[str, Style]) -> List[Dict]:
        """Classifies heading levels and performs a final, reliable cleanup."""
        if not headings: return []

        headings.sort(key=lambda h: (h['block'].page_num, h['block'].bbox[1]))

        style_to_level = {}
        for level_name, style in font_styles.items():
            if level_name != 'body':
                style_to_level[style] = level_name.upper()

        final_outline = []
        for heading in headings:
            block = heading['block']
            
            # Final check to ensure this is a meaningful heading
            if not self._is_meaningful_heading(block.text):
                continue
                
            block_style = Style(block.size, block.bold, block.italic, block.font)
            
            level = 'H3' # Default
            if block_style in style_to_level:
                level = style_to_level[block_style]
            else:
                if font_styles.get('h1') and block.size >= font_styles['h1'].size - 0.5: level = 'H1'
                elif font_styles.get('h2') and block.size >= font_styles['h2'].size - 0.5: level = 'H2'

            # **IMPROVED LEVEL DETECTION FOR NUMBERED HEADINGS**
            numbered_match = re.match(r'^\s*(\d{1,2}(?:\.\d{1,2})*)\s*[\.\:\-\s]*(.+)', block.text)
            if numbered_match:
                number_part, text_part = numbered_match.groups()
                if len(text_part.strip()) >= 3:  # Only process if substantial text follows
                    num_dots = number_part.count('.')
                    level = f"H{min(num_dots + 1, 4)}"

            final_outline.append({"level": level, "text": block.text.strip(), "page": block.page_num + 1})

        # Remove duplicates and perform final cleanup
        seen = set()
        clean_outline = []
        for item in final_outline:
            key = (item['text'], item['page'])
            if key not in seen:
                # One more check to ensure quality
                if self._is_meaningful_heading(item['text']):
                    clean_outline.append(item)
                    seen.add(key)

        return clean_outline

# Advanced PDF Outline Extractor

This project provides a robust, containerized solution for automatically extracting a structured outline and title from PDF documents. It uses a document-adaptive scoring model based on font metrics, text patterns, and layout analysis to identify hierarchical headings (H1, H2, H3) with high precision, making it effective across a wide variety of document formats.

The entire process is packaged within a Docker container, ensuring easy setup and consistent execution in any environment.

## Demo
[![Watch the video](https://i.sstatic.net/Vp2cE.png)](https://youtu.be/A_VfTeD94Rg)


## ✨ Features

-   **Automatic Title Extraction**: Intelligently identifies the main title of the document.
-   **Hierarchical Outline Generation**: Reconstructs the document's structure with up to three levels of headings (H1, H2, H3).
-   **Document-Adaptive Scoring**: The core model adjusts its scoring strategy based on whether a document is text-heavy (like an academic paper) or sparse (like a presentation).
-   **Header & Footer Removal**: Automatically detects and filters out repeating text from page headers and footers to reduce noise.
-   **Robust Artifact Filtering**: Employs a comprehensive set of rules to ignore common non-heading elements like page numbers, tables of contents, figure captions, and stray punctuation.
-   **Dockerized for Portability**: Comes with a `Dockerfile` for one-command setup, eliminating dependency issues and ensuring the environment is consistent.

---

## ⚙️ How It Works

The extractor processes PDFs through a multi-stage pipeline designed to logically deconstruct the document and identify meaningful structural elements.

1.  **Text Block Extraction (`extractor.py`)**:
    -   The process starts by opening a PDF using `PyMuPDF` (`fitz`).
    -   It extracts all text on a line-by-line basis, capturing not just the text itself but also its rich metadata: font name, size, boldness, italics, and bounding box coordinates on the page. Each line is stored as a `TextBlock` object.

2.  **Header & Footer Detection**:
    -   To avoid including repetitive text in the outline, the script analyzes text that appears frequently in the top 12% and bottom 12% of pages.
    -   If a piece of text appears on at least half the pages (or a minimum of 2), it's classified as a header or footer and excluded from further analysis.

3.  **Style Analysis (`utils.py`)**:
    -   The script analyzes all the remaining content blocks to understand the document's typographic hierarchy.
    -   It first identifies the **body text style**, typically the most common style (font, size, weight) found in longer paragraphs.
    -   It then identifies potential **heading styles** by finding styles that are larger, bolder, or otherwise distinct from the body style. These are sorted by prominence and mapped to `H1`, `H2`, and `H3`.

4.  **Document Classification**:
    -   A simple heuristic classifies the document as either `'text_heavy'` or `'sparse'`. This classification allows the scoring model to adapt its rules, as headings in dense academic papers look very different from headings in a slide deck.

5.  **Title Extraction**:
    -   The title is assumed to be on the first page.
    -   Blocks on the first page are scored based on font size (relative to the largest font in the document), boldness, and vertical position (higher is better). The highest-scoring, meaningful block is chosen as the title.

6.  **Heading Scoring Model (`_score_blocks_for_headings`)**:
    -   This is the core of the extractor. Every content block is scored to determine its likelihood of being a heading. The scoring is weighted based on a combination of features:
        -   **Font Size**: Larger size relative to the body text earns a high score.
        -   **Bold Weight**: Bold text is a very strong indicator.
        -   **Numbered Lists**: Text following a clear numbered pattern (e.g., `1.`, `2.1`, `3.1.2`) receives a significant score boost.
        -   **Capitalization**: ALL CAPS or Title Case text is more likely to be a heading.
        -   **Keywords**: The presence of common section keywords (e.g., "Introduction", "Conclusion", "Methodology") increases the score.
        -   **Spacing**: Extra vertical space before a block suggests it's a heading.
        -   **Negative Patterns**: Blocks that end in a period (like a sentence) or contain only numbers are penalized.

7.  **Classification & Cleanup (`_classify_and_clean`)**:
    -   Blocks that pass a score threshold (e.g., score > 30) are considered headings.
    -   They are assigned a level (`H1`, `H2`, `H3`) based on their style matching the pre-identified heading styles or their numbered list depth.
    -   Finally, the list is cleaned to remove duplicates and any remaining low-quality artifacts before being formatted into the final JSON output.

---

## 📂 File Structure

```
.
├── Dockerfile              # Defines the container environment and setup.
├── requirements.txt        # Lists Python dependencies.
├── input/                  # Directory for input PDFs (mounted into the container).
│   └── sample.pdf
└── src/
    ├── extractor.py        # Contains the main AdvancedPDFOutlineExtractor class and logic.
    ├── main.py             # The entry point script that orchestrates the processing.
    └── utils.py            # Helper functions for style analysis and data structures.
```

---

## 🚀 Usage

The project is designed to be run using Docker. You will need to have Docker installed and running on your system.

### Step 1: Build the Docker Image

Navigate to the root directory of the project (where the `Dockerfile` is located) and run the build command.

```bash
docker build -t pdf-extractor .
```

This command builds a Docker image named `pdf-extractor` based on the instructions in the `Dockerfile`, installing all necessary dependencies.

### Step 2: Run the Container

1.  Place all the PDF files you want to process into the `input/` directory.
2.  Create an `output/` directory in the project root. This is where the JSON results will be written.
3.  Run the container using the following command. This will mount your local `input` and `output` directories into the container.

```bash
docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" pdf-extractor
```

The container will start, execute the `main.py` script, process every PDF in `/app/input`, and write the corresponding JSON files to `/app/output`. The `--rm` flag ensures the container is automatically removed after it finishes.

---

## 📥 Input and Output

### Input
-   **Format**: Standard PDF files (`.pdf`).
-   **Location**: Place files inside the `input/` directory before running the container.

### Output
-   **Format**: JSON (`.json`). For each `document.pdf` in the input, a `document.json` will be created.
-   **Location**: Results are saved in the `output/` directory.
-   **Structure**: The JSON file has two main keys: `title` and `outline`.

**Example `output.json`:**
```json
{
    "title": "A Framework for Adaptive Learning Systems",
    "outline": [
        {
            "level": "H1",
            "text": "1. Introduction",
            "page": 2
        },
        {
            "level": "H2",
            "text": "1.1. Background and Motivation",
            "page": 2
        },
        {
            "level": "H1",
            "text": "2. System Architecture",
            "page": 4
        },
        {
            "level": "H2",
            "text": "2.1. Data Ingestion Layer",
            "page": 5
        },
        {
            "level": "H2",
            "text": "2.2. Processing Core",
            "page": 6
        },
        {
            "level": "H1",
            "text": "3. Conclusion",
            "page": 9
        }
    ]
}
```

---

## 📦 Dependencies

The application relies on the following key Python library:

-   **PyMuPDF (`fitz`)**: A high-performance library for PDF parsing and text extraction.

All dependencies are listed in `requirements.txt` and are automatically installed when building the Docker image.

---

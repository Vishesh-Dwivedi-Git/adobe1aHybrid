import os
import json
import time
import logging
from pathlib import Path
from extractor import AdvancedPDFOutlineExtractor

# Configure basic logging to provide visibility into the process.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main execution function.
    - Defines input and output directories as per competition requirements.
    - Iterates through all PDF files in the input directory.
    - Processes each PDF to extract the title and outline.
    - Saves the result as a JSON file in the output directory.
    """
    # Define input and output directories relative to the container's /app/ directory.
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")

    # Ensure the output directory exists.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate the core extractor class.
    extractor = AdvancedPDFOutlineExtractor()

    # Check if the input directory exists and has PDF files.
    if not input_dir.is_dir():
        logging.error(f"Input directory not found: {input_dir}")
        return

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logging.warning(f"No PDF files found in {input_dir}")
        return

    logging.info(f"Found {len(pdf_files)} PDF(s) to process.")

    # Process each PDF file found in the input directory.
    for pdf_path in pdf_files:
        logging.info(f"Processing: {pdf_path.name}")
        start_time = time.time()

        # Generate the full path for the output JSON file.
        output_filename = pdf_path.stem + ".json"
        output_path = output_dir / output_filename

        try:
            # Call the main processing method of the extractor.
            result = extractor.process_pdf(str(pdf_path))

            # Write the extracted data to the corresponding JSON file.
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)

            processing_time = time.time() - start_time
            logging.info(
                f"Successfully processed {pdf_path.name} in {processing_time:.2f}s. "
                f"Output saved to {output_path}"
            )

        except Exception as e:
            # Handle potential errors during PDF processing.
            logging.error(f"Failed to process {pdf_path.name}: {e}", exc_info=True)
            # Create an error JSON file.
            error_result = {
                "title": f"Error processing {pdf_path.name}",
                "outline": [],
                "error": str(e)
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(error_result, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
OCR Helper for Scanned PDFs
===========================
Uses PyMuPDF to convert PDF pages to images, then RapidOCR to extract text.

Usage:
  python3 ocr_helper.py <input.pdf> <output_dir>

Dependencies:
  pip install rapidocr-onnxruntime pymupdf

Output:
  Saves OCR text to {output_dir}/text/_text_page_{N}.txt for each page
  Also saves a combined text file: {output_dir}/text/_ocr_combined.txt
"""

import sys
import os
import fitz  # pymupdf


def is_scanned_pdf(pdf_path: str, sample_pages: int = 5) -> bool:
    """
    Check if a PDF is scanned (image-based) by sampling pages.
    
    A PDF is considered scanned if:
    - Most pages have very little extractable text (< 50 chars per page)
    - Pages contain images but no text layers
    
    Args:
        pdf_path: Path to the PDF file
        sample_pages: Number of pages to sample (default: 5)
    
    Returns:
        True if the PDF appears to be scanned, False otherwise
    """
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    pages_to_check = min(sample_pages, total_pages)
    
    textless_pages = 0
    
    for i in range(pages_to_check):
        page = doc[i]
        text = page.get_text("text").strip()
        
        # If page has very little text, it's likely scanned
        if len(text) < 50:
            textless_pages += 1
    
    doc.close()
    
    # If most sampled pages have little text, consider it scanned
    return textless_pages >= pages_to_check * 0.8


def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 300) -> list:
    """
    Convert PDF pages to images using PyMuPDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save images
        dpi: Resolution for image conversion (default: 300)
    
    Returns:
        List of image file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    image_paths = []
    
    zoom = dpi / 72  # 72 is the default DPI
    mat = fitz.Matrix(zoom, zoom)
    
    for page_num in range(doc.page_count):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)
        
        img_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
    
    doc.close()
    
    return image_paths


def ocr_images(image_paths: list, output_dir: str) -> dict:
    """
    Use RapidOCR to extract text from images.
    
    Args:
        image_paths: List of image file paths
        output_dir: Directory to save OCR text files
    
    Returns:
        Dict mapping page number to extracted text
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except ImportError:
        print("[ERROR] rapidocr-onnxruntime is not installed.")
        print("Install it with: pip install rapidocr-onnxruntime")
        sys.exit(1)
    
    os.makedirs(output_dir, exist_ok=True)
    page_texts = {}
    
    for img_path in image_paths:
        # Extract page number from filename
        page_num = int(os.path.basename(img_path).replace("page_", "").replace(".png", ""))
        
        print(f"  OCR processing page {page_num}...")
        
        try:
            result, _ = ocr(img_path)
            
            if result:
                # Sort results by position (top to bottom)
                result.sort(key=lambda x: x[0][0][1])  # Sort by y-coordinate
                
                # Extract text lines
                lines = [item[1] for item in result]
                text = "\n".join(lines)
            else:
                text = ""
            
            page_texts[page_num] = text
            
            # Save individual page text
            txt_path = os.path.join(output_dir, f"_text_page_{page_num}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
        
        except Exception as e:
            print(f"  [WARN] OCR failed for page {page_num}: {e}")
            page_texts[page_num] = ""
    
    # Save combined text
    combined_path = os.path.join(output_dir, "_ocr_combined.txt")
    with open(combined_path, "w", encoding="utf-8") as f:
        for page_num in sorted(page_texts.keys()):
            f.write(f"\n=== Page {page_num} ===\n\n")
            f.write(page_texts[page_num])
    
    return page_texts


def ocr_scanned_pdf(pdf_path: str, output_dir: str, dpi: int = 300) -> dict:
    """
    Full OCR pipeline for scanned PDFs.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save OCR results
        dpi: Resolution for image conversion (default: 300)
    
    Returns:
        Dict mapping page number to extracted text
    """
    img_dir = os.path.join(output_dir, "images")
    
    print("Converting PDF pages to images...")
    image_paths = pdf_to_images(pdf_path, img_dir, dpi)
    
    print(f"Processing {len(image_paths)} pages with OCR...")
    page_texts = ocr_images(image_paths, output_dir)
    
    print(f"OCR complete! Text saved to: {output_dir}")
    
    return page_texts


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 ocr_helper.py <input.pdf> <output_dir>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found: {pdf_path}")
        sys.exit(1)
    
    # Check if PDF is scanned
    print("Checking if PDF is scanned...")
    if is_scanned_pdf(pdf_path):
        print("PDF appears to be scanned (image-based).")
        print("Running OCR pipeline...")
        ocr_scanned_pdf(pdf_path, output_dir)
    else:
        print("PDF contains text layers (not scanned).")
        print("Use pdf2mindmap.py instead for text-based PDFs.")


if __name__ == "__main__":
    main()

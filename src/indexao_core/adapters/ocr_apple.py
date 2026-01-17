import sys
import os
from pathlib import Path
from typing import List, Optional

# Only import PyObjC frameworks if on Darwin
if sys.platform == "darwin":
    import Quartz
    import Vision
    from Cocoa import NSURL
    from AppKit import NSImage
else:
    pass

class AppleVisionOCR:
    """
    OCR Adapter using native macOS Vision Framework.
    Optimized for Apple Silicon.
    """
    
    def __init__(self):
        if sys.platform != "darwin":
            raise RuntimeError("AppleVisionOCR requires macOS.")

    def extract_text(self, file_path: str) -> str:
        """
        Extract text from an image or PDF file.
        Detects file type and dispatches accordingly.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        suffix = path.suffix.lower()
        
        if suffix == ".pdf":
            return self._process_pdf(str(path))
        elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".heic"]:
            return self._process_image(str(path))
        else:
            raise ValueError(f"Unsupported file type for OCR: {suffix}")

    def _process_image(self, image_path: str) -> str:
        """Process a single image file."""
        url = NSURL.fileURLWithPath_(image_path)
        return self._recognize_text_in_image(url)

    def _process_pdf(self, pdf_path: str) -> str:
        """
        Process a PDF file page by page.
        Convert PDF pages to images then run OCR.
        """
        url = NSURL.fileURLWithPath_(pdf_path)
        pdf_doc = Quartz.PDFDocument.alloc().initWithURL_(url)
        
        if not pdf_doc:
            raise ValueError(f"Could not open PDF: {pdf_path}")
            
        page_count = pdf_doc.pageCount()
        full_text = []
        
        for i in range(page_count):
            page = pdf_doc.pageAtIndex_(i)
            # Render the page to TIFF Data (safest way to pass to Vision)
            tiff_data = render_pdf_page_to_tiff_data(page)
            if tiff_data:
                text = self._recognize_text_in_data(tiff_data)
                full_text.append(f"--- Page {i+1} ---\n{text}")
            else:
                full_text.append(f"--- Page {i+1} ---\n[Error: Could not render page]")
                
        return "\n\n".join(full_text)

    def _recognize_text_in_data(self, data) -> str:
        request_handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        return self._perform_request(request_handler)

    def _recognize_text_in_image(self, image_url) -> str:
        request_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
        return self._perform_request(request_handler)

    def _perform_request(self, request_handler) -> str:
        request = Vision.VNRecognizeTextRequest.alloc().init()
        
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setUsesLanguageCorrection_(True)
        # Using Traditional + Simplified Chinese as preference triggers, plus English
        # This order matters for verification
        request.setRecognitionLanguages_(["zh-Hant", "zh-Hans", "en-US"])
        
        success, error = request_handler.performRequests_error_([request], None)
        
        if not success:
            print(f"OCR Error: {error}")
            return ""
            
        observations = request.results()
        text_lines = []
        for observation in observations:
            candidate = observation.topCandidates_(1)[0]
            text_lines.append(candidate.string())
            
        return "\n".join(text_lines)

def render_pdf_page_to_tiff_data(page):
    """
    Helper to convert PDFPage to TIFF NSData.
    """
    rect = page.boundsForBox_(Quartz.kPDFDisplayBoxMediaBox)
    
    # Scale x3 for ~216 DPI (72 * 3), decent for OCR without exploding memory
    scale = 3.0 
    target_size = (rect.size.width * scale, rect.size.height * scale)
    
    # thumbnailOfSize generates an NSImage
    ns_image = page.thumbnailOfSize_forBox_(target_size, Quartz.kPDFDisplayBoxMediaBox)
    
    if ns_image:
        return ns_image.TIFFRepresentation()
    return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ocr = AppleVisionOCR()
        try:
            print(ocr.extract_text(sys.argv[1]))
        except Exception as e:
            print(f"Error: {e}")

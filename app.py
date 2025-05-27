from flask import Flask, request, jsonify
import requests
import pdfplumber
import PyPDF2
import io
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_with_pdfplumber(pdf_bytes):
    """Extract text using pdfplumber (best for complex layouts)"""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {str(e)}")
        return None

def extract_text_with_pypdf2(pdf_bytes):
    """Fallback extraction using PyPDF2"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {str(e)}")
        return None

def download_pdf(url):
    """Download PDF from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Check if it's actually a PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type:
            logger.warning(f"Content type is {content_type}, not PDF")
        
        return response.content
    except Exception as e:
        logger.error(f"Failed to download PDF: {str(e)}")
        return None

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "PDF Text Extraction Service",
        "version": "1.0"
    })

@app.route('/extract-pdf', methods=['POST'])
def extract_pdf():
    """Extract text from PDF URL"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "error": "Missing 'url' parameter"
            }), 400
        
        pdf_url = data['url']
        logger.info(f"Processing PDF: {pdf_url}")
        
        # Download PDF
        pdf_bytes = download_pdf(pdf_url)
        if not pdf_bytes:
            return jsonify({
                "error": "Failed to download PDF",
                "url": pdf_url
            }), 400
        
        # Try pdfplumber first
        extracted_text = extract_text_with_pdfplumber(pdf_bytes)
        
        # Fallback to PyPDF2 if pdfplumber fails
        if not extracted_text or len(extracted_text.strip()) < 10:
            logger.info("Trying PyPDF2 as fallback")
            extracted_text = extract_text_with_pypdf2(pdf_bytes)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            return jsonify({
                "error": "Could not extract readable text from PDF",
                "url": pdf_url,
                "extracted_length": len(extracted_text) if extracted_text else 0
            }), 400
        
        return jsonify({
            "success": True,
            "text": extracted_text,
            "length": len(extracted_text),
            "url": pdf_url
        })
        
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/extract-multiple', methods=['POST'])
def extract_multiple_pdfs():
    """Extract text from multiple PDF URLs"""
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data:
            return jsonify({
                "error": "Missing 'urls' parameter (should be array)"
            }), 400
        
        urls = data['urls']
        if not isinstance(urls, list):
            return jsonify({
                "error": "'urls' should be an array"
            }), 400
        
        results = []
        
        for i, url in enumerate(urls):
            logger.info(f"Processing PDF {i+1}/{len(urls)}: {url}")
            
            # Download PDF
            pdf_bytes = download_pdf(url)
            if not pdf_bytes:
                results.append({
                    "url": url,
                    "success": False,
                    "error": "Failed to download PDF"
                })
                continue
            
            # Extract text
            extracted_text = extract_text_with_pdfplumber(pdf_bytes)
            
            # Fallback to PyPDF2
            if not extracted_text or len(extracted_text.strip()) < 10:
                extracted_text = extract_text_with_pypdf2(pdf_bytes)
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                results.append({
                    "url": url,
                    "success": False,
                    "error": "Could not extract readable text"
                })
            else:
                results.append({
                    "url": url,
                    "success": True,
                    "text": extracted_text,
                    "length": len(extracted_text)
                })
        
        return jsonify({
            "success": True,
            "results": results,
            "total_processed": len(urls)
        })
        
    except Exception as e:
        logger.error(f"Multiple extraction error: {str(e)}")
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)

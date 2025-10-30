# main.py - Combined, Robust, and Efficient Bill Parser

import io
import re
import uuid
from datetime import date
from typing import List, Optional, Dict
# In parser.py (at the top)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from google.cloud import vision


import pdfplumber
import pytesseract
from dateutil.parser import parse as parse_date
from fastapi import FastAPI, File, UploadFile, HTTPException
from pdf2image import convert_from_bytes
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
import pandas as pd
from validator import run_validations
from models import ParsedBill, ValidationResult, LineItem, ExplanationResponse, AppealDraftResponse, Citation, ValidationFlag
from llm_service import get_llm_response
from prompts import SYSTEM_PROMPT, get_explanation_prompt_with_rag, get_appeal_draft_prompt_with_rag
from rag_service import rag_service
from models import ValidationResultInput 
from google.oauth2 import service_account 
# =====================================================================================
# 1. CONFIGURATION & PRE-COMPILED REGEX
# =====================================================================================
# For Windows users: If Tesseract/Poppler are not in your system's PATH,
# uncomment and set the correct paths below.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# POPPLER_PATH = r"C:\path\to\poppler\bin"

# Pre-compiling regex improves performance for repeated use.
# These patterns are designed to be more flexible.
PROVIDER_PATTERN = re.compile(r"\b(?:Provider|Billed by|From|Clinic|Hospital)[:\s]*([^\n\r]*)", re.IGNORECASE)
PATIENT_NAME_PATTERN = re.compile(r"\b(?:Patient Name|Patient|For|Billed to|To)\b[:\s]*([^\n\r]*)", re.IGNORECASE)
CLAIM_ID_PATTERN = re.compile(r"(?:Claim Number|Claim #|EOB ID)[:\s#]*([\w\s-]+?)\s*\n", re.IGNORECASE)
DATE_PATTERN = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE)

# New, more flexible patterns for EOBs
TOTAL_BILLED_PATTERN = re.compile(r"(?:Total Charges|Totals|Hospital charges)[:\s$]*([\d,]+\.\d{2})", re.IGNORECASE)
PATIENT_RESPONSIBILITY_PATTERN = re.compile(r"(?:You pay|Your total cost|Patient Responsibility)[:\s$]*([\d,]+\.\d{2})", re.IGNORECASE)

# Updated Line Item pattern to be more flexible (CPT is now optional)
LINE_ITEM_PATTERN = re.compile(
    r"(\d{2}[/-]\d{2}[/-]\d{2,4})\s+"  # 1: Date of Service
    r"(.*?)\s{2,}"                      # 2: Description (looks for 2+ spaces as a separator)
    r"(\$?[\d,]+\.\d{2})"             # 3: Billed Amount
    , re.IGNORECASE | re.MULTILINE
)
CPT_PATTERN = re.compile(r"\b(\d{4}[A-Z0-9])\b")
ICD_PATTERN = re.compile(r"\b([A-TV-Z][0-9][A-Z0-9](?:\.[A-Z0-9]{1,4})?)\b", re.IGNORECASE)
# =====================================================================================
# 2. PYDANTIC SCHEMAS (Data Structure)
# =====================================================================================

# Moved to models.py for better modularity
# =====================================================================================
# 3. HELPER & PARSING FUNCTIONS
# =====================================================================================

def clean_amount(amount_str: Optional[str]) -> Optional[float]:
    """Safely removes currency symbols, commas, and converts a string to a float."""
    if not amount_str:
        return None
    try:
        # Remove common currency symbols, commas, and whitespace
        cleaned_str = re.sub(r'[$,\s]', '', amount_str)
        return float(cleaned_str)
    except (ValueError, TypeError):
        return None

def parse_date_safely(date_str: Optional[str]) -> Optional[date]:
    """Safely parses a string into a date object, handling various formats."""
    if not date_str:
        return None
    try:
        # dateutil.parser is very flexible and can handle most common date formats
        return parse_date(date_str).date()
    except (ValueError, TypeError):
        return None

def find_best_match(pattern: re.Pattern, text: str) -> Optional[str]:
    """Finds the first match of a compiled regex pattern in the text."""
    match = pattern.search(text)
    if match:
        # Return the first capturing group if it exists, otherwise the full match
        return match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
    return None
# In parser.py

def parse_line_items(text: str, pricing_data: Dict[str, float]) -> List[LineItem]:
    """Finds and parses all service line items in the text, now more flexible for EOBs."""
    line_items = []
    # This regex is now designed for EOBs that may not have CPT codes.
    # It looks for a date, some text, and a price on the same line.
    eob_line_pattern = re.compile(
        r"^(\d{2}/\d{2}/\d{2,4})\s+" # 1: Date
        r".*?\s+"                      # Intermediate text we don't need
        r"([\d,]+\.\d{2})"             # 2: Billed Amount (charges)
        r".*?\s+"                      # More intermediate text
        r"([\d,]+\.\d{2})$"            # 3: Patient Responsibility for this line
        , re.MULTILINE
    )

    for match in eob_line_pattern.finditer(text):
        try:
            # We don't have a CPT, so we'll use the date as the key identifier
            desc = f"Service on {match.group(1)}"
            billed = clean_amount(match.group(2))
            
            line_items.append(
                LineItem(
                    cpt_code=None, # Explicitly state no CPT code was found
                    description=desc,
                    billed_amount=billed,
                    national_average_price=None
                )
            )
        except IndexError:
            continue
    return line_items

def parse_bill_text(text: str, pricing_data: Dict[str, float]) -> ParsedBill:
    """
    Parses raw text from a medical bill with smarter logic for EOBs.
    """
    # --- Step 1: Extract all potential fields ---
    provider = find_best_match(PROVIDER_PATTERN, text)
    patient_name = find_best_match(PATIENT_NAME_PATTERN, text)
    claim_id = find_best_match(CLAIM_ID_PATTERN, text)
    dos_date_str = find_best_match(DATE_PATTERN, text)
    
    # Try our new EOB-specific patterns first
    total_billed_str = find_best_match(TOTAL_BILLED_PATTERN, text)
    if not total_billed_str:
        # Fallback for invoices
        total_billed_str = find_best_match(re.compile(r"Amount Due[:\s$]*([\d,]+\.\d{2})"), text)
        
    patient_responsibility_str = find_best_match(PATIENT_RESPONSIBILITY_PATTERN, text)
    
    line_items = parse_line_items(text, pricing_data)
    
    # --- Step 2: Intelligent Provider/Patient Cleanup ---
    # If the provider or patient name contains conversational text, nullify it.
    if provider and "benefits" in provider:
        provider = None
    if patient_name and "benefits" in patient_name:
        patient_name = None

    cpt_codes = list(set(CPT_PATTERN.findall(text)))
    icd_codes = list(set(ICD_PATTERN.findall(text, re.IGNORECASE)))
    
    # If total billed is still zero, but we have a patient responsibility, use that.
    final_billed = clean_amount(total_billed_str)
    if not final_billed or final_billed == 0:
        final_billed = clean_amount(patient_responsibility_str)

    bill_data = ParsedBill(
        provider=provider,
        patient_name=patient_name,
        claim_id=claim_id,
        date_of_service=parse_date_safely(dos_date_str),
        line_items=line_items,
        total_billed=final_billed,
        cpt_codes=cpt_codes,
        icd_codes=icd_codes,
        raw_text=text
    )
    return bill_data


# =====================================================================================
# 4. OCR & FILE PROCESSING LOGIC
# =====================================================================================

# In parser.py

# --- Make sure these imports are at the top of your parser.py file ---
from google.cloud import vision
from google.oauth2 import service_account # New import for explicit credentials
import os
import json

# Load Google API Vision credentials if needed
credentials_path = r"C:\bill_parser\google_api_vision.json"  # Update this path as needed

# --- This is the new, upgraded OCR function with explicit credential loading ---

async def extract_text_from_file(file_content: bytes, content_type: str) -> str:
    """
    Extracts raw text from a file, prioritizing Google Vision API for high accuracy
    and falling back to pytesseract for resilience.
    """
    text = ""
    
    # --- 1. Attempt to use Google Vision API (High Accuracy) ---
    # Get the credentials path from the environment variable we set in .env
    # In parser.py, inside extract_text_from_file
    credentials_path = r"C:\bill_parser\google_api_vision.json"
    
    if credentials_path and os.path.exists(credentials_path):
        try:
            print(f"Attempting OCR with Google Cloud Vision using credentials at: {credentials_path}")
            
            # --- THIS IS THE CRITICAL FIX ---
            # Manually load the credentials from the specified file path.
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            client = vision.ImageAnnotatorClient(credentials=credentials)
            # --------------------------------
            
            image = vision.Image(content=file_content)
            response = client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f"Google Vision API Error: {response.error.message}")
            
            if response.full_text_annotation:
                text = response.full_text_annotation.text.strip()
                print("Google Cloud Vision OCR successful.")
        except FileNotFoundError:
             print(f"FATAL ERROR: Google credentials file not found at path: {credentials_path}. Check your .env file.")
             text = "" # Ensure fallback
        except Exception as e:
            print(f"WARNING: Google Cloud Vision failed ({e}). Falling back to pytesseract.")
            text = "" # Ensure fallback
    else:
        print("INFO: Google Cloud credentials not configured or file not found. Using pytesseract as default.")

    # --- 2. Fallback to pytesseract/pdfplumber ---
    if not text:
        # ... (The entire fallback logic for pytesseract and pdfplumber remains exactly the same) ...
        print("Using fallback OCR (pytesseract/pdfplumber)...")
        if content_type == "application/pdf":
            try:
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    full_text = "".join(page.extract_text() or "" for page in pdf.pages)
                text = full_text.strip()
            except Exception:
                text = ""

            if len(text) < 100:
                text = ""
                try:
                    images = convert_from_bytes(file_content)
                    ocr_text = "".join(pytesseract.image_to_string(img) for img in images)
                    text = ocr_text.strip()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"PDF processing failed during OCR fallback: {e}")

        elif content_type in ["image/jpeg", "image/png"]:
            try:
                image = Image.open(io.BytesIO(file_content))
                text = pytesseract.image_to_string(image).strip()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Image processing failed with pytesseract: {e}")

    if not text:
        raise HTTPException(status_code=422, detail="All OCR methods failed to extract any text from the document.")
        
    return text

# --- Load datasets into memory on application startup ---
try:
    pricing_df = pd.read_csv("cpt_pricing_data.csv", dtype={'cpt_code': str})    # Create a dictionary for fast lookups: {cpt_code: median_price}
    PRICING_DATA = pd.Series(pricing_df.median_price.values, index=pricing_df.cpt_code).to_dict()
except FileNotFoundError:
    print("WARNING: cpt_pricing_data.csv not found. Pricing validation will be disabled.")
    PRICING_DATA = {}
# =====================================================================================
# 5. FASTAPI APPLICATION & API ENDPOINTS
# =====================================================================================

app = FastAPI(
    title="Bill Ingestion & OCR API",
    description="An API to upload medical bills and extract structured data.",
    version="1.0.0", # Version bump for this robust release
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True) # This safely creates the 
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# =====================================================================================
@app.get("/", response_class=HTMLResponse, tags=["UI"], summary="Main User Interface")
async def serve_ui():
 """Serves the main single-page application UI."""
 try:
   with open(os.path.join(static_dir, "index.html")) as f:
    return HTMLResponse(content=f.read(), status_code=200)
 except FileNotFoundError:
   return HTMLResponse(content="<h1>UI not found. Please create a static/index.html file.</h1>", status_code=404)
@app.post("/validate-bill/", response_model=ValidationResult, tags=["Bill Processing"], summary="Upload, Parse, and Validate a Medical Bill")
async def parse_bill(file: UploadFile = File(..., description="A medical bill file (PDF, JPG, or PNG).")):
    """
    This endpoint performs a full pipeline:
    1.  Validates the uploaded file type.
    2.  Reads the file content.
    3.  Extracts text using OCR or direct extraction.
    4.  Parses the raw text to find key-value pairs.
    5.  Returns a structured JSON object.
    """
    # --- 1. Validate File Type ---
    allowed_content_types = ["application/pdf", "image/jpeg", "image/png","text/plain"]
    if file.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type '{file.content_type}'. Please upload a PDF, JPG, or PNG.")

    # --- 2. Read File Content ---
    # Reading the entire file into memory is acceptable for typical bill sizes.
    # For very large files, a streaming approach would be more memory-efficient.
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read the uploaded file: {e}")

    # --- 3. Extract Text ---
    extracted_text = await extract_text_from_file(file_content, file.content_type)
    if not extracted_text:
        raise HTTPException(status_code=422, detail="Could not extract any text from the document. It may be empty or unreadable.")

    # --- 4. Parse Text ---
    try:
        parsed_data = parse_bill_text(extracted_text, PRICING_DATA)
    except Exception as e:
        # This catches unexpected errors during the parsing logic itself.
        raise HTTPException(status_code=500, detail=f"An error occurred during text parsing: {e}")
    # --- 4b. Run Validations ---
    flags = run_validations(parsed_data, PRICING_DATA) if PRICING_DATA else []

    # --- 5. Return Result ---
    return ValidationResult(parsed_data=parsed_data, flags=flags)
# =====================================================================================
# 6. PHASE 3 - LLM ENDPOINTS
# =====================================================================================

def format_context(retrieved_docs: list[tuple[dict, float]]) -> str:
    """Helper function to format retrieved documents into a string for the prompt."""
    if not retrieved_docs:
        return "No relevant context found in the knowledge base."
    
    context_str = ""
    for doc, score in retrieved_docs:
        context_str += f"Source Content (Relevance Score: {score:.2f}):\n{doc['content']}\n\n"
    return context_str.strip()
# Define the weights for our scoring algorithm
RULE_CONFIDENCE_WEIGHT = 0.6  # The deterministic rule is the most important signal
RETRIEVAL_SCORE_WEIGHT = 0.4  # The RAG evidence quality is the secondary signal

def calculate_final_confidence(flags: List[ValidationFlag], retrieved_docs_with_scores: list[tuple[dict, float]]) -> List[ValidationFlag]:
    """
    Calculates the final confidence score for each flag based on its rule confidence
    and the relevance of the retrieved RAG context.
    """
    # Find the highest relevance score from all retrieved docs. This represents
    # the "best evidence" we found for the set of flags.
    max_retrieval_score = 0.0
    if retrieved_docs_with_scores:
        max_retrieval_score = max([score for doc, score in retrieved_docs_with_scores])

    updated_flags = []
    for flag in flags:
        # Calculate the weighted average
        final_score = (flag.rule_confidence * RULE_CONFIDENCE_WEIGHT) + (max_retrieval_score * RETRIEVAL_SCORE_WEIGHT)
        
        # Update the flag object with the new scores
        flag.retrieval_score = round(max_retrieval_score, 4)
        flag.final_confidence = round(final_score, 4)
        updated_flags.append(flag)

    return updated_flags

@app.post("/explain-bill/", response_model=ExplanationResponse, tags=["LLM Services"], summary="Explain a Bill with RAG Citations")
async def explain_bill(result: ValidationResultInput):
    """
    Accepts validated bill JSON, retrieves relevant context from a vector DB,
    and uses an LLM to generate a cited explanation of the bill's issues.
    """
    # --- DATA CONVERSION BRIDGE ---
    # Convert the raw input flags into the richer internal ValidationFlag format.
    # This is the crucial step that fixes the schema mismatch.
    internal_flags = [
        ValidationFlag(
            flag_id=f.flag_id,
            flag_type=f.flag_type,
            message=f.message,
            rule_confidence=f.confidence, # Map 'confidence' to 'rule_confidence'
            final_confidence=0 # Temporary value, will be calculated next
        ) for f in result.flags
    ]
    # --- RAG Retrieval Step ---
    all_retrieved_docs = []
    retrieved_docs_with_scores = []
    scored_flags = internal_flags 
    
    # Perform retrieval only if there are flags to investigate
    if internal_flags:
        query = " ".join([flag.message for flag in internal_flags])
        retrieved_docs_with_scores = rag_service.retrieve_context(query)
        all_retrieved_docs = [doc for doc, score in retrieved_docs_with_scores]
        scored_flags = calculate_final_confidence(internal_flags, retrieved_docs_with_scores)
    context_str = format_context(retrieved_docs_with_scores)
    # --- LLM Composition Step ---
    final_validation_result = ValidationResult(parsed_data=result.parsed_data, flags=scored_flags)
    validation_json_str = final_validation_result.model_dump_json(indent=2)
    prompt = get_explanation_prompt_with_rag(validation_json_str, context_str)
    
    explanation = await get_llm_response(prompt, SYSTEM_PROMPT)

    citations = [Citation(**doc) for doc in all_retrieved_docs]
    
    return ExplanationResponse(explanation_text=explanation, citations=citations, flags=scored_flags)


# In parser.py

@app.post("/draft-appeal/", response_model=AppealDraftResponse, tags=["LLM Services"], summary="Draft an Appeal Letter with RAG Citations")
async def draft_appeal(result: ValidationResultInput):
    """
    Accepts validated bill JSON, retrieves context, and uses an LLM to
    draft a formal appeal letter strengthened with citations.
    """
    # --- DATA CONVERSION BRIDGE ---
    # Convert the raw input flags into the richer internal ValidationFlag format.
    # This fixes the schema mismatch from the /validate-bill/ endpoint.
    internal_flags = [
        ValidationFlag(
            flag_id=f.flag_id,
            flag_type=f.flag_type,
            message=f.message,
            rule_confidence=f.confidence, # Map 'confidence' to 'rule_confidence'
            final_confidence=0 # Temporary value, will be calculated next
        ) for f in result.flags
    ]

    # --- RAG Retrieval and Confidence Scoring Step ---
    all_retrieved_docs = []
    retrieved_docs_with_scores = []
    # Default to the initial flags; they will be updated if retrieval is successful
    scored_flags = internal_flags
    
    # Perform retrieval and scoring only if there are flags to investigate
    if internal_flags:
        query = " ".join([flag.message for flag in internal_flags])
        retrieved_docs_with_scores = rag_service.retrieve_context(query)
        all_retrieved_docs = [doc for doc, score in retrieved_docs_with_scores]
        
        # Calculate the final confidence scores and update the flags
        scored_flags = calculate_final_confidence(internal_flags, retrieved_docs_with_scores)

    context_str = format_context(retrieved_docs_with_scores)
    
    # --- LLM Composition Step ---
    # Create the final, enriched object to send to the LLM.
    # This object now contains the final, calculated confidence scores.
    final_validation_result = ValidationResult(parsed_data=result.parsed_data, flags=scored_flags)
    validation_json_str = final_validation_result.model_dump_json(indent=2)
    prompt = get_appeal_draft_prompt_with_rag(validation_json_str, context_str)
    
    appeal_draft = await get_llm_response(prompt, SYSTEM_PROMPT)

    # --- Create Citations for the Final Response ---
    citations = [Citation(**doc) for doc in all_retrieved_docs]

    return AppealDraftResponse(appeal_draft_text=appeal_draft, citations=citations, flags=scored_flags)

 
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
import uuid
# In models.py

class LineItem(BaseModel):
    """Represents a single line item from a bill."""
    cpt_code: Optional[str] = Field(None, description="The CPT code for the service.")
    description: Optional[str] = Field(None, description="The description of the service.")
    billed_amount: Optional[float] = Field(None, description="The amount billed for this specific service.")
    # --- ADD THIS NEW FIELD ---
    national_average_price: Optional[float] = Field(None, description="The CMS national average price for this service (non-facility).")
class ParsedBill(BaseModel):
    """Defines the structured JSON output for a parsed bill."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID for this processing session.")
    provider: Optional[str] = Field(None, description="The name of the medical provider or clinic.")
    patient_name: Optional[str] = Field(None, description="The name of the patient.") # <-- ADD THIS
    claim_id: Optional[str] = Field(None, description="The claim or EOB identification number.") # <-- ADD THIS
    date_of_service: Optional[date] = Field(None, description="The primary date of service found on the bill.")
    total_billed: Optional[float] = Field(None, description="The total amount billed to the patient.")
    line_items: List[LineItem] = Field(default_factory=list, description="List of all service line items found.") 
    cpt_codes: List[str] = Field(default_factory=list, description="List of unique CPT codes found.")
    icd_codes: List[str] = Field(default_factory=list, description="List of unique ICD-10 codes found.")
    raw_text: str = Field(..., description="The full raw text extracted from the document for debugging.")
# In models.py

class ValidationFlag(BaseModel):
    """Represents a single deterministic issue found in the bill, enriched with confidence scores."""
    flag_id: str = Field(..., description="A unique identifier for the type of flag.")
    flag_type: str = Field(..., description="The category of the flag (e.g., 'warning', 'error').")
    message: str = Field(..., description="A human-readable explanation of the issue.")
    rule_confidence: float = Field(..., description="The base confidence from the deterministic rule (0.0 to 1.0).")
    retrieval_score: Optional[float] = Field(None, description="The retrieval score from the knowledge base (0.0 to 1.0), if applicable.")
    final_confidence: Optional[float] = Field(None, description="The final combined confidence score (0.0 to 1.0).")    

class ValidationResult(BaseModel):
    """The final API response, including parsed data and validation flags."""
    parsed_data: ParsedBill
    flags: List[ValidationFlag]
# In models.py (at the end of the file)

class Citation(BaseModel):
    """Represents a single piece of evidence retrieved from the knowledge base."""
    source: str
    content: str

class ExplanationResponse(BaseModel):
    """The structured response for a bill explanation with citations."""
    explanation_text: str
    citations: List[Citation] = []
    flags: List[ValidationFlag] = Field([], description="The final, scored list of flags that were analyzed.") # <-- ADD THIS

class AppealDraftResponse(BaseModel):
    """The structured response for a generated appeal letter with citations."""
    appeal_draft_text: str
    citations: List[Citation] = []
    flags: List[ValidationFlag] = Field([], description="The final, scored list of flags that were analyzed.") # <-- ADD THIS
class FlagInput(BaseModel):
    """Represents the raw flag data coming from the validation endpoint."""
    flag_id: str
    flag_type: str
    # This is the key change: it expects the OLD field name
    confidence: float
    message: str


class ValidationResultInput(BaseModel):
    """Represents the exact JSON structure we expect as input for the LLM endpoints."""
    parsed_data: ParsedBill
    flags: List[FlagInput]
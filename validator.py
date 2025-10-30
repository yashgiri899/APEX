# validator.py

from typing import List, Dict
# We need to import the models from our main parser file
from models import ParsedBill, ValidationFlag

# --- RULE 1: Check for Missing Claim ID ---
def check_missing_claim_id(parsed_bill: ParsedBill) -> ValidationFlag | None:
    """Flags bills that are likely EOBs but are missing a claim ID."""
    # This heuristic can be improved, e.g., by checking for "Explanation of Benefits" in raw_text
    is_eob = "eob" in parsed_bill.raw_text.lower() or "explanation of benefits" in parsed_bill.raw_text.lower()
    
    if is_eob and not parsed_bill.claim_id:
        return ValidationFlag(
            flag_id="missing_claim_id",
            flag_type="warning",
            rule_confidence=0.95,
            message="This document appears to be an EOB but is missing a Claim ID."
        )
    return None

# --- RULE 2: Check for Outlier Pricing ---
# In validator.py

# --- RULE 2 (REVISED): Check for Outlier Pricing on a Line-Item Basis ---
def check_outlier_pricing(parsed_bill: ParsedBill, pricing_data: Dict[str, float]) -> List[ValidationFlag]:
    """
    Flags individual CPT codes with billed amounts far exceeding the median price.
    This rule is robust and works on a per-line-item basis.
    """
    flags = []
    OVERCHARGE_THRESHOLD = 5.0  # Flag if billed amount is > 5x the median.

    # Pre-condition: This check is impossible without parsed line items.
    if not parsed_bill.line_items:
        return flags

    # Iterate through each service line we found on the bill.
    for item in parsed_bill.line_items:
        # --- Robustness Check 1: Ensure the line item is usable ---
        # Skip any line items where the CPT code or amount couldn't be parsed.
        if not item.cpt_code or item.billed_amount is None:
            continue

        # --- Robustness Check 2: Ensure we have pricing data for this code ---
        if item.cpt_code in pricing_data:
            median_price = pricing_data[item.cpt_code]

            # --- Robustness Check 3: Avoid division by zero or invalid data ---
            if median_price <= 0:
                continue

            # --- The Core Logic: Compare the line item's price to the median ---
            if item.billed_amount > (median_price * OVERCHARGE_THRESHOLD):
                # Calculate the multiplier to create a more helpful message.
                times_median = item.billed_amount / median_price

                # Create a highly specific and actionable flag.
                
                flags.append(ValidationFlag(
                    flag_id="outlier_pricing_line_item",
                    flag_type="warning",
                    message=(
                        f"Line item for CPT {item.cpt_code} billed at ${item.billed_amount:,.2f} "
                        f"is ~{times_median:.1f}x the median price of ${median_price:,.2f}."
                    ),
                    # --- THIS IS THE CRITICAL FIX ---
                    # Provide the required base confidence. The final score will be calculated later.
                    rule_confidence=0.90,
                    final_confidence=0  # Provide a temporary default value.
                ))
    return flags
# --- RULE 3: Check for Common Denial Reasons ---
def check_denial_reasons(parsed_bill: ParsedBill) -> List[ValidationFlag]:
    """Scans the raw text for keywords indicating a claim denial."""
    flags = []
    
    # A list of common denial phrases. This can be expanded.
    # We use lowercase to make the search case-insensitive.
    DENIAL_KEYWORDS = [
        "denied",
        "denial",
        "not covered",
        "not a covered benefit",
        "lack of documentation",
        "out of network",
        "prior authorization required",
        "service not medically necessary"
    ]

    raw_text_lower = parsed_bill.raw_text.lower()

    for keyword in DENIAL_KEYWORDS:
        if keyword in raw_text_lower:
            flags.append(ValidationFlag(
                flag_id="denial_reason_found",
                flag_type="critical", # This is a more severe flag
                rule_confidence=0.98,
                message=f"Potential denial detected. Found keyword: '{keyword}'."
            ))

    # To avoid returning multiple flags for the same denial, we'll return only the first one found.
    # In a more advanced system, you might group them.
    return flags[:1]
def check_duplicates(parsed_bill: ParsedBill) -> List[ValidationFlag]:
    """Finds duplicate line items (same CPT and billed amount)."""
    flags = []
    seen_items = set()

    # We need at least 2 line items to have a duplicate
    if len(parsed_bill.line_items) < 2:
        return flags

    for item in parsed_bill.line_items:
        # A unique identifier for a line item is its code and price
        # We skip items where parsing might have failed
        if not item.cpt_code or item.billed_amount is None:
            continue

        item_tuple = (item.cpt_code, item.billed_amount)
        
        if item_tuple in seen_items:
            # We've seen this exact item before, it's a duplicate
            flags.append(ValidationFlag(
                flag_id="duplicate_line_item",
                flag_type="error", # Duplicates are a serious issue
                rule_confidence=1.0, # This is a deterministic check
                message=f"Duplicate line item found: CPT {item.cpt_code} for ${item.billed_amount:,.2f}."
            ))
        else:
            seen_items.add(item_tuple)
    
    return flags
def check_invalid_cpt_codes(parsed_bill: ParsedBill, valid_codes: set) -> List[ValidationFlag]:
    """Flags any CPT code that does not exist in the official fee schedule."""
    flags = []
    if not parsed_bill.line_items:
        return flags

    for item in parsed_bill.line_items:
        if item.cpt_code and item.cpt_code not in valid_codes:
            flags.append(ValidationFlag(
                flag_id="invalid_cpt_code",
                flag_type="error",
                
                rule_confidence=1.0, # This is a very certain error
                message=f"Invalid or non-billable CPT code found: {item.cpt_code}."
            ))
    return flags
# --- Main Orchestrator ---
def run_validations(parsed_bill: ParsedBill, pricing_data: Dict[str, float]) -> List[ValidationFlag]:
    """
    Runs all configured validation rules and returns a list of flags.
    """
    all_flags = []
    valid_cpt_codes_set = set(pricing_data.keys())

    # Run Rule 1
    flag1 = check_missing_claim_id(parsed_bill)
    if flag1:
        all_flags.append(flag1)

    # Run Rule 2
    flags2 = check_outlier_pricing(parsed_bill, pricing_data)
    all_flags.extend(flags2)
    
    # --- ADD THIS SECTION FOR THE NEW RULE ---
    # Run Rule 3
    flags3 = check_denial_reasons(parsed_bill)
    all_flags.extend(flags3)
    flags4 = check_duplicates(parsed_bill)
    all_flags.extend(flags4)
    # ----------------------------------------
    flags5 = check_invalid_cpt_codes(parsed_bill, valid_cpt_codes_set)
    all_flags.extend(flags5)

    return all_flags
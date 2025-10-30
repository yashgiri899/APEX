
# prompts.py

SYSTEM_PROMPT = """You are an expert US medical billing analyst. Your task is to help a patient understand their medical bill and take action on potential issues. You must be formal, accurate, and base your entire response ONLY on the JSON data and the authoritative context provided. You must cite your sources.
"""

def get_explanation_prompt_with_rag(validation_result: str, context: str) -> str:
    """Creates the prompt for explaining a bill using retrieved context."""
    return f"""
<INSTRUCTIONS>
A patient needs help understanding their medical bill. Your task is to provide a clear, concise explanation based ONLY on the provided JSON data and the authoritative context.

**Follow these steps exactly:**
1.  Provide a brief, one-sentence summary of the bill.
2.  Create a section titled "Analysis of Findings:".
3.  For EACH flagged item in the `flags` array, write an explanation.
4.  **Crucially, you MUST use the provided <AUTHORITATIVE_CONTEXT> to support your explanation for each flag. If a piece of context does not directly relate to a specific flag, DO NOT mention it in your explanation for that flag.**
5.  At the end of each explanation for a flag, you MUST include a citation in the format `[Source: Source ID]`. For example: `[Source: CMS-Duplicate-Billing-001]`.
6.  If the context does not apply to a flag, do not invent a citation.
</INSTRUCTIONS>

<AUTHORITATIVE_CONTEXT>
{context}
</AUTHORITATIVE_CONTEXT>

<JSON_DATA>
{validation_result}
</JSON_DATA>
"""

def get_appeal_draft_prompt_with_rag(validation_result: str, context: str) -> str:
    """Creates the prompt for drafting an appeal letter using retrieved context."""
    return f"""
<INSTRUCTIONS>
Your task is to draft a formal appeal letter for a patient based ONLY on the validated issues in the JSON data and the supporting evidence in the authoritative context.

**Follow these requirements exactly:**
1.  Draft a formal, polite, and citation-ready appeal letter.
2.  Start with placeholders for patient and insurance information.
3.  Use the Claim ID from the JSON in the subject line.
4.  In the letter's body, for each flag, state the issue found.
5.  **You MUST reference the authoritative context to strengthen the appeal. If a piece of context does not directly relate to a specific flag, DO NOT use it in the letter.** For example: "This appears to be a duplicate charge, which is inconsistent with billing guidelines (see Source: CMS-Duplicate-Billing-001)."```
6.  You MUST include the full text of the cited sources in a "References" section at the end of the letter.
</INSTRUCTIONS>

<AUTHORITATIVE_CONTEXT>
{context}
</AUTHORITATIVE_CONTEXT>

<JSON_DATA>
{validation_result}
</JSON_DATA>
"""
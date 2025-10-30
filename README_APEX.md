# APEX 🤖🧾

**APEX** is an AI-powered application that parses, validates, and
explains complex medical bills. It converts unstructured documents such
as PDFs and images into structured, actionable insights using a
multi-stage AI pipeline that combines advanced OCR, deterministic rules,
and Retrieval-Augmented Generation (RAG).

------------------------------------------------------------------------

## 🚀 Core Purpose

To help users understand and verify their medical bills by transforming
messy, unstructured data into clear, validated, and evidence-backed
insights.

------------------------------------------------------------------------

## ⚙️ Workflow

1.  **Upload a document** (PDF, JPG, PNG).
2.  **OCR Processing:** A powerful hybrid OCR engine reads and converts
    text from images.
3.  **Parsing Engine:** Extracts key information such as provider,
    patient, dates, and service details.
4.  **Data Enrichment:** Adds official national average pricing for each
    service using CMS data.
5.  **Rules Engine:** Flags potential billing errors like duplicates,
    overcharges, or invalid codes.
6.  **AI Assistant (RAG-Powered):**
    -   Explains findings in plain English.
    -   Generates formal appeal letters with citations from the
        knowledge base.

------------------------------------------------------------------------

## 🧠 Technical Architecture

  ------------------------------------------------------------------------
  Component                Technology                 Purpose
  ------------------------ -------------------------- --------------------
  **Backend**              FastAPI (Python)           High-performance API
                                                      framework with async
                                                      support

  **OCR Engine**           Google Cloud Vision +      Robust document text
                           Pytesseract                extraction

  **Parser**               Custom Regex-based engine  Deterministic data
                                                      extraction

  **Knowledge Base**       CMS Physician Fee Schedule Authoritative U.S.
                                                      medical billing data

  **Vector DB**            FAISS                      Fast, local semantic
                                                      search for RAG

  **Embedding Model**      all-MiniLM-L6-v2           Converts knowledge
                                                      base text to
                                                      embeddings

  **LLM Provider**         Together.ai (Llama 3 70B)  Provides AI
                                                      reasoning and
                                                      explanation
                                                      generation

  **RAG Framework**        LangChain + FAISS          Evidence-backed LLM
                                                      reasoning

  **Frontend**             Vanilla HTML, CSS, JS      Lightweight web
                                                      interface
  ------------------------------------------------------------------------

------------------------------------------------------------------------

## 💡 Key Features

-   **Multi-Format Ingestion:** Supports PDFs, JPGs, and PNGs.\
-   **Hybrid OCR Engine:** Combines Google Vision and Tesseract for
    reliability.\
-   **Intelligent Parsing:** Extracts and validates key billing
    information.\
-   **Data Enrichment:** Compares with CMS national averages.\
-   **Deterministic Rules Engine:** Flags duplicate or invalid billing
    items.\
-   **RAG-Backed AI Assistant:** Produces evidence-based explanations
    and letters.\
-   **Web Interface:** Simple upload and results page for end-users.

------------------------------------------------------------------------

## 🧩 Setup & Installation

### 1. Prerequisites

-   Python 3.10+\
-   Google Cloud Platform account with Vision API enabled\
-   Together.ai API key

### 2. Clone the Repository

``` bash
git clone <your-repository-url>
cd apex
```

### 3. Environment Setup

Create a `.env` file in the project root:

    TOGETHER_API_KEY=<your-together-api-key>
    GOOGLE_APPLICATION_CREDENTIALS=<path-to-google-credentials.json>

### 4. Install Dependencies

``` bash
pip install -r requirements.txt
```

### 5. Run the Application

``` bash
uvicorn main:app --reload
```

Access the app at: **http://localhost:8000**

------------------------------------------------------------------------

## 🧱 Technical Challenges & Solutions

### 🧩 Dirty CMS Data

-   **Problem:** Inconsistent column names and malformed headers.\
-   **Solution:** Built an intelligent ingestion script that
    auto-detects header rows and normalizes data.

### 🧩 OCR Quality

-   **Problem:** Low-quality scans caused parsing failures.\
-   **Solution:** Integrated Google Vision API with pytesseract fallback
    for resilience.

### 🧩 Regex Parsing Reliability

-   **Problem:** Regex rules broke with format variations.\
-   **Solution:** Iteratively refined patterns and added fallback rules
    for flexible parsing.

### 🧩 LLM Hallucination

-   **Problem:** LLMs may invent facts.\
-   **Solution:** Enforced deterministic preprocessing, structured
    prompts, and RAG-based evidence retrieval.

------------------------------------------------------------------------

## 🛡️ Guardrail System

-   **Structured JSON Inputs Only:** Prevents unverified data from
    reaching the LLM.\
-   **Fact-Based Prompting:** Forces LLM responses to rely solely on
    validated fields.\
-   **RAG Evidence Citations:** Every explanation cites factual
    references.

------------------------------------------------------------------------

## 🧰 Tech Stack Summary

-   **Language:** Python\
-   **Framework:** FastAPI\
-   **AI Model:** Llama-3-70b-chat-hf via Together.ai\
-   **Search Engine:** FAISS + LangChain\
-   **OCR:** Google Cloud Vision + pytesseract\
-   **Frontend:** HTML, CSS, JS

------------------------------------------------------------------------

## 📜 License

This project is licensed under the MIT License.

------------------------------------------------------------------------

## 👨‍💻 Author

Developed with ❤️ by the APEX Team.

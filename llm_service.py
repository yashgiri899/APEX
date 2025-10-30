# llm_service.py
import httpx
import json
from fastapi import HTTPException

# Import the API key from our config file
from config import TOGETHER_API_KEY

# We'll use a powerful and reliable open-source instruction-following model
LLM_MODEL = "meta-llama/Llama-3-70b-chat-hf"
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

async def get_llm_response(prompt: str, system_prompt: str) -> str:
    """
    Sends a prompt to the Together.ai API and returns the response.
    This function is asynchronous and includes robust error handling.
    """
    if not TOGETHER_API_KEY:
        raise HTTPException(status_code=500, detail="TOGETHER_API_KEY is not configured on the server.")

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048, # Limit the output length
        "temperature": 0.1, # Low temperature for factual, less creative output
    }

    # Use an async client with a timeout
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(TOGETHER_API_URL, headers=headers, json=payload)
            
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()

            response_data = response.json()
            # Extract the text content from the first choice in the response
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                raise HTTPException(status_code=500, detail="LLM returned an empty response.")
            
            return content.strip()

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Request to LLM service timed out.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not connect to LLM service: {e}")
        except httpx.HTTPStatusError as e:
            # Provide more specific error details if possible
            error_detail = f"LLM service returned an error: {e.response.status_code}."
            if e.response.status_code == 401:
                error_detail += " Please check the API key."
            raise HTTPException(status_code=502, detail=error_detail)
        except (json.JSONDecodeError, IndexError, KeyError):
            raise HTTPException(status_code=500, detail="Failed to parse a valid response from the LLM service.")
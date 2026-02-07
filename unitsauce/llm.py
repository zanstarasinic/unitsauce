import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv

from rich.spinner import Spinner
from rich.live import Live
from unitsauce.models import Diagnosis
from unitsauce.prompts import DIAGNOSIS_PROMPT, SYSTEM_PROMPT
from .utils import console, parse_json

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def parse_llm_response(response_text):
    """Extract explanation and code from structured response."""
    
    explanation = ""
    code = None
    
    exp_match = re.search(r'<explanation>(.*?)</explanation>', response_text, re.DOTALL)
    if exp_match:
        explanation = exp_match.group(1).strip()
    
    fix_match = re.search(r'<fix>\s*```python(.*?)```\s*</fix>', response_text, re.DOTALL)
    if fix_match:
        code = fix_match.group(1).strip()
        if not code:
            code = None
    return {"explanation": explanation, "code": code}


def call_llm(fix_prompt, functions, test_code, error_message, diff, previous_attempt_error=None):
    
    prompt_content = fix_prompt.format(
        function_code=functions,
        test_code=test_code,
        error_message=error_message,
        diff=diff
    )
    
    if previous_attempt_error:
        prompt_content += "\n\nNOTE: A previous fix attempt did not resolve the issue. Try a different approach."
    
    with Live(Spinner("dots", text="Generating solution..."), console=console):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt_content}
            ],
        )
    
    console.print()
    
    result = parse_llm_response(response.content[0].text)
    
    return result  # {"explanation": "...", "code": "..."} or {"explanation": "...", "code": None}


def diagnose(functions, test_code, error_message, diff,):
    prompt_content = DIAGNOSIS_PROMPT.format(
            function_code=functions,
            test_code=test_code,
            error_message=error_message,
            diff=diff
        )
    with Live(Spinner("dots", text="Diagnosting..."), console=console):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt_content}
            ],
        )
    
    console.print()

    result = parse_json(response.content[0].text)

    diagnosis = Diagnosis(cause=result.get("cause"), fix_location=result.get("fix_location"), confidence=result.get("confidence") )

    return diagnosis



    


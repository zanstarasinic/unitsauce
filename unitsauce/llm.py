import os
import re
from anthropic import Anthropic
from dotenv import load_dotenv

from rich.spinner import Spinner
from rich.live import Live
from unitsauce.models import Diagnosis
from unitsauce.prompts import DIAGNOSIS_PROMPT, SYSTEM_PROMPT
from .utils import console, debug_log, parse_json

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

LLM_MODEL = "claude-sonnet-4-20250514"

def parse_llm_response(response_text):
    """
    Parse structured response from LLM.
    
    Extracts explanation, code fix, and imports from XML-tagged response.
    
    Args:
        response_text: Raw LLM response text
        
    Returns:
        Dict with keys: explanation, code (or None), imports (list)
    """
    explanation = ""
    code = None
    imports = []
    
    exp_match = re.search(r'<explanation>(.*?)</explanation>', response_text, re.DOTALL)
    if exp_match:
        explanation = exp_match.group(1).strip()
    
    imp_match = re.search(r'<imports>(.*?)</imports>', response_text, re.DOTALL)
    if imp_match:
        imp_text = imp_match.group(1).strip()
        if imp_text.lower() != "none":
            imports = [line.strip() for line in imp_text.splitlines() if line.strip()]
    
    fix_match = re.search(r'<fix>\s*```python(.*?)```\s*</fix>', response_text, re.DOTALL)
    if fix_match:
        code = fix_match.group(1).strip()
        if not code:
            code = None
    
    return {"explanation": explanation, "code": code, "imports": imports}


def call_llm(fix_prompt, functions, test_code, error_message, diff, failing_test, previous_attempt_error=None):
    """
    Call LLM to generate a fix for failing test.
    
    Args:
        fix_prompt: Prompt template for the fix
        functions: Affected function source code
        test_code: Failing test source code
        error_message: Test error message
        diff: Git diff showing changes
        failing_test: Name of the failing test
        previous_attempt_error: Error from previous fix attempt (for retry)
        
    Returns:
        Dict with keys: explanation, code (or None), imports
    """
    prompt_content = fix_prompt.format(
        function_code=functions,
        test_code=test_code,
        error_message=error_message,
        failing_test=failing_test,
        diff=diff
    )
    
    if previous_attempt_error:
        prompt_content += "\n\nNOTE: A previous fix attempt did not resolve the issue. Try a different approach."
    
    debug_log("PROMPT CONTENT", prompt_content)
    try:
        with Live(Spinner("dots", text="Generating solution..."), console=console):
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt_content}
                ],
            )
        
        console.print()
        
        result = parse_llm_response(response.content[0].text)
        debug_log("Call LLM response: ", response.content[0].text)
    except Exception as e :
        result = {"explanation": e, "code": None}
    
    return result  # {"explanation": "...", "code": "..."} or {"explanation": "...", "code": None}


def diagnose(functions, test_code, error_message, diff):
    """
    Diagnose the root cause of a test failure.
    
    Args:
        functions: Affected function source code
        test_code: Failing test source code
        error_message: Test error message
        diff: Git diff showing changes
        
    Returns:
        Diagnosis object with cause, fix_location, and confidence
    """

    prompt_content = DIAGNOSIS_PROMPT.format(
            function_code=functions,
            test_code=test_code,
            error_message=error_message,
            diff=diff
        )
    with Live(Spinner("dots", text="Diagnosing..."), console=console):
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt_content}
            ],
        )
    
    console.print()

    result = parse_json(response.content[0].text)
    debug_log("Diagnosis LLM Output: ", result)

    

    diagnosis = Diagnosis(cause=result.get("cause"), fix_location=result.get("fix_location"), confidence=result.get("confidence") )
    debug_log("Diagnosis", diagnosis)

    return diagnosis
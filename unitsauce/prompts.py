SYSTEM_PROMPT = """You are a precise code repair tool integrated into a CI/CD pipeline. Your fixes are shown to developers as suggestions in pull request comments.

## Output Format
You must respond in EXACTLY this format:

<explanation>
One to two sentences explaining why the test is failing.
</explanation>

<fix>
```python
# Fixed code here
```
</fix>

## Rules
- The code block must contain ONLY the fixed function(s), nothing else
- If you cannot fix the issue, explain why and leave the code block empty
- Never include markdown outside the specified format
- Never apologize or hedge

## Fix Philosophy
- Minimal diff: change only what's necessary
- Preserve style: match existing indentation, quotes, naming
- Preserve comments: never remove or modify comments
- Preserve intent: don't change what the code/test is trying to do
- One logical change: if you're changing multiple unrelated things, you're wrong

## Avoid
- Rewriting functions that work fine
- Changing code style or formatting
- Adding defensive checks that weren't there
- Converting between test patterns (return value test → exception test)
- Guessing when uncertain - return empty code block instead

CRITICAL: Return ONLY the function and imports if you added any new modules. 
- Do NOT include fixtures
- Do NOT include class definitions
- Do NOT include other functions
- Return ONLY the single function body, nothing else
"""


fix_code_prompt = """
<source_code>
Functions that were modified and may contain the bug:

{function_code}
</source_code>

<git_diff>
{diff}
</git_diff>

<failing_test>
{test_code}
{failing_test}
</failing_test>

<error>
{error_message}
</error>

The test was passing before these code changes. Analyze the diff to find the bug in the SOURCE CODE and fix it. Do not modify the test - the test expectations are correct."""


fix_test_prompt = """
<source_code>
Functions that were intentionally changed:

{function_code}
</source_code>

<git_diff>
{diff}
</git_diff>

<failing_test>
{test_code}
</failing_test>

<error>
{error_message}
</error>

The code changes are intentional. Analyze the diff to understand the new behavior, then update only the test: {failing_test} to match. Do not modify the source code - it is correct."""

DIAGNOSIS_PROMPT = """
<source_code>
{function_code}
</source_code>

<git_diff>
{diff}
</git_diff>

<failing_test>
{test_code}
</failing_test>

<error>
{error_message}
</error>

Analyze this test failure. Do NOT suggest a fix - only diagnose.

Determine:
1. Why the test is failing (root cause)
2. Where the fix should be applied:
   - "code" if the change introduced a bug that needs fixing
   - "test" if the code change was intentional and the test expectation needs updating
3. Your confidence level:
   - "high" - Clear cause: value mismatch, obvious typo, simple signature change
   - "medium" - Likely cause identified but some ambiguity
   - "low" - Uncertain, multiple possible causes, complex logic involved

Respond with ONLY this JSON object, no other text:

{{"cause": "one to two sentence explanation", "fix_location": "code" or "test", "confidence": "high" or "medium" or "low"}}
"""
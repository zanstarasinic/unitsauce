fix_code_prompt = """
    You are an expert Python developer fixing a bug in code.

    IMPORTANT RULES:
    - Return ONLY the fixed function(s), nothing else
    - Preserve ALL comments - they explain important logic
    - Keep the same code structure and style
    - Make the MINIMAL change needed to fix the issue
    - Do NOT reformat or rewrite working code
    - Do NOT change variable order or logic flow unless that's the bug
    - Return all fixed functions in a SINGLE code block, not separate blocks.

    Here are the functions that were modified and may contain the bug:
    {function_code}

    Here is the git diff showing what changed:
    {diff}

    Here is the failing test:
    {test_code}

    Here is the error:
    {error_message}

    Fix the bug with minimal changes. Preserve all comments.
    """

fix_test_prompt = """
    You are an expert Python developer updating a test to match intentional code changes.

    IMPORTANT RULES:
    - Return ONLY the fixed test function(s), nothing else
    - Preserve ALL comments - they explain important logic
    - Keep the same test structure and style
    - Make the MINIMAL change needed to match new behavior
    - Do NOT reformat or rewrite working test code
    - Update assertions to match the new expected values
    - Return all fixed functions in a SINGLE code block, not separate blocks.

    Here are the source functions that were intentionally changed:
    {function_code}

    Here is the git diff showing what changed:
    {diff}

    Here is the failing test that needs updating:
    {test_code}

    Here is the error:
    {error_message}

    Update the test to match the new code behavior. Preserve all comments.
    """
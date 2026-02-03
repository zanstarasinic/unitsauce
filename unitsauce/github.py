import json
import os

import httpx

def check_if_pull_request():
    event_name = os.getenv("GITHUB_EVENT_NAME")
    event_path = os.getenv("GITHUB_EVENT_PATH")
    repo = os.getenv("GITHUB_REPOSITORY")

    if event_name != "pull_request":
        return None
    
    if not event_path or not os.path.exists(event_path):
        return None
        
    with open(event_path) as f:
        event_details = json.load(f)
    
    pr = event_details.get("pull_request", {})
    
    return {
        "number": pr.get("number"),
        "repo": repo,
        "sha": pr.get("head", {}).get("sha")
    }


def post_pr_comment(repo, pr_number, body):
    """Post a comment to a PR. Returns True if successful."""

    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        return False
    
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    # Use requests or httpx
    response = httpx.post(url, json={"body": body}, headers=headers)
    return response.status_code == 201


def format_pr_comment(result):
    """Format fix result as PR comment markdown."""
    
    if result.fixed:
        status = "✅ Fixed"
    else:
        status = "❌ Could not fix"
    
    comment = f"## {status}: `{result.test_file}::{result.test_function}`\n\n"
    comment += f"**Error:** `{result.error_message[:100]}`\n\n"
    
    if result.fixed:
        comment += f"**Fixed by:** Updating `{result.fix_type}` in `{result.file_changed}`\n\n"
        comment += f"**Apply this change:**\n\n"
        comment += f"```python\n{result.generated_code}\n```\n"
    
    return comment


def format_pr_comment_summary(results):
    """Format all fix results as a single PR comment."""
    
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    
    # Header
    comment = "## 🔧 UnitSauce Analysis\n\n"
    comment += f"Found **{total}** failing test(s), fixed **{fixed}**.\n\n"
    comment += "---\n\n"
    
    # Each result
    for result in results:
        if result.fixed:
            comment += f"### ✅ `{result.test_file}::{result.test_function}`\n\n"
            comment += f"**Error:** `{result.error_message[:100]}`\n\n"
            comment += f"**Fixed by:** Updating `{result.fix_type}` in `{result.file_changed}`\n\n"
            comment += f"```diff\n{result.diff}\n```\n\n"
        else:
            comment += f"### ❌ `{result.test_file}::{result.test_function}`\n\n"
            comment += f"**Error:** `{result.error_message[:100]}`\n\n"
            comment += "Could not auto-fix this failure.\n\n"
        
        comment += "---\n\n"
    
    return comment

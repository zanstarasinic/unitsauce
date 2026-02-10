import json
import os
from .utils import console
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
    
    response = httpx.post(url, json={"body": body}, headers=headers)
    if response.status_code == httpx.codes.ok:
        console.print("Comment posted successfully\n")
    else:
        console.print(response.raise_for_status())



def get_confidence_badge(confidence: str) -> str:
    badges = {
        "high": "🟢",
        "medium": "🟡",
        "low": "🔴"
    }
    return badges.get(confidence, "⚪")


def get_confidence_label(confidence: str) -> str:
    return confidence.capitalize() if confidence else "Unknown"


def format_diff_section(diff: str) -> str:
    if not diff:
        return ""
    
    diff = diff.strip()
    
    if diff.startswith("```"):
        lines = diff.split("\n")
        diff = "\n".join(lines[1:])
    if diff.endswith("```"):
        lines = diff.split("\n")
        diff = "\n".join(lines[:-1])
    
    diff = diff.strip()
    
    return f"```diff\n{diff}\n```"


def format_pr_comment_summary(results):
    total = len(results)
    fixed = sum(1 for r in results if r.fixed)
    partial = sum(1 for r in results if r.partial)
    
    comment = "## 🔧 UnitSauce Analysis\n\n"
    comment += f"Found **{total}** failing test(s)"
    
    if fixed > 0:
        comment += f", fixed **{fixed}**"
    if partial > 0:
        comment += f", partially fixed **{partial}**"
    
    comment += ".\n\n---\n\n"
    
    for result in results:
        badge = get_confidence_badge(result.confidence)
        confidence_label = get_confidence_label(result.confidence)
        cause_text = result.cause if result.cause else "Unknown"
        
        if result.fixed:
            comment += f"### ✅ `{result.test_file}::{result.test_function}`\n\n"
            comment += f"**Error:** `{result.error_message[:150]}`\n\n"
            comment += f"**Why it failed:** {cause_text}\n\n"
            comment += f"**Confidence:** {confidence_label} {badge}\n\n"
            
            fix_label = "Suggested fix" if result.confidence != "low" else "Possible fix (low confidence)"
            comment += f"**{fix_label}** ({result.fix_type}):\n\n"
            comment += format_diff_section(result.diff)
            comment += "\n\n---\n\n"
        
        elif result.partial:
            comment += f"### ⚠️ `{result.test_file}::{result.test_function}`\n\n"
            comment += f"**Error:** `{result.error_message[:150]}`\n\n"
            comment += f"**Why it failed:** {cause_text}\n\n"
            comment += f"**Confidence:** {confidence_label} {badge}\n\n"
            comment += "**Partial fix applied** - original error resolved but new error occurred:\n\n"
            comment += f"`{result.new_error[:150] if result.new_error else 'Unknown error'}`\n\n"
            comment += format_diff_section(result.diff)
            comment += "\n\n---\n\n"
        
        else:
            comment += f"### ❌ `{result.test_file}::{result.test_function}`\n\n"
            comment += f"**Error:** `{result.error_message[:150]}`\n\n"
            comment += f"**Why it failed:** {cause_text}\n\n"
            comment += f"**Confidence:** {confidence_label} {badge}\n\n"
            comment += "Could not auto-fix this failure.\n\n---\n\n"
    
    return comment
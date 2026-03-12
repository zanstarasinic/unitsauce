import json
import os
from pathlib import Path
import httpx

from .output import _format_markdown_summary
from .utils import console


def check_if_pull_request():
    """
    Check if running in a GitHub Actions pull request context.
    
    Reads GitHub Actions environment variables and event payload
    to determine if this is a PR and extract PR details.
    
    Returns:
        Dict with keys: number, repo, sha if in PR context
        None if not in PR context
    """
    event_name = os.getenv("GITHUB_EVENT_NAME")
    event_path = os.getenv("GITHUB_EVENT_PATH")
    repo = os.getenv("GITHUB_REPOSITORY")

    if event_name != "pull_request":
        return None
    
    if not event_path or not Path(event_path).exists():
        return None
        
    with open(event_path) as f:
        event_details = json.load(f)
    
    pr = event_details.get("pull_request", {})
    
    return {
        "number": pr.get("number"),
        "repo": repo,
        "sha": pr.get("head", {}).get("sha")
    }


COMMENT_MARKER = "<!-- unitsauce -->"


def _find_existing_comment(repo, pr_number, headers):
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    try:
        response = httpx.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            for comment in response.json():
                if COMMENT_MARKER in comment.get("body", ""):
                    return comment["id"]
    except Exception:
        pass
    return None


def post_pr_comment(repo, pr_number, body):
    """
    Post or update a UnitSauce comment on a GitHub pull request.

    Uses the GitHub API with GITHUB_TOKEN for authentication.
    Updates an existing UnitSauce comment if one exists, otherwise creates new.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: Pull request number
        body: Comment body (markdown supported)

    Returns:
        True if comment posted/updated successfully, False otherwise
    """
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        console.print("[red]✗[/red] No GITHUB_TOKEN found")
        return False

    body = COMMENT_MARKER + "\n" + body

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        existing_id = _find_existing_comment(repo, pr_number, headers)

        if existing_id:
            url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}"
            response = httpx.patch(url, json={"body": body}, headers=headers, timeout=30)
            success_code = 200
        else:
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            response = httpx.post(url, json={"body": body}, headers=headers, timeout=30)
            success_code = 201

        if response.status_code == success_code:
            return True
        else:
            console.print(f"[red]✗[/red] Failed to post comment: {response.status_code}")
            return False
    except Exception as e:
        console.print(f"[red]✗[/red] Error posting comment: {e}")
        return False


def format_pr_comment(results):
    """
    Format fix results as a PR comment.
    
    Args:
        results: List of FixResult objects
        
    Returns:
        Markdown formatted string ready for posting
    """
    """Format results for PR comment. Uses shared markdown formatter."""
    return _format_markdown_summary(results)
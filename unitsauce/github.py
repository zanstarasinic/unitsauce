import json
import os
import httpx

from .output import _format_markdown_summary
from .utils import console


def check_if_pull_request():
    """Check if running in a PR context. Returns PR info or None."""
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
        console.print("[red]✗[/red] No GITHUB_TOKEN found")
        return False
    
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    try:
        response = httpx.post(url, json={"body": body}, headers=headers)
        if response.status_code == 201:
            console.print(f"[green]✓[/green] Posted to PR #{pr_number}")
            return True
        else:
            console.print(f"[red]✗[/red] Failed to post comment: {response.status_code}")
            return False
    except Exception as e:
        console.print(f"[red]✗[/red] Error posting comment: {e}")
        return False


def format_pr_comment(results):
    """Format results for PR comment. Uses shared markdown formatter."""
    return _format_markdown_summary(results)
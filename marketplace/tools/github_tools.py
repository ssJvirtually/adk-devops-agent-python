import os
import requests
from dotenv import load_dotenv

load_dotenv()


def list_accessible_repositories(
    affiliation: str = "owner,collaborator,organization_member",
    visibility: str = "all",
    limit: int = 50,
) -> str:
    """Lists all GitHub repositories that the authenticated user has access to.
    
    Args:
        affiliation: Comma-separated affiliations: 'owner', 'collaborator', 'organization_member'. Default is all three.
        visibility: Can be 'all', 'public', or 'private'. Default is 'all'.
        limit: Maximum number of repositories to return (default: 50).
    
    Returns:
        A formatted list of accessible repositories with visibility, URL, and description.
    """
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error: Neither GITHUB_PERSONAL_ACCESS_TOKEN nor GITHUB_TOKEN is configured in environment."

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    params = {
        "per_page": min(limit, 100),
        "affiliation": affiliation,
        "visibility": visibility,
        "sort": "updated",
        "direction": "desc",
    }

    try:
        url = "https://api.github.com/user/repos"
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            return f"Failed to fetch repositories from GitHub API: HTTP {resp.status_code} - {resp.text}"

        repos = resp.json()
        if not repos:
            return "No accessible repositories found with the given criteria."

        lines = [f"Found {len(repos)} accessible repositories (showing up to {limit}):\n"]
        for r in repos[:limit]:
            full_name = r.get("full_name")
            is_private = r.get("private", False)
            vis_label = "Private" if is_private else "Public"
            desc = r.get("description") or "No description provided"
            html_url = r.get("html_url")
            default_branch = r.get("default_branch", "main")
            lines.append(f"- **[{full_name}]({html_url})** [{vis_label}] | Branch: `{default_branch}`")
            lines.append(f"  Description: {desc}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving repositories: {str(e)}"

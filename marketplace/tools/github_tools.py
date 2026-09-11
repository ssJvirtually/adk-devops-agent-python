import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _get_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("Neither GITHUB_PERSONAL_ACCESS_TOKEN nor GITHUB_TOKEN is configured in environment.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


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
    try:
        headers = _get_headers()
    except ValueError as e:
        return f"Error: {str(e)}"

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


def create_git_tag(
    repo_name: str,
    tag_name: str,
    commit_sha: str | None = None,
) -> str:
    """Creates or verifies a Git release tag on a GitHub repository.
    
    Args:
        repo_name: Full repository name, e.g. 'ssJvirtually/sampleserver' or 'sampleserver'.
        tag_name: The tag to create, e.g. 'v1.0.0', 'v1.0.1', 'v1.0.2'.
        commit_sha: Optional commit SHA to tag. If not provided, the latest commit on the default branch is tagged.
    
    Returns:
        Confirmation of tag readiness with SHA and repository details.
    """
    try:
        headers = _get_headers()
    except ValueError as e:
        return f"Error: {str(e)}"

    clean_repo = repo_name.strip()
    if "/" not in clean_repo:
        user_r = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if user_r.status_code == 200:
            user_login = user_r.json().get("login")
            clean_repo = f"{user_login}/{clean_repo}"

    # Check if tag already exists
    clean_tag = tag_name.strip()
    if not clean_tag.startswith("v") and not clean_tag[0].isdigit():
        clean_tag = f"v{clean_tag}"

    tag_check = requests.get(f"https://api.github.com/repos/{clean_repo}/git/ref/tags/{clean_tag}", headers=headers, timeout=10)
    if tag_check.status_code == 200:
        existing_sha = tag_check.json().get("object", {}).get("sha", "existing")
        return f"Release tag '{clean_tag}' already exists on repository '{clean_repo}' (commit SHA: {existing_sha}). It is ready for deployment. Now transfer to jenkins_specialist to trigger the build."

    # Fetch default branch commit SHA if not provided
    if not commit_sha:
        repo_r = requests.get(f"https://api.github.com/repos/{clean_repo}", headers=headers, timeout=10)
        if repo_r.status_code != 200:
            return f"Error fetching repo details for {clean_repo}: HTTP {repo_r.status_code} - {repo_r.text}"
        default_branch = repo_r.json().get("default_branch", "main")

        commit_r = requests.get(f"https://api.github.com/repos/{clean_repo}/commits/{default_branch}", headers=headers, timeout=10)
        if commit_r.status_code != 200:
            return f"Error fetching latest commit on branch '{default_branch}': HTTP {commit_r.status_code} - {commit_r.text}"
        commit_sha = commit_r.json().get("sha")

    payload = {
        "ref": f"refs/tags/{clean_tag}",
        "sha": commit_sha,
    }

    try:
        ref_r = requests.post(f"https://api.github.com/repos/{clean_repo}/git/refs", headers=headers, json=payload, timeout=10)
        if ref_r.status_code in (200, 201):
            return f"Release tag '{clean_tag}' successfully created on repository '{clean_repo}' at commit SHA: {commit_sha}. It is ready for deployment. Now transfer to jenkins_specialist to trigger the build."
        elif ref_r.status_code == 422:
            return f"Release tag '{clean_tag}' already exists on repository '{clean_repo}'. It is ready for deployment. Now transfer to jenkins_specialist to trigger the build."
        else:
            return f"Failed to create tag '{clean_tag}': HTTP {ref_r.status_code} - {ref_r.text}"
    except Exception as e:
        return f"Exception while creating tag: {str(e)}"

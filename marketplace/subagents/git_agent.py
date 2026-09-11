from google.adk.agents import LlmAgent
from marketplace.connection_configs import get_github_toolset
from marketplace.tools.github_tools import list_accessible_repositories

GIT_INSTRUCTION = """You are the Git & GitHub Specialist Agent.
Your role:
1. List accessible repositories for the user using the `list_accessible_repositories` tool whenever the user asks to view or list repositories they have access to. You can filter by affiliation ('owner', 'collaborator', 'organization_member') or visibility ('all', 'public', 'private').
2. Handle GitHub repository queries, inspect commits, branches, pull requests, and releases.
3. Create or verify release tags for requested deployments.
4. Confirm repository status and commit SHAs before deployments proceed.
5. Always report the exact tag, commit SHA, and repository details clearly to the orchestrator.
"""

git_specialist = LlmAgent(
    name="git_specialist",
    description="Specialist in GitHub operations, listing user repositories, release tagging, commits, and branch management.",
    instruction=GIT_INSTRUCTION,
    model="gemini-2.5-flash",
    tools=[get_github_toolset(), list_accessible_repositories],
)

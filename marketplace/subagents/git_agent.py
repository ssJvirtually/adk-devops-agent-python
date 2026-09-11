from google.adk.agents import LlmAgent
from marketplace.connection_configs import get_github_toolset
from marketplace.tools.github_tools import list_accessible_repositories, create_git_tag

GIT_INSTRUCTION = """You are the Git & GitHub Specialist Agent.
Your role:
1. List accessible repositories for the user using `list_accessible_repositories` whenever asked to view or list repositories.
2. Create or verify Git release tags on repositories using the `create_git_tag` tool.
   - When asked to deploy or tag a repository, immediately call `create_git_tag(repo_name, tag_name)`.
   - Once the tag is created or confirmed ready, transfer directly to `jenkins_specialist` with the repository name and tag name to proceed with the CI/CD build. Do not transfer back to devops_orchestrator.
3. Handle GitHub repository queries, inspect commits, branches, pull requests, and releases.
4. Confirm repository status and commit SHAs before deployments proceed.
"""

git_specialist = LlmAgent(
    name="git_specialist",
    description="Specialist in GitHub operations, listing user repositories, release tagging, commits, and branch management.",
    instruction=GIT_INSTRUCTION,
    model="gemini-2.5-flash",
    tools=[get_github_toolset(), list_accessible_repositories, create_git_tag],
)

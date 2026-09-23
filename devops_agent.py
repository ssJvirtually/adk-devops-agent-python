"""
================================================================================
Multi-Agent DevOps Marketplace (All-In-One Unified Agent)
================================================================================
This single file provides a complete, production-grade DevOps multi-agent system
using Google ADK (Agent Development Kit) and Model Context Protocol (MCP).

Architecture & Components:
1. Jenkins FastMCP Server & Tools:
   - Automates Jenkins builds, job listings, log inspection, and deployment.
   - Exposes tools via FastMCP (or direct functions for maximum performance).
2. GitHub API & MCP Tools:
   - Lists accessible repositories (owner, collaborator, organization member).
   - Generates and verifies Git release tags on GitHub.
3. Specialized Sub-Agents:
   - git_specialist: Handles repository access and release tagging.
   - jenkins_specialist: Manages pipeline dispatch, Maven packaging, and deployment.
   - sonar_specialist: Standby for static code analysis and quality gate checks.
4. Root DevOps Orchestrator (root_agent):
   - Coordinates end-to-end releases: Git Tag -> Maven Build -> Host Deploy.
5. Interactive Shell & CLI Launcher:
   - Run `python devops_agent.py` for terminal chat or single queries.
   - Run `adk web .` for the visual web interface.
================================================================================
"""

import os
import sys
import time
import shutil
import requests
from dotenv import load_dotenv

# Ensure stdout and stderr use UTF-8 on Windows consoles to prevent encoding errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment credentials from .env
load_dotenv()

# ==============================================================================
# CONFIGURATION & ENVIRONMENT CREDENTIALS
# ==============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN", "")
JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8088").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "admin")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "admin")

# ==============================================================================
# FASTMCP SERVER SETUP
# Compatible across both MCP v1 (FastMCP) and v2 (MCPServer)
# ==============================================================================
try:
    from mcp.server.mcpserver import MCPServer
    mcp_app = MCPServer("jenkins-mcp-server")
except ImportError:
    from mcp.server.fastmcp import FastMCP
    mcp_app = FastMCP("jenkins-mcp-server")


# ==============================================================================
# SECTION 1: JENKINS CI/CD AUTOMATION TOOLS
# ==============================================================================

def get_jenkins_session() -> requests.Session:
    """
    Creates and configures an authenticated requests Session for Jenkins.
    
    Features:
    - Attaches HTTP Basic Auth credentials (JENKINS_USER / JENKINS_API_TOKEN).
    - Automatically requests and caches CSRF crumb token from /crumbIssuer/api/json
      to prevent 403 Forbidden errors when submitting POST requests.
    """
    session = requests.Session()
    if JENKINS_USER and JENKINS_API_TOKEN:
        session.auth = (JENKINS_USER, JENKINS_API_TOKEN)
    
    try:
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        resp = session.get(crumb_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            session.headers.update({data["crumbRequestField"]: data["crumb"]})
    except Exception:
        pass  # Crumb issuer may be disabled; proceed without crumb
    return session


@mcp_app.tool()
def list_jobs() -> str:
    """
    Queries the Jenkins master and returns a list of all configured jobs.
    
    Returns:
        A human-readable list of job names, status colors, and URLs.
    """
    try:
        session = get_jenkins_session()
        resp = session.get(f"{JENKINS_URL}/api/json", timeout=10)
        if resp.status_code != 200:
            return f"Error connecting to Jenkins: HTTP {resp.status_code} - {resp.text}"
        data = resp.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return "No jobs found on the Jenkins server."
        lines = ["Available Jenkins Jobs:"]
        for j in jobs:
            lines.append(f"- Name: {j.get('name')}, Color: {j.get('color')}, URL: {j.get('url')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list jobs: {str(e)}"


@mcp_app.tool()
def build_job(job_name: str, params: dict | None = None) -> str:
    """
    Triggers a fresh build for a specified Jenkins job with optional parameters.
    
    Parameters handled:
    - TAG: Git release tag to build (e.g. 'v1.0.4').
    - REPO_URL: Git repository URL to clone and build.
    - DEPLOY_DIR: Deployment destination directory on host machine.
    - GITHUB_TOKEN: Automatically injected from environment if cloning private repos.
    
    Returns:
        Confirmation message with queue location or allocated build number.
    """
    try:
        session = get_jenkins_session()
        build_params = dict(params) if params else {}

        # Transparently inject GITHUB_TOKEN so private repos clone seamlessly
        if GITHUB_TOKEN and "GITHUB_TOKEN" not in build_params:
            build_params["GITHUB_TOKEN"] = GITHUB_TOKEN

        if build_params:
            url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"
            resp = session.post(url, params=build_params, timeout=10)
        else:
            url = f"{JENKINS_URL}/job/{job_name}/build"
            resp = session.post(url, timeout=10)

        if resp.status_code not in (200, 201):
            return f"Failed to trigger build for {job_name}: HTTP {resp.status_code} - {resp.text}"

        queue_location = resp.headers.get("Location")
        if not queue_location:
            return f"Build triggered for {job_name} successfully."

        # Quick poll (up to 3s) to resolve the queued item to an actual build number
        build_number = None
        for _ in range(3):
            time.sleep(1)
            try:
                q_resp = session.get(f"{queue_location}api/json", timeout=3)
                if q_resp.status_code == 200:
                    q_data = q_resp.json()
                    executable = q_data.get("executable")
                    if executable and "number" in executable:
                        build_number = executable["number"]
                        break
            except Exception:
                pass

        if build_number is not None:
            return f"Build triggered successfully! Job: '{job_name}', Build Number: #{build_number}. URL: {JENKINS_URL}/job/{job_name}/{build_number}/"
        return f"Build queued successfully for job '{job_name}'. Queue item: {queue_location}. Use get_last_build_status to monitor progress."
    except Exception as e:
        return f"Error triggering build for {job_name}: {str(e)}"


@mcp_app.tool()
def get_job_status(job_name: str, build_number: int) -> str:
    """
    Retrieves the execution status and duration of a specific Jenkins build number.
    
    Args:
        job_name: Name of the Jenkins job (e.g. 'spring-api-deploy-job').
        build_number: Specific build execution number (e.g. 5).
    """
    try:
        session = get_jenkins_session()
        url = f"{JENKINS_URL}/job/{job_name}/{build_number}/api/json"
        resp = session.get(url, timeout=10)
        if resp.status_code == 404:
            return f"Build #{build_number} for job '{job_name}' not found."
        if resp.status_code != 200:
            return f"Failed to get build status: HTTP {resp.status_code} - {resp.text}"

        data = resp.json()
        building = data.get("building", False)
        result = data.get("result")
        duration_ms = data.get("duration", 0)

        if building:
            return f"Job '{job_name}' build #{build_number} is currently RUNNING (Duration: {duration_ms / 1000:.1f}s)."
        return f"Job '{job_name}' build #{build_number} finished with status: {result} (Duration: {duration_ms / 1000:.1f}s)."
    except Exception as e:
        return f"Error getting status for {job_name} #{build_number}: {str(e)}"


@mcp_app.tool()
def get_last_build_status(job_name: str) -> str:
    """
    Retrieves the execution status of the most recent build for a given job.
    Useful when the build number is not known in advance.
    """
    try:
        session = get_jenkins_session()
        url = f"{JENKINS_URL}/job/{job_name}/lastBuild/api/json"
        resp = session.get(url, timeout=10)
        if resp.status_code == 404:
            return f"No builds found for job '{job_name}'."
        if resp.status_code != 200:
            return f"Failed to get latest build status: HTTP {resp.status_code} - {resp.text}"

        data = resp.json()
        build_number = data.get("number")
        building = data.get("building", False)
        result = data.get("result")
        duration_ms = data.get("duration", 0)

        if building:
            return f"Latest build #{build_number} for '{job_name}' is currently RUNNING (Duration: {duration_ms / 1000:.1f}s)."
        return f"Latest build #{build_number} for '{job_name}' finished with status: {result} (Duration: {duration_ms / 1000:.1f}s)."
    except Exception as e:
        return f"Error getting latest build status for {job_name}: {str(e)}"


@mcp_app.tool()
def get_build_log_tail(job_name: str, build_number: int | None = None, lines: int = 50) -> str:
    """
    Retrieves the trailing console output lines for a specific build or the latest build.
    Used to inspect Maven compilation results, jar packaging, and deployment paths.
    """
    try:
        session = get_jenkins_session()
        build_target = str(build_number) if build_number is not None else "lastBuild"
        url = f"{JENKINS_URL}/job/{job_name}/{build_target}/consoleText"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return f"Failed to retrieve logs: HTTP {resp.status_code} - {resp.text}"

        all_lines = resp.text.splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail)
    except Exception as e:
        return f"Error retrieving logs for {job_name}: {str(e)}"


# ==============================================================================
# SECTION 2: GITHUB REPOSITORY & RELEASE TAG TOOLS
# ==============================================================================

def _get_github_headers() -> dict[str, str]:
    """Helper method to construct standard GitHub API headers with Bearer authentication."""
    if not GITHUB_TOKEN:
        raise ValueError("Neither GITHUB_PERSONAL_ACCESS_TOKEN nor GITHUB_TOKEN is configured in environment.")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def list_accessible_repositories(
    affiliation: str = "owner,collaborator,organization_member",
    visibility: str = "all",
    limit: int = 50,
) -> str:
    """
    Lists all GitHub repositories the authenticated user has access to.
    
    Args:
        affiliation: Comma-separated affiliations: 'owner', 'collaborator', 'organization_member'.
        visibility: Filter by 'all', 'public', or 'private'.
        limit: Maximum number of repositories to return (default: 50).
    
    Returns:
        Formatted Markdown list with repo full name, visibility badge, default branch, and description.
    """
    try:
        headers = _get_github_headers()
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
    """
    Creates or verifies a Git release tag on a GitHub repository.
    
    Args:
        repo_name: Full repository name, e.g. 'ssJvirtually/sampleserver' or 'sampleserver'.
        tag_name: The tag to create, e.g. 'v1.0.0', 'v1.0.4'.
        commit_sha: Optional commit SHA to tag. If not provided, latest commit on default branch is used.
    
    Returns:
        Confirmation of tag readiness and instruction to proceed with deployment.
    """
    try:
        headers = _get_github_headers()
    except ValueError as e:
        return f"Error: {str(e)}"

    clean_repo = repo_name.strip()
    if "/" not in clean_repo:
        user_r = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if user_r.status_code == 200:
            user_login = user_r.json().get("login")
            clean_repo = f"{user_login}/{clean_repo}"

    clean_tag = tag_name.strip()
    if not clean_tag.startswith("v") and not clean_tag[0].isdigit():
        clean_tag = f"v{clean_tag}"

    # Check if tag reference already exists
    tag_check = requests.get(f"https://api.github.com/repos/{clean_repo}/git/ref/tags/{clean_tag}", headers=headers, timeout=10)
    if tag_check.status_code == 200:
        existing_sha = tag_check.json().get("object", {}).get("sha", "existing")
        return f"Release tag '{clean_tag}' already exists on repository '{clean_repo}' (commit SHA: {existing_sha}). It is ready for deployment. Now transfer to jenkins_specialist to trigger the build."

    # Fetch default branch commit SHA if not specified
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


# ==============================================================================
# SECTION 3: FASTMCP CLI HOOK
# Allows this single file to act as the FastMCP server when launched with --mcp-jenkins
# ==============================================================================
if len(sys.argv) > 1 and sys.argv[1] == "--mcp-jenkins":
    mcp_app.run()
    sys.exit(0)


# ==============================================================================
# SECTION 4: GOOGLE ADK MCP TOOLSETS
# ==============================================================================
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

def get_github_toolset() -> McpToolset:
    """
    Instantiates the official GitHub MCP server toolset (@modelcontextprotocol/server-github).
    Runs as a local Node.js process over Standard I/O (`stdio`).
    """
    env = os.environ.copy()
    env["GITHUB_PERSONAL_ACCESS_TOKEN"] = GITHUB_TOKEN
    env["GITHUB_TOKEN"] = GITHUB_TOKEN

    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    server_params = StdioServerParameters(
        command=npx_cmd,
        args=["-y", "@modelcontextprotocol/server-github"],
        env=env,
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server_params, timeout=60.0))


def get_jenkins_toolset() -> McpToolset:
    """
    Instantiates the Jenkins MCP Toolset by connecting to this very file
    spawned in `--mcp-jenkins` mode over Standard I/O (`stdio`).
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.abspath(__file__), "--mcp-jenkins"],
        env=os.environ.copy(),
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server_params, timeout=60.0))


# ==============================================================================
# SECTION 5: SPECIALIZED DOMAIN SUB-AGENTS
# ==============================================================================

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


JENKINS_INSTRUCTION = """You are the Jenkins CI/CD Specialist Agent.
Your mandatory execution procedure:
1. When instructed to deploy or build an application (e.g. `sampleserver` or any Spring Boot API):
   - STEP 1 (MANDATORY): You MUST immediately call `build_job` to trigger a fresh build!
     For Java/Spring projects, call: `build_job(job_name='spring-api-deploy-job', params={'TAG': '<tag_name>', 'REPO_URL': '<repo_url>', 'DEPLOY_DIR': '/host_deployments/sampleserver'})`.
     DO NOT simply inspect previous builds without triggering a new one first.
   - STEP 2: Note the newly triggered build number or wait a few seconds and call `get_last_build_status(job_name='spring-api-deploy-job')` to track progress.
   - STEP 3: Retrieve the console log using `get_build_log_tail(job_name='spring-api-deploy-job')` to verify that Maven compilation, packaging, and host deployment succeeded.
   - STEP 4: Report the deployment results:
     * Job Name and new Build Number
     * Build Status (SUCCESS / FAILURE)
     * Host Artifact path: `deployments/sampleserver/app.jar` (deployed directly on Windows host machine)
     * Windows Launcher: `deployments/sampleserver/start.bat`
     * Deployed Version
     * Console Highlights
"""

jenkins_specialist = LlmAgent(
    name="jenkins_specialist",
    description="Specialist in Jenkins CI/CD builds, triggering fresh Maven Spring Boot pipelines, parameter dispatch, and log inspection.",
    instruction=JENKINS_INSTRUCTION,
    model="gemini-2.5-flash",
    tools=[get_jenkins_toolset()],
)


sonar_specialist = LlmAgent(
    name="sonar_specialist",
    description="Specialist in SonarQube static code analysis, security hotspots, and quality gates.",
    instruction="Inspect project quality gates and check for security vulnerabilities (currently on standby).",
    model="gemini-2.5-flash",
    tools=[],
)


# ==============================================================================
# SECTION 6: ROOT DEVOPS ORCHESTRATOR AGENT
# ==============================================================================

ORCHESTRATOR_INSTRUCTION = """You are the DevOps Orchestrator Agent.
You coordinate DevOps workflows across specialized sub-agents:
1. `git_specialist`: Handles GitHub operations, listing user repositories, inspecting commits/branches, and creating Git release tags.
2. `jenkins_specialist`: Manages Jenkins CI/CD builds, triggering parameterized pipelines (e.g., `spring-api-deploy-job`, `deploy-job`), polling build status, and retrieving console logs.
3. `sonar_specialist`: Inspects code quality gates, vulnerabilities, and security hotspots (currently on standby).

### WORKFLOW 1 - REPOSITORY DISCOVERY:
When a user asks to list, see, or search repositories they have access to:
1. Delegate to `git_specialist` to fetch accessible repositories using `list_accessible_repositories`.
2. Format the response clearly with repository name, visibility, default branch, and description.

### WORKFLOW 2 - REAL APPLICATION RELEASE & HOST DEPLOYMENT:
When a user asks to deploy a repository (such as `https://github.com/ssJvirtually/sampleserver` or any Spring/Java API):
1. Determine the repository name (e.g., `ssJvirtually/sampleserver`) and the release tag to create (e.g., `v1.0.1`, `v1.0.4`, or user-specified).
2. Delegate to `git_specialist` to create the new release tag on GitHub using `create_git_tag`.
3. Once the tag is confirmed by `git_specialist`, delegate to `jenkins_specialist` to trigger the deployment build:
   - For Java/Spring projects like `sampleserver`: trigger `spring-api-deploy-job` with `TAG`, `REPO_URL`, and `DEPLOY_DIR=/host_deployments/sampleserver`.
   - For other jobs: trigger `deploy-job` with `TAG` and `REPO`.
4. Have `jenkins_specialist` monitor the job status and retrieve Maven compile/package logs.
5. If the build succeeds:
   - Provide the user with a structured Deployment Summary:
     * Repository: <repo>
     * Release Tag: <tag> (Created on GitHub)
     * Jenkins Job & Build: <job_name> #<build_number>
     * Host Artifact: `deployments/sampleserver/app.jar` (Directly on Windows Host)
     * Windows Launcher: `deployments/sampleserver/start.bat`
     * Status: SUCCESS
     * Key Build & Deployment Logs
6. If the build fails:
   - If related to quality gates, delegate to `sonar_specialist`.
   - If critical issues occur, HALT and output a formatted incident report:
     ===========================================
     HUMAN INTERVENTION REQUIRED
     ===========================================
     - Issue: <Description of failure>
     - Jenkins Build: #<build_number>
     - Failure Details: <Error log>
     - Recommended Action: <Steps to remediate>
     ===========================================
"""

root_agent = LlmAgent(
    name="devops_orchestrator",
    description="DevOps Orchestrator coordinating repository management, release tagging, Maven Spring Boot packaging, Jenkins deployments, and escalation workflows.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    model="gemini-2.5-flash",
    sub_agents=[git_specialist, jenkins_specialist, sonar_specialist],
)


# ==============================================================================
# SECTION 7: INTERACTIVE TERMINAL & CLI RUNNER
# ==============================================================================

if __name__ == "__main__":
    import asyncio
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    async def main():
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="devops_marketplace", user_id="user_cli")
        runner = Runner(agent=root_agent, app_name="devops_marketplace", session_service=session_service)

        print("\n" + "=" * 70)
        print("DevOps Multi-Agent Marketplace Interactive Terminal (Unified Single File)")
        print("Sub-Agents: git_specialist | jenkins_specialist | sonar_specialist")
        print("Type your message and press Enter. (Type 'exit' or 'quit' to quit)")
        print("=" * 70 + "\n")

        # If user passed prompt as command line argument: python devops_agent.py "List my repos"
        if len(sys.argv) > 1:
            initial_query = " ".join(sys.argv[1:])
            print(f"User > {initial_query}\n\nAgent > ", end="", flush=True)
            msg = Content(role="user", parts=[Part.from_text(text=initial_query)])
            async for event in runner.run_async(session_id=session.id, user_id="user_cli", new_message=msg):
                if hasattr(event, "content") and event.content:
                    for p in event.content.parts:
                        if getattr(p, "text", None):
                            print(p.text, end="", flush=True)
                if hasattr(event, "actions") and event.actions and event.actions.transfer_to_agent:
                    print(f"\n[-> Delegating to {event.actions.transfer_to_agent}...]\n", flush=True)
            print("\n")
            return

        # Interactive loop
        while True:
            try:
                user_input = input("User > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break

                msg = Content(role="user", parts=[Part.from_text(text=user_input)])
                print("\nAgent > ", end="", flush=True)
                async for event in runner.run_async(session_id=session.id, user_id="user_cli", new_message=msg):
                    if hasattr(event, "content") and event.content:
                        for p in event.content.parts:
                            if getattr(p, "text", None):
                                print(p.text, end="", flush=True)
                    if hasattr(event, "actions") and event.actions and event.actions.transfer_to_agent:
                        print(f"\n[-> Delegating to {event.actions.transfer_to_agent}...]\n", flush=True)
                print("\n")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                break

    asyncio.run(main())

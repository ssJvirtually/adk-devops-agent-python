import os
import sys

# Set stdout/stderr to utf-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.agents import LlmAgent
from marketplace.subagents.git_agent import git_specialist
from marketplace.subagents.jenkins_agent import jenkins_specialist
from marketplace.subagents.sonar_agent import sonar_specialist

ORCHESTRATOR_INSTRUCTION = """You are the DevOps Orchestrator Agent.
You coordinate DevOps workflows across specialized sub-agents:
1. `git_specialist`: Handles GitHub operations, listing user repositories, inspecting commits/branches, and creating/verifying release tags.
2. `jenkins_specialist`: Manages Jenkins CI/CD builds, triggering parameterized pipelines, polling build status, and retrieving console logs.
3. `sonar_specialist`: Inspects code quality gates, vulnerabilities, and security hotspots (currently on standby).

### WORKFLOW 1 - REPOSITORY DISCOVERY & ACCESS:
When a user asks to list, see, or search repositories they have access to:
1. Delegate to `git_specialist` to fetch accessible repositories using `list_accessible_repositories`.
2. Format the response clearly with repository name, visibility (public/private), default branch, and description.

### WORKFLOW 2 - RELEASE & LOCAL DEPLOYMENT:
When a user asks to deploy a repository or create a release:
1. Identify the repository name and the desired release tag (e.g., v1.0.0, v1.1.0). If not specified by the user, ask or suggest from their accessible repositories.
2. Delegate to `git_specialist` to verify the repository and create/confirm the release tag.
3. Once the release tag is confirmed, delegate to `jenkins_specialist` to trigger the Jenkins deployment job (`deploy-job` by default) with parameters:
   - TAG: <the release tag>
   - REPO: <the repository name>
4. Have `jenkins_specialist` monitor the job status and retrieve the execution logs.
5. If the build succeeds:
   - Provide the user with a structured Deployment Summary:
     * Repository: <repo>
     * Release Tag: <tag>
     * Jenkins Job & Build: <job_name> #<build_number>
     * Target: Local Machine
     * Status: SUCCESS
     * Console Highlights: <key logs>
6. If the build fails:
   - If related to quality gates, delegate to `sonar_specialist` to investigate.
   - If critical issues or failures occur, HALT execution and output a formatted incident report:
     ===========================================
     🚨 HUMAN INTERVENTION REQUIRED
     ===========================================
     - Issue: <Description of failure>
     - Jenkins Build: #<build_number>
     - Failure Details: <Error / Vulnerability log>
     - Recommended Action: <Steps to remediate>
     ===========================================
   - Never perform blind retries on critical failures.
"""

root_agent = LlmAgent(
    name="devops_orchestrator",
    description="DevOps Orchestrator coordinating repository management, release tagging, Jenkins deployments, and escalation workflows.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    model="gemini-2.5-flash",
    sub_agents=[git_specialist, jenkins_specialist, sonar_specialist],
)


if __name__ == "__main__":
    import asyncio
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    async def cli_chat():
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="marketplace", user_id="user_cli")
        runner = Runner(agent=root_agent, app_name="marketplace", session_service=session_service)

        print("\n" + "=" * 65)
        print("DevOps Orchestrator Interactive Shell")
        print("Type your message and press Enter. (Type 'exit' or 'quit' to stop)")
        print("=" * 65 + "\n")

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

    asyncio.run(cli_chat())

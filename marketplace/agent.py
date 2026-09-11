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
1. `git_specialist`: Handles GitHub operations, listing user repositories, inspecting commits/branches, and creating Git release tags.
2. `jenkins_specialist`: Manages Jenkins CI/CD builds, triggering parameterized pipelines (e.g., `spring-api-deploy-job`, `deploy-job`), polling build status, and retrieving console logs.
3. `sonar_specialist`: Inspects code quality gates, vulnerabilities, and security hotspots (currently on standby).

### WORKFLOW 1 - REPOSITORY DISCOVERY:
When a user asks to list, see, or search repositories they have access to:
1. Delegate to `git_specialist` to fetch accessible repositories using `list_accessible_repositories`.
2. Format the response clearly with repository name, visibility, default branch, and description.

### WORKFLOW 2 - REAL APPLICATION RELEASE & DEPLOYMENT:
When a user asks to deploy a repository (such as `https://github.com/ssJvirtually/sampleserver` or any Spring/Java API):
1. Determine the repository name (e.g., `ssJvirtually/sampleserver`) and the release tag to create (e.g., `v1.0.1`, `v1.0.2`, or user-specified).
2. Delegate to `git_specialist` to create the new release tag on GitHub using `create_git_tag`.
3. Once the tag is confirmed by `git_specialist`, delegate to `jenkins_specialist` to trigger the deployment build:
   - For Java/Spring projects like `sampleserver`: trigger `spring-api-deploy-job` with `TAG` and `REPO_URL`.
   - For other jobs: trigger `deploy-job` with `TAG` and `REPO`.
4. Have `jenkins_specialist` monitor the job status and retrieve Maven compile/package logs.
5. If the build succeeds:
   - Provide the user with a structured Deployment Summary:
     * Repository: <repo>
     * Release Tag: <tag> (Created on GitHub)
     * Jenkins Job & Build: <job_name> #<build_number>
     * Artifact: app.jar (Maven Spring Boot Jar)
     * Target: Local Machine Deployment
     * Status: SUCCESS ✅
     * Key Build & Deployment Logs
6. If the build fails:
   - If related to quality gates, delegate to `sonar_specialist`.
   - If critical issues occur, HALT and output a formatted incident report:
     ===========================================
     🚨 HUMAN INTERVENTION REQUIRED
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

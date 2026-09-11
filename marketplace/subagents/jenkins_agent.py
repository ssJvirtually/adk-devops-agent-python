from google.adk.agents import LlmAgent
from marketplace.connection_configs import get_jenkins_toolset

JENKINS_INSTRUCTION = """You are the Jenkins CI/CD Specialist Agent.
Your role:
1. List available jobs, trigger builds with parameters (such as TAG and REPO), and inspect build logs.
2. When instructed to trigger a deployment build:
   - Identify the job (default: 'deploy-job' if unspecified).
   - Trigger the build passing parameters: TAG (the release tag) and REPO (the repo name).
   - Check status using `get_job_status`.
   - If the build is RUNNING, check again until complete, or provide the current execution status.
   - Fetch the console output using `get_build_log_tail` to verify whether deployment succeeded or failed.
3. Report the build status, execution duration, and log highlights back to the orchestrator.
"""

jenkins_specialist = LlmAgent(
    name="jenkins_specialist",
    description="Specialist in Jenkins CI/CD builds, parameter dispatch, build monitoring, and log inspection.",
    instruction=JENKINS_INSTRUCTION,
    model="gemini-2.5-flash",
    tools=[get_jenkins_toolset()],
)

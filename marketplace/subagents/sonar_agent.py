from google.adk.agents import LlmAgent
from marketplace.connection_configs import get_sonar_toolset

SONAR_INSTRUCTION = """You are the SonarQube Security & Quality Specialist Agent.
Your role:
1. Inspect project quality gates and check for security vulnerabilities, bugs, or code smells.
2. If a build fails due to a quality gate, query SonarQube for critical issues and blockers.
3. Provide exact file paths, line numbers, and issue severity back to the orchestrator.
"""

sonar_toolset = get_sonar_toolset()
sonar_tools = [sonar_toolset] if sonar_toolset else []

sonar_specialist = LlmAgent(
    name="sonar_specialist",
    description="Specialist in SonarQube static code analysis, security hotspots, and quality gates.",
    instruction=SONAR_INSTRUCTION,
    model="gemini-2.5-flash",
    tools=sonar_tools,
)

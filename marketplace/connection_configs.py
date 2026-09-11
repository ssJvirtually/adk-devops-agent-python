import os
import sys
import shutil
from dotenv import load_dotenv
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()


def get_github_toolset() -> McpToolset:
    """Creates and returns the MCP Toolset connected to GitHub MCP server."""
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN", "")
    env = os.environ.copy()
    env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
    env["GITHUB_TOKEN"] = token

    # Ensure correct npx path on Windows (.cmd)
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx") or "npx"

    server_params = StdioServerParameters(
        command=npx_cmd,
        args=["-y", "@modelcontextprotocol/server-github"],
        env=env,
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server_params, timeout=60.0))


def get_jenkins_toolset() -> McpToolset:
    """Creates and returns the MCP Toolset connected to the local Jenkins FastMCP server."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_script = os.path.join(project_root, "mcp_servers", "jenkins_server.py")

    env = os.environ.copy()
    env["JENKINS_URL"] = os.getenv("JENKINS_URL", "http://localhost:8088")
    env["JENKINS_USER"] = os.getenv("JENKINS_USER", "admin")
    env["JENKINS_API_TOKEN"] = os.getenv("JENKINS_API_TOKEN", "admin")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=env,
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server_params, timeout=60.0))


def get_sonar_toolset() -> McpToolset | None:
    """Creates the SonarQube MCP Toolset (reserved / on hold)."""
    sonar_token = os.getenv("SONARQUBE_TOKEN")
    sonar_url = os.getenv("SONARQUBE_URL", "http://localhost:9000")
    if not sonar_token or sonar_token.startswith("sqa_xxxx"):
        return None

    docker_cmd = shutil.which("docker") or "docker"
    server_params = StdioServerParameters(
        command=docker_cmd,
        args=[
            "run",
            "-i",
            "--rm",
            "-e",
            f"SONARQUBE_TOKEN={sonar_token}",
            "-e",
            f"SONARQUBE_URL={sonar_url}",
            "sonarsource/sonarqube-mcp",
        ],
        env=os.environ.copy(),
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server_params, timeout=60.0))

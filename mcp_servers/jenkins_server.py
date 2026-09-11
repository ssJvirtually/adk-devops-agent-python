import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# Compatibility across MCP versions (v1 FastMCP vs v2 MCPServer)
try:
    from mcp.server.mcpserver import MCPServer
    mcp_app = MCPServer("jenkins-mcp-server")
except ImportError:
    from mcp.server.fastmcp import FastMCP
    mcp_app = FastMCP("jenkins-mcp-server")

JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8088").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "admin")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "admin")


def get_session() -> requests.Session:
    session = requests.Session()
    if JENKINS_USER and JENKINS_API_TOKEN:
        session.auth = (JENKINS_USER, JENKINS_API_TOKEN)
    
    # Try fetching CSRF crumb if enabled
    try:
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        resp = session.get(crumb_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            session.headers.update({data["crumbRequestField"]: data["crumb"]})
    except Exception:
        pass
    return session


@mcp_app.tool()
def list_jobs() -> str:
    """List all available jobs on the Jenkins server."""
    try:
        session = get_session()
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
    """Trigger a Jenkins build for a specified job name with optional parameters (e.g. TAG, REPO)."""
    try:
        session = get_session()
        if params:
            url = f"{JENKINS_URL}/job/{job_name}/buildWithParameters"
            resp = session.post(url, params=params, timeout=10)
        else:
            url = f"{JENKINS_URL}/job/{job_name}/build"
            resp = session.post(url, timeout=10)

        if resp.status_code not in (200, 201):
            return f"Failed to trigger build for {job_name}: HTTP {resp.status_code} - {resp.text}"

        queue_location = resp.headers.get("Location")
        if not queue_location:
            return f"Build triggered for {job_name} successfully."

        # Quick poll (up to 3 seconds) for the build number
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
        return f"Build queued successfully for job '{job_name}'. Queue item: {queue_location}. Use get_last_build_status to check status."
    except Exception as e:
        return f"Error triggering build for {job_name}: {str(e)}"


@mcp_app.tool()
def get_job_status(job_name: str, build_number: int) -> str:
    """Get the execution status and result of a specific Jenkins build number."""
    try:
        session = get_session()
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
    """Get the execution status and result of the latest build for a given job."""
    try:
        session = get_session()
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
    """Retrieve the trailing console output lines for a specific build or the latest build if not specified."""
    try:
        session = get_session()
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


if __name__ == "__main__":
    mcp_app.run()

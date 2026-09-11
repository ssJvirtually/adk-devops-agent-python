import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8088").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "admin")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "admin")

XML_CONFIG = """<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description>DevOps Deployment Job</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.StringParameterDefinition>
          <name>TAG</name>
          <description>Git Release Tag</description>
          <defaultValue>v1.0.0</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>REPO</name>
          <description>Git Repository</description>
          <defaultValue>sample-app</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <canRoam>true</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers/>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>echo "========================================="
echo "Starting deployment for repository: $REPO"
echo "Deploying release tag: $TAG"
echo "Target: local machine"
echo "Step 1: Fetching code artifact for tag $TAG..."
sleep 2
echo "Step 2: Validating configuration and environment..."
sleep 2
echo "Step 3: Deploying application to local machine..."
sleep 2
echo "SUCCESS: Release $TAG successfully deployed to local machine!"
echo "========================================="</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers/>
</project>"""

def setup_jenkins(retries=15, delay=3):
    session = requests.Session()
    if JENKINS_USER and JENKINS_API_TOKEN:
        session.auth = (JENKINS_USER, JENKINS_API_TOKEN)

    print(f"Checking Jenkins at {JENKINS_URL}...")
    for i in range(retries):
        try:
            r = session.get(f"{JENKINS_URL}/api/json", timeout=5)
            if r.status_code == 200:
                print("Jenkins is reachable!")
                break
        except Exception:
            pass
        print(f"Waiting for Jenkins... attempt {i+1}/{retries}")
        time.sleep(delay)
    else:
        print("Could not reach Jenkins.")
        return False

    # Check crumb
    try:
        crumb_r = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", timeout=5)
        if crumb_r.status_code == 200:
            crumb_data = crumb_r.json()
            session.headers[crumb_data["crumbRequestField"]] = crumb_data["crumb"]
    except Exception:
        pass

    session.headers["Content-Type"] = "application/xml"
    job_resp = session.post(f"{JENKINS_URL}/createItem?name=deploy-job", data=XML_CONFIG)
    if job_resp.status_code in (200, 201):
        print("Successfully created 'deploy-job' on Jenkins!")
    elif job_resp.status_code == 400 and "already exists" in job_resp.text:
        print("'deploy-job' already exists on Jenkins.")
    else:
        print(f"Job creation returned status {job_resp.status_code}: {job_resp.text}")
    return True

if __name__ == "__main__":
    setup_jenkins()

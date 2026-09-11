import os
import requests
import xml.sax.saxutils as saxutils
from dotenv import load_dotenv

load_dotenv()

JENKINS_URL = os.getenv("JENKINS_URL", "http://localhost:8088").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "admin")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "admin")
GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN", "")

SHELL_SCRIPT = """set -e
echo "================================================================="
echo "STARTING REAL SPRING BOOT API CI/CD BUILD & DEPLOYMENT"
echo "Repository: $REPO_URL"
echo "Release Tag: $TAG"
echo "Host Deploy Target: $DEPLOY_DIR"
echo "Timestamp: $(date)"
echo "================================================================="

export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
echo "--> Using Java: $(java -version 2>&1 | head -n 1)"
echo "--> Using Maven: $(mvn -version 2>&1 | head -n 1)"

BUILD_SRC_DIR="${WORKSPACE}/source"
rm -rf "${BUILD_SRC_DIR}"
mkdir -p "${BUILD_SRC_DIR}"

echo "--> Step 1: Cloning repository and checking out release tag '${TAG}'..."
if [ -n "$GITHUB_TOKEN" ]; then
    CLONE_URL=$(echo "${REPO_URL}" | sed -E "s|https://|https://${GITHUB_TOKEN}@|")
else
    CLONE_URL="${REPO_URL}"
fi

git clone "${CLONE_URL}" "${BUILD_SRC_DIR}"
cd "${BUILD_SRC_DIR}"
git checkout "tags/${TAG}" || git checkout "${TAG}" || git checkout master

echo "--> Current Git commit:"
git log -1 --oneline

echo "--> Step 2: Compiling and packaging Spring Boot application with Maven..."
mvn clean package -DskipTests

JAR_FILE=$(find target -maxdepth 1 -name "*.jar" ! -name "*sources*" ! -name "*original*" | head -n 1)
if [ -z "$JAR_FILE" ]; then
    echo "ERROR: No executable jar was generated in target/!"
    exit 1
fi
echo "--> Successfully generated artifact: $JAR_FILE"

echo "--> Step 3: Deploying artifact directly to host machine directory: $DEPLOY_DIR"
mkdir -p "${DEPLOY_DIR}"
cp "$JAR_FILE" "${DEPLOY_DIR}/app.jar"
echo "${TAG}" > "${DEPLOY_DIR}/current_version.txt"
date > "${DEPLOY_DIR}/deployed_at.txt"

# Create Linux/Bash launcher
cat << 'EOF' > "${DEPLOY_DIR}/start.sh"
#!/bin/bash
exec java -jar app.jar
EOF
chmod +x "${DEPLOY_DIR}/start.sh"

# Create Windows Batch launcher
cat << 'EOF' > "${DEPLOY_DIR}/start.bat"
@echo off
echo Starting Spring Boot API on Windows Host...
java -jar app.jar
pause
EOF

echo "================================================================="
echo "SUCCESS: SPRING BOOT API DEPLOYED DIRECTLY TO HOST MACHINE!"
echo "Host Artifact: ${DEPLOY_DIR}/app.jar"
echo "Deployed Version: $(cat "${DEPLOY_DIR}/current_version.txt")"
echo "Deployment Timestamp: $(cat "${DEPLOY_DIR}/deployed_at.txt")"
echo "Windows Launcher: ${DEPLOY_DIR}/start.bat"
echo "Linux/WSL Launcher: ${DEPLOY_DIR}/start.sh"
echo "================================================================="
"""

def create_job():
    escaped_script = saxutils.escape(SHELL_SCRIPT)
    xml_config = f"""<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description>Spring Boot Java API Build &amp; Deploy Pipeline (Host Machine Mounted)</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.StringParameterDefinition>
          <name>REPO_URL</name>
          <description>Git Repository URL</description>
          <defaultValue>https://github.com/ssJvirtually/sampleserver.git</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>TAG</name>
          <description>Release Tag to Checkout and Build</description>
          <defaultValue>v1.0.0</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>DEPLOY_DIR</name>
          <description>Target Deployment Directory (Host Mounted)</description>
          <defaultValue>/host_deployments/sampleserver</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.PasswordParameterDefinition>
          <name>GITHUB_TOKEN</name>
          <description>GitHub Token for Private Repo Cloning</description>
          <defaultValue>{GITHUB_TOKEN}</defaultValue>
        </hudson.model.PasswordParameterDefinition>
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
      <command>{escaped_script}</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers/>
</project>"""

    session = requests.Session()
    session.auth = (JENKINS_USER, JENKINS_API_TOKEN)
    try:
        crumb_r = session.get(f"{JENKINS_URL}/crumbIssuer/api/json", timeout=5)
        if crumb_r.status_code == 200:
            data = crumb_r.json()
            session.headers[data["crumbRequestField"]] = data["crumb"]
    except Exception:
        pass

    session.headers["Content-Type"] = "application/xml"
    res = session.post(f"{JENKINS_URL}/job/spring-api-deploy-job/config.xml", data=xml_config)
    if res.status_code == 200:
        print("Updated 'spring-api-deploy-job' config for host mounting successfully!")
    else:
        res2 = session.post(f"{JENKINS_URL}/createItem?name=spring-api-deploy-job", data=xml_config)
        print("Create response:", res2.status_code)

if __name__ == "__main__":
    create_job()

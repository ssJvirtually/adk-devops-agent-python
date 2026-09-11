import jenkins.model.*
import hudson.model.*
import hudson.tasks.*

def instance = Jenkins.getInstance()
def jobName = "deploy-job"

if (instance.getItem(jobName) == null) {
    def project = instance.createProject(FreeStyleProject, jobName)
    
    def paramsDef = [
        new StringParameterDefinition("TAG", "v1.0.0", "Release Tag to Deploy"),
        new StringParameterDefinition("REPO", "main-repo", "Repository Name")
    ]
    project.addProperty(new ParametersDefinitionProperty(paramsDef))
    
    def shellScript = '''
echo "========================================="
echo "Starting deployment for repository: "
echo "Deploying release tag: "
echo "Deployment target: local machine"
echo "Timestamp: 09/11/2026 14:32:39"
echo "Step 1: Fetching code artifact for tag ..."
sleep 2
echo "Step 2: Validating configuration and environment..."
sleep 2
echo "Step 3: Deploying application to local machine..."
sleep 2
echo "SUCCESS: Release  successfully deployed!"
echo "========================================="
'''
    project.getBuildersList().add(new Shell(shellScript))
    project.save()
    println("--> deploy-job created successfully")
} else {
    println("--> deploy-job already exists")
}

import sys
from time import sleep
import re
import os
from ods_ci.utils.scripts.logger import log
from ods_ci.utils.scripts.util import execute_command
from pathlib import Path


# Get the available Azure/ARO versions
def get_aro_version(version) -> str | None:

    char_to_count = "."

    if version.count(char_to_count) == 1:
        version = version + "."

    get_versions_cmd=(f"az aro get-versions -l eastus | grep {version}")
    final_list = []

    ret = execute_command(get_versions_cmd)

    version_string = re.sub("[\"\']", "", ret)
    version_string = version_string.lstrip(' ').replace("\n","").replace(",","")
    version_list = version_string.split()

    for version_string in version_list:
        if version in version_string:
            final_list.append(version_string)

    if len(final_list) > 0:
        return final_list[-1]
    else:
        log.error("INVALID OCP VERSION FOR ARO CLUSTER: ", version)
        log.error("Versions available:")
        execute_command("az aro get-versions -l eastus")
        sys.exit(1)
    

# ARO cli login
def aro_cli_login(aro_client_id, aro_tenant_id, aro_secret_pwd):

    aro_cli_login_cmd=(f"az login --service-principal -u {aro_client_id} -p {aro_secret_pwd} --tenant {aro_tenant_id}")

    ret = execute_command(aro_cli_login_cmd)
    if "ERROR" in ret:
        log.error("LOGIN UNSUCCESSFUL")
        log.error("Invalid tenant id, client it and/or secret")
        sys.exit(1)
    else:
        print("LOGIN SUCCESSFUL")


# Execute Terraform to create the cluster
def execute_terraform(cluster_name, subscription_id, version, location, directory_path):
    print(">>>>> Here is the cluster name again: ", cluster_name)
    print(">>>>> Here is the version: ", version)
    print(">>>>> Here is the location: ", location)
    pull_secret_path = get_pull_secret(directory_path)
    execute_command(f"terraform init && terraform plan -out tf.plan -var=subscription_id={subscription_id} -var=cluster_name={cluster_name} -var=aro_version={version} -var=location={location} -var=pull_secret_path={pull_secret_path} && terraform apply tf.plan")


# Get information (api url, console url, cluster version, provisioning state, location) from the cluster
def get_aro_cluster_info(cluster_name):
    api_server_url = get_cluster_info_field_value(cluster_name, "apiserverProfile.url")
    console_url = get_cluster_info_field_value(cluster_name, "consoleProfile.url")
    cluster_version =  get_cluster_info_field_value(cluster_name, "clusterProfile.version")
    provisioning_state = get_cluster_info_field_value(cluster_name, "provisioningState")
    cluster_location =  get_cluster_info_field_value(cluster_name, "location") 

    if provisioning_state == "Succeeded":
        print("cluster is up and running")
    else:
        print("Provisioning state: ", provisioning_state)
        print("The cluster is not in a healthy state. Please manually delete all resources from the Azure portal")
        sys.exit(1)

    print("Cluster name: ", cluster_name)
    print("Provisioning status: ", provisioning_state)
    print("Cluster location: ", cluster_location)
    print("Version: ", cluster_version)
    print("Console URL: ", console_url)
    print("API URL: ", api_server_url)


# Log into the ARO cluster
def aro_cluster_login(cluster_name, file_path, subscription_id):
    resource_group = cluster_name + "-rg"
    output = 0

    print("Obtain cluster credentials...")
    api_server_url = get_cluster_info_field_value(cluster_name, "apiserverProfile.url")
    api_server_url = api_server_url[:-1]

    aro_cluster_pwd = execute_command(f"az aro list-credentials --name {cluster_name} --resource-group {resource_group} -o tsv --query kubeadminPassword")

    print("Login to the cluster...")

    # set KUBECONFIG
    print("Setting the KUBECONFIG...")
    execute_command(f"az aro get-admin-kubeconfig --subscription {subscription_id} --name {cluster_name} --resource-group {resource_group}")
    kubeconfig_path = file_path + "/kubeconfig"
    print("KUBECONFIG: ", kubeconfig_path)
    os.environ["KUBECONFIG"] = kubeconfig_path
    # print("waiting...")
    # sleep(15)
    # print("Now login...")
    cluster_login_command = (f"oc login --insecure-skip-tls-verify=true --kubeconfig={kubeconfig_path} {api_server_url} -u kubeadmin -p {aro_cluster_pwd}")

    # print("[" + cluster_login_command + "]")
   
    output = execute_command(cluster_login_command)
    
    print(output)

    if "Login successful" in output:
        execute_command("oc get nodes")
        execute_command("oc get co; oc get clusterversion")
    else:
        log.error("unable to log into cluster")
        log.error("get the cluster credentials with the command:")
        log.error("az aro list-credentials --name <cluster name> --resource-group <resource group> -o tsv --query kubeadminPassword")
        sys.exit(1)


# Delete the ARO cluster
def aro_cluster_delete(cluster_name):
    resource_group = cluster_name + "-rg"
    provisioning_state = get_cluster_info_field_value(cluster_name, "provisioningState")
    
    time_count = 0
    if provisioning_state == "Succeeded":
        print("Deleting cluster: ", cluster_name)
        execute_command(f"az aro delete --name {cluster_name} --resource-group {resource_group} --yes -y --no-wait")
        delete_provisioning_state = get_cluster_info_field_value(cluster_name, "provisioningState")
        while delete_provisioning_state == "Deleting" and time_count < 3600:
            print(delete_provisioning_state)
            sleep(60)
            time_count += 60
            delete_provisioning_state = get_cluster_info_field_value(cluster_name, "provisioningState")
        if "ERROR: (ResourceNotFound)" in delete_provisioning_state:
            print("Cluster has been successfully deleted")
        elif time_count >= 3600:
            log.error("Time exceeded for cluster deletion. Please delete the cluster manually")
            sys.exit(1)

    else:
        print("Cannot find cluster. Check for the cluster and delete manually if present.")
        sys.exit(1)


 # Get the value of a field from the cluster info json   
def get_cluster_info_field_value(cluster_name, cluster_info_field):
    resource_group = cluster_name + "-rg"

    command_output = execute_command(f"az aro show --name {cluster_name} --resource-group {resource_group} | jq '.{cluster_info_field}'")
    command_output = re.sub("[\"\']", "", command_output)

    return command_output.strip()


# Check for an existing cluster with the same name
def check_for_existing_cluster(cluster_name):
    provisioning_state = get_cluster_info_field_value(cluster_name, "provisioningState")

    if ("ERROR: (ResourceNotFound)" in provisioning_state) or ("ERROR: (ResourceGroupNotFound)" in provisioning_state):
        print(f"cluster does not exist. Proceeding with provisioning cluster {cluster_name}")
        return None
    else:
        log.error(f"ERROR: cluster {cluster_name} exists.")
        sys.exit(1)


# Find the pull secret
def get_pull_secret(directory_path):
    pull_secret_name = "pull-secret.txt"
    pull_secret_path=""
    for root, dirs, files in os.walk(directory_path):
        if pull_secret_name in files:
            pull_secret_path = os.path.join(root, pull_secret_name)
    return pull_secret_path


# Clone the repo with the terraform files
def clone_terraform_files():
    terraform_files = "terraform-aro-ods-ci"
    file_path = Path(terraform_files)
    terraform_repo = "https://github.com/lenahorsley/terraform-aro-ods-ci.git"
    terraform_repo_clone_command = (f"git clone {terraform_repo}")
    print("Searching for the directory: ", file_path)
    if file_path.exists():
        print("The directory exists. Removing for a new cluster build")
        os.system(f"rm -rf {terraform_files}")
        sleep(30)
        print(f"Previous {terraform_files} directory removed") 
    else:
        print(f"The directory {terraform_files} does not exist") 

    print("Cloning Terraform files...")
    os.system(terraform_repo_clone_command)
    terraform_path = os.path.dirname(os.path.abspath(__file__)) + "/" + terraform_files
    os.chdir(terraform_path)
    return terraform_path
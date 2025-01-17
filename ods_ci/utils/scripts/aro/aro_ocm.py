import sys
import argparse
from time import sleep
import re
import os
from pathlib import Path

from aroOps import (
    get_aro_version,
    aro_cli_login,
    execute_terraform,
    get_aro_cluster_info,
    aro_cluster_login,
    aro_cluster_delete,
    check_for_existing_cluster,
    clone_terraform_files,
)

from ods_ci.utils.scripts.logger import log
from ods_ci.utils.scripts.util import execute_command

class AroClusterManager:
    def __init__(self, args={}):
        self.aro_client_id = args.get("aro_client_id")
        self.aro_tenant_id = args.get("aro_tenant_id")
        self.aro_secret_pwd = args.get("aro_secret_pwd")
        self.aro_ocp_version = args.get("aro_ocp_version")
        self.aro_cluster_name = args.get("aro_cluster_name")
        self.aro_subscription_id = args.get("aro_subscription_id")
        self.aro_location = args.get("location")
        self.aro_pull_secret_path = args.get("aro_pull_secret_path")



    def create_aro_cluster(self):
        aro_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(aro_path)

        #Clone the repo with the Terraform files
        terraform_path = clone_terraform_files()

        # Now, create the cluster
        print("Name of cluster to be created", self.aro_cluster_name)
        aro_cli_login(self.aro_client_id, self.aro_tenant_id, self.aro_secret_pwd)
        my_version = get_aro_version(self.aro_ocp_version)
        print("OCP version selected for ARO cluster: ", my_version)
        check_for_existing_cluster(self.aro_cluster_name)
        execute_terraform(self.aro_cluster_name, self.aro_subscription_id, str(my_version), self.aro_location, self.aro_pull_secret_path)
        get_aro_cluster_info(self.aro_cluster_name)
        aro_cluster_login(self.aro_cluster_name, terraform_path, self.aro_subscription_id)

    def delete_aro_cluster(self):
        print("Name of cluster to be deleted", self.aro_cluster_name)
        aro_cli_login(self.aro_client_id, self.aro_tenant_id, self.aro_secret_pwd)
        get_aro_cluster_info(self.aro_cluster_name)
        aro_cluster_delete(self.aro_cluster_name)


def main():
    parser = argparse.ArgumentParser(
        description="ARO Cluster Actions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    

    subparsers = parser.add_subparsers(title="Available sub commands", help="Available sub commands")
   

    # Argument parser for creating an ARO cluster
    aro_create_cluster_parser = subparsers.add_parser(
        "create_aro_cluster",
        help="create ARO clusters",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Argument parser for deleting an ARO cluster
    aro_delete_cluster_parser = subparsers.add_parser(
        "delete_aro_cluster",
        help="delete ARO clusters",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # aro_create_cluster_parser arguments/parameters
    aro_create_cluster_parser.add_argument(
        "--aro-cluster-name",
        required=True,
        action="store",
        dest="aro_cluster_name",
        help="ARO Cluster Name",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-client-id",
        required=True,
        action="store",
        dest="aro_client_id",
        help="ARO Client ID",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-tenant-id",
        required=True,
        action="store",
        dest="aro_tenant_id",
        help="ARO Tenant ID",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-subscription-id",
        required=True,
        action="store",
        dest="aro_subscription_id",
        help="ARO Subscription ID",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-secret-pwd",
        required=True,
        action="store",
        dest="aro_secret_pwd",
        help="ARO Secret PWD",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-ocp-version",
        required=True,
        action="store",
        dest="aro_ocp_version",
        help="ARO OCP Version",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-location",
        required=True,
        action="store",
        dest="aro_location",
        help="ARO Location",
    )

    aro_create_cluster_parser.add_argument(
        "--aro-pull-secret-path",
        required=True,
        action="store",
        dest="aro_pull_secret_path",
        help="ARO Pull Secret path",
    )

    # aro_delete_cluster_parser arguments/parameters
    aro_delete_cluster_parser.add_argument(
        "--aro-cluster-name",
        required=True,
        action="store",
        dest="aro_cluster_name",
        help="ARO Cluster Name",
    )

    aro_delete_cluster_parser.add_argument(
        "--aro-client-id",
        required=True,
        action="store",
        dest="aro_client_id",
        help="ARO Client ID",
    )

    aro_delete_cluster_parser.add_argument(
        "--aro-tenant-id",
        required=True,
        action="store",
        dest="aro_tenant_id",
        help="ARO Tenant ID",
    )

    aro_delete_cluster_parser.add_argument(
        "--aro-subscription-id",
        required=True,
        action="store",
        dest="aro_subscription_id",
        help="ARO Subscription ID",
    )

    aro_delete_cluster_parser.add_argument(
        "--aro-secret-pwd",
        required=True,
        action="store",
        dest="aro_secret_pwd",
        help="ARO Secret PWD",
    )


    aro_cluster_manager = AroClusterManager()

    aro_create_cluster_parser.set_defaults(func=aro_cluster_manager.create_aro_cluster)

    aro_delete_cluster_parser.set_defaults(func=aro_cluster_manager.delete_aro_cluster) 
    args = parser.parse_args(namespace=aro_cluster_manager)
    if hasattr(args, "func"):
        args.func()


if __name__ == "__main__":
    main()
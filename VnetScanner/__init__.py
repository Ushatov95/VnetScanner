import azure.functions as func
import subprocess
import json
import os
from datetime import datetime

def run_az_command(command, ignore_error=False):
    """Run an Azure CLI command and return the output."""
    print(f"Executing AZ command: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"AZ command STDOUT: {result.stdout.strip()}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"AZ command FAILED: {e.cmd}")
        print(f"AZ command STDOUT (on error): {e.stdout.strip()}")
        print(f"AZ command STDERR (on error): {e.stderr.strip()}")
        if not ignore_error:
            print(f"Error running command: {e}")
            print(f"Error output: {e.stderr}")
            raise
        return e.stderr

def get_network_info():
    """Get VNets and Subnets information from the current subscription."""
    print("Querying network information...")
    
    # Get VNets with more details including location, resource group, address space, and subnets' address prefixes
    # The command automatically uses the active subscription context.
    vnets_cmd = "az network vnet list --query \"[].{name:name, location:location, resourceGroup:resourceGroup, addressSpace:addressSpace.addressPrefixes[0], subnets:subnets[].{name:name, addressPrefix:addressPrefix}}\" -o json"
    vnets_output = run_az_command(vnets_cmd)
    vnets_data = json.loads(vnets_output)
    
    print(f"Found {len(vnets_data)} VNets")
    return vnets_data

def _upsert_entity(table_name, storage_account, partition_key, row_key, entity_props):
    """Helper to upsert an entity (replace if exists, insert if not)."""
    entity_str = ' '.join(entity_props)
    
    # Try to replace the entity first, if it doesn't exist, insert it
    replace_cmd = f"az storage entity replace --table-name {table_name} --entity {entity_str} --account-name {storage_account} --auth-mode login"
    replace_output = run_az_command(replace_cmd, ignore_error=True)
    
    if "ResourceNotFound" in replace_output or "The specified entity does not exist" in replace_output:
        insert_cmd = f"az storage entity insert --table-name {table_name} --entity {entity_str} --account-name {storage_account} --auth-mode login"
        run_az_command(insert_cmd)
        print(f"Inserted entity: PartitionKey={partition_key}, RowKey={row_key}")
    else:
        print(f"Replaced entity: PartitionKey={partition_key}, RowKey={row_key}")

def store_network_info(table_name, storage_account, vnets_data):
    """Store VNet and Subnet information in the table."""
    print("Storing network information...")
    
    for vnet in vnets_data:
        vnet_name = vnet['name']
        vnet_location = vnet.get('location', 'N/A')
        vnet_resource_group = vnet.get('resourceGroup', 'N/A')
        vnet_address_space = vnet.get('addressSpace', 'N/A')
        subnets = vnet['subnets']
        
        # Store VNet information
        vnet_entity_props = [
            f"PartitionKey=vnet",
            f"RowKey={vnet_name}",
            f"Type=VNet",
            f"Name={vnet_name}",
            f"Location=\"{vnet_location}\"",
            f"ResourceGroup=\"{vnet_resource_group}\"",
            f"AddressSpace=\"{vnet_address_space}\"",
            f"Timestamp={datetime.utcnow().isoformat()}"
        ]
        _upsert_entity(table_name, storage_account, "vnet", vnet_name, vnet_entity_props)
        print(f"Processed VNet: {vnet_name}")
        
        # Store Subnet information
        for subnet in subnets:
            subnet_name = subnet['name']
            subnet_address_prefix = subnet.get('addressPrefix', 'N/A')
            subnet_entity_props = [
                f"PartitionKey=subnet",
                f"RowKey={subnet_name}",
                f"Type=Subnet",
                f"Name={subnet_name}",
                f"VNetName={vnet_name}",
                f"AddressPrefix=\"{subnet_address_prefix}\"",
                f"Timestamp={datetime.utcnow().isoformat()}"
            ]
            _upsert_entity(table_name, storage_account, "subnet", subnet_name, subnet_entity_props)
            print(f"Processed Subnet: {subnet_name} in VNet: {vnet_name}")

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        print("Starting VNet and Subnet scan...")

        # Dynamically get Subscription ID and Tenant ID
        print("Retrieving current subscription and tenant information...")
        account_info_cmd = "az account show -o json"
        account_info_output = run_az_command(account_info_cmd)
        account_info = json.loads(account_info_output)
        
        subscription_id = account_info.get("id", "N/A")
        tenant_id = account_info.get("tenantId", "N/A")
        
        print(f"Operating in Subscription ID: {subscription_id}")
        print(f"Tenant ID: {tenant_id}")

        # Get storage account details
        storage_account = os.environ["STORAGE_ACCOUNT_NAME"]
        # storage_key = os.environ["STORAGE_ACCOUNT_KEY"] # No longer needed with --auth-mode login
        
        print(f"Using storage account: {storage_account}")
        
        # Table creation logic removed as per user request
        table_name = os.environ["STORAGE_TABLE_NAME"]
        
        # Get network information
        vnets_data = get_network_info()
        
        # Store network information
        store_network_info(table_name, storage_account, vnets_data)
        
        return func.HttpResponse(
            f"Successfully scanned and stored {len(vnets_data)} VNets and their subnets",
            status_code=200
        )

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )

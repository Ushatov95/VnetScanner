import azure.functions as func
import logging
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.data.tables import TableServiceClient
from datetime import datetime

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Retrieve environment variables for Azure configuration
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    storage_account_name = os.environ["STORAGE_ACCOUNT_NAME"]
    table_name = os.environ["STORAGE_TABLE_NAME"]

    try:
        # Initialize Azure credentials using Managed Identity
        # DefaultAzureCredential attempts to authenticate via various methods,
        # including Managed Identity when deployed to Azure Functions.
        credential = DefaultAzureCredential()
        logging.info("DefaultAzureCredential initialized for Managed Identity.")

        # Initialize Azure Network Management Client
        # This client is used to interact with Azure Virtual Networks and Subnets.
        network_client = NetworkManagementClient(credential, subscription_id)
        logging.info("Azure Network Management Client initialized.")
        
        # Initialize Azure Table Service Client
        # This client is used to interact with Azure Table Storage.
        # The endpoint is constructed using the storage account name.
        table_service_endpoint = f"https://{storage_account_name}.table.core.windows.net"
        logging.info(f"Azure Table Service endpoint: {table_service_endpoint}")
        table_service = TableServiceClient(
            endpoint=table_service_endpoint,
            credential=credential
        )
        logging.info("Azure Table Service Client initialized.")
        
        # Get or create the Azure Table Storage table
        # The function attempts to get the table; if it doesn't exist, it creates it.
        try:
            table_client = table_service.get_table_client(table_name)
            logging.info(f"Table '{table_name}' found.")
        except Exception:
            logging.info(f"Table '{table_name}' not found, attempting to create it.")
            table_client = table_service.create_table(table_name)
            logging.info(f"Table '{table_name}' created successfully.")

        # List all Virtual Networks (VNets) in the subscription
        vnets = network_client.virtual_networks.list_all()
        logging.info("Successfully retrieved all Virtual Networks.")
        
        # Process each VNet and its subnets
        for vnet in vnets:
            logging.info(f"Processing VNet: {vnet.name} in location {vnet.location}")
            
            # Extract the resource group name from the VNet's ID
            resource_group_name = vnet.id.split('/')[4]
            
            # List subnets for the current VNet
            subnets = network_client.subnets.list(resource_group_name, vnet.name)
            logging.info(f"Successfully retrieved subnets for VNet: {vnet.name}")
            
            # For each subnet, create an entity and store it in Azure Table Storage
            for subnet in subnets:
                # Construct the entity to be stored.
                # PartitionKey and RowKey are mandatory for Azure Table Storage and form the unique identifier for each entity.
                # We use the VNet name as PartitionKey and the Subnet name as RowKey.
                entity = {
                    'PartitionKey': vnet.name,
                    'RowKey': subnet.name,
                    'vnetName': vnet.name,
                    'subnetName': subnet.name,
                    'addressPrefix': subnet.address_prefix,
                    'resourceGroup': resource_group_name,
                    'location': vnet.location,
                    'timestamp': datetime.utcnow().isoformat(),
                    'vnetId': vnet.id,
                    'subnetId': subnet.id,
                    'vnetAddressSpace': vnet.address_space.address_prefixes[0] if vnet.address_space and vnet.address_space.address_prefixes else "",
                    'subnetAddressSpace': subnet.address_prefix # Adding subnet address space as requested
                }
                
                logging.info(f"Attempting to write entity for subnet '{subnet.name}' in VNet '{vnet.name}'.")
                
                try:
                    # Attempt to update the entity first.
                    # If it doesn't exist, an exception will be raised.
                    table_client.update_entity(entity)
                    logging.info(f"Updated existing entity for subnet '{subnet.name}' in VNet '{vnet.name}'.")
                except Exception as e:
                    # If the entity doesn't exist (ResourceNotFound), create a new one.
                    if "ResourceNotFound" in str(e) or "The specified entity does not exist" in str(e):
                        logging.info(f"Entity for subnet '{subnet.name}' in VNet '{vnet.name}' not found, creating new entity.")
                        table_client.create_entity(entity)
                        logging.info(f"Created new entity for subnet '{subnet.name}' in VNet '{vnet.name}'.")
                    else:
                        # Log any other unexpected errors during table operation.
                        logging.error(f"Error processing subnet '{subnet.name}' for VNet '{vnet.name}': {str(e)}")

        # Return a success response upon successful completion of the scan.
        return func.HttpResponse(
            "VNet and Subnet scan completed successfully.",
            status_code=200
        )

    except Exception as e:
        # Catch any high-level exceptions and return an error response.
        logging.error(f"An unexpected error occurred during function execution: {str(e)}")
        return func.HttpResponse(
             f"An error occurred: {str(e)}",
             status_code=500
        )

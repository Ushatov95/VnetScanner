import azure.functions as func
import logging
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.data.tables import TableServiceClient
from datetime import datetime

# Configure logging for azure.identity and azure.data.tables
# This needs to be done before any azure sdk clients are initialized
logging.getLogger("azure.identity").setLevel(logging.DEBUG)
logging.getLogger("azure.data.tables").setLevel(logging.DEBUG)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Get environment variables
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    storage_account_name = os.environ["STORAGE_ACCOUNT_NAME"]
    table_name = os.environ["STORAGE_TABLE_NAME"]

    try:
        # Initialize Azure credentials
        credential = DefaultAzureCredential()
        logging.info("DefaultAzureCredential initialized.")
        
        # Initialize Network Management Client
        network_client = NetworkManagementClient(credential, subscription_id)
        logging.info("NetworkManagementClient initialized.")
        
        # Initialize Table Service Client
        table_service_endpoint = f"https://{storage_account_name}.table.core.windows.net"
        logging.info(f"Table Service Endpoint: {table_service_endpoint}")
        table_service = TableServiceClient(
            endpoint=table_service_endpoint,
            credential=credential
        )
        logging.info("TableServiceClient initialized.")
        
        # Get or create table
        try:
            table_client = table_service.get_table_client(table_name)
            logging.info(f"Table {table_name} found.")
        except Exception as e:
            logging.info(f"Table {table_name} not found, attempting to create it. Error: {str(e)}")
            table_client = table_service.create_table(table_name)
            logging.info(f"Table {table_name} created successfully.")

        # Get all VNets
        vnets = network_client.virtual_networks.list_all()
        logging.info("Successfully listed all VNets.")
        
        # Process each VNet
        for vnet in vnets:
            logging.info(f"Processing VNet: {vnet.name}")
            
            # Extract resource group name from VNet ID
            resource_group_name = vnet.id.split('/')[4]
            
            # Get subnets for this VNet
            subnets = network_client.subnets.list(resource_group_name, vnet.name)
            logging.info(f"Successfully listed subnets for VNet: {vnet.name}")
            
            # Create entity for each subnet
            for subnet in subnets:
                entity = {
                    'PartitionKey': vnet.name,
                    'RowKey': subnet.name,'VnetName': vnet.name,
                    'SubnetName': subnet.name,
                    'AddressPrefix': subnet.address_prefix,
                    'ResourceGroup': resource_group_name,
                    'Location': vnet.location,
                    'Timestamp': datetime.utcnow().isoformat()
                }
                
                try:
                    # Try to update first
                    logging.info(f"Attempting to update entity for subnet {subnet.name} in VNet {vnet.name}")
                    table_client.update_entity(entity)
                    logging.info(f"Updated entity for subnet {subnet.name} in VNet {vnet.name}")
                except Exception as e:
                    if "ResourceNotFound" in str(e) or "The specified entity does not exist" in str(e): # Handle specific error for non-existent entity
                        # If entity doesn't exist, create it
                        logging.info(f"Entity for subnet {subnet.name} in VNet {vnet.name} not found, attempting to create.")
                        table_client.create_entity(entity)
                        logging.info(f"Created entity for subnet {subnet.name} in VNet {vnet.name}")
                    else:
                        logging.error(f"Error processing subnet {subnet.name}: {str(e)}")

        return func.HttpResponse(
            "VNet and Subnet scan completed successfully.",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error in function execution: {str(e)}")
        return func.HttpResponse(
             f"Error: {str(e)}",
             status_code=500
        )

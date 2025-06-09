import azure.functions as func
import logging
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.data.tables import TableServiceClient
from datetime import datetime

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Get environment variables
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    storage_account_name = os.environ["STORAGE_ACCOUNT_NAME"]
    storage_account_key = os.environ["STORAGE_ACCOUNT_KEY"]
    table_name = os.environ["STORAGE_TABLE_NAME"]

    try:
        # Initialize Azure credentials
        credential = DefaultAzureCredential()
        
        # Initialize Network Management Client
        network_client = NetworkManagementClient(credential, subscription_id)
        
        # Initialize Table Service Client
        table_service = TableServiceClient(
            account_url=f"https://{storage_account_name}.table.core.windows.net",
            credential=credential
        )
        
        # Get or create table
        try:
            table_client = table_service.get_table_client(table_name)
        except Exception as e:
            logging.info(f"Table {table_name} not found, creating it...")
            table_client = table_service.create_table(table_name)
            logging.info(f"Table {table_name} created successfully")

        # Get all VNets
        vnets = network_client.virtual_networks.list_all()
        
        # Process each VNet
        for vnet in vnets:
            logging.info(f"Processing VNet: {vnet.name}")
            
            # Get subnets for this VNet
            subnets = network_client.subnets.list(vnet.resource_group, vnet.name)
            
            # Create entity for each subnet
            for subnet in subnets:
                entity = {
                    'PartitionKey': vnet.name,
                    'RowKey': subnet.name,
                    'VnetName': vnet.name,
                    'SubnetName': subnet.name,
                    'AddressPrefix': subnet.address_prefix,
                    'ResourceGroup': vnet.resource_group,
                    'Location': vnet.location,
                    'Timestamp': datetime.utcnow().isoformat()
                }
                
                try:
                    # Try to update first
                    table_client.update_entity(entity)
                    logging.info(f"Updated entity for subnet {subnet.name} in VNet {vnet.name}")
                except Exception as e:
                    if "ResourceNotFound" in str(e):
                        # If entity doesn't exist, create it
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

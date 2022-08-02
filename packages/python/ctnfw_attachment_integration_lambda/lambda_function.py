from __future__ import print_function
import boto3
import os
import json
ec2 = boto3.client('ec2')

def lambda_handler(event, context):   
    message = event['Records'][0]['Sns']['Message']
    print(f"Message received from SNS: {message}")
    attachmentEvent = json.loads(message)
    transitGatewayAttachmentArn = attachmentEvent['detail']['transitGatewayAttachmentArn']
    print(f"Transit Gateway Attachment ARN is {transitGatewayAttachmentArn}")
    attachmentArray = transitGatewayAttachmentArn.split('/')
    print(f"Transit Gateway Attachment ID is {attachmentArray[1]}")
    ec2response1 = ec2.associate_transit_gateway_route_table(
        # Spoke route table
        TransitGatewayRouteTableId = os.environ["TGW_SPOKE_RTBL_ID"]
        TransitGatewayAttachmentId = attachmentArray[1],
        DryRun = False
    )
    print(f"{ec2response1}")
    ec2response2 = ec2.enable_transit_gateway_route_table_propagation(
        # Firewall route table
        TransitGatewayRouteTableId = os.environ["TGW_FIREWALL_RTBL_ID"],
        TransitGatewayAttachmentId = attachmentArray[1],
        DryRun = False
    )
    print(f"{ec2response2}")
    return()
from __future__ import print_function
import boto3
import os

sts = boto3.client('sts')
cloudformation = boto3.client('cloudformation')

def lambda_handler(event, context):
    childAccountId = event['detail']['serviceEventDetails']['createManagedAccountStatus']['account']['accountId']
    def addSCLaunchRoleStackSetInstanceForMemberAccount():  
        region = os.environ["AWS_REGION"]
        stackSetName = os.environ['STACKSET_NAME']
        
        print(f"Stackset name is {stackSetName}")
        print(f"Event Account ID is {childAccountId}")
        print("Calling CF StackSet update")
        cfresponse = cloudformation.create_stack_instances(
            StackSetName = stackSetName,
            DeploymentTargets = {
                'Accounts': [
                    childAccountId,
                ],
            },
            Regions = [
                region,
            ]
        )
        if cfresponse == None:
            print(f"Error {cfresponse}")
            return()
        else:
            operationId = cfresponse['OperationId']
            print(f"The StackSet operation ID is {operationId}")
    #end addSCLaunchRoleStackSetInstanceForMemberAccount

    def shareTGWToMemberAccount():
        stsResponse = sts.assume_role(
            RoleArn = os.environ["EXECUTION_ROLE_ARN"],
            RoleSessionName = "ControlTowerExecutionRoleSession"
        )
        print(f"Assumed Role ARN is {stsResponse['AssumedRoleUser']['Arn']}")
        ACCESS_KEY = stsResponse['Credentials']['AccessKeyId']
        SECRET_KEY = stsResponse['Credentials']['SecretAccessKey']
        SESSION_TOKEN = stsResponse['Credentials']['SessionToken']
        
        ram = boto3.client(
            'ram',
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                aws_session_token=SESSION_TOKEN,
        )

        print(f"Child account Id is {childAccountId}")
        
        tgwARN = os.environ["TGW_ARN"]
        print(f"The TGW ARN is {tgwARN}")
        tgwShareName = f"tgwShare-{childAccountId}"
        ramresponse = ram.create_resource_share(
        name = tgwShareName,
        resourceArns = [
            tgwARN,
        ],
        principals = [
            childAccountId,
        ],
        allowExternalPrincipals = True
        )
        if ramresponse['ResponseMetadata']['HTTPStatusCode'] != 200:
            print(f"Error, quitting: {ramresponse}")
            return()
        else:
            print(f"{ramresponse}")   
    addSCLaunchRoleStackSetInstanceForMemberAccount()
    shareTGWToMemberAccount()
    #end shareTGWToMemberAccount
#end lambda_handler
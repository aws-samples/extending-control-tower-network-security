# --------------- DNS Firewall
# Create firewall domain list
# aws route53resolver create-firewall-domain-list --name Test-List
# 
# Save ID of created list to parameter store, because it seems impossible to retrieve it again, even by name.
# aws ssm put-parameter --name route53resolverlistid --value 
# 
# Import domain list (imports entire list)
# aws route53resolver import-firewall-domains --firewall-domain-list-id
# 
# R53R Firewall can have *.example.com (no leading .)
# Ntwk Firewall can have .example.com (no leading *)
# ---------------- DNS Firewall Lambda
############# CloudFormation should: 
#   create a bucket with versioning, events enabled, and 2 prefixes - original and modified
#   modified prefix will contain 2 files - R53R and NFW
#   upload example list (example.org/net/com)
#   create rule group for Ntwk firewall
#   create rule group for R53R firewall
#   create initial firewall list and save firewall-domain-list-id to SSM
#   create lambda with env vars of S3 bucket, 
#   Lambda should be triggered by S3 event of new list upload


#use cases: 
#user wants to manage one central list for domain blocking
#user modifies (add/removes entries) 1 file, uploads to s3
#lambda parses file

# R53R Firewall can have *.example.com (no leading .)
# Ntwk Firewall can have .example.com (no leading *)
# Must get domain list and customize it for each service...

#manual cloudshell update: pip3 install boto3 --upgrade --user
#################################
#env_vars needed
domain_list_name = os.environ.get('domain_list_name')
#manual testing: domain_list_name = 'Example-List'

domain_list_location = os.environ.get('domain_list_location')
#syntax s3://bucket/prefix/file.txt
#manual testing: domain_list_location = 's3://dns-fw-list-ejkfh4f84/blockeddomains.txt'
#permissions: s3 get/put (specific bucket created by CF), SSM get, r53r and nfw rule group perms

NtwkFirewallRuleGroupArn = os.environ.get('NtwkFirewallRuleGroupArn')
# PS C:\Users\tapple> aws network-firewall describe-rule-group --rule-group-name "test-lambda-add" --type "STATEFUL" --region us-east-2
#manual testing: NtwkFirewallRuleGroupArn = "arn:aws:network-firewall:us-east-2:933980827860:stateful-rulegroup/test-lambda-add"

FirewallPolicyArn = os.environ.get('FirewallPolicyArn')
#manual testing: FirewallPolicyArn = "arn:aws:network-firewall:us-east-2:933980827860:firewall-policy/Firewall-Policy-1-02ef6f85416c"


import boto3
import json
import sys
import logging

s3 = boto3.client('s3')
r53rclient = boto3.client('route53resolver')
nfwclient = boto3.client('network-firewall')

sts_connection = boto3.client('sts')
from botocore.exceptions import ClientError


######### 2 lambdas? no, cross-account access to each member account. can we assume existing role that our CFN creates? AWSControlTowerExecutionRole
bucketname = domain_list_location.split('/')[2]
objectname = domain_list_location.split('/')[-1]
localfilename = domain_list_location.split('/')[-1]
s3.download_file(bucketname, objectname, localfilename)

with open(localfilename, 'r') as f:
    data = f.read()
    f.close()
    
strdata = data.splitlines()

# Append dot to each entry for Ntwk firewall ############################## combine appenddot and appendastr
def appenddomains():
    dot_list = []
    astr_list = []
    for str in strdata:
        dotstr = '.' + str
        dot_list.append(dotstr)
        astrstr = '*' + dotstr
        astr_list.append(astrstr)
    return dot_list, astr_list
    
appenddomainlist = appenddomains()
dotlist = appenddomainlist[0]
astrlist = appenddomainlist[1]
#Append asterisk and dot to each entry for R53R firewall
#def appendastr():
#    astr_list = []
#    for str in dotlist:
#        newstr = '*' + str
#        astr_list.append(newstr)
#    return astr_list

# save R53R (asterisk) file locally
with open ('astrlist.txt', 'w') as filehandle:
    for listitem in astrlist:
        filehandle.write('%s\n' % listitem)
    filehandle.close()


# save R53R file to s3 for bulk upload
def upload_file(file_name, bucket, object_name=None):
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    try:
        response = s3.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True
    
upload_file(astrlist.txt, bucketname)
# Ntwk firewall does not support bulk upload, no need to upload

response = r53rclient.create_firewall_domain_list(
    Name=domain_list_name ############################### do we need this? CFN SC Product is creating the list.
) 

# https://aws.amazon.com/premiumsupport/knowledge-center/lambda-function-assume-iam-role/

#acct_b = CT master acct - below code checks to see if svc catalog product has been provisioned.
acct_b = sts_connection.assume_role(
    RoleArn="arn:aws:iam::366696389109:role/LambdaServiceCatalogAccess", #### master account hardcoded, fix
    RoleSessionName="cross_acct_lambda"
)

ACCESS_KEY = acct_b.get('Credentials').get('AccessKeyId')
SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
SESSION_TOKEN = acct_b['Credentials']['SessionToken']

svccatclient = boto3.client(
    'servicecatalog',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    aws_session_token=SESSION_TOKEN   
)
svccatresponse = svccatclient.describe_portfolio_shares(
    PortfolioId='port-3laii46nzk23u', #### hardcoded, fix
    Type='ORGANIZATION'
)

{'PortfolioShareDetails': [{'PrincipalId': 'o-gbs5q97xkd', 'Type': 'ORGANIZATION', 'Accepted': True, 'ShareTagOptions': False}], 'ResponseMetadata': {'RequestId': '3b3981a9-0ba1-4704-b54c-bbe61cf5fd6d', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': '3b3981a9-0ba1-4704-b54c-bbe61cf5fd6d', 'content-type': 'application/x-amz-json-1.1', 'content-length': '148', 'date': 'Fri, 25 Jun 2021 17:00:07 GMT'}, 'RetryAttempts': 0}}

svccatresponse2 = svccatclient.list_portfolio_access(
    PortfolioId='port-3laii46nzk23u', #### hardcoded, fix
    OrganizationParentId='o-gbs5q97xkd' ## hardcoded, fix
)

{'AccountIds': ['332165721655', '933980827860', '792087581269', '187547605332', '093829855164', '162495624595'], 'ResponseMetadata': {'RequestId': 'c7998f3e-b296-44e9-b9cb-64b3a4f36036', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': 'c7998f3e-b296-44e9-b9cb-64b3a4f36036', 'content-type': 'application/x-amz-json-1.1', 'content-length': '106', 'date': 'Fri, 13 Aug 2021 17:39:42 GMT'}, 'RetryAttempts': 0}}

svccatresponse3 = svccatclient.list_record_history( ###################### looks like I need to run this in conjunction with list_portfolio_access and enumerate EACH ACCOUNT. 
    AccessLevelFilter={
        'Key': 'Account',
        'Value': '162495624595' ########## hardcoded, fix
    },
    SearchFilter={
        'Key': 'product',
        'Value': 'prod-yimmbalxd5rjm' #### hardcoded, fix
    }
)

svccatresponse4 = svccatclient.search_provisioned_products(
    AccessLevelFilter={
        'Key': 'Account',
        'Value': 'self'
    },
    Filters={
        'SearchQuery': [
            'productId:prod-yimmbalxd5rjm',  #### hardcoded, fix
        ]
    }
)

# https://aws.amazon.com/blogs/security/how-to-use-trust-policies-with-iam-roles/
# ok, I don't have a way to know which accounts have deployed the VPC Svc Catalog Product. At this point, I need to plan to deploy the R53R Lambda to each account as part of the VPC Svc Catalog Product.
# https://us-east-2.console.aws.amazon.com/config/home?region=us-east-2#/aggregators/resources/details?accountId=187547605332&aggregatorName=aws-controltower-ConfigAggregatorForOrganizations&awsRegion=us-east-2&resourceId=arn%3Aaws%3Acloudformation%3Aus-east-2%3A187547605332%3Astack%2FSC-187547605332-pp-irtdcblsyb3vm%2F23814550-9e0d-11eb-bf09-0a66227d48ea&resourceType=AWS%3A%3ACloudFormation%3A%3AStack
############################ Assume AWSControlTowerExecute role for cross-account access
# Get list of accounts where SC product is deployed?
# Or how to trigger multiple lambdas in multiple accounts from central S3 bucket?
# IN S3 trigger CFN, can specify a bunch of Lambda ARNs?
# Keep Lambda centralized in ntwk account - 
# Call SvcCatalog API to update automatically?

# Find list id by name, returns list, since multiple
# domain lists can have same name, but different Id.
r53rlistdomainlistsresponse = r53rclient.list_firewall_domain_lists()
r53rdomainlistid = [x['Id'] for x in r53rlistdomainlistsresponse['FirewallDomainLists'] if x['Name'] == domain_list_name]

# R53R
importfwdomainresponse = r53rclient.import_firewall_domains(
    FirewallDomainListId=ssmgetresponse['Parameter']['Value'],
    Operation='REPLACE',
    DomainFileUrl=domain_list_location
)

# R53R
getfwdomainlistresponse = r53rclient.get_firewall_domain_list(
    FirewallDomainListId=ssmgetresponse['Parameter']['Value'],
)
domainimportstatusmsg = getfwdomainlistresponse['FirewallDomainList']['StatusMessage']
domaincount = getfwdomainlistresponse['FirewallDomainList']['DomainCount']

# Describe the existing policy to pass along to the "update" call below. Guh. Run "describe" every time to see if this is a subsequent run. If so, Use If/Else to not run "update".

# NFW
nfwdescriberesponse = nfwclient.describe_firewall_policy(
    FirewallPolicyArn=FirewallPolicyArn
)

# NFW # Run once, and only once. 
NtwkFirewallRuleGroupArnDict = {}
NtwkFirewallRuleGroupArnDict['ResourceArn'] = NtwkFirewallRuleGroupArn

# NFW # Add new rule to the firewall policy
nfwdescriberesponse["FirewallPolicy"]["StatefulRuleGroupReferences"].append(NtwkFirewallRuleGroupArnDict.copy())

####### associate the modified policy with the fw
nfwupdateresponse = nfwclient.update_firewall_policy(
    UpdateToken=nfwdescriberesponse["UpdateToken"],
    FirewallPolicyArn=FirewallPolicyArn,
    FirewallPolicy=nfwdescriberesponse["FirewallPolicy"],
    Description=nfwdescriberesponse["FirewallPolicyResponse"]["Description"]
)

# For subsequent runs, just update the rule group.
#https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/network-firewall.html?highlight=network%20firewall#NetworkFirewall.Client.update_rule_group

# Call describe_rule_group first.
nfwdescriberuleresponse = nfwclient.describe_rule_group(
    RuleGroupArn=NtwkFirewallRuleGroupArn
)

print(f"Domains currently blocked: {nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']['Targets']}")

def appenddotnfw(): ################### edit with new combined list function
    for str in strdata:
        newstr = '.' + str
        nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']['Targets'].append(newstr)
    return nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']['Targets']

nfwupdateddomainlist = appenddotnfw()
print(f"Domains to be blocked: {nfwupdateddomainlist}")

nfwupdaterulegroupresponse = nfwclient.update_rule_group(
    UpdateToken=nfwdescriberuleresponse["UpdateToken"],
    RuleGroupArn=NtwkFirewallRuleGroupArn,
    RuleGroup={
        'RulesSource': {
            'RulesSourceList': nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']
        }
    },
    Description=nfwdescriberuleresponse['RuleGroupResponse']['Description']
)

if nfwupdaterulegroupresponse['ResponseMetadata']['HTTPStatusCode'] == 200:
    print(f"Rule group update successful: {nfwupdaterulegroupresponse}")
else:
    print(f"Rule group update failed: {nfwupdaterulegroupresponse}")
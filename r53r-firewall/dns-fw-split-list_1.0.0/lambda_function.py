#env_vars needed
domain_list_name = os.environ.get('domain_list_name')
#manual testing: domain_list_name = 'Test-crossaccount'

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
from __future__ import print_function
import botocore.exceptions
import itertools
import os

s3 = boto3.client('s3')
r53rclient = boto3.client('route53resolver')
nfwclient = boto3.client('network-firewall')

bucketname = domain_list_location.split('/')[2]
objectname = domain_list_location.split('/')[-1]
localfilename = domain_list_location.split('/')[-1]
s3.download_file(bucketname, objectname, localfilename)

with open(localfilename, 'r') as f:
    data = f.read()
    f.close()
    
strdata = data.splitlines()

def appenddomains():
    dot_list = []
    astr_list = []
    for str in strdata:
        dotstr = '.' + str
        dot_list.append(dotstr)
        astrstr = '*' + dotstr
        astr_list.append(astrstr)
        astr_list.append(str)
    return dot_list, astr_list
    
appenddomainlist = appenddomains()
dotlist = appenddomainlist[0]
astrlist = appenddomainlist[1]

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

astrlistpath = 's3://' + bucketname + '/astrlist.txt'
upload_file("astrlist.txt", bucketname)
############ at this point, the 2 lists are created, and the R53R list is uploaded to S3.

# Find list id by name, returns list, since multiple
# domain lists can have same name, but different Id.
r53rlistdomainlistsresponse = r53rclient.list_firewall_domain_lists()
r53rdomainlistid = [x['Id'] for x in r53rlistdomainlistsresponse['FirewallDomainLists'] if x['Name'] == domain_list_name]

# R53R
importfwdomainresponse = r53rclient.import_firewall_domains(
    FirewallDomainListId=r53rdomainlistid[0],
    Operation='REPLACE',
    DomainFileUrl=astrlistpath
)

# R53R
getfwdomainlistresponse = r53rclient.get_firewall_domain_list(
    FirewallDomainListId=r53rdomainlistid[0]
)

if importfwdomainresponse['ResponseMetadata']['HTTPStatusCode'] == 200:
    print(f"Rule group update successful: {getfwdomainlistresponse}")
else:
    print(f"Rule group update failed: {getfwdomainlistresponse}")

######## NFW below

# NFW
NtwkFirewallRuleGroupArnDict = {}
NtwkFirewallRuleGroupArnDict['ResourceArn'] = NtwkFirewallRuleGroupArn

# Call describe_rule_group first.
nfwdescriberuleresponse = nfwclient.describe_rule_group(
    RuleGroupArn=NtwkFirewallRuleGroupArn
)
nfwblockeddomains = nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']['Targets']
print(f"Domains currently blocked: {nfwblockeddomains}")
    
if 'Description' in nfwdescriberuleresponse['RuleGroupResponse']:
    print(f"NFW rule group description exists")
else:
    nfwdescriberuleresponse['RuleGroupResponse']['Description'] = "Domain list modified by Lambda"

def domainlistmerge():
# Assume dotlist will have more current domain entries, since an administrator updated it.
    deltalistadd = list(itertools.filterfalse(lambda x: x in nfwblockeddomains, dotlist))
    print(f"Adding domains: {deltalistadd}")
    # Existing domain list may have stale entries that were removed by an administrator
    deltalistremove = list(itertools.filterfalse(lambda x: x in dotlist, nfwblockeddomains))
    print(f"Removing domains: {deltalistremove}")
    
    nfwblockeddomainsremoved = [domain for domain in nfwblockeddomains if domain not in deltalistremove]
    mergedlist = [*nfwblockeddomainsremoved, *deltalistadd]
    nfwdescriberuleresponse['RuleGroup']['RulesSource']['RulesSourceList']['Targets'] = mergedlist
    print(f"Domains to be blocked: {mergedlist}")

domainlistmerge()

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

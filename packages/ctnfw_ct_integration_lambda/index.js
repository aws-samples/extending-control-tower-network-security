const https = require('https');
const AWS = require('aws-sdk');
var sts = new AWS.STS();

var resp = {};


// This function makes a call to CloudFormation StackSet createStackInstances to create the Service Catalog 
// Launch Role in the newly created account (received from the event).
 
const _addSCLaunchRoleStackSetInstanceForMemberAccount = function(event, context, callbackFunc) {
    

    let childAccountId = event.detail.serviceEventDetails.createManagedAccountStatus.account.accountId;
    console.log("Member Account ID = "+ childAccountId);
    var params = {
      Regions: [ /* required */
        process.env.AWS_REGION,
        /* more items */
      ],
      StackSetName: process.env.STACKSET_NAME, /* required */
      DeploymentTargets: {
        Accounts: [
          childAccountId,
          /* more items */
        ],
      },
    };
    var cloudformation = new AWS.CloudFormation();
    cloudformation.createStackInstances(params, function(err, data) {
      if (err) {
          console.log(err, err.stack); // an error occurred
          callbackFunc(err, err.stack);
          
      }
      else {
          console.log(data);           // successful response
          console.log("Stackset operation id = "+ data.OperationId);


      }
    });
    
};

// This function makes assumes AWSControlTowerExecution role in Networking account
// and shares the centralized AWS Transit Gateway with the newly created account 
//(received from the event).
const _shareTGWToMemberAccount = function(event, context, callbackFunc) {
  
  //Assuming the new role will return temporary credentials
    var sts_params = {
      RoleArn: process.env.EXECUTION_ROLE_ARN,
      RoleSessionName: "ControlTowerExecutionRoleSession"
    };
  
    sts.assumeRole(sts_params, function (err, data) {
      if (err) {
        console.log(err, err.stack);
      } else {
        console.log(data);

        //Once we've gotten the temp credentials, let's apply them
        AWS.config.credentials = new AWS.TemporaryCredentials({RoleArn: sts_params.RoleArn});
        
        var ram = new AWS.RAM();
        let childAccountId = event.detail.serviceEventDetails.createManagedAccountStatus.account.accountId;
        console.log("TGW ARN = "+process.env.TGW_ARN);
        var params = {
          name: 'tgwShare-'+childAccountId, /* required */
          allowExternalPrincipals: true,
          principals: [
            childAccountId
            /* more items */
          ],
          resourceArns: [
            process.env.TGW_ARN
            /* more items */
          ]
        };
        console.log("Sharing TGW to member account");
        ram.createResourceShare(params, function(err, data) {
        if (err) console.log(err, err.stack); // an error occurred
        else     console.log(data);           // successful response
        });
      }
    })
    
};

exports.handler =  (event, context, callback) => {
    
    _addSCLaunchRoleStackSetInstanceForMemberAccount(event, context, callback);
    _shareTGWToMemberAccount(event,context,callback);

};

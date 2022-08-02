const https = require('https');
const AWS = require('aws-sdk');
var ec2 = new AWS.EC2();


exports.handler =  (event, context, callback) => {

    console.log(event);
    var message = event.Records[0].Sns.Message;
    console.log('Message received from SNS:', message);
    var attachmentEvent = JSON.parse (message);

    let transitGatewayAttachmentArn = attachmentEvent.detail.transitGatewayAttachmentArn;
    console.log("Transit Gateway Attachment ARN = "+ transitGatewayAttachmentArn);
    var attachmentArray = transitGatewayAttachmentArn.split("/");
    console.log("Transit Gateway Attachment ID = "+ attachmentArray[1]);
    
    var params = {
     TransitGatewayAttachmentId: attachmentArray[1], /* required */
     TransitGatewayRouteTableId: process.env.TGW_SPOKE_RTBL_ID, /* required */
     DryRun: false
   };
    ec2.associateTransitGatewayRouteTable(params, function(err, data) {
    if (err) console.log(err, err.stack); // an error occurred
    else     console.log(data);           // successful response
   });
    
    var params2 = {
      TransitGatewayAttachmentId: attachmentArray[1], /* required */
      TransitGatewayRouteTableId: process.env.TGW_FIREWALL_RTBL_ID, /* required */
      DryRun: false
    };
    ec2.enableTransitGatewayRouteTablePropagation(params2, function(err, data) {
    if (err) console.log(err, err.stack); // an error occurred
      else     console.log(data);           // successful response
    });

};

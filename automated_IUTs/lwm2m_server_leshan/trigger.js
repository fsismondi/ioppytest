var bodyParser = require("body-parser");
var request = require("request");
var base = "http://127.0.0.1:8080/api/clients";
var td=process.argv[3];

switch (td) {
  case "TD_LWM2M_1_INT_201_step_01": //Get resource
    execute("GET","/3/0/0","Text","");
    break;
  case "TD_LWM2M_1_INT_201_step_05": 
    execute("GET","/3/0/1","Text","");
    break;
  case "TD_LWM2M_1_INT_201_step_09":
    execute("GET","/3/0/2","Text","");
    break;
  case "TD_LWM2M_1_INT_203_step_01": 
    execute("GET","/3/0","TLV","");
    break;
  case "TD_LWM2M_1_INT_204_step_01": //Get instance
    execute("GET","/3/0","JSON","");
    break;
  case "TD_LWM2M_1_INT_205_step_01": // update resource
    execute("PUT","/1/0/2","Text",{id: 2, value: "1000000"});
    break;
  case "TD_LWM2M_1_INT_205_step_05": 
    execute("PUT","/1/0/3","Text",{id: 3, value: "10000000"});
    break;
  case "TD_LWM2M_1_INT_205_step_09": 
    execute("PUT","/1/0/5","Text",{id: 5, value: "false"});
    break;
  case "TD_LWM2M_1_INT_205_step_13": 
    execute("GET","/1/0/2","TLV","");
    break;
  case "TD_LWM2M_1_INT_205_step_17": 
    execute("GET","/1/0/3","TLV","");
    break;
  case "TD_LWM2M_1_INT_205_step_21": 
    execute("GET","/1/0/5","TLV","");
    break;
   case "TD_LWM2M_1_INT_205_step_25": 
    execute("PUT","/1/0/2","Text",{id: 2, value: "100000"});
    break;
  case "TD_LWM2M_1_INT_205_step_29": 
    execute("PUT","/1/0/3","Text",{id: 3, value: "1000000"});
    break;
  case "TD_LWM2M_1_INT_205_step_33": 
    execute("PUT","/1/0/5","Text",{id: 5, value: "true"});
    break;
  case "TD_LWM2M_1_INT_205_step_37": 
    execute("GET","/1/0/2","TLV","");
    break;
  case "TD_LWM2M_1_INT_205_step_41": 
    execute("GET","/1/0/3","TLV","");
    break;
  case "TD_LWM2M_1_INT_205_step_45": 
    execute("GET","/1/0/5","TLV","");
    break;
  case "TD_LWM2M_1_INT_220_step_01": //update instance 
    execute("PUT","/1/0","JSON",{"id":"0","resources":[{"id":13,"value":"2018-06-14T09:12:17+02:00"},{"id":14,"value":"+02"},{"id":15,"value":"Europe/Paris"}]});
    break;
  case "TD_LWM2M_1_INT_220_step_05": 
    execute("GET","/1/0","JSON","");
    break;
  case "TD_LWM2M_1_INT_220_step_09": 
    execute("PUT","/1/0","JSON",{"id":"0","resources":[{"id":13,"value":"2018-06-02T16:16:08+02:00"},{"id":14,"value":"+08"},{"id":15,"value":"Europe/Brussels"}]});
    break;
  case "TD_LWM2M_1_INT_220_step_13": 
    execute("GET","/1/0","JSON","");
    break;
  case "TD_LWM2M_1_INT_270_step_01": //create instance example
    execute("POST","/1","JSON",{"id":"1","resources":[{"id":7,"value":"U"}]});
    break;
  case "TD_LWM2M_1_INT_270_step_05": 
    execute("GET","/1","JSON","");
    break;
  case "TD_IPSO_3300_01_step_01": 
    execute("GET","3300/0/5700","Text","");
    break;
  case "TD_IPSO_3300_01_step_05": 
    execute("GET","3300/0/5701","Text","");
    break;
  case "TD_IPSO_3300_02_step_01": 
    execute("GET","3300/0","JSON","");
    break;
  case "TD_IPSO_3300_03_step_01": 
    execute("PUT","3300/0","JSON",{"id":"0","resources":[{"id":5750,"value":"C02"}]});
    break;
  case "TD_IPSO_3300_05_step_01": 
    execute("DELETE","3300/0","","");
    break;
  case "TD_IPSO_3302_01_step_01": 
    execute("GET","3302/0","JSON","");
    break;
  case "TD_IPSO_3302_02_step_01": 
    execute("GET","3302/0/5500","Text","");
    break;
  case "TD_IPSO_3302_02_step_05": 
    execute("GET","3302/0/5500","Text","");
    break;
  case "TD_IPSO_3302_03_step_01": 
    execute("POST","/3302","JSON",{"id":"1","resources":[{"id":5500,"value":"True"}]});
    break;
  case "TD_IPSO_3302_03_step_05": 
    execute("GET","/3302/1","JSON","");
    break;
  case "TTD_IPSO_3302_04_step_01": //update instance example
    execute("PUT","3302/0/","JSON",{"id":"0","resources":[{"id":5903,"value":"100"},{"id":5904,"value":"200"}]});
  case "TD_IPSO_3302_05_step_01": 
    execute("DELETE","3302/0","","");
    break;
  case "TD_IPSO_3303_01_step_01": 
    execute("GET","3303/0/5700","Text","");
    break;
  case "TD_IPSO_3303_01_step_05": 
    execute("GET","3303/0/5701","Text","");
    break;
  case "TD_IPSO_3303_02_step__01": //create instance example
    execute("POST","/3303","JSON",{"id":"1","resources":[{"id":5700,"value":"37"}]});
    break; 
  case "TD_IPSO_3303_03_step_01": 
    execute("DELETE","3303/1","","");
    break;
  case "TD_IPSO_3304_01_step_01": 
    execute("GET","/3304/0","JSON","");
    break;
  case "TD_IPSO_3304_03_step_01": 
    execute("DELETE","3303/1","","");
    break;
  case "TD_IPSO_3306_01_step_01": 
    execute("GET","/3306/0","JSON","");
    break;
  case "TD_IPSO_3306_03_step_01": 
    execute("DELETE","3306/0","","");
    break;
  default:
    console.log("TD unknown "+process.argv[3]);
}

function execute(method,uri,format,rep){
    console.log("\n▶▶▶▶▶ (Find deviceID)");
    console.log("GET "+base);

    var options = {
        uri: base,
        method: "GET"
    };

    request(options, function (error, response, body) {
        console.log("◀◀◀◀◀");
        if(error){
            console.log(error);
        }else{
            console.log(response.statusCode);
            var json = JSON.parse(body);
            console.log(body);
            var clientID = json[0].endpoint;
            console.log("DeviceID: "+clientID);

            console.log("\n▶▶▶▶▶ (Send request to client "+clientID+")");
            console.log(method+" "+base+"/"+clientID+uri+"?format="+format);
            console.log(rep);
            var options = {
                uri: base+"/"+clientID+uri+"?format="+format,
                method: method,
                json: rep
            };

            request(options, function (error, response, body) {
                console.log("◀◀◀◀◀");
                if(error){
                    console.log(error);
                }else{
                    console.log(response.statusCode);
                    console.log(body);
                }
            });
        }
    });
}

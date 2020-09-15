# OPCUA_Demonstrator
Depository for two-stage demonstration of OPC UA capabilities using python-opcua

Phase 1 is a minimal demonstrator designed to prove the basic OPC-UA features were running successfully.  

It simulates a Server running on a single sensor in a manufacturing plant, which is then accessed by a Client  which prompts the user to retrieve different information in the Server Address Space. Realistically, Client and Server will run on different devices. 

The Phase 2.0 demonstrator aims to incorporate a device which simulates a Server and Client simultaneously. 

It access as a Client the sensor values from a different server, perform a moving average calculation on the results, and then act as a Server when reporting these results so other clients can access the moving average. Phase 2.0 cannot run successfully without Phase 1.0, and it can run on the same device as Phase 1.0 Server. 

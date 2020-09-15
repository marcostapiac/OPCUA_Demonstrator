# OPCUA_Demonstrator
Depository for two-stage demonstration of OPC UA capabilities using python-opcua

Phase 1 is a minimal demonstrator designed to prove the basic OPC-UA features were running successfully.  

It aims to simulate a Server running on a single sensor in a manufacturing plant, which is then accessed to by a Client script which prompts the user for different information in the Server Address Space. 

The “Phase 2.0” demonstrator aims to incorporate a device which simulates a Server and Client simultaneously, accessing as a Client the sensor values from a different server, perform a moving average calculation on the results, and then act as a Server when reporting these results so other clients can access the moving average.

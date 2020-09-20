from opcua import Client
from opcua.ua import AttributeIds, BrowseDirection, ObjectIds


# Handler class for Subscription
class SubHandler(object):
    """
    Subscription Handler. To receive events from server for a subscription
    """

    def datachange_notification(self, nodeid, val, data):
        print("New data change event on Node: {}, with a new value: {}\n".format(nodeid, val))

    def event_notification(self, event):
        print("New event with source Id 'ns={};i={}', and type '{}'.\n".format(event.SourceNode.NamespaceIndex,
                                                                               event.SourceNode.Identifier,
                                                                               event.Message.Text))
class ExtendedClient(Client):

    def __init__(self, ip, port):
        self.url = "opc.tcp://" + str(ip) + ":" + str(port) + "/freeopcua/server/"
        super().__init__(self.url)  # Returns client object with access to Server Address Space

    def obtainHistoricalValues(self, node, parentNode, methodNode):
        childs = node.get_referenced_nodes(direction=BrowseDirection.Forward, nodeclassmask=1 << 1)
        TempHistory = []

        for child in childs:
            if "Unit" in child.get_browse_name().Name:
                unit = child.get_value()
            elif "Value" in child.get_browse_name().Name:
                print("Sensor calibration model is linear, ie, y = mx + c\n")
                m = input("Please input linear calibration parameter, 'm'.\n")
                if m == "":  # No calibration parameters given
                    for val in child.read_raw_history():
                        val = parentNode.call_method(methodNode, val.Value.Value)
                        TempHistory.append(val)  # Latest value is at 0th index
                else:
                    c = input("Please input linear calibration parameter, 'c'.\n")
                    for val in child.read_raw_history():
                        val = parentNode.call_method(methodNode, val.Value.Value, float(m), float(c))
                        TempHistory.append(val)  # Latest value is at 0th index

        TempHistory = [str(x) + unit for x in TempHistory]
        if not TempHistory:
            print("No historized values for node {}\n".format(node.get_display_name().Text))
        else:
            print("Temperature History (°C): {}\n".format(", ".join(TempHistory)))  # Print calibrated data
        return TempHistory

    def initiateSubscriptions(self, Nodes, thisSubscription=None):
        """Function takes a list of Nodes as input, and iterates through to find, and subscribe to, Event and Data Change Nodes
        Returns Subscription Variable for future Subscriptions"""
        if thisSubscription is None:
            # Begin EventNotifier and DataChange subscriptions
            handler = SubHandler()
            thisSubscription = self.create_subscription(period=500, handler=handler)

        # Obtain Event and Historizing Nodes
        eventNotifiers = []
        for node in Nodes:
            refs = node.get_references(ObjectIds.GeneratesEvent)
            if len(refs) != 0:
                eventNotifiers.append(node)

        historizing = []
        for node in Nodes:
            refNodes = node.get_referenced_nodes(nodeclassmask=1 << 1)  # Return Variables associated with Sensors
            for refNode in refNodes:
                if refNode.get_attribute(AttributeIds.Historizing).Value.Value:  # Check if Variable historizes
                    historizing.append(refNode)

        # Begin EventNotifier and DataChange subscriptions
        dataChangeHandlers = []
        eventHandlers = []
        for hist in historizing:
            dataChangeHandlers.append(thisSubscription.subscribe_data_change(hist))
        for eventNotifier in eventNotifiers:
            eventHandlers.append(thisSubscription.subscribe_events(eventNotifier))  # Returns handler to unsubscribe

        # Once we have identified events to subscribe to, we need to subscribe to server to interface with client
        thisSubscription.subscribe_events()
        return thisSubscription, dataChangeHandlers, eventHandlers

    def getModelInformation(self, thisSensor):
        childs = thisSensor.get_referenced_nodes(direction=BrowseDirection.Forward,
                                                 nodeclassmask=1 << 1)  # Obtain Variables associated to sensor
        for child in childs:
            if "Model" in child.get_browse_name().Name:
                print(
                    "Serial Number of Sensor {} is {}\n".format(thisSensor.get_display_name().Text, child.get_value()))

    def getSensorValue(self, thisSensor):
        childs = thisSensor.get_referenced_nodes(direction=BrowseDirection.Forward,
                                                 nodeclassmask=1 << 1)  # Obtain Variables associated to sensor
        val = "No Value"
        unit = ""
        for child in childs:
            if "Value" in child.get_browse_name().Name:
                val = child.get_value()
            elif "Unit" in child.get_browse_name().Name:
                unit = child.get_value()

        print("Sensor Value of Sensor {} is {}{}\n".format(thisSensor.get_display_name().Text, val, unit))

    def haltSubscriptions(self, Subscriptions, dataChangeHandlers=[], eventHandlers=[]):
        handlers = dataChangeHandlers + eventHandlers
        for handler in handlers:
            Subscriptions.unsubscribe(handler)

    def getInput(self):
        return input("Please specify the information you require:\n"
                     "    Obtain Sensor's Serial number: Write 'Serial'\n"
                     "    Obtain latest Sensor Values: Write 'Historize'\n"
                     "    Obtain current Sensor Value: Write 'Value'\n"
                     "    Listen to Server notifications: Enter the Space bar.\n"
                     "If you wish to exit the client, write 'Exit'.\n")


if __name__ == "__main__":
    client = ExtendedClient("172.20.10.9", 4840)  # Connect to server
    try:
        client.connect()
        print("Client connected at {}\n".format(client.url))

        # Obtain root node of Address Space
        RootNode = client.get_root_node()  # Obtain NodeId of RootNode
        root_children = RootNode.get_children()
        ObjectsRoot = root_children[0]

        # Obtain Objects (NOT Root or Server; in this case, Sensors)
        objs = ObjectsRoot.get_referenced_nodes(direction=BrowseDirection.Forward,
                                                nodeclassmask=1 << 0)  # Returns Nodes of NodeClass Object
        Sensors = []
        for obj in objs:
            if ("Sensor" or "sensor") in obj.get_display_name().Text:
                Sensors.append(obj)  # Append all sensors

        methods = ObjectsRoot.get_methods()  # Obtain all methods which are DIRECT children of ObjectsRoot
        for method in methods:
            if "Calibration" in method.get_browse_name().Name:
                calibrationMethod = method
                break  # WHEN calibration Method is found, break

        choice = client.getInput()
        while choice != "Exit":
            if choice == "Serial":
                for sensor in Sensors:
                    client.getModelInformation(sensor)  # Get model information for each sensor
            elif choice == "Historize":
                for sensor in Sensors:
                    # Calibrate Sensor for every loading of Historical values
                    if sensor.get_child("2:SensorValue").get_attribute(AttributeIds.Historizing):
                        client.obtainHistoricalValues(sensor, ObjectsRoot, calibrationMethod)
            elif choice == "Value":
                for sensor in Sensors:
                    client.getSensorValue(sensor)
            elif choice == " ":
                # Pub-Sub for Temp Sensor
                Subscription, dataChange_Handlers, event_Handlers = client.initiateSubscriptions(Sensors)
                while input() != "":
                    continue
                Subscription.delete()  # Or haltSubscriptions(Subscriptions, dataChange_Handlers, event_Handlers)
            else:
                print("Please input a valid option\n")
            choice = client.getInput()

        client.disconnect()

    except Exception as e:
        print(e)
        client.disconnect()

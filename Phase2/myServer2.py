import socket
import time
from opcua import Server, ua, Client, uamethod
from opcua.ua import BrowseDirection
from opcua.ua.attribute_ids import AttributeIds
from opcua.ua.uatypes import ValueRank  # Library where we can find different ua types (EventNotifiers, etc)
from opcua.common.ua_utils import value_to_datavalue


class ExtendedServer(Server):
    """ Class used to setup single Namespace within a URL. Extends Server class with a function to setup a Calibration
        Method """

    def __init__(self, port):
        super().__init__()
        ip = "192.168.41.126"
        self.url = "opc.tcp://" + str(ip) + ":" + str(port) + "/freeopcua/server/"
        self.set_endpoint(self.url)

        # Create personal Namespace (good practice)
        uri = "OPCUA_SIMULATION_SERVER"
        self.idx = self.register_namespace(uri)  # Returns NamespaceArray index corresponding to our new Namespace

    def createMovingAverageTemperatureMethod(self, parentNode):
        @uamethod
        def movingAvgTemp(self, temperatures):
            n = len(temperatures)
            return round(sum(temperatures) / n, 3)

        inArg1 = ua.Argument()
        outArg = ua.Argument()
        inArg1.ValueRank = 1  # One Dimensional Array
        inArg1.DataType = ua.NodeId(ua.ObjectIds.Float)
        outArg.ValueRank = -1
        outArg.DataType = ua.NodeId(ua.ObjectIds.Float)
        method = parentNode.add_method(self.idx, "Moving Temperature Average", movingAvgTemp, [inArg1], [outArg])
        method.set_modelling_rule(mandatory=1)
        return method

    def obtainHistoricalValues(self, node, parentNode, methodNode):
        childs = node.get_referenced_nodes(direction=BrowseDirection.Forward, nodeclassmask=1 << 1)
        TempHistory = []
        for child in childs:
            if "Value" in child.get_browse_name().Name:
                for val in child.read_raw_history():
                    val = parentNode.call_method(methodNode, val.Value.Value)
                    TempHistory.append(val)  # Latest value is at 0th index

        return TempHistory

    def connectToClient(self, port, ip=""):
        if ip == "":
            ip = socket.gethostbyname(socket.gethostname())  # Assume both Servers run on same IP address

        url = "opc.tcp://" + str(ip) + ":" + str(port) + "/freeopcua/server/"
        thisClient = Client(url)  # Returns client object with access to Server Address Space
        thisClient.connect()
        return thisClient

    def addVariable(self, parentNode, browseName, value, datatype, Access, UserAccess, ValueRankValue, Historizing):
        """ Function to add Data Variables, which represent the content of an Object """
        # 10 Float datatype, 12 String datatype
        variable = parentNode.add_variable(self.idx, browseName, value, datatype=datatype)
        # 1 Current R, 3 Current RW, 15 Current RW & History RW
        variable.set_attribute(AttributeIds.AccessLevel, value_to_datavalue(Access))
        variable.set_attribute(AttributeIds.UserAccessLevel, value_to_datavalue(UserAccess))
        variable.set_attribute(AttributeIds.ValueRank, value_to_datavalue(ValueRankValue))
        variable.set_attribute(AttributeIds.Historizing, value_to_datavalue(Historizing))
        return variable

    def addProperty(self, parentNode, browseName, value, Access, UserAccess, ValueRankValue, Historizing):
        """ Function to add Data Variables, which represent the content of an Object """
        # 10 Float datatype, 12 String datatype
        variable = parentNode.add_property(self.idx, browseName, value)
        # 1 Current R, 3 Current RW, 15 Current RW & History RW
        variable.set_attribute(AttributeIds.AccessLevel, value_to_datavalue(Access))
        variable.set_attribute(AttributeIds.UserAccessLevel, value_to_datavalue(UserAccess))
        variable.set_attribute(AttributeIds.ValueRank, value_to_datavalue(ValueRankValue))
        variable.set_attribute(AttributeIds.Historizing, value_to_datavalue(Historizing))
        return variable


if __name__ == "__main__":

    server = ExtendedServer(4841)
    Root = server.get_root_node()
    ObjectsRoot = Root.get_children()[0]
    MovingAverageNode = ObjectsRoot.add_object(server.idx, "MovingAverage", objecttype=ua.ObjectIds.BaseObjectType)
    MovingAverageNode.set_attribute(AttributeIds.EventNotifier, value_to_datavalue(1))  # Subscribable node
    EngineeringUnit = server.addProperty(MovingAverageNode, "EngineeringUnit", 0, 1, 1, ValueRank.Scalar, False)
    Value = server.addVariable(MovingAverageNode, "ValueNode", 0.0, 10, 15, 15, ValueRank.Scalar, True)

    try:
        server.start()
        print("Server started at {}".format(server.url))

        # Keep record of latest 10 moving Average Values
        server.historize_node_data_change(Value, count=1)  # Data change only true for Variables

        methodNode = server.createMovingAverageTemperatureMethod(ObjectsRoot)
        client = server.connectToClient(4840, "192.168.41.126")  # Connect to Server1

        while True:
            ObjectsRoot1 = client.get_root_node().get_children()[0]
            TemperatureSensor = ObjectsRoot1.get_child(["2:TemperatureSensor"])  # Return Temperature Sensor in other
            # Server via Browse Name
            unit = TemperatureSensor.get_child(["2:EngineeringUnit"]).get_value()  # Get Sensor Unit
            EngineeringUnit.set_attribute(AttributeIds.Value, value_to_datavalue(unit))  # Write to property
            calibrationMethod = ObjectsRoot1.get_methods()[0]  # Access Methods in Server 1
            TemperatureHistory = server.obtainHistoricalValues(TemperatureSensor, ObjectsRoot1, calibrationMethod)
            movingAverage = ObjectsRoot.call_method(methodNode, TemperatureHistory)
            Value.set_attribute(AttributeIds.Value,
                                value_to_datavalue(movingAverage))  # Update MovingAverage Node Value
            print("{}{}\n".format(Value.get_value(), unit))
            time.sleep(0.5)  # Same time delay as Temperature Sensor

    except Exception as e:
        print(e)
        server.stop()

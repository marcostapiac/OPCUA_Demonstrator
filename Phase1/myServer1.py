import time
import cryptography
from random import randint

from opcua import Server, ua, uamethod
from opcua.common.ua_utils import value_to_datavalue
from opcua.ua.attribute_ids import AttributeIds
from opcua.ua.uatypes import ValueRank  # Library where we can find different ua types (EventNotifiers, etc)


class ExtendedServer(Server):
    """ Class used to setup single Namespace within a URL. Extends Server class with a function to setup a Calibration
    Method """

    def __init__(self, port):
        super().__init__()
        ip = "192.168.41.126"
        self.url = "opc.tcp://" + str(ip) + ":" + str(port) + "/server/"
        self.set_endpoint(self.url)

        # Create personal Namespace (good practice)
        uri = "OPCUA_SIMULATION_SERVER"
        self.idx = self.register_namespace(uri)  # Returns NamespaceArray index corresponding to our new Namespace

    def setupCalibrationMethod(self, parentNode):
        # Setup for Method
        class Calibration(object):
            def __init__(self):
                self.m = 1
                self.c = 0

            def __call__(self, val, slope, intercept):
                if slope != "":
                    self.m = slope
                    self.c = intercept
                return self.m * val + self.c
        calibrated = Calibration()

        @uamethod
        def calibration(self, val, m="", c=""):
            """ Linear calibration for TemperatureSensor"""
            return calibrated(val, m, c)

        # Need to specify Arguments
        inArg1 = ua.Argument()
        inArg2 = ua.Argument()
        inArg3 = ua.Argument()
        outArg = ua.Argument()
        inArg1.ValueRank = -1  # Single value
        inArg1.DataType = ua.NodeId(ua.ObjectIds.Float)
        inArg2.ValueRank = -1  # Single value
        inArg2.DataType = ua.NodeId(ua.ObjectIds.Float)
        inArg3.ValueRank = -1  # Single value
        inArg3.DataType = ua.NodeId(ua.ObjectIds.Float)
        outArg.ValueRank = -1  # Single value
        outArg.DataType = ua.NodeId(ua.ObjectIds.Float)
        method = parentNode.add_method(self.idx, "Calibration", calibration, [inArg1, inArg2, inArg3], [outArg])
        method.set_modelling_rule(mandatory=1)

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
    server = ExtendedServer(4840)

    # Obtain Root node where we place all existing Object nodes
    Root = server.get_root_node()
    ObjectRoot = Root.get_children()[0]
    TypeRoot = Root.get_children()[1]
    ObjectTypesFolder = TypeRoot.get_children()[0]
    ServerNode = server.get_node(ua.ObjectIds.Server)

    # Create custom TypeDefinition for Sensor
    BaseSensorType = ObjectTypesFolder.add_object_type(server.idx,
                                                       "BaseSensorType")  # Returns custom TypeDefinition id, creates
    # a Forward Reference
    BaseSensorType.set_attribute(AttributeIds.IsAbstract, value_to_datavalue(True))  # Prevents instances of this type

    SensorModelInformation = server.addVariable(BaseSensorType, "SensorModelInformation", "K", 12, 3, 3,
                                                ValueRank.Scalar, False)
    SensorModelInformation.set_modelling_rule(mandatory=1)  # 1 Mandatory 2 Optional

    AbsSensValue = server.addVariable(BaseSensorType, "SensorValue", 0, 10, 15, 15, ValueRank.Scalar, True)
    AbsSensValue.set_modelling_rule(mandatory=1)  # Mandatory

    TempSensors = BaseSensorType.add_object_type(server.idx, "TemperatureSensorType")
    TempSensors.set_attribute(AttributeIds.IsAbstract, value_to_datavalue(False))

    EngineeringUnit = server.addProperty(TempSensors,  "EngineeringUnit", "°C", 1, 1, ValueRank.Scalar, False)
    EngineeringUnit.set_modelling_rule(mandatory=1)  # Mandatory

    # Instantiate objects
    Temp = ObjectRoot.add_object(server.idx, "TemperatureSensor", objecttype=TempSensors)
    Temp.get_child(["2:SensorModelInformation"]).set_attribute(AttributeIds.Value, value_to_datavalue("SMTIR 9901"))

    # Enable Event Notifier for Server for Events and History
    Temp.set_attribute(AttributeIds.EventNotifier, value_to_datavalue(1))
    ServerNode.set_attribute(AttributeIds.EventNotifier, value_to_datavalue(1))

    try:
        server.start()
        print("Server started at {}".format(server.url))

        # Initiate Subscription Monitored Items
        myevengen = server.get_event_generator(ua.NodeId(2041), Temp)  # Sets Temp as BaseEventNotifier
        # Keep record of latest 10 Temp values for one week
        server.historize_node_data_change(Temp.get_child("2:SensorValue"),
                                          count=10)  # Data change only true for Variables

        server.setupCalibrationMethod(ObjectRoot)

        while True:
            # Generate random values for Temperature (simulate the real Sensor)
            Temperature = randint(20, 50)
            # Assign these values to Sensors
            Temp.get_child(["2:SensorValue"]).set_value(Temperature)
            myevengen.trigger(message="Temperature Change")
            time.sleep(0.5)  # Simulate Sensor delay

    except Exception as e:
        print(e)
        server.stop()


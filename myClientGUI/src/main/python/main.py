from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSlot, Qt, QEventLoop, QTimer
from opcua.ua import BrowseDirection, ObjectIds, AttributeIds
from opcua import Client
import sys
import time
from fbs_runtime.application_context.PyQt5 import ApplicationContext, cached_property


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

    def getParams(self, gui, parameterInterface):
        m, c = 0, 0
        m, okPressed = QInputDialog.getDouble(parameterInterface, "Get Parameter",
                                              "Please input linear calibration parameter, 'm'.\n "
                                              "If you do not know, enter 0.0.\n")
        if okPressed and m != 0:
            c, okPressed = QInputDialog.getDouble(parameterInterface, "Get Parameter",
                                                  "Please input linear calibration parameter, 'c'\n")
        gui.setCentralWidget(parameterInterface)
        gui.setWindowTitle("Options GUI")
        gui.show()
        return m, c

    def obtainHistoricalValues(self, gui, node, parentNode, methodNode):
        childs = node.get_referenced_nodes(direction=BrowseDirection.Forward, nodeclassmask=1 << 1)
        TempHistory = []

        for child in childs:
            if "Unit" in child.get_browse_name().Name:
                unit = child.get_value()
            elif "Value" in child.get_browse_name().Name:
                parameterInterface = QGroupBox("Sensor calibration model is linear, ie, y = mx + c")
                m, c = self.getParams(gui, parameterInterface)
                if m != 0:  # m = 0 corresponds to constant sensor values, hence it is a null input value
                    for val in child.read_raw_history():
                        val = parentNode.call_method(methodNode, val.Value.Value, float(m), float(c))
                        TempHistory.append(val)  # Latest value is at 0th index
                else:
                    for val in child.read_raw_history():
                        val = parentNode.call_method(methodNode, val.Value.Value)
                        TempHistory.append(val)  # Latest value is at 0th index
        TempHistory = [str(x) + unit for x in TempHistory]

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
                return child.get_value()

    def getSensorValue(self, thisSensor):
        childs = thisSensor.get_referenced_nodes(direction=BrowseDirection.Forward,
                                                 nodeclassmask=1 << 1)  # Obtain Variables associated to sensor
        val = "No Value"
        unit = ""
        for child in childs:
            if "Value" in child.get_browse_name().Name:
                val = child.get_value()
            if "Unit" in child.get_browse_name().Name:
                unit = child.get_value()

        return str(val) + unit

    def haltSubscriptions(self, Subscriptions, dataChangeHandlers=[], eventHandlers=[]):
        handlers = dataChangeHandlers + eventHandlers
        for handler in handlers:
            Subscriptions.unsubscribe(handler)


class ClientGUI(QMainWindow):
    def __init__(self):
        # app = QApplication([])  # Required to start application

        super(ClientGUI, self).__init__(None)  # Initialises connection
        self.connectInterface()

        # app.exec_()  # Executes application

    def createButton(self, checkable, checked, name):
        button = QPushButton(name)
        button.setCheckable(checkable)
        button.setDefault(checked)
        return button

    def createLayout(self, buttons):
        layout = QVBoxLayout()
        for button in buttons:
            layout.addWidget(button)
        layout.addStretch(1)
        return layout

    def getClientNodes(self):
        # Obtain root node of Address Space
        self.client.RootNode = self.client.get_root_node()  # Obtain NodeId of RootNode
        root_children = self.client.RootNode.get_children()
        self.client.ObjectsRoot = root_children[0]

        # Obtain Objects (NOT Root or Server; in this case, Sensors)
        objs = self.client.ObjectsRoot.get_referenced_nodes(direction=BrowseDirection.Forward,
                                                            nodeclassmask=1 << 0)  # Returns Nodes of NodeClass Object
        self.client.Sensors = []
        for obj in objs:
            if ("Sensor" or "sensor") in obj.get_display_name().Text:
                self.client.Sensors.append(obj)  # Append all sensors

        methods = self.client.ObjectsRoot.get_methods()  # Obtain all methods which are DIRECT children of ObjectsRoot
        for method in methods:
            if "Calibration" in method.get_browse_name().Name:
                self.client.calibrationMethod = method
                break  # WHEN calibration Method is found, break

    def connectInterface(self):
        cInterface = QGroupBox("Connect to Server: " + "ocp:tcp://172.20.10.9:4840/freeopcua/server")

        connectButton = self.createButton(True, False, "Connect")
        connectButton.clicked.connect(self.checkConnectionInterface)  # When click connect

        layout = self.createLayout([connectButton])
        cInterface.setLayout(layout)

        self.setCentralWidget(cInterface)  # Sets Widget to the centre
        self.setWindowTitle("Client GUI")
        self.show()  # Outputs Window layout

    def checkConnectionInterface(self):
        self.client = ExtendedClient("172.20.10.9", 4840)
        try:
            checkInterface = QGroupBox("Successful connection")
            self.client.connect()
            self.getClientNodes()
            stateButton = self.createButton(True, False, "Ok!")
            stateButton.clicked.connect(self.optionsInterface)

            layout = self.createLayout([stateButton])
            checkInterface.setLayout(layout)
            self.setCentralWidget(checkInterface)  # Sets Widget to the centre
            self.setWindowTitle("Connection GUI")
            self.show()  # Outputs Window layout

        except Exception as e:
            checkInterface = QGroupBox("Failed to connect")
            stateButton = self.createButton(True, False, "Retry!")
            stateButton.clicked.connect(self.connectInterface)

            layout = self.createLayout([stateButton])
            checkInterface.setLayout(layout)
            self.setCentralWidget(checkInterface)  # Sets Widget to the centre
            self.setWindowTitle("Connection GUI")
            self.show()  # Outputs Window layout

    def optionsInterface(self):
        interface = QGroupBox("User options")

        self.serialButton = self.createButton(True, False, "Serial")
        self.serialButton.clicked.connect(self.onSerialButtonClick)

        self.valueButton = self.createButton(True, False, "Value")
        self.valueButton.clicked.connect(self.onValueButtonClick)

        self.historizingButton = self.createButton(True, False, "Historized Values")
        self.historizingButton.clicked.connect(self.onHistorizingButtonClick)

        self.exitButton = self.createButton(True, False, "Exit")
        self.exitButton.clicked.connect(self.onExitButtonClick)

        layout = self.createLayout([self.serialButton, self.valueButton, self.historizingButton, self.exitButton])
        interface.setLayout(layout)

        self.setCentralWidget(interface)
        self.setWindowTitle("Options GUI")
        self.show()

    @pyqtSlot()
    def onSerialButtonClick(self):
        for sensor in self.client.Sensors:
            serialInterface = QGroupBox()
            text = QTextEdit()
            text.setFontPointSize(17)
            text.append("Serial Model for Sensor '" + sensor.get_display_name().Text + "' :")
            text.append("\n")
            text.setFontPointSize(14)
            text.setFontWeight(75)  # Bold
            text.append(self.client.getModelInformation(sensor))  # Get model info for each sensor
            text.setAlignment(Qt.AlignCenter)
            text.setReadOnly(True)

            back = self.createButton(True, False, "Go Back")
            back.clicked.connect(self.optionsInterface)

            layout = self.createLayout([text, back])
            serialInterface.setLayout(layout)

            self.setCentralWidget(serialInterface)
            self.setWindowTitle("Options GUI")
            self.show()
            loop = QEventLoop()
            QTimer.singleShot(1000, loop.quit)
            loop.exec_()

    @pyqtSlot()
    def onValueButtonClick(self):
        for sensor in self.client.Sensors:
            valueInterface = QGroupBox()
            text = QTextEdit()
            text.setFontPointSize(17)
            text.append("Sensor Value for Sensor '" + sensor.get_display_name().Text + "' :")
            text.append("\n")
            text.setFontPointSize(14)
            text.setFontWeight(75)  # Bold
            text.append(str(self.client.getSensorValue(sensor)))  # Get model info for each sensor
            text.setAlignment(Qt.AlignCenter)
            text.setReadOnly(True)

            back = self.createButton(True, False, "Go Back")
            back.clicked.connect(self.optionsInterface)

            layout = self.createLayout([text, back])
            valueInterface.setLayout(layout)

            self.setCentralWidget(valueInterface)
            self.setWindowTitle("Options GUI")
            self.show()
            loop = QEventLoop()
            QTimer.singleShot(1000, loop.quit)
            loop.exec_()

    @pyqtSlot()
    def onHistorizingButtonClick(self):
        for sensor in self.client.Sensors:
            # Calibrate Sensor for every loading of Historical values
            historicalInterface = QGroupBox()
            text = QTextEdit()
            text.setFontPointSize(15)
            text.append("Historical Sensor Values for Sensor '" + sensor.get_display_name().Text + "' :")
            text.append("\n")
            text.setFontPointSize(14)
            text.setFontWeight(75)  # Bold
            # Get historical values for each sensor
            vals = self.client.obtainHistoricalValues(self, sensor, self.client.ObjectsRoot,
                                                                         self.client.calibrationMethod)
            if not vals:
                text.append("No Values")
            else:
                text.append(str(", ".join(vals)))
            text.setAlignment(Qt.AlignCenter)
            text.setReadOnly(True)

            back = self.createButton(True, False, "Go Back")
            back.clicked.connect(self.optionsInterface)

            layout = self.createLayout([text, back])
            historicalInterface.setLayout(layout)

            self.setCentralWidget(historicalInterface)
            self.setWindowTitle("Options GUI")
            self.show()

    @pyqtSlot()
    def onExitButtonClick(self):
        self.client.disconnect()
        self.close()


class MyApp(ApplicationContext):
    def run(self):
        self.main_window.show()
        return self.app.exec_()

    @cached_property
    def main_window(self):
        return ClientGUI()


if __name__ == "__main__":
    app = MyApp()
    exit_code = app.run()
    sys.exit(exit_code)

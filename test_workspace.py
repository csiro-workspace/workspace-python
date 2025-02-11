import csiro_workspace as ws
import unittest
import os.path

class TestWorkspace(unittest.TestCase):

    def setUp(self):
        def onConnected(workspace):
            return True
        self.filePath = os.path.join(os.path.dirname(__file__), 'test_workspace.wsx')
        self.ws = ws.Workspace(self.filePath, onConnected)

    def tearDown(self):
        self.ws.terminate()

    def test_fileName(self):
        self.assertEqual(self.ws.fileName, self.filePath)

    def test_setInput(self):
        def watchCallback(workspace, watchList):
            self.watchListOut = watchList
            self.called = True
            return 1
        self.watchListOut = None
        self.ws.watch(callback=watchCallback, watchList=ws.WatchList.fromIONames(outputs=['Result']), autoDelete=True)
        self.ws.setInput('Value1', '2')
        self.ws.setInput('Value2', '4')
        self.ws.runOnce()
        while not self.watchListOut:
            ws.Workspace.poll()
        self.assertEqual(len(self.watchListOut.inputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.outputs.keys()), 1)
        self.assertEqual(len(self.watchListOut.globalNames.keys()), 0)
        self.assertEqual(self.watchListOut.outputs['Result']['value'], 8)

    def test_setInput_WrongName(self):
        exceptionOccurred = False
        def onErrorCallback(workspace, msg):
            nonlocal exceptionOccurred 
            exceptionOccurred = True
            return True
        self.ws.onError(onErrorCallback) 
        self.ws.setInput('ValueX', 5)
        while (not exceptionOccurred):
            ws.Workspace.poll()
        self.assertEqual(exceptionOccurred, True)

    def test_setInput_WrongValue(self):
        exceptionOccurred = False
        def onErrorCallback(workspace, msg):
            nonlocal exceptionOccurred 
            exceptionOccurred = True
            return True
        self.ws.onError(onErrorCallback) 
        self.ws.setInput('Value1', 'b')
        while (not exceptionOccurred):
            ws.Workspace.poll()
        self.assertEqual(exceptionOccurred, True)

    def test_setGlobalName(self):
        def watchCallback(workspace, watchList):
            self.watchListOut = watchList
            return True
        self.watchListOut = None
        self.ws.watch(callback=watchCallback, watchList=ws.WatchList.fromIONames(globalNames=['StringOut']), autoDelete=True)
        self.ws.setGlobalName('StringIn', '_plus_string')
        self.ws.runOnce()
        while not self.watchListOut:
            self.ws.poll()
        self.assertEqual(len(self.watchListOut.inputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.outputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.globalNames.keys()), 1)
        self.assertEqual(self.watchListOut.globalNames['StringOut']['value'], 'Result: 0_plus_string')

    def test_cancelWatch(self):
        self.watchListOut = None
        def watchCallback(workspace, watchList):
            self.watchListOut = watchList
            return True
        self.watchListIn = ws.WatchList.fromIONames(outputs=['Result'])
        self.ws.watch(callback=watchCallback, watchList=self.watchListIn, autoDelete=False)
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 4)
        self.ws.runOnce()
        while not self.watchListOut:
            ws.Workspace.poll()
        self.assertEqual(self.watchListOut.id, self.watchListIn.id)
        self.ws.cancelWatch(self.watchListIn.id)

    def test_success(self):
        self.called = False
        def successCallback(workspace):
            self.called = True
            return True
        self.ws.onSuccess(successCallback)
        self.ws.runOnce()
        while not self.called:
            self.ws.poll()
        self.assertTrue(self.called)

    def test_successRunOnce(self):
        self.called = False
        def successCallback(workspace):
            self.called = True
            return True
        self.ws.onSuccess(successCallback)
        self.ws.runOnceAndWait()
        self.assertTrue(self.called)

    def test_error(self):
        self.called = False
        def errorCallback(workspace, message):
            self.called = True
            return True
        self.ws.onError(errorCallback)
        self.ws.setInput('Value1', 'not_an_integer')
        self.ws.runOnce()
        while not self.called:
            self.ws.poll()
        self.assertTrue(self.called)

    def test_listInputs(self):
        def listCallback(workspace, resultsList):
            self.resultsList = resultsList
            return True;
        self.resultsList = None
        self.ws.listInputs(listCallback)
        while not self.resultsList:
            self.ws.poll()
        self.assertEqual(len(self.resultsList.inputs.keys()), 3)
        self.assertEqual(len(self.resultsList.outputs.keys()), 0)
        self.assertEqual(len(self.resultsList.globalNames.keys()), 0)
        self.assertEqual(0, self.resultsList.inputs['Value1']['value'])
        self.assertEqual(0, self.resultsList.inputs['Value2']['value'])
        self.assertEqual('int', self.resultsList.inputs['Value1']['type'])
        self.assertEqual('int', self.resultsList.inputs['Value2']['type'])
        self.assertEqual('CSIRO::DataExecution::Dependency', self.resultsList.inputs['Dependencies']['type'])

    def test_listGlobalNames(self):
        def listCallback(workspace, resultsList):
            self.resultsList = resultsList
            return True
        self.resultsList = None
        self.ws.setGlobalName('StringIn', 'oh_hello')
        self.ws.listGlobalNames(listCallback)
        while not self.resultsList:
            self.ws.poll()
        self.assertEqual(len(self.resultsList.inputs.keys()), 0)
        self.assertEqual(len(self.resultsList.outputs.keys()), 0)
        self.assertEqual(len(self.resultsList.globalNames.keys()), 2)
        self.assertEqual(len(self.resultsList.globalNames['StringIn'].keys()), 2)
        self.assertEqual(len(self.resultsList.globalNames['StringOut'].keys()), 2)
        self.assertEqual('QString', self.resultsList.globalNames['StringIn']['type'])
        self.assertEqual('QString', self.resultsList.globalNames['StringOut']['type'])
        self.assertEqual('oh_hello', self.resultsList.globalNames['StringIn']['value'])
        self.assertEqual('', self.resultsList.globalNames['StringOut']['value'])

    def test_getOutputs_Success(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 6)
        self.ws.runOnceAndWait()
        outputs = self.ws.getOutputs()
        self.assertEqual(outputs['Result']['value'], 12)

    def test_getOutputs_Fail(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 'b')
        self.ws.runOnceAndWait()
        outputs = self.ws.getOutputs()
        self.assertEqual(outputs['Result']['value'], 0)

    def test_getOutputs_NotRunning(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 6)
        outputs = self.ws.getOutputs()
        self.assertEqual(outputs['Result']['value'], 0)

    def test_getInputs_Success(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 6)
        self.ws.runOnceAndWait()
        inputs = self.ws.getInputs()
        self.assertEqual(inputs['Value1']['value'], 2)
        self.assertEqual(inputs['Value2']['value'], 6)

    def test_getInputs_Fail(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 'b')
        self.ws.runOnceAndWait()
        inputs = self.ws.getInputs()
        self.assertEqual(inputs['Value1']['value'], 2)
        self.assertEqual(inputs['Value2']['value'], 0)

    def test_getInputs_NotRunning(self):
        self.ws.setInput('Value1', 2)
        self.ws.setInput('Value2', 6)
        inputs = self.ws.getInputs()
        self.assertEqual(inputs['Value1']['value'], 2)
        self.assertEqual(inputs['Value2']['value'], 6)

    def test_getGlobalNames(self):
        self.ws.setGlobalName('StringIn', 'oh_hello')
        value1 = 2
        value2 = 4
        self.ws.setInput('Value1', value1)
        self.ws.setInput('Value2', value2)
        self.ws.runOnceAndWait()
        globalNames = self.ws.getGlobalNames()
        self.assertEqual(len(globalNames.keys()), 2)
        self.assertEqual(len(globalNames['StringIn'].keys()), 2)
        self.assertEqual(len(globalNames['StringOut'].keys()), 2)
        expString = 'oh_hello'
        self.assertEqual('QString', globalNames['StringIn']['type'])
        self.assertEqual('QString', globalNames['StringOut']['type'])
        self.assertEqual(expString, globalNames['StringIn']['value'])

        expNumber = value1 * value2
        self.assertEqual(f"Result: {expNumber}{expString}", globalNames['StringOut']['value'])

    def test_eventLoop(self):
        self.started = False
        self.expectedResults = [1, 1, 2, 3, 4, 5]
        self.watchCount = 0
        def watchCallback(workspace, watchList):
            print(self.watchCount)
            self.assertEqual(watchList.outputs['Result']['value'], self.expectedResults[self.watchCount])
            self.watchCount += 1
            if (self.watchCount < len(self.expectedResults)):
                workspace.setInput('Value2', self.watchCount)
            elif self.watchCount == len(self.expectedResults):
                ws.Workspace.stopEventLoop()
            return True
        def eventLoopStarted():
            #try:
            self.started = True
            self.assertTrue(self.started)
            watchListIn = ws.WatchList.fromIONames(outputs=['Result'])
            self.ws.watch(callback=watchCallback, watchList=watchListIn, autoDelete=False)
            self.ws.setInput('Value1', 1)
            self.ws.setInput('Value2', 1)
            self.ws.runContinuously()
            return True

        ws.Workspace.startEventLoop(eventLoopStarted)

suite = unittest.TestLoader().loadTestsFromTestCase(TestWorkspace)
unittest.TextTestRunner(verbosity=0).run(suite)


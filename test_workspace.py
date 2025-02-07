import csiro_workspace.workspace as workspace
import unittest
import os.path

class TestWorkspace(unittest.TestCase):

    def setUp(self):
        def onConnected(workspace):
            return True
        self.filePath = os.path.join(os.path.dirname(__file__), 'test_workspace.wsx')
        self.ws = workspace.Workspace(self.filePath, onConnected)

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
        self.ws.watch(callback=watchCallback, watchList=workspace.WatchList.fromIONames(outputs=['Result']), autoDelete=True)
        self.ws.setInput('Value1', '2')
        self.ws.setInput('Value2', '4')
        self.ws.runOnce()
        while not self.watchListOut:
            self.ws.poll()
        self.assertEqual(len(self.watchListOut.inputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.outputs.keys()), 1)
        self.assertEqual(len(self.watchListOut.globalNames.keys()), 0)
        self.assertEqual(self.watchListOut.outputs['Result']['value'], 8)

    def test_setGlobalName(self):
        def watchCallback(workspace, watchList):
            self.watchListOut = watchList
            return True
        self.watchListOut = None
        self.ws.watch(callback=watchCallback, watchList=workspace.WatchList.fromIONames(globalNames=['StringOut']), autoDelete=True)
        self.ws.setGlobalName('StringIn', '_plus_string')
        self.ws.runOnce()
        while not self.watchListOut:
            self.ws.poll()
        self.assertEqual(len(self.watchListOut.inputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.outputs.keys()), 0)
        self.assertEqual(len(self.watchListOut.globalNames.keys()), 1)
        self.assertEqual(self.watchListOut.globalNames['StringOut']['value'], 'Result: 0_plus_string')

    def test_cancelWatch(self):
        def watchCallback(workspace, watchList):
            self.watchListOut = watchList
            return True
        self.watchListOut = None
        self.watchListIn = workspace.WatchList.fromIONames(outputs=['Result'])
        self.ws.watch(callback=watchCallback, watchList=self.watchListIn, autoDelete=False)
        self.ws.setInput('Value1', '2')
        self.ws.setInput('Value2', '4')
        self.ws.runOnce()
        while not self.watchListOut:
            self.ws.poll()
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

    def test_eventLoop(self):
        self.started = False
        self.expectedResults = [1, 1, 2, 3, 4, 5]
        self.watchCount = 0
        def watchCallback(ws, watchList):
            self.assertEqual(watchList.outputs['Result']['value'], self.expectedResults[self.watchCount])
            self.watchCount += 1
            ws.setInput('Value2', self.watchCount)
            if self.watchCount == len(self.expectedResults):
                workspace.Workspace.stopEventLoop()
            return True
        def eventLoopStarted():
            #try:
            self.started = True
            self.assertTrue(self.started)
            watchListIn = workspace.WatchList.fromIONames(outputs=['Result'])
            self.ws.watch(callback=watchCallback, watchList=watchListIn, autoDelete=False)
            self.ws.setInput('Value1', 1)
            self.ws.setInput('Value2', 1)
            self.ws.runContinuously()
            return True

        workspace.Workspace.startEventLoop(eventLoopStarted)

suite = unittest.TestLoader().loadTestsFromTestCase(TestWorkspace)
unittest.TextTestRunner(verbosity=0).run(suite)


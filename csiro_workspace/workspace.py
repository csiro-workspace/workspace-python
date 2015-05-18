# ===========================================================================
#
#  Revision:       $Revision: 4 $
#  Last changed:   $Date: 2010-05-24 11:57:57 +1000 (Mon, 24 May 2010) $
#
#  Copyright 2015 by:
#
#  Commonwealth Scientific and Industrial Research Organisation (CSIRO)
#
#  This file is licensed by CSIRO under the copy of the CSIRO Binary
#  License Agreement included with the file when downloaded or obtained
#  from CSIRO (including any Supplementary License).  If no copy was
#  included, you must obtain a new copy of the Software from CSIRO before
#  any use is permitted.
#
#  For further information, contact: workspace@csiro.au
#
#  This copyright notice must be included with all copies of the source code.
#
# ===========================================================================

from ctypes import cdll, byref, c_char, c_char_p, c_int, c_void_p, c_bool, Structure, pointer, POINTER, CFUNCTYPE
import copy
import subprocess
import atexit
import uuid
import json
import datetime
import os.path

# Struct for our WorkspaceId type. Don't attempt to print
# the host, as it won't work. We only need it to pass to the Workspace API
# anyway.
class WORKSPACE_ID(Structure):
    _fields_ = [("key",  c_int),
                ("port", c_int),
                ("host", c_char * 255)]

    # Returns the key in the correct format. We don't want it as a c_int.
    def getKey(self):
        return int(self.key)


# Load our Workspace config file
ws_config_file = open(os.path.dirname(__file__) + '/workspace.cfg', 'r')
ws_config = json.load(ws_config_file)

# Function types for our C++ code to call back into
LOOPSTARTFUNC = CFUNCTYPE(c_int)
CONNFUNC      = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID))
SUCCESSFUNC   = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID))
FAILFUNC      = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID))
ERRORFUNC     = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID), c_char_p)
WATCHFUNC     = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID), c_char_p)
LISTFUNC      = CFUNCTYPE(c_int, POINTER(WORKSPACE_ID), c_char_p)

# Our C++ function references
LibWorkspaceWeb                       = cdll.LoadLibrary(ws_config['workspace_install_dir'] + '/lib/libworkspaceweb.dylib')
server_init                           = LibWorkspaceWeb.server_init
server_listen_for_connection_and_wait = LibWorkspaceWeb.server_listen_for_connection_and_wait
server_start_event_loop               = LibWorkspaceWeb.server_start_event_loop
server_stop_event_loop                = LibWorkspaceWeb.server_stop_event_loop
workspace_register_func_success       = LibWorkspaceWeb.workspace_register_func_success
workspace_register_func_failed        = LibWorkspaceWeb.workspace_register_func_failed
workspace_register_func_error         = LibWorkspaceWeb.workspace_register_func_error
server_poll                           = LibWorkspaceWeb.server_poll
workspace_run_once                    = LibWorkspaceWeb.workspace_run_once
workspace_run_continuously            = LibWorkspaceWeb.workspace_run_continuously
workspace_terminate                   = LibWorkspaceWeb.workspace_terminate
workspace_set_input                   = LibWorkspaceWeb.workspace_set_input
workspace_set_global_name             = LibWorkspaceWeb.workspace_set_global_name
workspace_list_inputs                 = LibWorkspaceWeb.workspace_list_inputs
workspace_list_outputs                = LibWorkspaceWeb.workspace_list_outputs
workspace_list_global_names           = LibWorkspaceWeb.workspace_list_global_names
workspace_watch                       = LibWorkspaceWeb.workspace_watch
workspace_cancel_watch                = LibWorkspaceWeb.workspace_cancel_watch

def initCInterface():
    """
    Initialises our C++ function references, assigning the correct parameter
    types and return types.
    """
    server_init.restype = c_int
    server_init.argtypes = [c_int]
    server_listen_for_connection_and_wait.restype = c_int
    server_listen_for_connection_and_wait.argtypes = [c_char_p, c_int, CONNFUNC]
    server_start_event_loop.restype = c_int
    server_start_event_loop.argtypes = [LOOPSTARTFUNC]
    server_stop_event_loop.restype = c_int
    workspace_register_func_success.restype = c_int
    workspace_register_func_success.argtypes = [POINTER(WORKSPACE_ID), SUCCESSFUNC]
    workspace_register_func_failed.restype = c_int
    workspace_register_func_failed.argtypes = [POINTER(WORKSPACE_ID), FAILFUNC]
    workspace_register_func_error.restype = c_int
    workspace_register_func_error.argtypes = [POINTER(WORKSPACE_ID), ERRORFUNC]
    server_poll.restype = c_int
    server_poll.argtypes = [c_int]
    workspace_run_once.restype = c_int
    workspace_run_once.argtypes = [POINTER(WORKSPACE_ID)]
    workspace_run_continuously.restype = c_int
    workspace_run_continuously.argtypes = [POINTER(WORKSPACE_ID)]
    workspace_terminate.restype = c_int
    workspace_terminate.argtypes = [POINTER(WORKSPACE_ID)]
    workspace_set_input.restype = c_int
    workspace_set_input.argtypes = [POINTER(WORKSPACE_ID), c_char_p, c_char_p]
    workspace_set_global_name.restype = c_int
    workspace_set_global_name.argtypes = [POINTER(WORKSPACE_ID), c_char_p, c_char_p]
    workspace_list_inputs.restype = c_int
    workspace_list_inputs.argtypes = [POINTER(WORKSPACE_ID), LISTFUNC]
    workspace_list_outputs.restype = c_int
    workspace_list_outputs.argtypes = [POINTER(WORKSPACE_ID), LISTFUNC]
    workspace_list_global_names.restype = c_int
    workspace_list_global_names.argtypes = [POINTER(WORKSPACE_ID), LISTFUNC]
    workspace_watch.restype = c_int
    workspace_watch.argtypes = [POINTER(WORKSPACE_ID), c_char_p, WATCHFUNC]
    workspace_cancel_watch.restype = c_int
    workspace_cancel_watch.argtypes = [POINTER(WORKSPACE_ID), c_char_p]

    # Initialise the server
    server_init(ws_config['log_level'])


class IONotExistsError(Exception):
    """
    Exception for when a named input, output or global name doesn't exist.
    """
    def __init__(self, name):
        self._name = name

    def __str__(self):
        return 'ERROR: Input/Output/GlobalName "%s" does not exist.' % self._name

    @property
    def name(self):
        return _name


class WatchList(object):
    """
    Wraps the C-API's WatchList class to manage scoped deletion etc.
    """
    @classmethod
    def fromIONames(cls, inputs=[], outputs=[], globalNames=[]):
        """
        Constructs a new WatchList object from a set of watch names.
        """
        id = str(uuid.uuid4())
        inputsDict = {}
        for name in inputs:
            inputsDict[name] = {}
        outputsDict = {}
        for name in outputs:
            outputsDict[name] = {}
        globalNamesDict = {}
        for name in globalNames:
            globalNamesDict[name] = {}

        return cls(id, inputsDict, outputsDict, globalNamesDict)

    @classmethod
    def fromJson(cls, jsonStr):
        """
        Constructs a new WatchList object from its json description.
        """
        wl = json.loads(jsonStr)
        if 'id' not in wl.keys():
            return None

        return cls(wl['id'], wl['inputs'] if 'inputs' in wl.keys() else {},
                             wl['outputs'] if 'outputs' in wl.keys() else {},
                             wl['globalNames'] if 'globalNames' in wl.keys() else {})

    def __init__(self, id, inputs, outputs, globalNames):
        """
        Constructs a watchlist from a watch list dictionary.
        """
        self._id = id
        self._inputs = inputs
        self._outputs = outputs
        self._globalNames = globalNames

    def __str__(self):
        """
        Return the WatchList in JSON format.
        """
        return json.dumps(self.asDict())

    def asDict(self): 
        """
        Return the WatchList as a dictionary.
        """
        wl = dict()
        wl['id'] = self._id
        wl['inputs'] = self._inputs
        wl['outputs'] = self._outputs
        wl['globalNames'] = self._globalNames
        return wl

    @property
    def id(self):
        """
        Returns the unique identifier for this watch list.
        """
        return self._id

    @property
    def inputs(self):
        """
        Returns a list of inputs, where each input is a dictionary with
        the members 'name', 'value' and 'type'.
        """
        return self._inputs

    @property
    def outputs(self):
        """
        Returns a list of outputs, where each output is a dictionary with
        the members 'name', 'value' and 'type'.
        """
        return self._outputs

    @property
    def globalNames(self):
        """
        Returns a list of outputs, where each output is a dictionary with
        the members 'name', 'value' and 'type'.
        """
        return self._globalNames

class WatchCallback(object):
    """
    Callback wrapper for watching an input, output or globalname in a
    Workspace. Can specify the autodelete parameter to control whether or not
    the callback is deleted after it is invoked.
    """
    def __init__(self, workspace, watchId, callback, autodelete=True):
        self.workspace = workspace
        self.watchId = watchId
        self.callback = callback
        self.autodelete = autodelete

    def __call__(self, watchList):
        result = self.callback(self.workspace, watchList)
        if self.autodelete:
            self.workspace._removeWatch(self.watchId)
        return result


class Workspace:
    """
    Workspace instance. Abstracts away our externally running C++ Workspace
    application, communicating with it asynchronously using TCP/IP.
    """

    # Variables used for ensuring that processes are terminated, even if
    # something goes wrong during the terminate communication process (e.g.
    # child process is frozen)
    SERVER_ADDRESS = '127.0.0.1'
    TERMINATE_TIMEOUT_SEC = 10
    terminating_processes = []
    registered_workspaces = {}
    event_loop_running    = False

    @staticmethod
    def startEventLoop(onStartFunc):
        """
        Used to start the event loop, if one is needed. For web-based
        applications, it's recommended to instead use the server's event loop
        to repeatedly call \a poll() rather than starting this event loop.
        For a simple command line application, the event loop will be required in
        order to repeatedly pool for updates, but again, a python-based event
        loop that repeatedly invokes \a poll() could be used instead.

        \note failure to stop the event loop will cause the application to
        hang.
        """
        server_start_event_loop(LOOPSTARTFUNC(onStartFunc))
        Workspace.event_loop_running = True

    @staticmethod
    def stopEventLoop():
        """
        Stops the event loop if it is running.
        """
        server_stop_event_loop()

    @staticmethod
    def atexit():
        """
        Always stop the event loop at application exit time.
        """
        if Workspace.event_loop_running:
            Workspace.stopEventLoop()

        # Don't forget we also need to make sure all our workspace processes
        # are shut down, since we started them!
        for key in Workspace.registered_workspaces.keys():
            Workspace.registered_workspaces[key].terminate()

    @staticmethod
    def poll(timeoutMs=0):
        """
        Static method for polling the client applications to determine what's
        updated.
        """
        server_poll(timeoutMs)

        # Each time we poll, we iterate over the list of existing terminating
        # procesess and kill them if they've been taking too long to shut down.
        # If a process has already been shutdown correctly, we just remove it
        # from the list.
        for procRef in Workspace.terminating_processes:
            ws = procRef[1]
            timeTerminated = procRef[0]
            if None == ws._process.poll():
                if (datetime.datetime.now() - timeTerminated).seconds > ws_config['terminate_timeout_sec']:
                    ws._process.kill()
                    ws._cleanup()
                    Workspace.terminating_processes.remove(procRef)
            else:
                Workspace.terminating_processes.remove(procRef)
                ws._cleanup()

    def _createConnectedCallback(self, onConnected):
        """
        Factory method to create an success callback function that can
        be invoked by ctypes that still has access to 'self' because it
        is a closure.
        """
        def callback(workspaceId):
            self._id = copy.deepcopy(workspaceId.contents)

            # Register the workspace itself so that it can be cleaned up later
            # if need be.
            Workspace.registered_workspaces[self.id] = self

            # Register success, failed and error callbacks. Make sure to store them
            # in the local workspace, otherwise they'll get garbage collected
            # before being invoked.
            workspace_register_func_success(workspaceId, self._successCallback)
            workspace_register_func_failed(workspaceId, self._failedCallback)
            workspace_register_func_error(workspaceId, self._errorCallback)

            # Invoke our callback for when a process has connected successfully
            return onConnected(self)
        return CONNFUNC(callback)

    def _createSuccessCallback(self):
        """
        Factory method to create an success callback function that can
        be invoked by ctypes that still has access to 'self' because it
        is a closure.
        """
        def callback(workspaceId):
            try:
                return self._onSuccessFunc(self)
            except:
                return True
        return SUCCESSFUNC(callback)

    def _createFailedCallback(self):
        """
        Factory method to create an failure callback function that can
        be invoked by ctypes that still has access to 'self' because it
        is a closure.
        """
        def callback(workspaceId):
            try:
                return self._onFailedFunc(self)
            except:
                return True
        return FAILFUNC(callback)

    def _createErrorCallback(self):
        """
        Factory method to create an error callback function that can
        be invoked by ctypes that still has access to 'self' because it
        is a closure.
        """
        def callback(workspaceId, errorMessage):
            try:
                return self._onErrorFunc(self, errorMessage)
            except:
                return True
        return ERRORFUNC(callback)

    def _createWatchCallback(self):
        """
        Factory method to create an watch callback function that can
        be invoked by ctypes that still has access to 'self' because it
        is a closure.
        """
        def callback(workspaceId, watchListStr):
            wl = WatchList.fromJson(watchListStr)
            if wl and wl.id in self._watches.keys():
                return self._watches[wl.id](wl)
        return WATCHFUNC(callback)

    def _createListCallback(self, ioType):
        """
        Factory method to create a callback function to invoke when a request
        for a list of inputs / outputs / globalNames is made. As with the other
        callback methods, 'self' is available because the callback is a closure.
        """
        def callback(workspaceId, ioListStr):
            ioList = WatchList.fromJson(ioListStr)
            result = self._listRequests[ioType](self, ioList)
            del self._listRequests[ioType]
            return result
        return LISTFUNC(callback)

    def _removeWatch(self, watchId):
        """
        Removes a specific watch callback. Generally this is only used by the
        WatchCallback class to remove itself when it is in 'autodelete' mode.
        """
        del self._watches[watchId]

    def _cleanup(self):
        """
        Clean up the workspace after it has terminated. We need to do this to
        make sure we safely delete all of our closures while they are not in
        call. If we don't delete them, the workspace object's reference count
        will never reach zero.
        """
        self._process = None
        del self._connectedCallback
        del self._successCallback
        del self._failedCallback
        del self._errorCallback
        del self._watchCallback
        del self._listCallbackInputs
        del self._listCallbackOutputs
        del self._listCallbackGlobalNames
        del Workspace.registered_workspaces[self.id]

    def __init__(self, fileName, onConnected):
        """
        Constructs a new Workspace object, creating a subprocess of the
        workspace-web (C++) application, telling it to connect to our workspace
        server. All actions performed on a Workspace object are communicated to
        this workspace-web process using the libworkspaceweb C interface (and ctypes).
        """
        self._fileName = fileName
        self._watches = dict()
        self._listRequests = dict()

        # Use our factory methods to create all our callback functions. These
        # callback functions are used to forward on to the functions that the
        # user registers.
        self._connectedCallback = self._createConnectedCallback(onConnected)
        self._successCallback = self._createSuccessCallback()
        self._failedCallback = self._createFailedCallback()
        self._errorCallback = self._createErrorCallback()
        self._watchCallback = self._createWatchCallback()
        self._listCallbackInputs = self._createListCallback('inputs')
        self._listCallbackOutputs = self._createListCallback('outputs')
        self._listCallbackGlobalNames = self._createListCallback('globalNames')

        # Start our actual child process. We start it first since it's
        # asynchronous, whereas our server isn't (since we don't have an event loop)
        self._process = subprocess.Popen([
            ws_config['workspace_install_dir'] + '/bin/workspace-web',
            fileName,
            '--port', '%d' % ws_config['connection_port'],
            '--log-level', '%d' % ws_config['log_level']
        ])

        # Listen to connections from our new process.
        success = server_listen_for_connection_and_wait(Workspace.SERVER_ADDRESS, ws_config['connection_port'], self._connectedCallback)
        if not success:
            raise RuntimeError('Failed to connect to Workspace process running "%s"' % fileName)

    @property
    def id(self):
        return self._id.getKey()

    @property
    def fileName(self):
        """
        The file name of the Workspace being invoked. This may be a url.
        """
        return self._fileName

    @fileName.setter
    def fileName(self, fileName):
        self._fileName = fileName

    def runOnce(self):
        """
        (asynchronous)
        Requests that the contained Workspace be executed once.
        """
        workspace_run_once(byref(self._id))

    def runContinuously(self):
        """
        (asynchronous)
        Requests that the contained Workspace be executed in continuous mode.
        """
        workspace_run_continuously(byref(self._id))

    def terminate(self):
        """
        (asynchronous)
        Requests that the workspace-web suprocess shut down.
        """
        if not self._process:
            return

        # Calling this will tell the process to terminate itself.
        success = workspace_terminate(byref(self._id))

        # Before we get rid of the process reference, store it in the queue of
        # terminating processes so that we can get kill it if it doesn't
        # promptly terminate itself.
        Workspace.terminating_processes.append((datetime.datetime.now(), self))

    def setInput(self, inputName, content):
        """
        (asynchronous)
        Assigns some content to a particular top-level input on the containd
        Workspace. If the Workspace is currently executing, this will be
        applied as soon as it is safe to do so.
        """
        return workspace_set_input(byref(self._id), inputName, str(content))

    def setGlobalName(self, globalName, content):
        """
        (asynchronous)
        Assigns some content to a global name (input or output) on the
        contained Workspace. If the Workspace is currently executing, this will
        be applied as soon as it is safe to do so.
        """
        return workspace_set_global_name(byref(self._id), globalName, str(content))

    def watch(self, callback, watchList, autoDelete=True):
        """
        (asynchronous)
        Sets up a watch on a specific Workspace output. When the output becomes
        up-to-date, the callback will be triggered.
        """
        self._watches[watchList.id] = WatchCallback(self, watchList.id, callback, autoDelete)
        if workspace_watch(byref(self._id), str(watchList), self._watchCallback, autoDelete):
            return watchList.id
        return None

    def cancelWatch(self, watchId):
        """
        Cancels a (non-single-shot) watch request, by de-registering the
        existing callback.
        """
        self._removeWatch(watchId)
        workspace_cancel_watch(byref(self._id), watchId)

    def listInputs(self, callback):
        """
        (asynchronous)
        Requests a list of inputs from the running Workspace, and invokes the
        callback, passing it itself and a IOList object containing the results.
        """
        self._listRequests['inputs'] = callback
        return workspace_list_inputs(byref(self._id), self._listCallbackInputs);

    def listOutputs(self, callback):
        """
        (asynchronous)
        Requests a list of outputs from the running Workspace, and invokes the
        callback, passing it itself and a IOList object containing the results.
        """
        self._listRequests['outputs'] = callback
        return workspace_list_outputs(byref(self._id), self._listCallbackOutputs);

    def listGlobalNames(self, callback):
        """
        (asynchronous)
        Requests a list of globalnames from the running Workspace and invokes
        the callback, passing itself and an IOList object containing the results.
        """
        self._listRequests['globalNames'] = callback
        return workspace_list_global_names(byref(self._id), self._listCallbackGlobalNames)

    def onSuccess(self, callback):
        """
        (asynchronous)
        Assign a callback function to invoke when the workflow successfully
        completes execution.
        """
        self._onSuccessFunc = callback

    def onFailed(self, callback):
        """
        (asynchronous)
        Assign a callback function to invoke when the workflow fails to
        execute.
        """
        self._onFailedFunc = callback

    def onError(self, callback):
        """
        (asynchronous)
        Assign a callback function to invoke when an error occurs.
        """
        self._onErrorFunc = callback

# Prior to using the module, all our c functions need to be initialised.
initCInterface()

# Make sure that on quit() or exit() calls, all our subprocesses are shut down.
atexit.register(Workspace.atexit)


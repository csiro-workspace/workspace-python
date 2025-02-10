"""
This module contains definitions of the `Workspace` and `WatchList` classes;
all the things necessary to create, execute and interact with Workspace
workflows in Python.

Importantly, alongside this module is a file called
_workspace.cfg_ which contains the configuration information required to use
this module. Among other things, this file contains configuration options to
control which copy of Workspace to use when running workflows, the port on
which TCP communication to running Workspace processes should occur, and the
log-level used by each process.

Copyright 2015 by:

Commonwealth Scientific and Industrial Research Organisation (CSIRO)

This file is licensed by CSIRO under the copy of the CSIRO Open Source Software
License Agreement included with the file when downloaded or obtained
from CSIRO (including any Supplementary License). If no copy was
included, you must obtain a new copy of the Software from CSIRO before
any use is permitted.

For further information, contact: workspace@csiro.au

This copyright notice must be included with all copies of the source code.
"""

from ctypes import cdll, byref, c_char, c_char_p, c_int, c_void_p, c_bool, Structure, pointer, POINTER, CFUNCTYPE
import platform
import copy
import subprocess
import atexit
import uuid
import json
import datetime
import os.path
import ctypes

class _WORKSPACE_ID(Structure):
    """
    Struct for our WorkspaceId type. Maps to a C struct in the WorkspaceWeb
    shared library by extending ctypes.Structure.
    """
    _fields_ = [("key",  c_int),
                ("port", c_int),
                ("host", c_char * 255)]

    # Returns the key in the correct format. We don't want it as a c_int.
    def getKey(self):
        return int(self.key)


# Load our Workspace config file
_ws_config_file = open(os.path.dirname(__file__) + '/workspace.cfg', 'r')
_ws_config = json.load(_ws_config_file)

# Function types for our C++ code to call back into
LOOPSTARTFUNC = CFUNCTYPE(c_int)
CONNFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
SUCCESSFUNC   = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
FAILFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
ERRORFUNC     = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)
WATCHFUNC     = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)
LISTFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)

# Our C++ function references
LibWorkspaceWeb = None
if platform.system() == 'Windows':
    LibWorkspaceWeb = ctypes.WinDLL(_ws_config['workspace_install_dir'] + '/lib/workspaceweb.dll', winmode = 0x8)
elif platform.system() == 'Linux':
    LibWorkspaceWeb = cdll.LoadLibrary(_ws_config['workspace_install_dir'] + '/lib/libworkspaceweb.so')
else:
    LibWorkspaceWeb = cdll.LoadLibrary(_ws_config['workspace_install_dir'] + '/lib/libworkspaceweb.dylib')
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
workspace_stop                        = LibWorkspaceWeb.workspace_stop

def _initCInterface():
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
    workspace_register_func_success.argtypes = [POINTER(_WORKSPACE_ID), SUCCESSFUNC]
    workspace_register_func_failed.restype = c_int
    workspace_register_func_failed.argtypes = [POINTER(_WORKSPACE_ID), FAILFUNC]
    workspace_register_func_error.restype = c_int
    workspace_register_func_error.argtypes = [POINTER(_WORKSPACE_ID), ERRORFUNC]
    server_poll.restype = c_int
    server_poll.argtypes = [c_int]
    workspace_run_once.restype = c_int
    workspace_run_once.argtypes = [POINTER(_WORKSPACE_ID)]
    workspace_run_continuously.restype = c_int
    workspace_run_continuously.argtypes = [POINTER(_WORKSPACE_ID)]
    workspace_terminate.restype = c_int
    workspace_terminate.argtypes = [POINTER(_WORKSPACE_ID)]
    workspace_set_input.restype = c_int
    workspace_set_input.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, c_char_p]
    workspace_set_global_name.restype = c_int
    workspace_set_global_name.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, c_char_p]
    workspace_list_inputs.restype = c_int
    workspace_list_inputs.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]
    workspace_list_outputs.restype = c_int
    workspace_list_outputs.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]
    workspace_list_global_names.restype = c_int
    workspace_list_global_names.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]
    workspace_watch.restype = c_int
    workspace_watch.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, WATCHFUNC]
    workspace_cancel_watch.restype = c_int
    workspace_cancel_watch.argtypes = [POINTER(_WORKSPACE_ID), c_char_p]
    workspace_stop.restype = c_int
    workspace_stop.argtypes = [POINTER(_WORKSPACE_ID)]

    # Initialise the server
    server_init(_ws_config['log_level'])


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
        """
        Returns the name of the input, output or global name that does not
        exist.
        """
        return self._name


class WatchList(object):
    """
    Represents a list of inputs, outputs or globalnames to watch in the running
    Workspace. Once one of these has been created, it is passed to the method
    `Workspace.watch()` which will monitor the specific inputs/outputs for
    updates. Wraps the C-API's WatchList class to manage scoped deletion etc.
    """
    @classmethod
    def fromIONames(cls, inputs=[], outputs=[], globalNames=[]):
        """
        Constructs a new WatchList object, where `inputs` is the list of input
        names, `outputs` is the list of output names and `globalNames` is the
        list of global names to watch.
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
        Constructs a new WatchList object from the json contained in `jsonStr`.
        An example of a valid json object is:

            {
                "id": "1lFDS-12314-VBAVD-1241-ADFS",
                "inputs": {
                    "input1": {
                        "type": "double",
                        "value": 0.1
                    },
                },
                "outputs": {
                    "output1": {
                        "type": "double",
                        "value": 3.4
                    },
                },
                "globalNames": {
                    "global1": {
                        "type": "QString",
                        "value": "Hello Workspace!"
                    },
                }
            }

        Note that when creating a WatchList object for the purposes of creating
        a new watch (i.e. with the `Workspace.watch()` method), the `type` and
        `value` members of each input, output or globalName are not required.
        Also note that the `id` member is crucial, as this is used to globally
        identify the WatchList. If an `id` parameter is not present in the
        string, `None` will be returned.
        """
        wl = json.loads(jsonStr)
        if 'id' not in wl.keys():
            return None

        return cls(wl['id'], wl['inputs'] if 'inputs' in wl.keys() else {},
                             wl['outputs'] if 'outputs' in wl.keys() else {},
                             wl['globalNames'] if 'globalNames' in wl.keys() else {})

    def __init__(self, id, inputs, outputs, globalNames):
        """
        Constructs a watchlist using `inputs`, `outputs` and `globalNames`, all
        of which are of type `dict`.
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
        the members `name`, `value` and `type`.
        """
        return self._inputs

    @property
    def outputs(self):
        """
        Returns a list of outputs, where each output is a dictionary with
        the members `name1, `value` and `type`.
        """
        return self._outputs

    @property
    def globalNames(self):
        """
        Returns a list of globalNames, where each output is a dictionary with
        the members `name`, `value` and `type`.
        """
        return self._globalNames


class _WatchCallback(object):
    """
    Callback wrapper for watching an input, output or globalname in a
    Workspace. Can specify the autodelete parameter to control whether or not
    the callback is automatically deleted after it is invoked.
    """
    def __init__(self, workspace, watchId, callback, autodelete=True):
        """
        Constructs a new _WatchCallback. When triggered in response to a watch
        event from the target `workspace`, the function `callback` is invoked
        and provided the `workspace` and a `WatchList` object as arguments.

        The `watchId` must be a globally unique identifier (usually a uuid), that
        uniquely identifies the set of watched inputs/outputs/globalNames and
        the associated callback.
        """
        self.workspace = workspace
        self.watchId = watchId
        self.callback = callback
        self.autodelete = autodelete

    def __call__(self, watchList):
        """
        Triggered when the watch idendified by the stored watchId is brought
        up-to-date in the associated Workspace workflow. Will invoke the stored
        callback function, providing it the original `Workspace` object and a
        `WatchList` object as arguments.
        """
        result = self.callback(self.workspace, watchList)
        if self.autodelete:
            self.workspace._removeWatch(self.watchId)
        return result


class Workspace:
    """
    Represents an instance of a Workspace workflow. Users create an instance of
    this class for each instance of a Workspace workflow (.wsx) file that they
    wish to execute. Behind the scenes, Workspaces are executed in a separate
    process, and this object communicates with it via TCP/IP. For this reason,
    the user provides a callback function when creating a new Workspace
    instance, which is invoked only after the instance has been connected to
    successfully.

    Once the Workspace instance is connected, the user is able to set input
    and globalName values using the `setInput` and `setGlobalName` methods,
    execute it using the `runOnce` or `runContinuously` methods, and
    monitor specific inputs, outputs or globalNames by using the `watch`
    method. Similarly, lists of inputs, outputs or globalNames can be retrieved
    by using the `listInputs`, `listOutputs` or `listGlobalNames` methods.

    To take action when the Workspace instance successfully completes its
    execution, fails to execute, or aborts due to an error, provide callback
    functions to the `onSuccess`, `onFailed` or `onError` methods.

    It is important to note that the Workspace class does not allow any
    interaction in a synchronous manner. This ensures that all interactions
    with a running Workspace workflow are safe. Therefore, users always
    interact with Workspace instances via callback functions. Importantly,
    since each running Workspace instance runs in its own separate process, the
    application must periodically check each process to see whether it has
    posted any updates. Calling code can manage this using either of two
    different methods. Users can either:

    - Use the static `startEventLoop` and `stopEventLoop` functions to
      conveniently create an event loop which will monitor workflows and
      notify each Workspace object appropriately, or
    - Use the static `poll` function to check for updates to all running
      Workspace instances. This function invokation could (for example)
      be embedded in your own event loop code elsewhere, such as within
      a python-based web-server, invoked at a frequency of your choosing.

    This is important, as if neither of these methods is followed, no
    callback responses (e.g. from `watch` or `list` requests) will ever be
    received from running Workspace instances.
    """

    # Variables used for ensuring that processes are terminated, even if
    # something goes wrong during the terminate communication process (e.g.
    # child process is frozen)
    _SERVER_ADDRESS = b'127.0.0.1'
    _terminating_processes = []
    _registered_workspaces = {}
    _event_loop_running    = False

    @staticmethod
    def _atexit():
        """
        This static method is always invoked when the Workspace module
        terminates. It ensures that the event loop has stopped, and is
        guaranteed to shut down any running Workspace instances.
        """
        if Workspace._event_loop_running:
            Workspace.stopEventLoop()

        # Don't forget we also need to make sure all our workspace processes
        # are shut down, since we started them!
        for key in Workspace._registered_workspaces.keys():
            Workspace._registered_workspaces[key].terminate()

    @staticmethod
    def startEventLoop(onStartFunc):
        """
        Used to start the event loop, if one is needed. For web-based
        applications, it's recommended to instead use the server's event loop
        to repeatedly call `poll()` rather than starting this event loop.
        For a simple command line application, the event loop will be required in
        order to repeatedly pool for updates, but again, a python-based event
        loop that repeatedly invokes `poll()` could be used instead.

        The `onStartFunc` parameter is a callback that will be invoked as soon
        as the event loop has been successfully started.

        *Note:* failure to stop the event loop will cause the application to
        hang on exit.
        """
        server_start_event_loop(LOOPSTARTFUNC(onStartFunc))
        Workspace._event_loop_running = True

    @staticmethod
    def stopEventLoop():
        """
        Stops the event loop if it is running.
        """
        server_stop_event_loop()

    @staticmethod
    def poll(timeoutMs=0):
        """
        Static method for polling the client applications to determine what's
        updated. If any watch events have occurred since the time this method
        was last invoked, all of these watch events will be triggered.

        The `timeoutMs` parameter should be a number representing how long the
        method should wait until returning in the case that there are no new
        updates available.
        """
        server_poll(timeoutMs)

        # Each time we poll, we iterate over the list of existing terminating
        # procesess and kill them if they've been taking too long to shut down.
        # If a process has already been shutdown correctly, we just remove it
        # from the list.
        for procRef in Workspace._terminating_processes:
            ws = procRef[1]
            timeTerminated = procRef[0]
            if None == ws._process.poll():
                if (datetime.datetime.now() - timeTerminated).seconds > _ws_config['terminate_timeout_sec']:
                    ws._process.kill()
                    ws._cleanup()
                    Workspace._terminating_processes.remove(procRef)
            else:
                Workspace._terminating_processes.remove(procRef)
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
            Workspace._registered_workspaces[self.id] = self

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

    def _create_WatchCallback(self):
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
        _WatchCallback class to remove itself when it is in 'autodelete' mode.
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
        del Workspace._registered_workspaces[self.id]

    def __init__(self, fileName, onConnected):
        """
        Constructs a new Workspace instance, creating a subprocess of the
        workspace-web (C++) application. All actions performed on a Workspace
        instance are communicated to this new workspace-web process using the
        underlying libworkspaceweb C interface (and ctypes).

        The `fileName` parameter should be a path (or URL) to a Workspace workflow
        (.wsx) file, and the `onConnected` parameter is a callback function
        that will be invoked once the connection to the newly created
        workspace-web process is successful. It is important to note that until
        the connection is successful, all attempts to communicate with the
        Workspace instance via this class' member functions will fail.
        """
        self._fileName = fileName
        self._watches = dict()
        self._listRequests = dict()

        # Create these so that calling code can rely on the attributes existing
        self._onFailedFunc = None
        self._onSuccessFunc = None
        self._onErrorFunc = None

        # Use our factory methods to create all our callback functions. These
        # callback functions are used to forward on to the functions that the
        # user registers.
        self._connectedCallback = self._createConnectedCallback(onConnected)
        self._successCallback = self._createSuccessCallback()
        self._failedCallback = self._createFailedCallback()
        self._errorCallback = self._createErrorCallback()
        self._watchCallback = self._create_WatchCallback()
        self._listCallbackInputs = self._createListCallback('inputs')
        self._listCallbackOutputs = self._createListCallback('outputs')
        self._listCallbackGlobalNames = self._createListCallback('globalNames')

        # Start our actual child process. We start it first since it's
        # asynchronous, whereas our server isn't (since we don't have an event loop)
        self._process = subprocess.Popen([
            _ws_config['workspace_install_dir'] + '/bin/workspace-web',
            fileName,
            '--port', '%d' % _ws_config['connection_port'],
            '--log-level', '%d' % _ws_config['log_level']
        ])

        # Listen to connections from our new process.
        success = server_listen_for_connection_and_wait(Workspace._SERVER_ADDRESS, _ws_config['connection_port'], self._connectedCallback)
        if not success:
            raise RuntimeError('Failed to connect to Workspace process running "%s"' % fileName)

    @property
    def id(self):
        """
        Returns a string representing the unique identifier of this Workspace
        instance.
        """
        return self._id.getKey()

    @property
    def fileName(self):
        """
        Returns the file name of the Workspace being invoked. This may be a url.
        """
        return self._fileName

    @fileName.setter
    def fileName(self, fileName):
        """
        Assigns the `fileName` to this Workspace instance.
        """
        self._fileName = fileName

    def runOnce(self):
        """
        Requests that the Workspace instance be executed once only until it
        either completes or fails. It is the responsibility of the user to
        re-execute it as required.
        """
        workspace_run_once(byref(self._id))

    def runOnceAndWait(self, timeoutMs=30000):
        """
        Requests that the Workspace instance be executed once only. Will wait 
        until this call succeeds or fails. Note that if the workflow fails to 
        terminate, this function can run indefinitely.
        """
        class WrapperFunc:
            def __init__(self, func):
                self.complete = False 
                self.func = func

            def __call__(self, ws):
                result = False
                if not self.func is None:
                    result = self.func(ws)

                # No mutex is required here as bool assignments are atomic
                # and only one of these can be invoked at any time.
                self.complete = True
                return result

        # Track the status of the workflow through the success / failure funcs.
        self._onSuccessFunc = WrapperFunc(self._onSuccessFunc)
        self._onFailedFunc = WrapperFunc(self._onFailedFunc)
        self.runOnce()
        while (not self._onSuccessFunc.complete and not self._onFailedFunc.complete):
            self.poll()

        # Return
        return self._onSuccessFunc.complete

    def runContinuously(self):
        """
        Requests that the Workspace instance be executed in continuous mode.
        This means that the underlying workflow will run until it complete, or
        fails, and then wait for user input. As soon as an input or globalName
        is updated via the `setInput` or `setGlobalName` methods, the workflow
        will re-execute the affected parts of the workflow.
        """
        workspace_run_continuously(byref(self._id))

    def stop(self):
        """
        Requests that the Workspace instance stop executing (though it does not
        guarantee that it will stop immediately). Once stopped, a Workspace
        instance can resume execution through use of the `runOnce` or
        `runContinously` methods. This is different from the `terminate` method
        which will terminate the entire process.

        __*Note:* This method is asynchronous__
        """
        workspace_stop(byref(self._id))

    def terminate(self):
        """
        Requests that the workspace-web suprocess shut down immediately.
        """
        if not self._process:
            return

        # Calling this will tell the process to terminate itself.
        success = workspace_terminate(byref(self._id))

        # Before we get rid of the process reference, store it in the queue of
        # terminating processes so that we can get kill it if it doesn't
        # promptly terminate itself.
        Workspace._terminating_processes.append((datetime.datetime.now(), self))

    def setInput(self, inputName, content):
        """
        Assigns `content` to the top-level input named `inputName` on the Workspace.
        If the Workspace is currently executing, this will be applied as soon as
        it is safe to do so.

        The `content` parameter must contain the serialized data appropriate to the
        underyling data type of the input. For example, if the input is a double,
        a string representing a floating-point number is required. If the input
        is of a more complex type, such as a DataCollection, then `content`
        must contain the serialized XML that can be read into this datatype.

        __*Note:* This method is asynchronous__
        """
        return workspace_set_input(byref(self._id), bytes(inputName, "ascii"), bytes(str(content), "ascii"))

    def setGlobalName(self, globalName, content):
        """
        Assigns `content` to the input with the attached global name
        `globalName`. If the Workspace is currently executing, this will
        be applied as soon as it is safe to do so.

        The `content` parameter must contain the serialized data appropriate to the
        underyling data type of the input. For example, if the input is a double,
        a string representing a floating-point number is required. If the input
        is of a more complex type, such as a DataCollection, then `content`
        must contain the serialized XML that can be read into this datatype.

        __*Note:* This method is asynchronous__
        """
        return workspace_set_global_name(byref(self._id), bytes(globalName, "ascii"), bytes(str(content), "ascii"))

    def watch(self, callback, watchList, autoDelete=True):
        """
        Sets up a watch on the specified `watchList`, which must be an object
        of the `WatchList` type. When all of the inputs, outputs and
        globalNames in the watch list are brought up-to-date by the running
        workflow, the `callback` function will be triggered, and passed as
        arguments a reference to this `Workspace` object, as well as the `WatchList`
        containing the name, type and value of each watched item.

        __*Note:* This method is asynchronous__
        """
        self._watches[watchList.id] = _WatchCallback(self, watchList.id, callback, autoDelete)
        if workspace_watch(byref(self._id), bytes(str(watchList), "ascii"), self._watchCallback, autoDelete):
            return watchList.id
        return None

    def cancelWatch(self, watchId):
        """
        Cancels a (non-single-shot) watch request, by de-registering the
        existing callback associated with the `watchId`.
        """
        self._removeWatch(watchId)
        workspace_cancel_watch(byref(self._id), bytes(str(watchId), "ascii"))

    def listInputs(self, callback):
        """
        Requests a list of inputs from the running Workspace, and invokes the
        `callback`, passing it itself and a `WatchList` object containing the results.

        __*Note:* This method is asynchronous__
        """
        self._listRequests['inputs'] = callback
        return workspace_list_inputs(byref(self._id), self._listCallbackInputs);

    def listOutputs(self, callback):
        """
        Requests a list of outputs from the running Workspace, and invokes the
        `callback`, passing it itself and a `WatchList` object containing the results.

        __*Note:* This method is asynchronous__
        """
        self._listRequests['outputs'] = callback
        return workspace_list_outputs(byref(self._id), self._listCallbackOutputs);

    def listGlobalNames(self, callback):
        """
        Requests a list of globalnames from the running Workspace and invokes
        the `callback`, passing itself and a `WatchList` object containing the results.

        __*Note:* This method is asynchronous__
        """
        self._listRequests['globalNames'] = callback
        return workspace_list_global_names(byref(self._id), self._listCallbackGlobalNames)

    def getOutputs(self):
        """
        Returns all Workspace outputs. 
        If the workflow is not running, will return immediately with the values already assigned.
        If the workflow is running, it will blocks until the data is ready.
        """
        outputData = None
        def listCallback(ws, outputs):
            nonlocal outputData
            outputData = outputs
            return True

        self.listOutputs(listCallback)
        while outputData is None:
            self.poll()
        return outputData.outputs

    def getInputs(self):
        """
        Returns all Workspace inputs. 
        If the workflow is not running, will return immediately with the values already assigned.
        If the workflow is running, it will blocks until the data is ready.
        """
        inputData = None
        def listCallback(ws, inputs):
            nonlocal inputData
            inputData = inputs
            return True

        self.listInputs(listCallback)
        while inputData is None:
            self.poll()
        return inputData.inputs


    def getGlobalNames(self):
        """
        Returns all Workspace inputs/outputs with global names attached. 
        If the workflow is not running, will return immediately with the values already assigned.
        If the workflow is running, it will blocks until the data is ready.
        """
        gnData = None
        def gnCallback(ws, globalNames):
            nonlocal gnData
            gnData = globalNames 
            return True

        self.listGlobalNames(gnCallback)
        while gnData is None:
            self.poll()
        return gnData.globalNames

    def onSuccess(self, callback):
        """
        Assign a `callback` function to invoke when the workflow successfully
        completes execution. The callback function is passed a reference to this
        Workspace object as an argument.

        __*Note:* This method is asynchronous__
        """
        self._onSuccessFunc = callback

    def onFailed(self, callback):
        """
        Assign a `callback` function to invoke when the workflow fails to
        execute. The callback function is passed a reference to this
        Workspace object as an argument.

        __*Note:* This method is asynchronous__
        """
        self._onFailedFunc = callback

    def onError(self, callback):
        """
        Assign a `callback` function to invoke when an error occurs in the
        workflow. The callback function is provided a reference to this
        Workspace object, and a string containing a description of the specific
        error message, as arguments.

        __*Note:* This method is asynchronous__
        """
        self._onErrorFunc = callback

# Prior to using the module, all our c functions need to be initialised.
_initCInterface()

# Make sure that on quit() or exit() calls, all our subprocesses are shut down.
atexit.register(Workspace._atexit)


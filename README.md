The Workspace Python Package is a lightweight Python module that allows Workspace
workflows to be executed from within Python code. Each Workspace workflow runs
as an independent child process; an instance of the workspace-web executable.
The python module binds to the Workspace C-API which it uses to interact with the
running processes.

## Dependencies
In order to use the Workspace Python package, you'll require:

* Python 3+
* An install of Workspace version 3.3.2 or greater.

## Installation
The easiest way to install the package into your Python environment is
to use [pip](https://pip.pypa.io):

1. Download [pip](https://pip.pypa.io) if your Python environment does not have it already.
2. Run the commands: 
    ```
    pip install csiro_workspace
    ```
    or alternatively,
    ```
    pip install git+https://github.com/csiro-workspace/workspace-python.git
    ```
    This will install the package so that it is editable under csiro_workspace, which will allow you to modify the configuration, which is covered in the next section.

## Building
Developers can build the project using:
```
python3 -m build
```
This relies on the build package being installed via pip, of course.

## Testing
Tests can be run using unittest:
```
python3 -m unittest tests/test_workspace.py
```

## Configuration
To run Workspace workflows, the csiro-workspace Python package needs to
know where the Workspace installation is. When first importing the
module, it will have a guess, but depending on your installation, it may
be incorrect. To fix this, start an interactive Python session and
update the configuration:
```
$ python3
>>> import csiro_workspace
Failed to initialize workspace-web shared library - possible the path in the config is incorrect.
Recommend setting csiro_workspace.config['workspace_install_dir'], then invoking csiro_workspace.save_config()
>>> csiro_workspace.config['workspace_install_dir'] = '/path/to/workspace'
>>> csiro_workspace.save_config()
>>> exit()
```
Under the hood, the csiro-workspace Python package is managing a JSON configuration file
`workspace.cfg` which can be found in your Python installation directory under
`site-packages/csiro_workspace` and looks vaguely like this:
```
{
   // Directory that Workspace is installed to. This example uses the
   // default OSX installation directory.
   "workspace_install_dir": "/usr/local/csiro.au/workspace",

   // The default connection port that the Workspace server will use to
   // connect to running instances. Generally does not need to be
   // changed.
   "connection_port": 58660,

   // If a Workspace process takes more than this amount of time to
   // terminate, it will be killed.
   "terminate_timeout_sec": 10,

   // Use this log level to control how much is written to the
   // console. Useful for debugging individual workflow outputs.
   "log_level": 2
}
```

## Generating the API documentation
For developers that wish to generate updated API documentation, this can
be done by running the following command once the package is installed
and correctly configured:
```
pdoc --html csiro_workspace
```

## Usage
Using the Workspace Python package is straightforward, though
it is useful to be aware that almost all of the functions on a Workspace
instance are asynchronous. [Complete API documentation](https://research.csiro.au/static/workspace/workspace-python-docs/index.html) is available,
and we provide a basic tutorial below.

### Loading a Workspace workflow
Creating a handle to a running Workspace workflow is straightforward:
```python
import csiro_workspace.workspace as workspace

def onConnected(ws):
    # Once this callback is invoked, it will be safe to interact with the workflow.
    print('Connected to workspace %d' % ws.id)
    return True   # Callbacks must return a value.

ws = workspace.Workspace('/path/to/my/workflow.wsx', onConnected)
```

### Executing a workflow
Executing a workflow is done by calling one of the two available
execution methods: `runOnce` or `runContinuously`. As the names of these
functions indicate, `runOnce` will execute the workflow a single time,
while `runContinously` will execute the function until completion, and
then silently wait for inputs or globalNames to be updated, triggering
later updates.
```
ws.runOnce()
```

### Assigning input and global name values
Once a workflow object is created, setting inputs and globalNames can be done with the code:
```python
ws.setInput('An Integer', 5)
ws.setGlobalName('A String', 'It was the best of times, it was blurst of times.')
```
These functions are safe to call at any time; Workspace will queue
requests and process them in the order that they're received, applying
them to the workflow as soon as it is safe to do so.

### Observing results
Workflow results are observed by using callbacks, as this allows us to
interact with our data at a time when the underlying Workspace process
knows it is safe to do so.

Depending on your needs, this can be achieved in two ways. Firstly, if we only want to know
whether the workflow has succeeded or aborted, we can observe the overall workflow state:
```python
def successCallback(ws):
    print('Workflow successfully completed execution.')
    return True   # Callbacks must return a value.

def errorCallback(ws, message):
    print('An error occurred in the workflow: %s' % (message))
    return True

def failedCallback(ws):
    print('Workflow aborted execution.')
    return True

ws.onSuccess(successCallback)
ws.onError(errorCallback)
ws.onFailed(failedCallback)
```
The second, more powerful method requires watching (i.e. monitoring)
specific outputs or globalNames on the workflow. This is done through the use of the `watch`
method and a `WatchList` object. `WatchList` objects are used to
nominate inputs, outputs or globalNames that we wish to monitor for changes. WatchLists
are also provided to the callback function (with each items updated results) when
the specified items are updated. Here's an example:
```python
def watchCallback(ws, watchList):
    # Invoked as soon as all the inputs, outputs and globalNames named
    # in the WatchList are brought up-to-date by Workspace.
    print('WatchList contains: %s' % (watchList))
    return True   # Callbacks must return a value.

ws.watch(callback=watchCallback, watchList=workspace.WatchList.fromIONames(outputs=['OutputResult'], globalNames=['GlobalNameResult'], autoDelete=true)
```
In this example, the `watchCallback` function will be called when both
the _OutputResult_ and _GlobalNameResult_ outputs are both up-to-date on
the workflow.

Note that the `autoDelete` parameter controls whether this watch will
automatically remove itself immediately after it has been triggered. For
continuously running workflows, it may be desirable to use `False` for
this parameter, in which case the watches can be removed later as
follows:
```
ws.cancelWatch(watchList)
```

While the workflow is executing, the static `poll` method is used to check
for results from all workflow instances, which will trigger the watch callbacks as needed.
If you are writing a basic application that does not have an event loop (e.g. you're running from
inside an interpreter, or you are creating a command line application), you can
manually call the `poll` function as follows:
```python
Workspace.poll()
```

Alternatively, if you're using a framework that has an event loop, it's recommended to place a call to
`poll` somewhere in this loop. For example, here is an example event loop in a _Tornado_ web server:
```python
from csiro_workspace.workspace import Workspace

def loopFunc():
    Workspace.poll()

def main():
    app = tornado.web.Application()
    app.listen(_options.port)
    mainLoop = tornado.ioloop.IOLoop.instance()
    poller = tornado.ioloop.PeriodicCallback(loopFunc, _options.pollRate, mainLoop)
    poller.start()
    mainLoop.start()

if __name__ == '__main__':
    main()
```
Or instead, you can start the built-in event loop by using the static methods
`startEventLoop` and `stopEventLoop` as follows:
```python
def eventLoopStarted():
    self.started = True
    self.assertTrue(self.started)
    watchListIn = workspace.WatchList.fromIONames(outputs=['Result'])
    self.ws.watch(callback=watchCallback, watchList=watchListIn, autoDelete=False)
    self.ws.setInput('Value1', 1)
    self.ws.setInput('Value2', 1)
    self.ws.runContinuously()
    return True

workspace.Workspace.startEventLoop(eventLoopStarted)
```


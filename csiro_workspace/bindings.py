"""
This module contains all bindings to the Workspace framework's API. 
It is not designed to be used directly, rather it should be used through
the workspace.py module.

--

Copyright 2025 by:

Commonwealth Scientific and Industrial Research Organisation (CSIRO)

This file is licensed by CSIRO under the copy of the CSIRO Open Source Software
License Agreement included with the file when downloaded or obtained
from CSIRO (including any Supplementary License). If no copy was
included, you must obtain a new copy of the Software from CSIRO before
any use is permitted.

For further information, contact: workspace@csiro.au

This copyright notice must be included with all copies of the source code.
"""

from ctypes import cdll, byref, c_char, c_char_p, c_int, Structure, pointer, POINTER, CFUNCTYPE
import platform
import ctypes
from .config import config

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


# Function types for our C++ code to call back into
LOOPSTARTFUNC = CFUNCTYPE(c_int)
CONNFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
SUCCESSFUNC   = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
FAILFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID))
ERRORFUNC     = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)
WATCHFUNC     = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)
LISTFUNC      = CFUNCTYPE(c_int, POINTER(_WORKSPACE_ID), c_char_p)


# Attempt to initialize our C++ function references
LibWorkspaceWeb = None
try:
    if platform.system() == 'Windows':
        LibWorkspaceWeb = ctypes.WinDLL(config['workspace_install_dir'] + '/lib/workspaceweb.dll', winmode = 0x8)
    elif platform.system() == 'Linux':
        LibWorkspaceWeb = cdll.LoadLibrary(config['workspace_install_dir'] + '/lib/libworkspaceweb.so')
    else:
        LibWorkspaceWeb = cdll.LoadLibrary(config['workspace_install_dir'] + '/lib/libworkspaceweb.dylib')

    # Prior to using the module, all our c functions need to be initialised.
    # I'd like to put them in a function, but I don't want to have to forward declare them.
    server_init = LibWorkspaceWeb.server_init
    server_init.restype = c_int
    server_init.argtypes = [c_int]

    server_listen_for_connection_and_wait = LibWorkspaceWeb.server_listen_for_connection_and_wait
    server_listen_for_connection_and_wait.restype = c_int
    server_listen_for_connection_and_wait.argtypes = [c_char_p, c_int, CONNFUNC]

    server_start_event_loop = LibWorkspaceWeb.server_start_event_loop
    server_start_event_loop.restype = c_int
    server_start_event_loop.argtypes = [LOOPSTARTFUNC]

    server_stop_event_loop = LibWorkspaceWeb.server_stop_event_loop
    server_stop_event_loop.restype = c_int

    workspace_register_func_success = LibWorkspaceWeb.workspace_register_func_success
    workspace_register_func_success.restype = c_int
    workspace_register_func_success.argtypes = [POINTER(_WORKSPACE_ID), SUCCESSFUNC]

    workspace_register_func_failed = LibWorkspaceWeb.workspace_register_func_failed
    workspace_register_func_failed.restype = c_int
    workspace_register_func_failed.argtypes = [POINTER(_WORKSPACE_ID), FAILFUNC]

    workspace_register_func_error = LibWorkspaceWeb.workspace_register_func_error
    workspace_register_func_error.restype = c_int
    workspace_register_func_error.argtypes = [POINTER(_WORKSPACE_ID), ERRORFUNC]

    server_poll = LibWorkspaceWeb.server_poll
    server_poll.restype = c_int
    server_poll.argtypes = [c_int]

    workspace_run_once = LibWorkspaceWeb.workspace_run_once
    workspace_run_once.restype = c_int
    workspace_run_once.argtypes = [POINTER(_WORKSPACE_ID)]

    workspace_run_continuously = LibWorkspaceWeb.workspace_run_continuously
    workspace_run_continuously.restype = c_int
    workspace_run_continuously.argtypes = [POINTER(_WORKSPACE_ID)]

    workspace_terminate = LibWorkspaceWeb.workspace_terminate
    workspace_terminate.restype = c_int
    workspace_terminate.argtypes = [POINTER(_WORKSPACE_ID)]

    workspace_set_input = LibWorkspaceWeb.workspace_set_input
    workspace_set_input.restype = c_int
    workspace_set_input.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, c_char_p]

    workspace_set_global_name = LibWorkspaceWeb.workspace_set_global_name
    workspace_set_global_name.restype = c_int
    workspace_set_global_name.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, c_char_p]

    workspace_list_inputs = LibWorkspaceWeb.workspace_list_inputs
    workspace_list_inputs.restype = c_int
    workspace_list_inputs.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]
    
    workspace_list_outputs = LibWorkspaceWeb.workspace_list_outputs
    workspace_list_outputs.restype = c_int
    workspace_list_outputs.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]

    workspace_list_global_names = LibWorkspaceWeb.workspace_list_global_names
    workspace_list_global_names.restype = c_int
    workspace_list_global_names.argtypes = [POINTER(_WORKSPACE_ID), LISTFUNC]

    workspace_watch = LibWorkspaceWeb.workspace_watch
    workspace_watch.restype = c_int
    workspace_watch.argtypes = [POINTER(_WORKSPACE_ID), c_char_p, WATCHFUNC]

    workspace_cancel_watch = LibWorkspaceWeb.workspace_cancel_watch
    workspace_cancel_watch.restype = c_int
    workspace_cancel_watch.argtypes = [POINTER(_WORKSPACE_ID), c_char_p]

    workspace_stop = LibWorkspaceWeb.workspace_stop
    workspace_stop.restype = c_int
    workspace_stop.argtypes = [POINTER(_WORKSPACE_ID)]

    # Initialise the server
    server_init(config['log_level'])

except OSError as e:
    print(f"Failed to initialize workspace-web shared library - possible the path in the config is incorrect. Message follows:\n{e}")
    print(f"Recommend setting csiro_workspace.config['workspace_install_dir'], then invoking csiro_workspace.save_config()")



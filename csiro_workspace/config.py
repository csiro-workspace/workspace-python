"""
This module contains all code related to loading the configuration.

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

import os
import json

_config_file_path = os.path.dirname(__file__) + '/workspace.cfg'

# Default config dict
_default_config = {
    "workspace_install_dir": "/Path/To/Workspace/Install/Dir",
    "connection_port": 58660,
    "terminate_timeout_sec": 10,
    "runonce_timeout_sec": 10,
    "log_level": 6
}
config = _default_config

def saveConfig():
    """
    Writes the Workspace config to disk, using the values stored in
    the config variable. Allows the caller to modify the config using
    an interactive Python session rather than having to find the file
    on Disk.
    """
    _config_file = open(_config_file_path, 'w')
    _config_file.write(json.dumps(config, sort_keys=True, indent=4))


try:
    # Load our Workspace config file
    _config_file = open(_config_file_path, 'r')
    config = json.load(_config_file)

except FileNotFoundError as e:
    # File doesn't exist, create it and populate it with a basic structure
    print(f"Configuration file {_config_file_path} does not exist. Creating file with default values.")
    _config_file = open(_config_file_path, 'x')
    _config_file.write(json.dumps(_default_config, sort_keys=True, indent=4))

except json.decoder.JSONDecodeError as e:
    print(f"Configuration file {_config_file_path} contains invalid JSON. Details follow:\n{e.msg}")

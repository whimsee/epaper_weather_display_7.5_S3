
import json
import microcontroller
import supervisor

from ⚙️ import *

# safemode.py is the entry point for SAFE MODE (hard fault, etc.)
# store supervisor.runtime.safe_mode_reason since it won't be available during boot.py or code.py

# NVM Safe Mode - to cross-check against safemode reason
if microcontroller.nvm[NVM_INDEX_SAFEMODE] != SAFEMODESET:
    microcontroller.nvm[NVM_INDEX_SAFEMODE] = SAFEMODESET

# set up the safemode dict
safemode_dict = {}
safemode_dict["safemode_reason"] = str(supervisor.runtime.safe_mode_reason)
update_restart_dict_time(safemode_dict)  # add timestamp

# write dict as JSON
precode_file_write("/safemode.json", json.dumps(safemode_dict))  # use storage.remount()

if False:  # check for any safemode conditions where we shouldn't RESET
    pass
else:
    # RESET out of safe mode
    microcontroller.reset()  # or alarm.exit_and_deep_sleep()
    
    
/////
import storage

# safemode.py & boot.py file write
def precode_file_write(file, data):
    storage.remount("/", False)  # writeable by CircuitPython
    with open(file, "w") as fp:
        fp.write(f"{data}\n")
        fp.flush()
    storage.remount("/", True)   # writeable by USB host
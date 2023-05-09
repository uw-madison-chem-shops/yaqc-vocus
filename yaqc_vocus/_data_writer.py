import time
import pathlib
import os

import numpy as np
import tidy_headers
import yaqc

from ._timestamp import TimeStamp


class DataWriter(object):
    def __init__(self, main_window):
        self._main_window = main_window
        self._mfc1 = yaqc.Client(38001)
        self._mfc2 = yaqc.Client(38002)
        self._mfc3 = yaqc.Client(38003)

    def create_file(self, start_time: int):
        filename = TimeStamp(at=start_time).path + " mfc.txt"
        self.filepath = pathlib.Path(os.path.expanduser("~")) / "mfc-data" / filename
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.touch()
        headers = {}
        headers["timestamp"] = TimeStamp(at=start_time).RFC3339
        headers["columns"] = ["timestamp",
                              "mfc1_flow",
                              "mfc1_voltage",
                              "mfc2_flow",
                              "mfc2_voltage",
                              "mfc3_flow",
                              "mfc3_voltage",
                              ]
        tidy_headers.write(self.filepath, headers)

    def write(self):
        arr = np.empty(7)
        arr[0] = time.time()
        arr[1] = self._mfc1.get_position() 
        arr[2] = self._mfc1.get_native_position()
        arr[3] = self._mfc2.get_position()
        arr[4] = self._mfc2.get_native_position()
        arr[5] = self._mfc3.get_position()
        arr[6] = self._mfc3.get_native_position()
        with open(self.filepath, "a") as f:
            np.savetxt(f, arr.T, delimiter="\t", newline="\t", fmt="%.6f")
            f.write("\n")

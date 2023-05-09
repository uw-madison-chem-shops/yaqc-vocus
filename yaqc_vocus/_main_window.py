#! /usr/bin/env python

import sys
import os
import pathlib
import time
from dataclasses import dataclass
import functools
from collections import deque

import numpy as np
from qtpy import QtWidgets, QtCore
import appdirs
import toml
import yaqc
import qtypes
import tidy_headers
import yaqc_qtpy
from yaqc_qtpy import property_items

from .__version__ import __version__
from ._data_writer import DataWriter
from ._plot import Plot1D


__here__ = pathlib.Path(os.path.abspath(__file__)).parent


class MainWindow(QtWidgets.QMainWindow):
    shutdown = QtCore.Signal()

    def __init__(self, config):
        super().__init__(parent=None)
        self.setWindowTitle("yaqc-wiqk")
        self._mfc_clients = [yaqc_qtpy.QClient(port=port, host="localhost") for port in (38001, 38002, 38003)]
        self._create_main_frame()
        self._data_writer = DataWriter(self)
        self._poll_timer = QtCore.QTimer(interval=1000)  # one second
        self._poll_timer.timeout.connect(self._poll)
        self._plot_timer = QtCore.QTimer(interval=1000)  # one second
        self._plot_timer.timeout.connect(self._plot)
        self._plot_timer.start()
        # buffers
        self._timestamp_buffers = [deque(maxlen=300) for _ in range(len(self._mfc_clients))]
        self._position_buffers = [deque(maxlen=300) for _ in range(len(self._mfc_clients))]
        for timestamp_buffer, position_buffer, client in zip(self._timestamp_buffers, self._position_buffers, self._mfc_clients):

            def fill(result, *, timestamp_buffer, position_buffer):
                timestamp_buffer.append(time.time())
                position_buffer.append(result)

            client.properties["position"].updated.connect(functools.partial(fill,
                                                                            timestamp_buffer=timestamp_buffer,
                                                                            position_buffer=position_buffer))

    def _create_main_frame(self):
        splitter = QtWidgets.QSplitter()

        # tree
        root = qtypes.Null()
        root.append(qtypes.Null("MFC setpoints"))
        for index, client in enumerate(self._mfc_clients):
            header = qtypes.Null(f"mfc{index+1}")
            destination = property_items.Float("destination",
                                               client.properties["destination"],
                                               client)
            header.append(destination)
            position = property_items.Float("position",
                                            client.properties["position"],
                                            client)
            header.append(position)
            root[0].append(header)
        root.append(qtypes.Null("data recording"))
        self._time_elapsed_widget = qtypes.String(label="time elapsed")
        root[1].append(self._time_elapsed_widget)
        self._filepath_widget = qtypes.String(label="filepath")
        root[1].append(self._filepath_widget)
        self._take_data_button = qtypes.Button("take data")
        root[1].append(self._take_data_button)
        self._take_data_button.set(value={"text": "go"})
        self._take_data_button.updated_connect(self._on_take_data)
        self._tree_widget = qtypes.TreeWidget(root)
        splitter.addWidget(self._tree_widget)

        # plot widgets
        self._plot_widgets = [Plot1D() for _ in range(len(self._mfc_clients))]
        self._scatters = [pw.add_scatter() for pw in self._plot_widgets]
        self._lines = [pw.add_infinite_line(angle=0, hide=False) for pw in self._plot_widgets]
        container = QtWidgets.QSplitter()
        container.setOrientation(QtCore.Qt.Vertical)
        for widget in self._plot_widgets:
            container.addWidget(widget)
        splitter.addWidget(container)

        # update plot limits
        for pw, client in zip(self._plot_widgets, self._mfc_clients):

            def update_limits(result, *, pw):
                pw.set_xlim(-3, 0)
                pw.set_ylim(*result)

            client.get_limits.finished.connect(functools.partial(update_limits, pw=pw))
            client.get_limits()

        # update destination indicator lines
        for line, client in zip(self._lines, self._mfc_clients):

            def update_destination(result, *, line):
                line.setValue(result)

            client.get_destination.finished.connect(functools.partial(update_destination, line=line))
            # get_destination will be called by yaqc_qtpy internally
            # because it is a property

        # finish
        self.setCentralWidget(splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self._tree_widget.expandAll()
        self._tree_widget.resizeColumnToContents(0)
        self._tree_widget.resizeColumnToContents(1)

    def _on_take_data(self, data):
        print("on take data", data)
        self._take_data_button.updated_disconnect(self._on_take_data)
        if data["text"] == "stop":
            self._take_data_button.set(value={"text": "go"})
            self._poll_timer.stop()
        else:
            self._take_data_button.set(value={"text": "stop"})
            self._poll_timer.start()
            self._last_procedure_started = time.time()
            self._data_writer.create_file(start_time=self._last_procedure_started)
            self._filepath_widget.set({"value": str(self._data_writer.filepath)})
        self._take_data_button.updated_connect(self._on_take_data)

    def _plot(self):
        # scatter data
        for timestamp_buffer, position_buffer, scatter in zip(self._timestamp_buffers, self._position_buffers, self._scatters):
            scatter.setData((np.array(timestamp_buffer) - time.time())/60, position_buffer)

    def _poll(self):
        print("poll")
        minutes, seconds = divmod(time.time() - self._last_procedure_started, 60)
        minutes = str(round(minutes)).zfill(2)
        seconds = str(round(seconds)).zfill(2)
        self._time_elapsed_widget.set_value(f"{minutes}:{seconds}")
        self._data_writer.write()

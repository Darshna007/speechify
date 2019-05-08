#!/usr/bin/env python
# -*- charset utf8 -*-

# from https://gist.github.com/netom/8221b3588158021704d5891a4f9c0edd

import pyaudio
import numpy
import math
import matplotlib.pyplot as plt
import matplotlib.animation
import scipy as sp
import scipy.signal

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

app = QtGui.QApplication([])
win = pg.GraphicsWindow()
win.setWindowTitle("microphone")
view = win.addViewBox()

view.setAspectLocked(True)

RATE = 44100
BUFFER = 2048
WIDTH = 129
HEIGHT = 600
SCALE = 4

win.resize(WIDTH * SCALE, HEIGHT)

image = numpy.zeros((WIDTH * SCALE, HEIGHT), dtype=numpy.int8)
img = pg.ImageItem(image)
view.addItem(img)
view.setRange(QtCore.QRectF(0, 0, WIDTH * SCALE, HEIGHT))
img.setLevels([0, 1])

def shift(a):
    image[:, :-1] = image[:, 1:]
    image[:, -1] = numpy.repeat(a[:WIDTH], SCALE)
    img.setImage(image)

p = pyaudio.PyAudio()

stream = p.open(
    format = pyaudio.paFloat32,
    channels = 1,
    rate = RATE,
    input = True,
    output = False,
    frames_per_buffer = BUFFER
)

def update_line():
    try:
        freq, pow = sp.signal.welch(
            numpy.frombuffer(stream.read(BUFFER), dtype=numpy.float32),
            44100,
            scaling='spectrum'
        )
    except IOError:
        pass
    pow *= 255 / numpy.max(pow)
    shift(pow)
    print(pow[:10])
    
def loop():
    update_line()

timer = QtCore.QTimer()
timer.timeout.connect(loop)
timer.start(10)

QtGui.QApplication.instance().exec_() # whee
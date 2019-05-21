from util.spectrogram_generator import whole_buffer
from util.data import LibriSpeech
import soundfile as sf
from os.path import join
import matplotlib.pyplot as p
import config
import numpy

class Sampler:
    def __init__(self, home=False):
        self.path = config.path
        self.ls = LibriSpeech()
        self.ls.load()
        self.wb = whole_buffer()
        self.wb.params.spectrum_range = config.librispeech_range
    
    def rand(self):
        file = self.ls.uniform_random()
        path = join(self.path, file['path'])
        buf, _ = sf.read(path)
        return file, self.wb.all(buf)
    
    def whatev(self):
        pass

def imshow(buf):
    # rar
    # rar
    import matplotlib
    import matplotlib.pyplot as p
    p.imshow(buf, norm=matplotlib.colors.Normalize(0, 255))
    p.show()

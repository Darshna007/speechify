import tensorflow as tf
import numpy
from util.data import LibriSpeech
from util.spectrogram_generator import whole_buffer
from nets.model import EncoderDecoder
import soundfile as sf
from os.path import join
import util.onehot as onehot
import config

WIDTH = 80
ENDPAD = 1
BUFPAD = 16
THICKNESS = 9

class bufmixer:
    z = numpy.linspace(0, 1, WIDTH)
    bufmixer0 = numpy.maximum(2*z - 1, 0)[:, None]
    bufmixer1 = 1 - numpy.abs(2*z - 1)[:, None]
    bufmixer2 = numpy.maximum(1 - 2*z, 0)[:, None]
    
    @staticmethod
    def mixer(buf):
        return numpy.concatenate([buf * bufmixer.bufmixer0,
                                  buf * bufmixer.bufmixer1,
                                  buf * bufmixer.bufmixer2], axis=2)


def _create(get, start, end):
    bufs = []
    transs = []
    longest_buf = 0
    longest_trans = 0
    for i in range(0, end - start):
        trans, buf = get(start + i)
        trans = trans[:16]
        buf = buf[:64, :]
        assert buf.shape[1:] == (WIDTH, 3)
        longest_buf = max(longest_buf, buf.shape[0])
        longest_trans = max(longest_trans, len(trans))
        bufs.append(buf)
        transs.append(trans)
    longest_buf = ((longest_buf + BUFPAD - 1) // BUFPAD) * BUFPAD
    bufmatrix = numpy.zeros((len(bufs), longest_buf, WIDTH, 9))
    for i, buf in enumerate(bufs):
        bufmatrix[i, :buf.shape[0], :, :] = bufmixer.mixer(buf)
    longest_trans += 1 + ENDPAD
    transmatrix = numpy.zeros((len(transs), longest_trans, onehot.nchars))
    transoffset = numpy.zeros((len(transs), longest_trans, onehot.nchars))
    #transoffset = numpy.zeros_like(transmatrix)
    for i, trans in enumerate(transs):
        trans = "@" + trans + "$" * (longest_trans - len(trans) - 1)
        for j, c in enumerate(trans):
            transmatrix[i, j, onehot.idx[c]] = 1
    transoffset[:, :-1, :] = transmatrix[:, 1:, :]
    transoffset[:, -1, onehot.idx["$"]] = 1
    return (bufmatrix, transmatrix), transoffset

class SequenceFromLibriSpeech(tf.keras.utils.Sequence):
    def __init__(self, dat, batchsize, get):
        self.data = dat
        self.batchsize = batchsize
        #self.wb = wholebuffer
        self.get = get
    
    def __len__(self):
        return (len(self.data) + self.batchsize - 1) // self.batchsize

    def __getitem__(self, idx):
        start = idx * self.batchsize
        end = min((idx + 1) * self.batchsize, len(self.data))
        #print("returning batch %d %d" % (start, end))
        retval = _create(self.get, start, end)
        return retval
        
class LibriSequence:
    def __init__(self):
        self.path = config.path
        self.specpath = config.specpath
        self.ls = LibriSpeech()
        self.ls.load()
        self.batchsize = 128
    
    def sequence(self, type="train"):
        array = self.ls.info[type][::-1]
        def get(ix):
            reader,book,i = array[ix]
            file = self.ls.data[reader][book][i]
            buf, _ = sf.read(join(self.path, file['path']))
            trans = file['trans']
            wb = whole_buffer()
            wb.params.spectrum_range = config.librispeech_range
            return trans, wb.all(buf)
        def get2(ix):
            reader,book,i = array[ix]
            file = self.ls.data[reader][book][i]
            path = file['path']
            if path.endswith(".flac"):
                path = path[:-5] + ".npy"
            buf = numpy.load(join(self.specpath, path)).astype(numpy.float32)/4096
            return file['trans'], buf
        return SequenceFromLibriSpeech(array, self.batchsize, get2)

"""
class FancySampler:
    ENDPAD = 6
    
    def __init__(self):
        self.path = config.path
        self.ls = LibriSpeech()
        self.ls.load()
        self.wb = whole_buffer()
        self.wb.params.spectrum_range = config.librispeech_range
        self.batchsize = 32
    
    def get(self, type="train"):
        if type == "train":
            file = self.ls.uniform_train()
        else:
            file = self.ls.uniform_test()
        buf, _ = sf.read(join(self.path, file['path']))
        trans = file['trans']
        return trans, self.wb.all(buf)
    
    def generate(self, type="train"):
        z = numpy.linspace(0, 1, 160)
        bufmixer0 = numpy.maximum(2*z - 1, 0)
        bufmixer1 = 1 - numpy.abs(2*z - 1)
        bufmixer2 = numpy.maximum(1 - 2*z, 0)
        while True:
            bufs = []
            transs = []
            longest_buf = 0
            longest_trans = 0
            for i in range(self.batchsize):
                trans, buf = self.get(type)
                assert buf.shape[1:] == (160, 3)
                longest_buf = max(longest_buf, buf.shape[0])
                longest_trans = max(longest_trans, len(trans))
                bufs.append(buf)
                transs.append(trans)
            bufmatrix = numpy.zeros((len(bufs), longest_buf, 160, 9))
            for i, buf in enumerate(bufs):
                bufmatrix[i, :buf.shape[0], :, :3] = buf * bufmixer0[:, None]
                bufmatrix[i, :buf.shape[0], :, 3:6] = buf * bufmixer1[:, None]
                bufmatrix[i, :buf.shape[0], :, 6:9] = buf * bufmixer2[:, None]
            longest_trans += 1 + FancySampler.ENDPAD
            transmatrix = numpy.zeros((len(transs), longest_trans, onehot.nchars))
            for i, trans in enumerate(transs):
                trans = "@" + trans + "$" * (longest_trans - len(trans) - 1)
                for j, c in enumerate(trans):
                    transmatrix[i, j, onehot.idx[c]] = 1
            print("yielding")
            yield bufmatrix, transmatrix
"""

def lrsche(epoch):
    rate = 4
    until = 9
    if epoch <= until:
        return 0.001 + (0.01 - 0.001) * epoch / until
        #return 0.001 + (0.01 - 0.001) * (epoch - 1) / (until - 1)
        # start at 0????
    else:
        return 0.01 * 0.5**((epoch - until) / rate)

def train(save="", epoch = 0):
    encdec = EncoderDecoder()
    spectrum = tf.keras.layers.Input((None, WIDTH, THICKNESS))
    transcript = tf.keras.layers.Input((None, len(onehot.chars)))
    decode = encdec(spectrum, transcript)
    #run_options = tf.RunOptions(trace_level = tf.RunOptions.FULL_TRACE)
    #run_metadata = tf.RunMetadata()
    model = tf.keras.models.Model([spectrum, transcript], decode)
    model.compile(optimizer=tf.keras.optimizers.SGD(lr=0.001, momentum=0.9, decay=0, nesterov=True),
                  loss = 'categorical_crossentropy',
                  metrics = ['accuracy']#,
                  #options = run_options,
                  #run_metadata = run_metadata
                  )
    samp = LibriSequence()
    checkp = tf.keras.callbacks.ModelCheckpoint(
            filepath = "checkpoints/weights.{epoch:04d}-{val_loss:.2f}.hdf5",
            save_weights_only = True
    )
    if save != "":
        model.load_weights(save)
    l = tf.keras.callbacks.LearningRateScheduler(lrsche, verbose=1)
    #tb = tf.keras.callbacks.TensorBoard("../speechify_log", 1, batch_size=8,
            #update_freq=20000)
    model.fit_generator(
        samp.sequence("train"),
        epochs = 10,
        verbose = 1,
        validation_data = samp.sequence("test"),
        workers = 4, shuffle=False, callbacks=[checkp, l], initial_epoch = epoch
    )

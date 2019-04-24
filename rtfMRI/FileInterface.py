import os
from rtfMRI.fileWatcher import FileWatcher
from rtfMRI.utils import findNewestFile


class FileInterface:
    def __init__(self, local=True):
        self.fileWatcher = FileWatcher()

    def getFile(self, filename):
        with open(filename, 'rb') as fp:
            data = fp.read()
        return data

    def getNewestFile(self, filePattern):
        baseDir, filePattern = os.path.split(filePattern)
        if not os.path.isabs(baseDir):
            # TODO - handle relative paths
            pass
        filename = findNewestFile(baseDir, filePattern)
        if filename is None:
            # No file matching pattern
            raise FileNotFoundError('No file found matching pattern {}'.format(filePattern))
        elif not os.path.exists(filename):
            raise FileNotFoundError('File missing after match {}'.format(filePattern))
        else:
            with open(filename, 'rb') as fp:
                data = fp.read()
            return data

    def putTextFile(self, filename, text):
        outputDir = os.path.dirname(filename)
        if not os.path.exists(outputDir):
            os.makedirs(outputDir)
        with open(filename, 'w+') as textFile:
            textFile.write(text)

    def initWatch(self, dir, filePattern, minFileSize, demoStep=0):
        self.fileWatcher.initFileNotifier(dir, filePattern, minFileSize, demoStep)
        return

    def watchFile(self, filename, timeout):
        retVal = self.fileWatcher.waitForFile(filename, timeout=timeout)
        if retVal is None:
            raise FileNotFoundError("WatchFile: Timeout {}s: {}".format(timeout, filename))
        else:
            with open(filename, 'rb') as fp:
                data = fp.read()
            return data

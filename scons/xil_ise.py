## Library for ISE-related python functions

import xml.etree.ElementTree
from xml.etree.ElementTree import parse


class XiseMissingFilesError (ValueError):
    pass


def get_project_files(filename, filetype=None, minfiles=0):

    """Parse Xilinx .xise file and extract source files having type
    <filetype>.  No path normalization is done here."""
    
    tree = parse(filename)    
    root = tree.getroot()
    files = root.find('{http://www.xilinx.com/XMLSchema}files')


    # Find chipscope files
    if filetype is None:
        matchFun = lambda ft: True
    else:
        matchFun = lambda ft: (ft == filetype)
        
    matchingFiles = [f.get('{http://www.xilinx.com/XMLSchema}name')
                     for f in files.findall('{http://www.xilinx.com/XMLSchema}file')
                     if matchFun(f.attrib['{http://www.xilinx.com/XMLSchema}type'])]

    if len(matchingFiles) < minfiles:
        msg = "Required at least {0:d} files of type {1}, found only {2:d}: {3} ".format(minfiles, filetype, len(matchingFiles), matchingFiles)
        raise XiseMissingFilesError(msg)

    return matchingFiles

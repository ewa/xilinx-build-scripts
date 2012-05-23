"""scan_ise: Scanners for dependencies in various ISE files
"""

import re
import string

import SCons.Scanner

def XiseScannerManual():
    """Return a prototype Scanner instance for scanning XISE project files"""
    xises = Xise(use_suffixes=False)
    return xises

class Xise(SCons.Scanner.Classic):
    def __init__ (self, use_suffixes=True):
        suffixes = {True:'$XISESUFFIXES',
                    False:[]}
        SCons.Scanner.Classic.__init__ (
            self,
            name = "XiseScanner",
            suffixes = suffixes,
            path_variable = 'ISEPATH',
            regex = '<file\s+xil_pn:name="([a-zA-Z0-9_./]+)"\s+xil_pn:type="FILE_COREGENISE">'
            '(?:\s+<association xil_pn:name="(?!Implementation)"[^.>]*/>)*'
            '\s+(?:\s+<association xil_pn:name="Implementation"[^.>]*/>)'
            '(?:\s+<association xil_pn:name="(?!Implementation)"[^.>]*/>)*'
            '\s+</file>')


def XcoScanner():
    return Xco()

class Xco(SCons.Scanner.Classic):
    def __init__ (self):
        SCons.Scanner.Classic.__init__ (
            self,
            name = "XcoScanner",
            suffixes = ['.xco'],
            path_variable = 'ISEPATH',
            regex = 'CSET\s+coe_file\s*=\s*([a-zA-Z0-9./_]+)')
    
    # def scan(self, node, path=()):
    #     print "Scanning %s, path =%s" % (str(node), str(path))
    #     return SCons.Scanner.Classic.scan (self, node, path)

    # def find_include_names(self, node):
    #     print "find_include_names on %s" % (str(node))
    #     foo = SCons.Scanner.Classic.find_include_names (self, node)
    #     print foo
    #     return foo

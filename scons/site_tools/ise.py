"""SCons.Tool.ise

Tool-specific initialization for Xilinx ISE

"""

import sys
import platform
import xilinx
import SCons.Util
from SCons.Script import *


def xilinx_defaults(env):
    "XXX this is totally-specifc to my site!"
    plat= ARGUMENTS.get('ARCH',platform.architecture()[0])
    

def generate(env):
    print "Yee-haw %s!"%env.Detect(['ise'])
    return

    
def exists(env):
    return env.Detect(['ise'])


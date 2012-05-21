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
    ise_exists = env.Detect(['ise'])
    if ise_exists is not None:
        print "Found ISE in tool generate phase"
    else:
        print "Could not find ISE in tool generate phase"
        return

        
    preconf_xst=Builder(action=xilinx.build_xst)
    env.Append(BUILDERS={'Preconf_xst' : preconf_xst})

    preconf_prj=Builder(action=xilinx.build_prj,
                      emitter=xilinx.generate_deps_all_cgise)
    env.Append(BUILDERS={'Preconf_prj' : preconf_prj})

    xst = Builder(generator=xilinx.generate_xst,
                  emitter=xilinx.source_files_from_xise,
                  chdir=True, suffix=".ngc", src_suffix=".xst")
    env.Append(BUILDERS={'Xst' : xst}) 


    coregen = Builder(generator=xilinx.generate_coregen,
                      suffix='.xise',
                      src_suffix='.xco')
    env.Append(BUILDERS={'Coregen' : coregen})


def exists(env):
    ise_exists = env.Detect(['ise'])
    return ise_exists


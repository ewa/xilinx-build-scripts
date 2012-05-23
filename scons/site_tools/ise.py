"""SCons.Tool.ise

Tool-specific initialization for Xilinx ISE

"""

import sys
import platform
import xilinx
import scan_ise
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

    # Set some reasonable variables
    env.Append(XISESUFFIXES=['.xise'])

    ##
    ## Make some buiders
    ##

    preconf_xst=Builder(action=xilinx.build_xst)    
    env.Append(BUILDERS={'Preconf_xst' : preconf_xst})

    ## Forcibly scan for dependencies because any file mentioned in
    ## the COREGEN .xise files is also part of the project, so those
    ## need to be up-to-date
    preconf_prj=Builder(action=xilinx.build_prj,
                        source_scanner=scan_ise.XiseScannerManual())
    env.Append(BUILDERS={'Preconf_prj' : preconf_prj})

    xst = Builder(generator=xilinx.generate_xst,
                  emitter=xilinx.source_files_from_xise,
                  chdir=True, suffix=".ngc", src_suffix=".xst")
    env.Append(BUILDERS={'Xst' : xst}) 


    coregen = Builder(generator=xilinx.generate_coregen,
                      suffix='.xise',
                      src_suffix='.xco')
    env.Append(BUILDERS={'Coregen' : coregen})

    # Make some scanners
    env.Append(SCANNERS=scan_ise.XiseScannerManual())
    env.Append(SCANNERS=scan_ise.XcoScanner())
    
    


def exists(env):
    ise_exists = env.Detect(['ise'])
    return ise_exists


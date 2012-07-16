"""SCons.Tool.ise

Tool-specific initialization for Xilinx ISE

"""

import sys
import platform
import xilinx
import xparseprops
import scan_ise
import SCons.Util
import pprint
from SCons.Script import *


def chain_emitters(emitter_list):
    """ Returns an emitter function (closure) which applies every emitter in emitter_list"""
    def multi_emit(target, source, env):
        t=target
        s=source
        for e in emitter_list:
            (t, s) = e(t,s,env)
        return (t, s)
    return multi_emit

def xilinx_defaults(env):
    "XXX this is totally-specifc to my site!"
    plat= ARGUMENTS.get('ARCH',platform.architecture()[0])

def depend_on_proj_props(target, source, env):
    """ Emitter which adds a dependency for the project properties file """
    #sys.stderr.write("depend_on_proj_props called\n")
    #sys.stderr.flush()

    return (target, source + [env['XISE_PY_PROPFILE']])

def depend_on_proj_file(target, source, env):
    """ Emitter which adds a dependency for the project (.xise) file"""
    return (target, source + [env.subst("$PROJECTFILE")])


def announce(words):
    def doit(target, source, env):
        sys.stderr.write("%s\n"%(words))
        return
    return  doit

def use_proplist_scanner(node, env, path, arg=None):
    #sys.stderr.write("Calling proplist_scanner for %s\n" %(str(node)))
    #sys.stderr.write("arg: %s\n" % (str(arg)))
    try:
        pp = env['PROJFILE_PROPS']
        #sys.stderr.write("PROJFILE_PROPS= %s \n" % (str(pp)))
    except KeyError, e:
        sys.stderr.write("...PROJFILE_PROPS not set (yet).  Must revisit!\n")
        return []
    if arg is None:
        sys.stderr.write("use_proplist_scanner needs an arg!\n")
        Exit(1)
    elif arg == 'XST':
        files=xilinx.expand_node_any((0, 'ROOT_XISE', env.subst('$PROJECTFILE')), '..') # How do we know that ".." is the root?  Just made it up!
        #pprint.pprint(files)
        return files
    elif arg == 'coregen':
        return [] #I don't think we need to do anything smarter here -- this was just to get
    elif arg == 'ngdbuild':
        return [] #I don't think we need to do anything smarter here -- this was just to get
    else:
        raise ValueError("use_proplist_scanner doesn't understand arg '%s'"%(repr(arg)))
    
def gimme_edif(target, source, env):
    edifs = []
    for s in source:
        parts = str(s).rpartition('.ngc')
        if parts[0] != '' and parts[1] != '' and parts[2] == '':
            #string endswith '.ngc'
            edifs.append(parts[0]+'.ndf')
    return (target, source + edifs)

def generate(env):
    ise_exists = env.Detect(['ise'])
    if ise_exists is not None:
        print "Found ISE in tool generate phase"
    else:
        print "Could not find ISE in tool generate phase"
        return

    get_props = Builder(action='xtclsh $XBUILDSCRIPTS/xprop_extract.tcl $SOURCE $TARGET > /dev/null 2>&1',
                        suffix='.prop_list',
                        src_suffix='.xise')
    env.Append(BUILDERS={'GetProps': get_props})

    foo = Builder(action=interp_props,
                  suffix=".step1",
                  src_suffix=".prop_list")
    env.Append(BUILDERS={'Foo' : foo})
    
    bar = Builder(action="cp $SOURCE $TARGET",
                  src_builder=foo,
                  src_suffix=".step1",
                  suffix=".step2")
    env.Append(BUILDERS={'Bar' : bar})


    # Store standard location for properties file
    env.Replace(XISE_PY_PROPFILE=File('.scons_build_tmp/project_properties.prop_list'))


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
                  emitter=chain_emitters([depend_on_proj_file, depend_on_proj_props]),
                  src_builder=foo,
                  target_scanner=Scanner(use_proplist_scanner, argument="XST"),
                  chdir=True, suffix=".ngc", src_suffix=".xst")
    env.Append(BUILDERS={'Xst' : xst}) 


    coregen = Builder(generator=xilinx.generate_coregen,
                      suffix='.xise',
                      src_suffix='.xco',
                      target_scanner=Scanner(use_proplist_scanner, argument="coregen"))
    #                      emitter=depend_on_proj_props)
    env.Append(BUILDERS={'Coregen' : coregen})

    # Make some scanners
    env.Append(SCANNERS=scan_ise.XiseScannerManual())
    env.Append(SCANNERS=scan_ise.XcoScanner())

    ## Translate 
    ngd = Builder(generator=xilinx.generate_ngdbuild,
                  suffix='.ngd',
                  src_suffix='.ngc',
                  chdir=True,
                  emitter=gimme_edif,
                  target_scanner=Scanner(use_proplist_scanner, argument="ngdbuild"))
    env.Append(BUILDERS={'Ngd' : ngd})

    ## Make an EDIF file (we'll use it later)
    ngc2edif = Builder(action="ngc2edif -intstyle silent -bd asis -w  $SOURCE $TARGET",
                       suffix=".ndf",
                       src_suffix=".ngc")
    env.Append(BUILDERS={'Ngc2Edif' : ngc2edif})

    ## Map
    map = Builder(generator=xilinx.generate_map,
                  suffix='.ncd',
                  src_suffix='.ngd',
                  chdir=True)
    env.Append(BUILDERS={'Map' : map})


    
def interp_props(target, source, env):
    #sys.stderr.write("interp_props: %s %s %s\n"%([str(f) for f in target], [str(f) for f in source], env))
    prop_dict = xparseprops.process(source[0].get_contents())
    env.Replace(PROJFILE_PROPS=prop_dict)
    if env.Execute(Copy(target[0], source[0])):
        #copy failed?
        Exit(1)

def exists(env):
    EnsureSConsVersion(1,2,0)
    ise_exists = env.Detect(['ise'])
    return ise_exists


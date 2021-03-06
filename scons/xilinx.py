# Build process for Xilinx FPGA programs.  The main purpose of this is to 
# automate the generation of images with different connection-specific 
# parameters for each device

from SCons.Script import *

import platform
import operator
import pprint
import os.path
import itertools
import xml.etree.ElementTree
from xml.etree.ElementTree import parse
from xil_ise import get_project_files
from xil_ise import process_xst_opts
from xil_ise import process_ngd_opts
from xil_ise import process_map_opts
#from xil_ise import get_project_prop

def seq_dedup(seq):
    "Unique-ifier from http://www.peterbe.com/plog/uniqifiers-benchmark"
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]

def get_impl_files(project_file):

    "Extract all files mentioned in XISE project file with an Implementation association"
    
    tree = parse(project_file)
    root = tree.getroot()
    files = root.find('{http://www.xilinx.com/XMLSchema}files')
    impl_files = []
    for f in files.findall('{http://www.xilinx.com/XMLSchema}file'):
        f_name = f.get('{http://www.xilinx.com/XMLSchema}name')
        f_type = f.attrib['{http://www.xilinx.com/XMLSchema}type']
        for a in f.findall('./{http://www.xilinx.com/XMLSchema}association'):
            a_name = a.get('{http://www.xilinx.com/XMLSchema}name')
            a_seqid = a.get('{http://www.xilinx.com/XMLSchema}seqID')
            if a_name == 'Implementation':
                impl_files.append((int(a_seqid), f_type, f_name))
                continue
                
    impl_files.sort(key=operator.itemgetter(0))
    return impl_files

def expand_node(n, fsroot, term_test, verbose=False):

    """Recursively find files we know what to do with.  Specifically,
    we recurse on FILE_COREGENISE files, and return a leaf node for
    files for which term_test(file_type) is true."""
    
    seq_no, file_type, file_name = n
    if term_test(file_type):
        this_node = [os.path.join(fsroot, file_name)]
    else:
        this_node = None 
    if file_type in ['ROOT_XISE','FILE_COREGENISE']:
        new_fs_root = os.path.join(fsroot, os.path.dirname(file_name))
        if verbose:
            print file_name                
            print new_fs_root
        try:
            raw = get_impl_files(file_name)
        except IOError, e:
            #  Usually means file is missing?
            sys.stderr.write("Unable to expand file -- perhaps it's not there (yet): %s\n" % (str(e)))
            raw = []
        #pprint.pprint(raw)
        sub_files = [f for f in raw if f is not None]
        expanded =[this_node] + [expand_node(f, new_fs_root, term_test) for f in sub_files]
        filtered=[n for n in expanded if n is not None]
        return list(itertools.chain.from_iterable(filtered))
    else:
        return this_node

def expand_node_rtl(n, fsroot):
    def is_rtl(filetype):
        return filetype in ['FILE_VERILOG', 'FILE_VHDL']
    return expand_node(n, fsroot, is_rtl)

def expand_node_any(n, fsroot):
    def no_root(filetype):
        return filetype != 'ROOT_XISE'
    return expand_node(n, fsroot, no_root)

def generate_extradeps_from_prj (target, source, env, test):
    extrafiles = expand_node((0, 'ROOT_XISE', env.subst('$PROJECTFILE')), '.', test)
    return target, source+extrafiles

def generate_deps_all_cgise (target, source, env):    
    def test_just_cgise(filetype):
        return filetype=='FILE_COREGENISE'
    return generate_extradeps_from_prj(target, source, env, test_just_cgise)


#
# This is following the Makefile examples -- and using the perl
# scripts -- from XESS Corp
# (http://www.xess.com/appnotes/makefile.php)
# Let's do a little configuration first

def process_project_file (context, pfile):

    """Configuration routine.  Uses the contents of FOO.xise to set
    some useful properties in the build environment.  Least-obviously,
    we expect to find exactly one UCF file and exactly one CDC
    (chipscope) file in the .xise file.  More or fewer will cause
    confusion.  """

    context.env['PROJECTFILE']=pfile
    topdir = os.path.normpath(os.getcwd())
    print "Expanding project file paths relative to PWD="+topdir
    context.env['TOPDIR']=topdir

    tree = parse(pfile)
    root = tree.getroot()
    props = root.find('{http://www.xilinx.com/XMLSchema}properties')

    # Find chipscope files
    chipscopes = get_project_files(pfile, "FILE_CDC",0)
    if len(chipscopes) > 1:
        print "Found > 1 chipscope files: ", chipscopes
        Exit(1)
    elif len(chipscopes) < 1:
        context.env['CHIPSCOPE_FILE']=None
    else:
        context.env['CHIPSCOPE_FILE']=os.path.abspath(chipscopes[0])
            
    # Find UCF files
    ucfs = get_project_files(pfile, "FILE_UCF", 1)
    if len(ucfs) != 1:
        print "Found != 1 UCF files: ", ucfs
        Exit(1)
    context.env['UCF']=os.path.abspath(ucfs[0])


    #Find properties
    prop_dict = {}
    for p in props.findall('{http://www.xilinx.com/XMLSchema}property'):
        prop_dict[p.get('{http://www.xilinx.com/XMLSchema}name')]=p.get('{http://www.xilinx.com/XMLSchema}value')

    #Part number
    device  = prop_dict['Device']
    package = prop_dict['Package']
    grade   = prop_dict['Speed Grade']
    partnum = "{0}{1}-{2}".format(device, grade, package)
    print "Part number = " + partnum
    context.env['PARTNUM']=partnum

    #Working directory
    wd = prop_dict['Working Directory']
    context.env['WORK_DIR'] = wd

    #Names
    design_top = prop_dict['Implementation Top Instance Path']
    print "Implementation Top Instance: " +design_top
    context.env['FILE_STEM']=design_top.strip('/')

    #Include dirs
    include_dirs = prop_dict["Verilog Include Directories"]
    context.env['INCLUDE_DIRS'] = include_dirs

    context.env['gp'] = prop_dict["Generics, Parameters"]


#
# Step 0:  Generate the FOO.xst and FOO.prj files which will guide XST.
#

def build_xst (target, source, env):

    """Create .xst file, which contains the full command line for xst,
    and .prj file, which contains a list of files involved"""

    xst_filename = str(target[0])
    prj_filename = os.path.splitext(xst_filename)[0]+'.prj'
    coregen_files= get_project_files(str(source[0]),'FILE_COREGEN', 0)

    coregen_dirs = ['"'+os.path.abspath(os.path.dirname(f))+'"' for f in coregen_files]
    coregen_dirs = seq_dedup(coregen_dirs)
    coregen_dir_fmt = "{"+' '.join(coregen_dirs)+" }"

    try:
        options=env['PROJFILE_PROPS']['Synthesize - XST']
    except KeyError, e:
        sys.stderr.write("Error getting synthesis options: %s\n" % (str(e)))
        Exit(1)
    pprint.pprint(options)

    ## XXX HACK!
    if options['Cores Search Directories'] is None:
        options['Cores Search Directories'] = ' '.join(coregen_dirs)
    
    set_args, run_args = process_xst_opts(options)
    pprint.pprint(set_args)
    pprint.pprint(run_args)

    ## Add some task-specific values:
    run_args = [['-ifn' , os.path.basename(prj_filename)],
                ['-ofn' ,  env.subst('$FILE_STEM')],
                ['-ofmt', 'NGC'],
                ['-p'   ,  env.subst('$PARTNUM')],
                ['-slice_utilization_ratio_maxmargin', '5'],
                ['-top' , env.subst('$FILE_STEM')]] + run_args
    
    cmd_line=""
    for sa in set_args:
        cmd_line = cmd_line + "set " + ' '.join(sa) + '\n'
    cmd_line  = cmd_line + "run\n"
    for ra in run_args:
        cmd_line = cmd_line + ' '.join(ra) + '\n'
    #print cmd_line
    
    outfile = open(xst_filename,"w")
    outfile.write(cmd_line)
    outfile.close()
        
    return 0


def build_prj (target, source, env):

    """Create .prj file, which contains a list of files involved"""

    prj_filename = str(target[0])

    
    impl_files = expand_node_rtl((0, 'ROOT_XISE', str(source[0])), '.')
    
    outfile = open(prj_filename,"w")
    for vfile in [os.path.abspath(f) for f in impl_files]:
        outfile.write('verilog work "{0}"\n'.format(vfile))
    outfile.close()
        
    return 0

def identify_coregens(env):
    prj_filename = env.subst('$PROJECTFILE')
    def is_xco (filetype):
        return filetype=='FILE_COREGEN'
    def is_cgise (filetype):
        return filetype=='FILE_COREGENISE'    
    coregen_xcos = expand_node((0, 'ROOT_XISE', prj_filename), '.', is_xco)
    coregen_xises = expand_node((0, 'ROOT_XISE', prj_filename), '.', is_cgise)

    # Naive -- not always true!
    xco_of = [(f, os.path.splitext(f)[0]+'.xco') for f in coregen_xises]

    return xco_of

def generate_coregen (source, target, env, for_signature):
    """ Produce a command-line for coregen"""
    cg_prj_filename = env.subst('$CG_PROJ')
    cmd_line = "coregen -p {0} -b {1} -r -intstyle silent; sed -i '/^# Date/ s/.*/# Date: REMOVED/g' {1}"
    cmd_line=cmd_line.format(cg_prj_filename, # 0 project file
                             str(source[0])) # 1 source
    # Assumed! that target is correct
    return cmd_line
    
#
# Step 1: First "real" step: .xst script (+source files) -> .ngc, .ngr, log file (.srp)
#

def generate_xst (source, target, env, for_signature):

    """Produce the command line for XST (not counting the additional
    command line stored in FOO.xst).  Expect the following sources
    [0]=.xst file"""

    xst_filename = os.path.basename(str(source[0]))
    syr_filename = os.path.splitext(xst_filename)[0]+'.syr'
    cmd_line = 'xst -intstyle {0} -ifn {1} -ofn {2}'
    cmd_line = cmd_line.format(env.subst('$INTSTYLE'),
                               xst_filename,
                               syr_filename)
                
    return cmd_line

def source_files_from_xise (target, source, env):
    files = expand_node_any((0, 'ROOT_XISE', str(source[0])), '.')
    #pprint.pprint(files)
    return target, source+[os.path.join(env.subst('$WORK_DIR'),
                                        env.subst('$FILE_STEM') + '.xst'),
                           os.path.join(env.subst('$WORK_DIR'),
                                        env.subst('$FILE_STEM') + '.prj')]+files

#
# Step 2: Translate
#

#2.1 Chipscope core inserter

def generate_chipsope_insert (source, target, env, for_signature):

    "Generator for chipscope insert Builder"
    
    cmd_line = """inserter -intstyle {0} \
    -mode insert \
    -ise_project_dir {1}/{2} \
    -proj {3} \
    -intstyle ise \
    -dd {1}/{2}/_ngo \
    -uc {4} \
    -p {5} \
    {6} \
    {7}""" #  after uc:  -sd ../../../coregen \
    cmd_line = cmd_line.format(env.subst('$INTSTYLE'), # 0 
                               env.subst('$TOPDIR'),   # 1
                               env.subst('$WORK_DIR'), # 2
                               env.subst('$CHIPSCOPE_FILE'), # 3
                               env.subst('$UCF'),            # 4
                               env.subst('$PARTNUM'),        # 5
                               os.path.basename(str(source[0])), # 6
                               os.path.basename(str(target[0]))) # 7
    return cmd_line

#2.2 Regular ngdbuild
def generate_ngdbuild (source, target, env, for_signature):

    try:
        options=env['PROJFILE_PROPS']['Translate']
        #pprint.pprint(options)
        opt_args = process_ngd_opts(options)
        #pprint.pprint(args)
    except KeyError, e:
        if not for_signature:
            sys.stderr.write("Error getting Translate / ngdbuild options: %s\n" % (str(e)))
            Exit(1)
        else:
            sys.stderr.write("generate_ngdbuild called before PROJFILE_PROPS was defined. That's OK as long as it gets called again later.\n")
            opt_args = []

    initial_args = ['ngdbuild',
                    '-quiet',
                    '-intstyle', env.subst('$INTSTYLE'),
                    '-sd', '../../coregen', # XXX bad!  Get this path somewhere reasonable!
                    '-uc', env.subst('$UCF'),
                    '-p', env.subst('$PARTNUM')]
                
    
    flat_args = [item for sublist in opt_args for item in sublist]
    
    args = initial_args + flat_args + [os.path.basename(str(source[0])),
                                       os.path.basename(str(target[0]))]
    #pprint.pprint(all_args)

    cmd_line=' '.join(args) + ' >/dev/null'
    return cmd_line


#
# Step 3: map
#
def generate_map (source, target, env, for_signature):
    try:
        options=env['PROJFILE_PROPS']['Map']
        pprint.pprint(options)
        opt_args = process_map_opts(options)        
        pprint.pprint(opt_args)
    except KeyError, e:
        if not for_signature:
            sys.stderr.write("Error getting Map options: %s\n" % (str(e)))
            Exit(1)
        else:
            sys.stderr.write("generate_map called before PROJFILE_PROPS was defined. That's OK as long as it gets called again later.\n")
            opt_args = []


    initial_args = ['map',
                    '-filter', '"/home/andersoe/emulator/src/fpga/SCM/SCM_OPTICAL/iseconfig/filter.filter"',
                    '-intstyle', 'ise', #env.subst('$INTSTYLE'),                    
                    '-p', env.subst('$PARTNUM'),
                    '-w']
    
    flat_args = [item for sublist in opt_args for item in sublist]

    #pprint.pprint(flat_args)
    
    args = initial_args + flat_args + ['-o', os.path.basename(str(target[0])), # NCD file
                                       os.path.basename(str(source[0])), #NGD file
                                       os.path.basename(str(target[1])),  # PCF file
                                       ]
    cmd_line=' '.join(args)
    return cmd_line                               
                               
    return cmd_line
    

#
# Step 4: Place and Route
#
def generate_par (source, target, env, for_signature):
    cmd_line = "par -w -intstyle {0} -ol high -t 1 {1} {2} {3}"
    cmd_line = cmd_line.format(env.subst('$INTSTYLE'),
                               os.path.basename(str(source[0])),     # in
                               os.path.basename(str(target[0])),     # out
                               os.path.basename(str(source[1])))     # constraint  (in)
    return cmd_line
    
               
#
# Step 5: Generate Programming File (bitgen)
#
def generate_bitgen (source, target, env, for_signature):
    cmd_line ="""bitgen -intstyle {0} \
    -w \
    -g DebugBitstream:No \
    -g Binary:no \
    -g CRC:Enable \
    -g ConfigRate:4 \
    -g CclkPin:PullUp \
    -g M0Pin:PullUp \
    -g M1Pin:PullUp \
    -g M2Pin:PullUp \
    -g ProgPin:PullUp \
    -g DonePin:PullUp \
    -g InitPin:Pullup \
    -g CsPin:Pullup \
    -g DinPin:Pullup \
    -g BusyPin:Pullup \
    -g RdWrPin:Pullup \
    -g PowerdownPin:PullUp \
    -g HswapenPin:PullUp \
    -g TckPin:PullUp \
    -g TdiPin:PullUp \
    -g TdoPin:PullUp \
    -g TmsPin:PullUp \
    -g UnusedPin:PullDown \
    -g UserID:0xFFFFFFFF \
    -g DCIUpdateMode:AsRequired \
    -g StartUpClk:CClk \
    -g DONE_cycle:4 \
    -g GTS_cycle:5 \
    -g GWE_cycle:6 \
    -g LCK_cycle:NoWait \
    -g Match_cycle:Auto \
    -g Security:None \
    -g DonePipe:No \
    -g DriveDone:No \
    -g Encrypt:No \
    {1}"""
    cmd_line=cmd_line.format(env.subst('$INTSTYLE'),
                             os.path.basename(str(source[0])))
    return cmd_line


def do_xilinx(env,project=None,plat=None):
    # Allow for different behavior on Windows, Linux, etc.
    # No such difference implemented yet, though.
    if project is None:
        project = ARGUMENTS.get('PROJECT','ChangeMe.xise')
    if plat is None:
        plat= ARGUMENTS.get('ARCH',platform.architecture()[0])

    #ISE 13.2, Linux, installed in /opt/Xilinx/13.2

    XIL_ROOT='/opt/Xilinx/13.2/ISE_DS'
    if plat=='32bit':
        ARCH_PATH='lin'
    elif plat=='64bit':
        ARCH_PATH='lin64'
    else:
        print "Unrecognized platform: " + platform.platform()
        Exit(1)

    env['PLATFORM']        = platform
    env['XILINX_DPS']      = XIL_ROOT + '/ISE'
    env['LD_LIBRARY_PATH'] = '{0}/common/lib/{1}:{0}/ISE/lib/{1}:{0}/ISE/smartmodel/{1}/installed_{1}/lib:{0}/EDK/lib/{1}'.format(XIL_ROOT, ARCH_PATH)
    env['XILINX_EDK']      = XIL_ROOT + '/EDK'
    env['PATH']            = '{0}/common/bin/{1}:{0}/PlanAhead/bin:{0}/ISE/bin/{1}:{0}/ISE/sysgen/util:{0}/EDK/bin/{1}:/sbin:/usr/sbin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin'.format(XIL_ROOT,ARCH_PATH)
    env['JAVA_HOME']       = '/usr/lib/jvm/java-1.6.0-openjdk/'
    env['LMC_HOME']        = XIL_ROOT + '/ISE/smartmodel/{0}/installed_{0}'.format(ARCH_PATH)
    env['XILINX_PLANAHEAD']= XIL_ROOT + '/PlanAhead'
    env['XILINX']          = XIL_ROOT + '/ISE'
    env['LM_LICENSE_FILE'] = 'XXX-fill this in'

    ##Project-specifc  preferences.  These should be discovered in some smarter way
    env['INTSTYLE'] = 'silent'
    
    
    conf = Configure(env)
    process_project_file(conf, project)
    env=conf.Finish()
    Export('env')
    
    
    # Build in working subdirectory
    WORK_DIR=env.subst('$WORK_DIR')
    FILE_STEM=env.subst('$FILE_STEM')
    VariantDir(WORK_DIR, '.', duplicate=0)


    #  Step 0
    preconfig=Builder(action=build_xst_and_prj)
    env.Append(BUILDERS={'Preconfig' : preconfig})
    env.Preconfig([os.path.join(WORK_DIR, FILE_STEM + '.xst'),
                   os.path.join(WORK_DIR, FILE_STEM + '.prj')],
                  env.subst('$PROJECTFILE'))

    # Step 1
    xst = Builder(generator=generate_xst, emitter=source_files_from_xise,
                  chdir=True, suffix=".ngc", src_suffix=".xst")
    env.Append(BUILDERS={'Xst' : xst})
    
    xst_build = env.Xst(os.path.join(WORK_DIR, FILE_STEM +'.ngc'),
                        os.path.abspath(env.subst('$PROJECTFILE')))

    # Step 2.1
    insert = Builder(generator=generate_chipsope_insert, chdir=True,
                     suffix="_cs.ngc", src_suffix=".ngc")

    # If CHIPSCOPE_FILE isn't defined, then the "real" .ngc file does not
    # depend on the _cs.ngc file.
    if env['CHIPSCOPE_FILE'] is not None:
        env.Append(BUILDERS={'Insert': insert})
        do_insert=env.Insert(os.path.join(WORK_DIR, FILE_STEM + '_cs.ngc'),
                             os.path.join(WORK_DIR, FILE_STEM + '.ngc'))
        Depends(do_insert,[env.subst('$CHIPSCOPE_FILE'), env.subst('$UCF')])

    # Step 2.2
    ngd = Builder(generator=generate_ngdbuild,
                  chdir=True)
    env.Append(BUILDERS={'Ngd' : ngd})
    
    ngd_build=env.Ngd(os.path.join(WORK_DIR, FILE_STEM +'.ngd'),
                      os.path.join(WORK_DIR, FILE_STEM + '_cs.ngc'))
    if env['CHIPSCOPE_FILE'] is not None:
        Depends(ngd_build,[env.subst('$CHIPSCOPE_FILE'), env.subst('$UCF')])

    # Step 3
    map = Builder(generator=generate_map,
                  chdir=True)
    env.Append(BUILDERS={'Map' : map})
    do_map=env.Map([os.path.join(WORK_DIR, FILE_STEM + '_map.ncd'),
                    os.path.join(WORK_DIR, FILE_STEM +'.pcf')],
                   os.path.join(WORK_DIR, FILE_STEM + '.ngd'))
    
    # Step 4
    par = Builder(generator=generate_par,
              chdir=True)
    env.Append(BUILDERS={'Par' : par})
    do_par=env.Par(os.path.join(WORK_DIR, FILE_STEM + '.ncd'),
                   [os.path.join(WORK_DIR, FILE_STEM + '_map.ncd'),
                    os.path.join(WORK_DIR, FILE_STEM + '.pcf')])

    # Step 5
    bitgen = Builder(generator=generate_bitgen, chdir=True)
    env.Append(BUILDERS={'Bitgen' : bitgen})
    do_bitgen=env.Bitgen(os.path.join(WORK_DIR, FILE_STEM + '.bit'),
                         os.path.join(WORK_DIR, FILE_STEM + '.ncd'))

    
    return None

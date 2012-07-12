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
    properties = root.find('{http://www.xilinx.com/XMLSchema}properties')


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

##
##      Definitions related to ISE command-line options
##



def process_opt_with_defn(process, key, defns, values):

    """ Use the map of option definitions provided (defns) and map of
    project/user-selected preferences (values) to produces appropriate
    command line arguments for the given key (key).

    In all current cases, the proc_fn in the defns map will either
    return the flag (from defns) and some appropriate formatting of
    the value (from values), or will return an empty list.
    """
    
    defn = defns[key]
    value = values[key]
    longname=key
    (flag, proc_fn) = defn
    args = proc_fn(process=process,
                   longname=longname,
                   flag=flag,
                   value=value)
    return args

def process_xst_opts(opt_dict):

    """Go through user/project specified option preferences (opt_dict)
    and build up XST command-line arguments for 'set' and 'run' """
    
    set_args = []
    run_args = []
    for k in opt_dict.keys():
        if k in XST_RUN_OPTS:
            #print "RUN %s\t%s\t%s" % (k,XST_RUN_OPTS[k],opt_dict[k])
            args = process_opt_with_defn('xst',k, XST_RUN_OPTS, opt_dict)
            if args != []:
                run_args.append(args)
            #print k, args
        elif k in XST_SET_OPTS:
            #print "SET %s\t%s\t%s" % (k,XST_SET_OPTS[k],opt_dict[k])
            args = process_opt_with_defn('xst',k, XST_SET_OPTS, opt_dict)
            if args != []:
                set_args.append(args)
            #print k, args
        else:
            raise ValueError("Option '%s' in opt_dict has no matching entry in XST_RUN_OPTS or XST_SET_OPTS" % (k))
    return (set_args, run_args)

def process_ngd_opts(opt_dict):

    """Go through user/project specified option preferences (opt_dict)
    and build up ngdbuild command-line arguments"""
    
    all_args = []

    for k in opt_dict.keys():
        if k in NGDBUILD_OPTS:
            #print "RUN %s\t%s\t%s" % (k,NGDBUILD_OPTS[k],opt_dict[k])
            args = process_opt_with_defn('ngd',k, NGDBUILD_OPTS, opt_dict)
            if args != []:
                all_args.append(args)
            #print k, args
        else:
            raise ValueError("Option '%s' in opt_dict has no matching entry in NGDBUILD_OPTS" % (k))
    return all_args



##
## Value/Flag formatting functions
##

def flag_if_bool(expect=True):
    """For Boolean values, return the flag iff the value matches 'expect' """
    def doit(process, longname, flag, value):
        if type(value) != bool:
            raise ValueError("flag_if_bool can't handle value '%s' of type '%s'"%(repr(value),type(value)))
        elif value==expect:
            return [flag]
        else:
            return []
    return doit

    

## Primitive _value_ formatting functions: Directly produce a value
## from the supplied arguments

def id(process, longname, flag, value):

    """Identity function:  returns value"""

    return value

def special_case(process, longname, flag, value):

    """Look for an entry ISE_OPT_VAL_MAP[flag][value] and return it"""
    
    cases = ISE_OPT_VAL_MAP[process][flag]
    new_val = cases[value]
    return new_val


def maybe_special_case(process, longname, flag, value):
    
    """Look for pre-defined special-case handling of this value, and
    substitute if possibe."""

    try:
        v = special_case(process, longname, flag, value)
        return v
    except KeyError:
        # No special-case map for this flag, or no entry in said map for this value
        return str(value)

def bool_yes_no(process, longname, flag, value):
    """ Phrase Boolean values as 'YES' or 'NO' """
    if value==True:
        return "YES"
    if value==False:
        return "NO"
    # Anything else wasn't a bool!
    raise ValueError("Flag value '%s' wasn't boolean." % repr(value))


## Almost primitive:  Takes parameter "extras" and returns a formatting function
def bool_and_more(extras):

    """ Handle values which must be either boolean or one of a
    pre-defined group of other options (e.g. 'auto').

    If 'extras' is a list, any value appearing in the list is used as is.
    If 'extras' is a dictionary, extras[value] is used, if defined."""
    
    def do_it_l(process, longname, flag, value):        
        if value in extras:
            return value
        else:
            return bool_yes_no(process, longname, flag, value)

    def do_it_d(process, longname, flag, value):
        try:
            new_val = extras[value]
            return new_val
        except KeyError:
            return bool_yes_no(process, longname, flag, value)

    if type(extras) == list:
        return do_it_l
    if type(extras) == dict:
        return do_it_d
    raise ValueError ("'extras' parameter had type %s (value '%s').  Only lists and dictionaries are allowed." % (type(extras), repr(extras)))


## Formatting combinators: Take some primitive formatting function and
## make a more complicated one

def normal(fn,drop_none=True):

    """Given a value-formatting function 'fn' use it to format the
    value, and return the flag and formatted value as a list.

    If drop_none is True, return an empty list if the formatted value
    is None or 'None'
    """
    
    def doit(process, longname, flag, value):
        new_val = fn(process, longname, flag, value)
        if drop_none and (new_val is None or new_val == 'None'):
            return ([])
        else:
            return ([flag, new_val])
    
    return doit

def must(allowed, fn):
    """ Use 'fn' to compute a value, and then check that it is in the list 'allowed'
    """
    def do_it(process, longname, flag, value):
        new_val = fn(process, longname, flag, value)
        if new_val not in allowed:
            raise ValueError("new_val '%s' is not one of the allowed values ('%s').  Something must be wrong!" % (new_val, allowed))
        return new_val
    return do_it


def as_list (fn, drop_none=False):

    """ Break value into a list, format each item with the supplied
    function, and quote result with { and }.

    If drop_none is False (default), an input of None will result in
    an output of '{}'.  If True, output will be None.
    """

    def doit(process, longname, flag, value):
        value_parts = []
        if value is None:
            if drop_none:
                return None
        else:
            value_parts = value.split()
            
        formatted_value_parts = [fn(process, longname, flag, p) for p in value_parts]
        full_string = '{' + ' '.join(formatted_value_parts) + '}'
        return full_string

    return doit

            

def simple_quote(fn, openq='"', closeq='"', drop_none=True):
    
    """Format value with fn, and wrap the result with openq and closeq.

    If drop_none is True, and the returned value is None or 'None',
    returns None."""
    
    def doit(process, longname, flag, value):
        new_val = fn(process, longname, flag, value)
        if drop_none and (new_val is None or new_val == 'None'):
            return None
        else:
            return openq + new_val + closeq
    
    return doit


## Convenient aliases for common formatting combinations

quoted_list = normal(as_list(simple_quote(maybe_special_case)))
simple_string = normal(maybe_special_case)
simple_bool = normal(bool_yes_no)
verbatim = normal(id)
 
ISE_OPT_VAL_MAP={'xst' : {'-glob_opt':           {'Maximum Delay':'Max_Delay'},
                          '-opt_level':          {'Normal': '1', # I know 'Normal' is what appears in XISE properties, but
                                                  'High'  : '2', # I'm just guessing about 'High'
                                                  'Fast'  : '3'}, # And 'Fast'
                          '-netlist_hierarchy' : {'As Optimized' : 'as_optimized',
                                                  'Rebuilt'      : 'rebuilt',}, # Another guess
                          },
                 'ngd' : {'-nt' : {'Timestamp' : 'timestamp',
                                   'On'        : 'on',
                                   'Off'       : 'off'}},
                 }
                 

# Definitions for ISE 13.4.  See "XST Commands" in Xilinx UG687, v.13.4
XST_RUN_OPTS={'Optimization Goal': ('-opt_mode', simple_string),
              'Optimization Effort': ('-opt_level', normal(special_case)),
              'Power Reduction': ('-power', simple_bool),
              'Use Synthesis Constraints File': ('-iuc', simple_bool),
              'Synthesis Constraints File': ('-uc', simple_string),
              'Keep Hierarchy': ('-keep_hierarchy', simple_string),
              'Netlist Hierarchy': ('-netlist_hierarchy', normal(special_case)),
              'Global Optimization Goal': ('-glob_opt', simple_string),
              'Generate RTL Schematic': ('-rtlview', normal(must(['yes','Yes','no','No','only','Only'],maybe_special_case))),
              'Read Cores': ('-read_cores', normal(bool_and_more(extras=['Optimize', 'optimize']))),
              'Cores Search Directories': ('-sd', quoted_list),
              'Write Timing Constraints': ('-write_timing_constraints', simple_bool),
              'Cross Clock Analysis': ('-cross_clock_analysis', simple_bool),
              'Hierarchy Separator': ('-hierarchy_separator', simple_string),
              'Bus Delimiter': ('-bus_delimiter', verbatim),
              'LUT-FF Pairs Utilization Ratio': ('-slice_utilization_ratio', simple_string),
              'BRAM Utilization Ratio': ('-bram_utilization_ratio', simple_string),
              'DSP Utilization Ratio': ('-dsp_utilization_ratio', simple_string),
              'Case': ('-case', simple_string),
              'Library Search Order': ('-lso', simple_string),
              'Library for Verilog Sources': (None, simple_string),
              'Verilog Include Directories': ('-vlgincdir', quoted_list),
              'Generics, Parameters': ('-generics', normal(as_list(id))),
              'Verilog Macros': ('-define', normal(as_list(id))),
              'FSM Extraction': ('-fsm_extract', simple_string),
              'FSM Encoding Algorithm': ('-fsm_encoding', simple_string),
              'Safe Implementation': ('-safe_implementation', simple_string),
              'Case Implementation Style': ('-vlgcase', simple_string),
              'FSM Style': ('-fsm_style', simple_string),
              'RAM Extraction': ('-ram_extract', simple_bool),
              'RAM Style': ('-ram_style', simple_string),
              'ROM Extraction': ('-rom_extract', simple_bool),
              'ROM Style': ('-rom_style', simple_string),
              'Automatic BRAM Packing': ('-auto_bram_packing', simple_bool),
              'Shift Register Extraction': ('-shreg_extract', simple_bool),
              'Shift Register Minimum Size': ('-shreg_min_size', simple_string),
              'Resource Sharing': ('-resource_sharing', simple_bool),
              'Use DSP Block': ('-use_dsp48', simple_string),
              'Asynchronous To Synchronous': ('-async_to_sync', simple_bool),
              'Add I/O Buffers': ('-iobuf', normal(bool_and_more(extras=['soft','Soft']))),
              'Max Fanout': ('-max_fanout', simple_string),
              'Number of Clock Buffers': ('-bufg', simple_string),
              'Register Duplication': ('-register_duplication', simple_bool),
              'Equivalent Register Removal': ('-equivalent_register_removal', simple_bool),
              'Register Balancing': ('-register_balancing', simple_string),
              'Move First Flip-Flop Stage': ('-move_first_stage', simple_bool),
              'Move Last Flip-Flop Stage': ('-move_last_stage', simple_bool),
              'Pack I/O Registers into IOBs': ('-iob', simple_string),
              'LUT Combining': ('-lc', simple_string),
              'Reduce Control Sets': ('-reduce_control_sets', simple_string),
              'Use Clock Enable': ('-use_clock_enable', simple_string),
              'Use Synchronous Set': ('-use_sync_set', simple_string),
              'Use Synchronous Reset': ('-use_sync_reset', simple_string),
              'Optimize Instantiated Primitives': ('-optimize_primitives', simple_bool),
              'Other XST Command Line Options': (None,verbatim)}


XST_SET_OPTS={None : ('-tmpdir', normal(simple_quote(maybe_special_case))),
              'Work Directory' : ('-xsthdpdir', normal(simple_quote(maybe_special_case))),
              'HDL INI File' : ('-xsthdpini', normal(simple_quote(maybe_special_case)))}

NGDBUILD_OPTS = {'Allow Unexpanded Blocks': ('-u', flag_if_bool(True)),
                 'Allow Unmatched LOC Constraints': ('-aul', flag_if_bool(True)),
                 'Allow Unmatched Timing Group Constraints': ('-aut', flag_if_bool(True)),
                 'Create I/O Pads from Ports': ('-a', flag_if_bool(True)),
                 'Macro Search Path': ('-sd', simple_string),
                 'Netlist Translation Type': ('-nt', simple_string),
                 'Other Ngdbuild Command Line Options': (None, verbatim),
                 'Use LOC Constraints': ('-r', flag_if_bool(False)),
                 'User Rules File for Netlister Launcher': ('-ur',normal(simple_quote(id)))}
                 

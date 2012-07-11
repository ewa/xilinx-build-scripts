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


def process_opt_with_defn(key, defns, values):
    defn = defns[key]
    value = values[key]
    longname=key
    (flag, proc_fn) = defn
    args = proc_fn(longname=longname,
                   flag=flag,
                   value=value)
    return args

def process_xst_opts(opt_dict):
    set_args = []
    run_args = []
    for k in opt_dict.keys():
        if k in ISE_RUN_OPTS:
            #print "RUN %s\t%s\t%s" % (k,ISE_RUN_OPTS[k],opt_dict[k])
            args = process_opt_with_defn(k, ISE_RUN_OPTS, opt_dict)
            if args != []:
                run_args.append(args)
            #print k, args
        elif k in ISE_SET_OPTS:
            #print "SET %s\t%s\t%s" % (k,ISE_SET_OPTS[k],opt_dict[k])
            args = process_opt_with_defn(k, ISE_SET_OPTS, opt_dict)
            if args != []:
                set_args.append(args)
            #print k, args
    return (set_args, run_args)

            
def val_as_string (longname, flag, value):
    if value is not None:
        return ([flag, str(value)])
    return ([])

def quote_list (longname, flag, value):
    value_parts = value.split()         # XXX be smarter
    quoted_value_parts = ['"' + str(p) + '" ' for p in value_parts]
    full_string = '{' + ''.join(quoted_value_parts) + '}'
    return ([flag, full_string])

def simple_quote(string_making_fn, openq='"', closeq='"'):
    def do_it (longname, flag, value):
        r = string_making_fn(longname, flag, value)
        if r != []:
            (f, v) = r 
            return ([f, openq +v+ closeq])
        else:
            return ([])
    return do_it



# Definitions for ISE 13.4.  See "XST Commands" in Xilinx UG687, v.13.4
ISE_RUN_OPTS={'Optimization Goal': ('-opt_mode', val_as_string),
              'Optimization Effort': ('-opt_level', val_as_string),
              'Power Reduction': ('-power', val_as_string),
              'Use Synthesis Constraints File': ('-iuc', val_as_string),
              'Synthesis Constraints File': ('-uc', val_as_string),
              'Keep Hierarchy': ('-keep_hierarchy', val_as_string),
              'Netlist Hierarchy': ('-netlist_hierarchy', val_as_string),
              'Global Optimization Goal': ('-glob_opt', val_as_string),
              'Generate RTL Schematic': ('-rtlview', val_as_string),
              'Read Cores': ('-read_cores', val_as_string),
              'Cores Search Directories': ('-sd', simple_quote(val_as_string, '{','}')),
              'Write Timing Constraints': ('-write_timing_constraints', val_as_string),
              'Cross Clock Analysis': ('-cross_clock_analysis', val_as_string),
              'Hierarchy Separator': ('-hierarchy_separator', val_as_string),
              'Bus Delimiter': ('-bus_delimiter', val_as_string),
              'LUT-FF Pairs Utilization Ratio': ('-slice_utilization_ratio', val_as_string),
              'BRAM Utilization Ratio': ('-bram_utilization_ratio', val_as_string),
              'DSP Utilization Ratio': ('-dsp_utilization_ratio', val_as_string),
              'Case': ('-case', val_as_string),
              'Library Search Order': ('-lso', val_as_string),
              'Library for Verilog Sources': (None, val_as_string),
              'Verilog Include Directories': ('-vlgincdir', quote_list),
              'Generics, Parameters': ('-generics', val_as_string),
              'Verilog Macros': ('-define', val_as_string),
              'FSM Extraction': ('-fsm_extract', val_as_string),
              'FSM Encoding Algorithm': ('-fsm_encoding', val_as_string),
              'Safe Implementation': ('-safe_implementation', val_as_string),
              'Case Implementation Style': ('-vlgcase', val_as_string),
              'FSM Style': ('-fsm_style', val_as_string),
              'RAM Extraction': ('-ram_extract', val_as_string),
              'RAM Style': ('-ram_style', val_as_string),
              'ROM Extraction': ('-rom_extract', val_as_string),
              'ROM Style': ('-rom_style', val_as_string),
              'Automatic BRAM Packing': ('-auto_bram_packing', val_as_string),
              'Shift Register Extraction': ('-shreg_extract', val_as_string),
              'Shift Register Minimum Size': ('-shreg_min_size', val_as_string),
              'Resource Sharing': ('-resource_sharing', val_as_string),
              'Use DSP Block': ('-use_dsp48', val_as_string),
              'Asynchronous To Synchronous': ('-async_to_sync', val_as_string),
              'Add I/O Buffers': ('-iobuf', val_as_string),
              'Max Fanout': ('-max_fanout', val_as_string),
              'Number of Clock Buffers': ('-bufg', val_as_string),
              'Register Duplication': ('-register_duplication', val_as_string),
              'Equivalent Register Removal': ('-equivalent_register_removal', val_as_string),
              'Register Balancing': ('-register_balancing', val_as_string),
              'Move First Flip-Flop Stage': ('-move_first_stage', val_as_string),
              'Move Last Flip-Flop Stage': ('-move_last_stage', val_as_string),
              'Pack I/O Registers into IOBs': ('-iob', val_as_string),
              'LUT Combining': ('-lc', val_as_string),
              'Reduce Control Sets': ('-reduce_control_sets', val_as_string),
              'Use Clock Enable': ('-use_clock_enable', val_as_string),
              'Use Synchronous Set': ('-use_sync_set', val_as_string),
              'Use Synchronous Reset': ('-use_sync_reset', val_as_string),
              'Optimize Instantiated Primitives': ('-optimize_primitives', val_as_string),
              'Other XST Command Line Options': (None,val_as_string)}


ISE_SET_OPTS={None : ('-tmpdir', simple_quote(val_as_string)),
              'Work Directory' : ('-xsthdpdir', simple_quote(val_as_string)),
              'HDL INI File' : ('-xsthdpini', simple_quote(val_as_string))}

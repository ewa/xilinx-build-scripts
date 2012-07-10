#!/usr/bin/env python
import sys
from parcon import *
import pprint

def mkparser():
    group = Forward()
    basic_string = Exact(OneOrMore(CharNotIn(['{','}',':'])))[concat]
    quoted_string="{" + basic_string + "}"
    term = basic_string|quoted_string|group
    foo = "{" + ZeroOrMore(term|SignificantLiteral(':')) + "}"
    group << foo(name="group")
    groups = OneOrMore(group)
    return groups
    

def process(input,verbose=False):

    def interpret(value):
        if type(value) == str:
            if value in ['true','TRUE','True']:
                return True
            if value in ['false','FALSE','False']:
                return False
            try:
                i_value = int(value)
                return i_value
            except ValueError:
                pass
            try:
                f_value = float(value)
                return f_value
            except ValueError:
                pass
            return value.decode('string_escape')
        if ((type(value) == list) and
            (value==[])):
            return None
        raise ValueError("Cannot process non-string value " + repr(value))
    
    listy=mkparser().parse_string(input)
    process_dict={}
    for (process, properties) in listy:
        if verbose:
            print "process: " + process
        property_dict = {}
        for p in properties:
            (n,_,v) = p
            if verbose:
                print "   property:%s=%s" % (n,v)
            property_dict[n.strip()]=interpret(v)
        process_dict[process.strip()]=property_dict
    return process_dict

def main(argv):
    for line in sys.stdin:
        x=process(line.strip())
        pprint.pprint(x)

        

if __name__ == '__main__':
    sys.exit(main(sys.argv))

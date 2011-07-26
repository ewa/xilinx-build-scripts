#!/usr/bin/env python

import optparse
import os.path
import hashlib
import xil_ise
import vcs

class FileStatus:
    EQUAL=0                             # File in both VC and WD, with same contents
    DIFFER=1                            # File in both VC and WD, contents differ
    WD_ONLY=2                           # File only in WD
    VC_ONLY=3                           # File only in VC

    
def formatFS(fs):
    return {FileStatus.EQUAL:"match",
            FileStatus.DIFFER:"differ",
            FileStatus.WD_ONLY:"missing",
            FileStatus.VC_ONLY:"deleted"}[fs]
    

def main(argv):
    usage = "usage: %prog [options] <project_file>"
    parser= optparse.OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
    
    vc_opts = optparse.OptionGroup(parser, "Version Control Options")
    vc_opts.add_option("-r","--repodir", help="repository root", metavar="DIR",
                       type="string", dest="repo_root")
    parser.add_option_group(vc_opts)
    
    ise_opts = optparse.OptionGroup(parser, "Xilinx ISE Options")
    ise_opts.add_option("-p","--projdir", help="Project Directory", metavar="DIR",
                       type="string", dest="proj_root")
    parser.add_option_group(ise_opts)
    


    
    parser.set_defaults(repo_root="..") # NOTE That this is an odd default
    parser.set_defaults(proj_root=".")
    parser.set_defaults(verbose=False)
    
    (opts, args) = parser.parse_args(argv)
    
    
    if len(args) != 2:
        parser.error("Incorrect command-line.")

        
    def path_ptv (proj_rel_path):
        full_proj_path = os.path.join(opts.proj_root, proj_rel_path)
        vcs_relpath = os.path.relpath(full_proj_path, opts.repo_root)
        return(vcs_relpath)

    def path_vcs_full (vcs_rel_path):
        full_vcs_path = os.path.join(opts.repo_root, vcs_rel_path)
        return(full_vcs_path)
        
    
    xise_file = args[1]

    xil_sources = xil_ise.get_project_files(xise_file)
    xil_sources_norm = [path_ptv(f) for f in xil_sources]

    repo=vcs.get_repo(path=opts.repo_root)
    head=repo.get_changeset()
    

    filestates=[]
    for fname in xil_sources_norm:
        try:
            vc_digest = hashlib.sha1(head.get_file_content(fname)).hexdigest()
            
            real_path=path_vcs_full(fname)            
            f = file(real_path, 'r')
            real_digest = hashlib.sha1(f.read()).hexdigest()
            f.close()

            if real_digest == vc_digest:
                filestates.append((fname, FileStatus.EQUAL))
            else:
                filestates.append((fname, FileStatus.DIFFER))
        except vcs.exceptions.NodeDoesNotExistError:
            filestates.append((fname,FileStatus.WD_ONLY))
        except IOError:
            filestates.append((fname,FileStatus.VC_ONLY))
        
        #print fname, vc_digest, real_digest

    for (f,s) in filestates:
        if (s != FileStatus.EQUAL) or (opts.verbose):
            print "{0:<5}:\t{1:<60}".format(formatFS(s),f)

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
    

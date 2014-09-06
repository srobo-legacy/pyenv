
import os
import re
import subprocess
import shutil
import tempfile

REPO_ROOT = os.path.dirname( __file__ )
PYENV_DIR = os.path.join( REPO_ROOT, "pyenv" )
assert os.path.isdir( PYENV_DIR )

def find_pyenv_rev( reporoot ):
    "Return the revision of pyenv"

    ver = subprocess.check_output( "git rev-list --max-count=1 HEAD",
                                   cwd = reporoot, shell = True )
    return ver.strip()

def add_pyenv_rev_file( reporoot, tmpd ):
    "Write a file into tmpd indicating the pyenv revision"

    f = open( os.path.join( tmpd, ".pyenv-rev" ), "w" )
    f.write( "%s\n" % find_pyenv_rev(reporoot) )
    f.close()

def remove_user_dir( tmpd ):
    "Remove any trace of a user directory"
    udir = os.path.join( tmpd, "user" )
    if os.path.exists( udir ):
        shutil.rmtree( udir )

def remove_gunk( tmpd ):
    "Remove unnecessary files"
    rem = [ ".gitignore", "*.pyc", "*~", "#*#", "log.txt*", ".*.swp", "*.save" ]
    r = " -o ".join( [ "-name '%s' -print0 " % x for x in rem ] )

    assert subprocess.call( "find . %s | xargs -0 rm -f" % r, cwd = tmpd, shell = True ) == 0

def get_elf_mach( elfname ):
    "Return the machine that the given ELF is for"
    r = re.compile( "Machine:\s*(.+)$" )

    o = subprocess.check_output( "readelf -h '%s' | grep 'Machine:'" % elfname, shell = True )

    mach = r.search( o ).group(1)
    return mach

def strip_binary( elfpath ):
    "Strip the given binary"

    strippers = { "Texas Instruments msp430 microcontroller": "msp430-strip",
                  "ARM": "arm-angstrom-linux-gnueabi-strip" }

    mach = get_elf_mach( elfpath )
    if mach not in strippers:
        return

    # Ignore errors: It's non-fatal if stuff doesn't strip
    err = open("/dev/null", "w")
    subprocess.call( "%s '%s'" % ( strippers[mach], elfpath ), shell = True,
                         stdout = err, stderr = err )

def strip_binaries( tmpd ):
    "Strip debug symbols from all the ARM binaries"

    for dirpath, dirnames, filenames in os.walk(tmpd):
        for fname in filenames:
            fpath = os.path.join( dirpath, fname )

            ftype = subprocess.check_output( "file '%s'" % fpath, shell = True )

            if "ELF" in ftype:
                "It's an ELF file"
                strip_binary(fpath)

def create_zip( source_dir, target_file ):
    # Temporary directory for the zipfile to reside in
    ziptmpd = tempfile.mkdtemp( suffix="-pyenv" )
    tmpzip = os.path.join( ziptmpd, "robot.zip" )

    try:
        subprocess.check_call( ["zip", "-9qr", tmpzip, "./"], cwd = source_dir )

        if os.path.exists( target_file ):
            os.unlink( target_file )

        shutil.move( tmpzip, target_file )
    finally:
        shutil.rmtree( ziptmpd )

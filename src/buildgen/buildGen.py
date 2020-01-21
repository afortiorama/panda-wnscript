#!/bin/bash

"exec" "python" "-u" "$0" "$@"

import os
import sys
import time
import getopt
import uuid
try:
    import urllib.request as urllib
except ImportError:
    import urllib
try:
    from urllib.request import urlopen
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import urlopen, HTTPError
from pandawnutil.wnmisc.misc_utils import commands_get_status_output, get_file_via_http

# error code
EC_MissingArg  = 10
EC_CMTFailed   = 20
EC_NoTarball   = 30
EC_NoROOT      = 40

print ("--- start ---")
print (time.ctime())

debugFlag = False
sourceURL = 'https://gridui01.usatlas.bnl.gov:25443'
runDir    = ''
bexec     = ''
useAthenaPackages = False
rootVer   = ''
useRootCore = False
cmtConfig = ''
noCompile = False
useMana   = False
manaVer   = ''
useCMake  = False

# command-line parameters
opts, args = getopt.getopt(sys.argv[1:], "i:o:u:r:",
                           ["pilotpars","debug","oldPrefix=","newPrefix=",
                            "directIn","sourceURL=","lfcHost=","envvarFile=",
                            "bexec=","useAthenaPackages",
                            "useFileStager","accessmode=",
                            "rootVer=","useRootCore","cmtConfig=",
                            "noCompile","useMana","manaVer=",
                            "useCMake"])
for o, a in opts:
    if o == "-i":
        sources = a
    if o == "-o":
        libraries = a
    if o == "-r":
        runDir = a
    if o == "--bexec":
        bexec = urllib.unquote(a)
    if o == "--debug":
        debugFlag = True
    if o == "--sourceURL":
        sourceURL = a
    if o == "--useAthenaPackages":
        useAthenaPackages = True
    if o == "--rootVer":
        rootVer = a 
    if o == "--useRootCore":
        useRootCore = True
    if o == "--cmtConfig":
        cmtConfig = a
    if o == "--noCompile":
        noCompile = True
    if o == "--useMana":
        useMana = True
    if o == "--manaVer":
        manaVer = a
    if o == "--useCMake":
        useCMake = True

# dump parameter
try:
    print ("sources",sources)
    print ("libraries",libraries)
    print ("debugFlag",debugFlag)
    print ("sourceURL",sourceURL)
    print ("runDir",runDir)
    print ("bexec",bexec)
    print ("useAthenaPackages",useAthenaPackages)
    print ("rootVer",rootVer)
    print ("useRootCore",useRootCore)
    print ("cmtConfig",cmtConfig)
    print ("noCompile",noCompile)
    print ("useMana",useMana)
    print ("manaVer",manaVer)
    print ("useCMake",useCMake)
except:
    sys.exit(EC_MissingArg)

# save current dir
currentDir = os.getcwd()

print ("Running in %s" % currentDir)

print ("--- wget ---")
print (time.ctime())


# compile Athena packages
if useAthenaPackages and not noCompile:
    # get TRF
    trfName    = 'buildJob-00-00-03'
    trfBaseURL = 'http://pandaserver.cern.ch:25080/trf/user/'
    url = trfBaseURL+trfName
    get_file_via_http(full_url=url)
    # execute
    commands_get_status_output('chmod +x %s' % trfName)
    if useCMake:
        tmpLibName = libraries
    else:
        tmpLibName = 'tmplib.%s' % str(uuid.uuid4())
    com = "./%s -i %s -o %s --debug --sourceURL %s " % (trfName,sources,tmpLibName,sourceURL)
    if useCMake:
        com += '--useCMake '
    print ("--- Compile Athena packages ---")
    print (time.ctime())
    print (com)
    if debugFlag:
        status = os.system(com)
    else:
        status,output = commands_get_status_output(com)
        print (output)
    if not useCMake:
        commands_get_status_output('rm -f %s' % tmpLibName)
    status %= 255    
    if status != 0:
        print ("--- failed to compile Athena packages %s ---" % status)
        print (time.ctime())
        # return
        sys.exit(status)
    print ("--- Successfully compiled Athena packages ---")
    print (time.ctime())
    if useCMake:
        sys.exit(status)
else:
    # get source files
    url = '%s/cache/%s' % (sourceURL, sources)
    print ('getting sandbox file from {0}'.format(url))
    tmpStat, tmpOut = get_file_via_http(full_url=url)
    if not tmpStat:
        print ("ERROR : " + tmpOut)
        sys.exit(EC_NoTarball)

# get root
useCvmfsROOT = False
if rootVer != '':
    print ('')
    print ("--- setting ROOT version name ---")
    if rootVer.count('.') != 2:
        rootVer += ".00"
    rootTgz = "root_v" + rootVer    
    # CVMFS version format
    if cmtConfig == '':
        print ("Use i686-slc5-gcc43-opt for ROOT by default when --cmtConfig is unset")
        rootCVMFS = rootVer + '-' + 'i686-slc5-gcc43-opt'
    else:
        rootCVMFS = rootVer + '-' + cmtConfig
    useCvmfsROOT = True
    print ("->",rootCVMFS)
    print ('')
    
# goto work dir
workDir = currentDir + '/workDir'
if not useAthenaPackages:
    print (commands_get_status_output('rm -rf %s' % workDir)[-1])
    os.makedirs(workDir)
print ("Goto workDir",workDir)
os.chdir(workDir)

# expand root 
if rootVer != '':
    rootBinDir = workDir + '/pandaRootBin'
    os.makedirs(rootBinDir)
    if not useCvmfsROOT:
        os.chdir(rootBinDir)
        commands_get_status_output('tar xvfzm %s/%s' % (currentDir,rootTgz))
        os.chdir(workDir)

# expand sources
if not useAthenaPackages or noCompile:
    print ("--- expand source ---")
    print (time.ctime())
    if sources.startswith('/'):
        out = commands_get_status_output('tar xvfzm %s' % sources)[-1]
    else:
        out = commands_get_status_output('tar xvfzm %s/%s' % (currentDir,sources))[-1]
    print (out)

# create cmt dir to setup Athena
setupEnv = ''
if useAthenaPackages:
    tmpDir = '%s/%s/cmt' % (workDir, str(uuid.uuid4()))
    print ("Making tmpDir",tmpDir)
    os.makedirs(tmpDir)
    # create requirements
    oFile = open(tmpDir+'/requirements','w')
    oFile.write('use AtlasPolicy AtlasPolicy-*\n')
    oFile.close()
    # setup command
    setupEnv  = 'export CMTPATH=%s:$CMTPATH; ' % workDir
    setupEnv += 'cd %s; cmt config; source ./setup.sh; cd -; ' % tmpDir

# setup root
if rootVer != '':
    if useCvmfsROOT:
        tmpSetupEnvStr  = "export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase; "
        tmpSetupEnvStr += "source $ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh --quiet; "
        tmpSetupEnvStr += "source $ATLAS_LOCAL_ROOT_BASE/packageSetups/atlasLocalROOTSetup.sh --rootVersion=%s --skipConfirm; " % rootCVMFS
        # check ROOT ver
        print ('')
        print ("--- check ROOT availability ---")
        print (tmpSetupEnvStr)
        tmpRootStat = os.system(tmpSetupEnvStr)
        tmpRootStat %= 255
        if tmpRootStat != 0:
            print ("ERROR : ROOT %s is unavailable on CVMFS" % rootCVMFS)
            sys.exit(EC_NoROOT)
        setupEnv += tmpSetupEnvStr
        setupEnv += "root.exe -q; "
        # keep setup str for runGen
        oFile = open('%s/pandaUseCvmfSetup.sh' % rootBinDir,'w')
        oFile.write(tmpSetupEnvStr)
        oFile.close()
    else:
        setupEnv += ' export ROOTSYS=%s/root; export PATH=$ROOTSYS/bin:$PATH; export LD_LIBRARY_PATH=$ROOTSYS/lib:$LD_LIBRARY_PATH; root.exe -q; ' % \
                    rootBinDir

# init status
status = 0

# make if needed
if status == 0 and (bexec != '' or useRootCore):
    if not useMana:
        print ("--- print env ---")
        print (commands_get_status_output(setupEnv+'env')[-1])
    print ("--- make ---")
    print (time.ctime())
    # make rundir just in case
    if runDir != '':
        commands_get_status_output('mkdir %s' % runDir)
    # go to run dir
    os.chdir(runDir)
    print ("PWD=%s" % os.getcwd())
    # add current dir to PATH
    os.environ['PATH'] = '.:'+os.environ['PATH']
    # make RootCore
    compileExec = ''
    if useRootCore:
        pandaRootCoreWD = os.path.abspath('%s/__panda_rootCoreWorkDir' % os.getcwd())
        if noCompile:
            compileExec = 'source %s/RootCore/scripts/grid_compile_nobuild.sh %s' % (pandaRootCoreWD,pandaRootCoreWD)
        else:
            compileExec = 'source %s/RootCore/scripts/grid_compile.sh %s' % (pandaRootCoreWD,pandaRootCoreWD)
    if bexec != '':                
        # chmod +x just in case
        commands_get_status_output('chmod +x %s' % bexec.split()[0])
        if compileExec != '':
            compileExec = compileExec + '; ' + bexec
        else:
            compileExec = bexec
    # execute
    if compileExec != '':
        print ("execute : "+setupEnv+compileExec)
        if debugFlag:
            status = os.system(setupEnv+compileExec)
        else:
            status,out = commands_get_status_output(setupEnv+compileExec)
            print (out)
        status %= 255
        if status != 0:
            print ("ERROR : make failed")
    # back to workdir
    os.chdir(workDir)

print ("--- archive libraries ---")
print (time.ctime())

# archive
if libraries.startswith('/'):
    commands_get_status_output('tar cvfz %s *' % libraries)
else:
    commands_get_status_output('tar cvfz %s/%s *' % (currentDir,libraries))

# go back to current dir
os.chdir(currentDir)

# remove workdir
if not debugFlag:
    commands_get_status_output('rm -rf %s' % workDir)

# remove root
if rootVer != '':
    commands_get_status_output('rm -rf %s' % rootTgz)
    
print ("--- finished with %s ---" % status)
print (time.ctime())

# return
sys.exit(status)

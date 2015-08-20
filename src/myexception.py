from messaging_lib import *

class MyException(Exception):
    '''A user-defined exception class.'''
    def __init__(self, msg=None):
        Exception.__init__(self)
        if (not (msg is None)):
          print msg


# SSH exceptions:
class SSHException(Exception):
    '''Exception for SSH errors'''
    def __init__(self):
        Exception.__init__(self)
class SSHConnectionException(Exception):
    '''Exception for SSH connection errors'''
    def __init__(self):
        Exception.__init__(self)
class SSHCrucialConnectionException(Exception):
    '''Exception for crucial SSH connection errors'''
    def __init__(self):
        Exception.__init__(self)

# SCP exceptions:
class SCPException(Exception):
    '''Exception for SCP connection errors'''
    def __init__(self):
        Exception.__init__(self)
class SCPCrucialException(Exception):
    '''Exception for SCP connection errors'''
    def __init__(self):
        Exception.__init__(self)

# SSH qstat exceptions:
class SSHQstatException(Exception):
    '''Exception for receiving unexpected output from "qstat -a" via SSH'''
    def __init__(self):
        Exception.__init__(self)

# Exception for exceeded disk quota on a cluster:
class DiskQuotaException(Exception):
    '''Exception when disk quota on a machine/cluster was exceeded'''
    def __init__(self):
        Exception.__init__(self)

# Exception for Tar operations:
class TarException(Exception):
    '''Exception for unknown/crucial tar operations'''
    def __init__(self):
        Exception.__init__(self)
class TarCrucialException(Exception):
    '''Exception for unknown/crucial tar operations'''
    def __init__(self):
        Exception.__init__(self)

# Email setup Exception:
class Email_Report_Exception(Exception):
    '''Exception for Email reports errors'''
    def __init__(self):
        Exception.__init__(self)
        print 'Email_Report_exception encountered!'

# Exception that should be raised when any kind of error/exception 
# occured during the manipulation of files:
class FileOperationException(Exception):
    '''Exception for any kind of exception while manipulating files'''
    def __init__(self):
        Exception.__init__(self)
# Or the one below if files where not found etc.:
class LocalOperationException(Exception):
    '''Exception for events when files were not found etc.'''
    def __init__(self):
        Exception.__init__(self)

# Exception that should be used during the waiting time 
# between iterations of processing all registered simulations:
class WaitBetweenQueryException(Exception):
    '''Exception for any exception during the waiting time until the next
       iteration of looping over all directories/simulations to monitor
    '''
    def __init__(self, msg=None):
        Exception.__init__(self)
        print 'Exception during the waiting time until the next iteration of monitoring starts.'
        if (not (msg is None)):
            print msg

# Exception which should be raised when an error was found in the
# cluster stdout/stderr files:
class CheckClusterForSimulationRunningException(Exception):
    '''Exception for errors/exceptions during qstat -a on the cluster'''
    def __init__(self):
        Exception.__init__(self)

# Exception which should be raised when an error was found in the
# cluster stdout/stderr files:
class SimulationError(Exception):
    '''Exception for error found in stdout/stderr files'''
    def __init__(self):
        Exception.__init__(self)

class CheckForSimulationErrorException(Exception):
    '''Exception for exceptions during method check_for_simulation_error'''
    def __init__(self):
        Exception.__init__(self)

# Some more classes that refer to unknown errors that were encountered during
# specific methods:
class SCPDataFromClusterException(Exception):
    '''Exception for unknown errors during method "scp_data_from_cluster"'''
    def __init__(self):
        Exception.__init__(self)

# Exception for an unknown exception occured during the trial to clean up 
# the directory on the cluster:
class CleanClusterDirException(Exception):
    '''Exception for unknown errors during method "clean_cluster_dir"'''
    def __init__(self):
        Exception.__init__(self)




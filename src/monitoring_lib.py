import os
import commands
import sys
import time
sys.path.append("/data/fmilthaler/fluidity-trunk/python/")
sys.path.append("/data/fmilthaler/Projects-Code/scripting-library/python/")
# Import other self written modules:
from io_routines import *
from pgf_io_routines import *
from messaging_lib import *
from myexception import *
## Requires libspud to be installed:
import libspud



class Monitoring:
  """ A class for monitoring and maintaining simulations until they are finished, meaning
      their specified finish time has been reached. This class comprehends all the required
      operations:
       * sending simulation files to a cluster
       * starting the simulation on a cluster
       * checking if the simulation is still running
       * if not, the results are packaged and sent back to the local machine, where
       * the results are analysed and checked if errors occured
       * in case of an error, the user has to fix the simulation manually, and once done
         has to create a file 'is_fixed' in the corresponding directory on the local machine
         such that the program picks the simulation up again and continues maintaining it,
       * or if the simulation finished successfully on the cluster, redundant checkpoint
         files are removed, results of the .stat/.detectors/.detectors.dat files are
         appended to the previous files, and checks if the finish time has been reached,
       * if the finish time has not been reached, the script packages the most recent
         checkpoint files and sends it back to the cluster to continue running the
         simulation.
       * Log- and error files are written to a directory 'logfiles'.
       * If an email address is given, crucial email reports are sent to the user, which
         is recommended,
       * If enabled, popups appear on the users screen with crucial steps in the maintainance
         of a simulation
       * In case of a reboot of the local machine, or ending the running script, it can be
         restarted, and if log/error files are present in the directory 'logfiles', it
         works out the status of each simulation, and continues from that point onwards.
       * Bkup files of the most recent checkpoint files as well as result files
         (stat/detectors/detectors.dat) can be found in a subdirectory 'bkup'.
  """
  def __init__(self, dirbasename, username, cluster_name, cluster_dir, cluster_fluidity_dir='', dir='', simname='', jobid='', simulation_running=False, simulation_crashed=False, simulation_finished=False, ncpus='---', nnopercpu=15000, errmaxcnt=100, errwaittime=0.01, query_waittime=60, verbosity=3, emailaddress=None, sendemail=True, popupmsg=False):
    # Constructor
    self._dirbasename = dirbasename

    self.dir = dir
    self.simname = simname
    self.jobid = jobid
    self.cluster_status = 'Q'
    self.cluster_walltime = '---'
    self.sim_time = 0.0
    self.simulation_running = simulation_running
    self.simulation_crashed = simulation_crashed
    self.simulation_finished = simulation_finished
    self.pbs_walltime = '72:00:00' # default value
    self.nmachines = '---' # if not set by user, it'll read it in from preset pbs.sh
    self.ncpus = ncpus
    self.memory = '---' # if not set by user, it'll read it in from preset pbs.sh
    self.total_ncpus = ncpus # default value
    self.infiniband = '---' # default value
    self.queue = None # if not set by user, it'll read it in from preset pbs.sh
    self.mpiprocs = ncpus # default value, only for cx2
    self.ompthreads = 1 # default value, only for cx2
    self.nnopercpu = nnopercpu
    # Variables for error handling:
    self.errmaxcnt = errmaxcnt
    self.errwaittime = errwaittime
    # Wait time between two rounds of checking all simulations:
    self.query_waittime = query_waittime
    # Variable for location of error:
    self.error_status = 0
    self.sim_clean_exit = False
    # Cluster variables:
    self.cluster_name = cluster_name
    self.cluster_dir = cluster_dir
    self.cluster_fluidity_dir = cluster_fluidity_dir
    self.username = username

    # Create an object for writing/sending reports:
    try:
      self.messaging = Messaging(verbosity, emailaddress=emailaddress, sendemail=sendemail, popupmsg=popupmsg)
      self.set_report_props(verbosity=verbosity, emailaddress=emailaddress, sendemail=sendemail, popupmsg=popupmsg)
    except Email_Report_Exception:
      #errmsg = "Caught Email_Report_Exception"
      #raise Email_Report_Exception(errmsg)
      # Error output was written, then exit the program, as this exception is highly unwanted,
      # e.g. sendemail==True, but email given is invalid!
      raise SystemExit

    # Set up dictionary:
    self.dict = self.construct_sim_dict(dirbasename)
    # Set up folders:
    # only do this IFF no log/error files are in the logfiles directory,
    # this means, that the simulations have not previously run
    continue_monitoring = self.check_if_previously_ran()
    if (continue_monitoring):
      # If simulations ran before, then get data either from dict_status_*
      # or log files:
      self.set_dict_from_dict_status()
    else:
      self.set_up_initial_subdirs(dirbasename)

    # Define columns of the dictionary to print in the pgf table which
    # gives an overview of all simulations:
    self.table_header = ['dirname', 'jobid', 'status', 'walltime', 'sim_time', 'nmachines', 'ncpus', 'mpiprocs', 'total_ncpus', 'memory', 'infiniband', 'error_status', 'sim_clean_exit']

  def set_cluster_props(self, username, cluster_name, cluster_dir, cluster_fluidity_dir):
    self.cluster_name = cluster_name
    self.cluster_dir = cluster_dir
    self.cluster_fluidity_dir = cluster_fluidity_dir
    self.username = username

  def set_report_props(self, verbosity=3, emailaddress=None, sendemail=True, popupmsg=True):
    """
        A method in order to set variables for reporting/messaging/logging.
        The input arguments are forwarded to the class Messaging, where
        its variables are set as well.
        Input:
         verbosity: Integer which determines the verbosity level
         emailaddress: String of email addresses separated by a semicolon, or a 
           list of email addresses to send the reports to
         sendemail: Boolean if emails are wanted or not
         popupmsg: Boolean if popup messages of reports are wanted or not
    """    
    try:
      self.verbosity = verbosity
      if (not emailaddress is None and sendemail):
        (sendemail, email) = self.messaging.check_email_setup(emailaddress)
        self.sendemail = sendemail
        self.email = email
      else:
        self.sendemail = False
        self.email = None
      self.popupmsg = popupmsg
      # Update variables in class Messaging:
      self.messaging.update_massaging_properties(verbosity=verbosity, emailaddress=emailaddress, sendemail=sendemail, popupmsg=popupmsg)
    except Email_Report_Exception:
      #errmsg = "Caught Email_Report_Exception"
      #raise Email_Report_Exception(errmsg)
      # Error output was written, then exit the program, as this exception is highly unwanted,
      # e.g. sendemail==True, but email given is invalid!
      raise SystemExit

  def set_up_initial_subdirs(self, dirbasename):
    """ Creates bkup-folders for all simulation folders,
        plus a folder 'logfiles' in their parent directory,
        in which log/error files of the monitoring are
        stored.
        Input:
         dirbasename: The common name of directories the
           script should monitor/maintain
    """
    (dirnames, status) = find_dir_names('./', dirbasename+'* -maxdepth 0')
    if (status != 0):
      printc("====================================================================", "red", False)
      print
      printc(" Aborting the whole operation, no directory with input string found ", "red", False)
      print
      printc("====================================================================", "red", False)
      print
      # Do NOT even start the script!!!
      raise SystemExit()
    for dir in sort_string_list(dirnames):
      # Create 'bkup' folder in 'dir':
      out = commands.getoutput('cd '+dir+'/; mkdir bkup')
    out = commands.getoutput('mkdir logfiles')


  def construct_sim_dict(self, dirbasename=None):
    if (dirbasename is None):
      dirbasename = self.dirbasename
    (dirnames, status) = find_dir_names('./', dirbasename+'* -maxdepth 0')
    if (status != 0):
      raise SystemExit("Could not find any directories nor symlinks that match the searchstring '"+dirbasename+"'.")
    dict = {}
    for dir in sort_string_list(dirnames):
      # This gets pbs parameters from preset pbs.sh scripts, which can be overwritten by calling the function
      # 'update_sim_properties'
      (pbs_simname, pbs_walltime, nmachines, ncpus, memory, total_ncpus, mpiprocs, ompthreads, queue, status) = self.get_simname_walltime_ncpus_pbs(dir, pbs_filename='pbs.sh')
      # Set up dictionary:
      dict.update({dir : {'simname' : '---', 'jobid' : '---', 'status' : '', 'walltime' : '---', 'sim_time' : '---', 'simulation_running' : False, 'simulation_crashed' : False, 'simulation_finished' : False, 'pbs_walltime' : pbs_walltime, 'nmachines' : nmachines, 'ncpus' : ncpus, 'memory' : memory, 'total_ncpus' : total_ncpus, 'mpiprocs' : mpiprocs, 'ompthreads' : ompthreads, 'nnopercpu' : self.nnopercpu, 'infiniband' : False, 'queue' : queue, 'error_status' : 0, 'cluster_name' : self.cluster_name, 'cluster_fluidity_dir' : self.cluster_fluidity_dir, 'cluster_dir' : self.cluster_dir, 'sim_clean_exit' : False}})
    return dict


  def set_sim_properties_from_dict(self, dir):
    self.dir = dir
    self.simname = self.dict[dir]['simname']
    self.jobid = self.dict[dir]['jobid']
    self.cluster_status = self.dict[dir]['status']
    self.cluster_walltime = self.dict[dir]['walltime']
    self.sim_time = self.dict[dir]['sim_time']
    self.simulation_running = self.dict[dir]['simulation_running']
    self.simulation_crashed = self.dict[dir]['simulation_crashed']
    self.simulation_finished = self.dict[dir]['simulation_finished']
    self.pbs_walltime = self.dict[dir]['pbs_walltime']
    self.nmachines = self.dict[dir]['nmachines']
    self.ncpus = self.dict[dir]['ncpus']
    self.memory = self.dict[dir]['memory']
    self.total_ncpus = self.dict[dir]['total_ncpus']
    self.mpiprocs = self.dict[dir]['mpiprocs']
    self.ompthreads = self.dict[dir]['ompthreads']
    self.nnopercpu = self.dict[dir]['nnopercpu']
    self.infiniband = self.dict[dir]['infiniband']
    self.queue = self.dict[dir]['queue']
    self.cluster_name = self.dict[dir]['cluster_name']
    self.cluster_dir = self.dict[dir]['cluster_dir']
    self.cluster_fluidity_dir = self.dict[dir]['cluster_fluidity_dir']
    self.error_status = self.dict[dir]['error_status']
    self.sim_clean_exit = self.dict[dir]['sim_clean_exit']


  def update_sim_properties(self, dir, simname=None, jobid=None, simulation_running=None, simulation_crashed=None, simulation_finished=None, pbs_walltime=None, nmachines=None, ncpus=None, memory=None, total_ncpus=None, mpiprocs=None, ompthreads=None, nnopercpu=None, infiniband=None, queue=None, sim_time=None, cluster_status=None, cluster_walltime=None, cluster_name=None, cluster_dir=None, cluster_fluidity_dir=None, error_status=None, sim_clean_exit=None):
    # Then, reset variables based on given variables:
    if (not (simname is None)):
      self.simname = simname
      self.dict[dir].update({'simname' : simname})
    if (not (jobid is None)):
      self.jobid = jobid
      self.dict[dir].update({'jobid' : jobid})
    if (not (cluster_status is None)):
      self.cluster_status = cluster_status
      self.dict[dir].update({'status' : cluster_status})
    if (not (cluster_walltime is None)):
      self.cluster_walltime = cluster_walltime
      self.dict[dir].update({'walltime' : cluster_walltime})
    if (not (sim_time is None)):
      self.sim_time = sim_time
      self.dict[dir].update({'sim_time' : sim_time})
    if (not (simulation_running is None)):
      self.simulation_running = simulation_running
      self.dict[dir].update({'simulation_running' : simulation_running})
    if (not (simulation_crashed is None)):
      self.simulation_crashed = simulation_crashed
      self.dict[dir].update({'simulation_crashed' : simulation_crashed})
    if (not (simulation_finished is None)):
      self.simulation_finished = simulation_finished
      self.dict[dir].update({'simulation_finished' : simulation_finished})
    if (not (pbs_walltime is None)):
      self.pbs_walltime = pbs_walltime
      self.dict[dir].update({'pbs_walltime' : pbs_walltime})
    if (not (nmachines is None)):
      self.nmachines = nmachines
      self.dict[dir].update({'nmachines' : nmachines})
    if (not (ncpus is None)):
      self.ncpus = ncpus
      self.dict[dir].update({'ncpus' : ncpus})
    if (not (memory is None)):
      self.memory = memory
      self.dict[dir].update({'memory' : memory})
    if (not (total_ncpus is None)):
      self.total_ncpus = total_ncpus
      self.dict[dir].update({'total_ncpus' : total_ncpus})
    if (not (mpiprocs is None)):
      self.mpiprocs = mpiprocs
      self.dict[dir].update({'mpiprocs' : mpiprocs})
    if (not (ompthreads is None)):
      self.ompthreads = ompthreads
      self.dict[dir].update({'ompthreads' : ompthreads})
    if (not (nnopercpu is None)):
      self.nnopercpu = nnopercpu
      self.dict[dir].update({'nnopercpu' : nnopercpu})
    if (not (infiniband is None)):
      self.infiniband = infiniband
      self.dict[dir].update({'infiniband' : infiniband})
    if (not (queue is None)):
      self.queue = queue
      self.dict[dir].update({'queue' : queue})
    if (not (cluster_name is None)):
      self.cluster_name = cluster_name
      self.dict[dir].update({'cluster_name' : cluster_name})
    if (not (cluster_dir is None)):
      self.cluster_dir = cluster_dir
      self.dict[dir].update({'cluster_dir' : cluster_dir})
    if (not (cluster_fluidity_dir is None)):
      self.cluster_fluidity_dir = cluster_fluidity_dir
      self.dict[dir].update({'cluster_fluidity_dir' : cluster_fluidity_dir})
    if (not (error_status is None)):
      self.error_status = error_status
      self.dict[dir].update({'error_status' : error_status})
    if (not (sim_clean_exit is None)):
      self.sim_clean_exit = sim_clean_exit
      self.dict[dir].update({'sim_clean_exit' : sim_clean_exit})


  def update_dict(self, dir, simname=None, jobid=None, cluster_status=None, cluster_walltime=None, sim_time=None, simulation_running=None, simulation_crashed=None, simulation_finished=None, pbs_walltime=None, nmachines=None, ncpus=None, memory=None, total_ncpus=None, mpiprocs=None, ompthreads=None, nnopercpu=None, infiniband=None, queue=None, cluster_name=None, cluster_dir=None, cluster_fluidity_dir=None, error_status=None, sim_clean_exit=None):
    if (simname is None):
      simname = self.simname
    if (jobid is None):
      jobid = self.jobid
    if (cluster_status is None):
      cluster_status = self.cluster_status
    if (cluster_walltime is None):
      cluster_walltime = self.cluster_walltime
    if (sim_time is None):
      sim_time = self.sim_time
    if (simulation_running is None):
      simulation_running = self.simulation_running
    if (simulation_crashed is None):
      simulation_crashed = self.simulation_crashed
    if (simulation_finished is None):
      simulation_finished = self.simulation_finished
    if (pbs_walltime is None):
      pbs_walltime = self.pbs_walltime
    if (nmachines is None):
      nmachines = self.nmachines
    if (ncpus is None):
      ncpus = self.ncpus
    if (memory is None):
      memory = self.memory
    if (total_ncpus is None):
      total_ncpus = self.total_ncpus
    if (mpiprocs is None):
      mpiprocs = self.mpiprocs
    if (ompthreads is None):
      ompthreads = self.ompthreads
    if (nnopercpu is None):
      nnopercpu = self.nnopercpu
    if (infiniband is None):
      infiniband = self.infiniband
    if (queue is None):
      queue = self.queue
    if (cluster_name is None):
      cluster_name = self.cluster_name
    if (cluster_dir is None):
      cluster_dir = self.cluster_dir
    if (cluster_fluidity_dir is None):
      cluster_fluidity_dir = self.cluster_fluidity_dir
    if (error_status is None):
      error_status = self.error_status
    if (sim_clean_exit is None):
      sim_clean_exit = self.sim_clean_exit
    self.dict[dir].update({'simname' : simname})
    self.dict[dir].update({'jobid' : jobid})
    self.dict[dir].update({'status' : cluster_status})
    self.dict[dir].update({'walltime' : cluster_walltime})
    self.dict[dir].update({'sim_time' : sim_time})
    self.dict[dir].update({'simulation_running' : simulation_running})
    self.dict[dir].update({'simulation_crashed' : simulation_crashed})
    self.dict[dir].update({'simulation_finished' : simulation_finished})
    self.dict[dir].update({'pbs_walltime' : pbs_walltime})
    self.dict[dir].update({'nmachines' : nmachines})
    self.dict[dir].update({'ncpus' : ncpus})
    self.dict[dir].update({'memory' : memory})
    self.dict[dir].update({'total_ncpus' : total_ncpus})
    self.dict[dir].update({'mpiprocs' : mpiprocs})
    self.dict[dir].update({'ompthreads' : ompthreads})
    self.dict[dir].update({'nnopercpu' : nnopercpu})
    self.dict[dir].update({'infiniband' : infiniband})
    self.dict[dir].update({'queue' : queue})
    self.dict[dir].update({'cluster_name' : cluster_name})
    self.dict[dir].update({'cluster_dir' : cluster_dir})
    self.dict[dir].update({'cluster_fluidity_dir' : cluster_fluidity_dir})
    self.dict[dir].update({'error_status' : error_status})
    self.dict[dir].update({'sim_clean_exit' : sim_clean_exit})



  def get_sim_properties(self, dir):
    """ Returns all simulation properties according to 'dir'.
        Input:
         dir: Current directory name
        Output:
         simname: Current simulation name
         jobid: Current jobid
         cluster_status: Current cluster status
         cluster_walltime: Current cluster elapsed walltime
         time: Current simulation time
         simulation_running: Current boolean if simulation is running
         simulation_crashed: Current boolean if simulation is crashed
         simulation_finished: Current boolean if simulation is finished
         pbs_walltime: String of the walltime in the pbs script
         nmachines: Current integer of how many nodes/machines the sim is running on
         ncpus: Current integer of cores per machine/node
         memory: String of how much memory should be used by the simulation
         total_ncpus: Current integer of nmachines*ncpus
         mpiprocs: Integer of how many mpiprocs should be used per node
         ompthreads: Integer of how many omp threads should be used per proc per node
         nnopercpu: Desired number of nodes of the coordinate mesh per cpu
         infiniband: Logical of whether infiniband is enabled or not
         queue: String of the queue name on which the simulation should run
         cluster_name: Address of the cluster where to run 'dir'
         cluster_dir: Directory on the cluster where the simulation dir is stored
         cluster_fluidity_dir: Directory of the Fluidity branch on the cluster
         error_status: Integer indicating where in the main loop it had an error
         sim_clean_exit: False if the program exited unsafely during self.dir, True otherwise
    """
    return self.simname, self.jobid, self.cluster_status, self.cluster_walltime, self.sim_time, self.simulation_running, self.simulation_crashed, self.simulation_finished, self.pbs_walltime, self.nmachines, self.ncpus, self.memory, self.total_ncpus, self.mpiprocs, self.ompthreads, self.nnopercpu, self.infiniband, self.queue, self.cluster_name, self.cluster_dir, self.cluster_fluidity_dir, self.error_status, self.sim_clean_exit


  def get_dict(self, dir=None):
    """ This method return the dictionary holding crucial monitoring properties.
        If the input argument 'dir' is given, a 1 dimensional dictionary of 
        all the properties corresponding to that particular simulation are returned,
        else a 2 dimensional dictionary is return which holds all properties
        for all simulations which are monitored/maintained by this class.
        Input:
         dir: String of a directory name in which one particular simulation sits in.
        Output:
         self.dict/self.dict[dir]: A dictionary (1D/2D) holding crucial monitoring
           properties.
    """
    if (not (dir is None)):
      return self.dict[dir]
    else:
      return self.dict
    


  def check_if_previously_ran(self, dir=None):
    """ This method checks if there are dictionary log files
        in the default directory 'logfiles'. If there are,
        then a boolean True is returned, and False otherwise
        Input:
         dir: String of the corresponding simulation directory
           for which the dictionary log file is searched for.
           Optional argument with default value 'None', if dir is
           not given, then any dictionary log file is searched for.
        Output:
         continue_monitoring: Boolean that is True if 
           at least one dictionary file was found, 
           and False otherwise.
    """
    if (dir is None): # dir was not given
      # Check for any dictionary status files:
      (statusfiles, status) = find_file_names('logfiles', 'dict_status_* -maxdepth 0 -not -name "dict_status_table*"')
      if (status == 0):
        continue_monitoring = True
      else:
        continue_monitoring = False
    else: # specific dir was given:
      # Check for 'dir' specific dictionary status file:
      (statusfiles, status) = find_file_names('logfiles', 'dict_status_'+dir+' -maxdepth 0 -not -name "dict_status_table*"')
      if (status == 0):
        continue_monitoring = True
      else:
        continue_monitoring = False
    return continue_monitoring


  def set_dict_from_dict_status(self):
    """ This method sets the dictionary for all simulations based on the
        dict_status_* files, that are dumped when the program exits safely.
    """
    for dir in self.dict.keys():
      # Get latest recorded information from dict_status_* files:
      (jobid, simulation_running, simulation_crashed, simulation_finished, simname, sim_time, pbs_walltime, nmachines, ncpus, memory, total_ncpus, mpiprocs, ompthreads, nnopercpu, infiniband, queue, cluster_status, cluster_walltime, cluster_name, cluster_dir, cluster_fluidity_dir, error_status, sim_clean_exit) = self.get_status_from_dict_status(dir)

      # Update variables:
      self.update_sim_properties(dir, simname=simname, jobid=jobid, cluster_status=cluster_status, cluster_walltime=cluster_walltime, sim_time=sim_time, simulation_running=simulation_running, simulation_crashed=simulation_crashed, simulation_finished=simulation_finished, pbs_walltime=pbs_walltime, nmachines=nmachines, ncpus=ncpus, memory=memory, total_ncpus=total_ncpus, mpiprocs=mpiprocs, ompthreads=ompthreads, nnopercpu=nnopercpu, infiniband=infiniband, queue=queue, cluster_name=cluster_name, cluster_dir=cluster_dir, cluster_fluidity_dir=cluster_fluidity_dir, error_status=error_status, sim_clean_exit=sim_clean_exit)

      # Update dictionary:
      self.update_dict(dir, simname=simname, jobid=jobid, cluster_status=cluster_status, cluster_walltime=cluster_walltime, sim_time=sim_time, simulation_running=simulation_running, simulation_crashed=simulation_crashed, simulation_finished=simulation_finished, pbs_walltime=pbs_walltime, nmachines=nmachines, ncpus=ncpus, memory=memory, total_ncpus=total_ncpus, mpiprocs=mpiprocs, ompthreads=ompthreads, nnopercpu=nnopercpu, infiniband=infiniband, queue=queue, cluster_name=cluster_name, cluster_dir=cluster_dir, cluster_fluidity_dir=cluster_fluidity_dir, error_status=error_status, sim_clean_exit=sim_clean_exit)


  def get_status_from_dict_status(self, dir):
    """ This method read in the status for all crucial variables from the
        dict_status_dirname file
        Input:
         dir: Name of directory of corresponding simulation
        Output:
         jobid: String of cluster jobID the simulation last had
         simulation_running: Boolean determining if the simulation last
           was running
         simulation_crashed: Boolean determining if the simulation last
           was flagged as 'crashed/broken'
         simulation_finished: Boolean determining if the simulation was
           flagged as finished.
         simname: The current simulation_name in the latest checkpoint
           flml file.
         sim_time: Elapsed seconds of simulation time
         pbs_walltime: String of the walltime in the pbs script
         nmachines: Current integer of how many nodes/machines the sim is running on
         ncpus: Current integer of cores per machine/node
         memory: String of how much memory should be used by the simulation
         total_ncpus: Current integer of nmachines*ncpus
         mpiprocs: Integer of how many mpiprocs should be used per node
         ompthreads: Integer of how many omp threads should be used per proc per node
         nnopercpu: Desired number of nodes of the coordinate mesh per cpu
         queue: String of the queue name on which the simulation should run
         status: Cluster status, either Q, R, or F (queueing, running,
           finished)
         walltime: Elapsed walltime on the cluster
         error_status: Error status, indicates location of error
         cluster_name: Name/Address of the cluster where to run the
           simulation that is in the local directory 'dir'
         cluster_dir: Directory on the cluster where the simulation dir is stored
         cluster_fluidity_dir: Absolute path of the Fluidity directory
           that should be used for the simulation of the local directory
           'dir'.
         sim_clean_exit: True/False depends on whether the program exited
           safely the last time it ran during processing the simulation of
           'dir'.
    """
    # Filename of dictionary status:
    statusfilename = 'dict_status_'+dir
    # check if the file exists:
    (files, status) = find_file_names('logfiles', statusfilename+' -maxdepth 0 -not -name "dict_status_table*"')
    # if file was does not exist, use initial values for parameters:
    if (not status == 0):
      simname = self.dict[dir]['simname']
      jobid = self.dict[dir]['jobid']
      status = self.dict[dir]['status']
      walltime = self.dict[dir]['walltime']
      sim_time = self.dict[dir]['sim_time']
      simulation_running = self.dict[dir]['simulation_running']
      simulation_crashed = self.dict[dir]['simulation_crashed']
      simulation_finished = self.dict[dir]['simulation_finished']
      pbs_walltime = self.dict[dir]['pbs_walltime']
      nmachines = self.dict[dir]['nmachines']
      ncpus = self.dict[dir]['ncpus']
      memory = self.dict[dir]['memory']
      total_ncpus = self.dict[dir]['total_ncpus']
      mpiprocs = self.dict[dir]['mpiprocs']
      ompthreads = self.dict[dir]['ompthreads']
      nnopercpu = self.dict[dir]['nnopercpu']
      infiniband = self.dict[dir]['infiniband']
      queue = self.dict[dir]['queue']
      cluster_name = self.dict[dir]['cluster_name']
      cluster_dir = self.dict[dir]['cluster_dir']
      cluster_fluidity_dir = self.dict[dir]['cluster_fluidity_dir']
      error_status = self.dict[dir]['error_status']
      sim_clean_exit = self.dict[dir]['sim_clean_exit']
      # And create bkup directory for this simulation, as we have to assume this is new:
      out = commands.getoutput('cd '+dir+'/; mkdir bkup')
    else: # if the corresponding dictionary log file exists, extract data from it:
      # Open file:
      statusfile = open('logfiles/'+statusfilename, 'r')
      statusfilelines = statusfile.readlines()
      # Close logfile:
      statusfile.close()
      mpiprocs = None; ompthreads = None
      for line in statusfilelines:
        if (not (line == '\n' or line.split() == [])):
          if (line.split()[0].startswith('ncpus:')):
            ncpus = int(line.split()[-1])
          elif (line.split()[0].startswith('total_ncpus:')):
            total_ncpus = int(line.split()[-1])
          elif (line.split()[0].startswith('mpiprocs:')):
            mpiprocs = int(line.split()[-1])
          elif (line.split()[0].startswith('ompthreads:')):
            ompthreads = int(line.split()[-1])
          elif (line.split()[0].startswith('nmachines:')):
            nmachines = int(line.split()[-1])
          elif (line.split()[0].startswith('nnopercpu:')):
            nnopercpu = line.split()[-1]
          elif (line.split()[0].startswith('memory:')):
            memory = line.split()[-1]
          elif (line.split()[0].startswith('infiniband:')):
            infiniband = line.split()[-1]
          elif (line.split()[0].startswith('pbs_walltime:')):
            pbs_walltime = line.split()[-1]
          elif (line.split()[0].startswith('queue:')):
            queue = line.split()[-1]
          elif (line.split()[0].startswith('jobid:')):
            jobid = line.split()[-1]
          elif (line.split()[0].startswith('simulation_running:')):
            simulation_running = line.split()[-1] == 'True'
          elif (line.split()[0].startswith('simulation_crashed:')):
            simulation_crashed = line.split()[-1] == 'True'
          elif (line.split()[0].startswith('simulation_finished:')):
            simulation_finished = line.split()[-1] == 'True'
          elif (line.split()[0].startswith('simname:')):
            simname = line.split()[-1]
          elif (line.split()[0].startswith('sim_time:')):
            sim_time = line.split()[-1]
          elif (line.split()[0].startswith('status:')):
            status = line.split()[-1]
          elif (line.split()[0].startswith('walltime:')):
            walltime = line.split()[-1]
          elif (line.split()[0].startswith('cluster_name:')):
            cluster_name = line.split()[-1]
          elif (line.split()[0].startswith('cluster_dir:')):
            cluster_dir = line.split()[-1]
          elif (line.split()[0].startswith('cluster_fluidity_dir:')):
            cluster_fluidity_dir = line.split()[-1]
          elif (line.split()[0].startswith('error_status:')):
            error_status = int(line.split()[-1])
          elif (line.split()[0].startswith('sim_clean_exit:')):
            sim_clean_exit = line.split()[-1] == 'True'
      if (mpiprocs is None): mpiprocs = ncpus
      if (ompthreads is None): ompthreads = 1
    return jobid, simulation_running, simulation_crashed, simulation_finished, simname, sim_time, pbs_walltime, nmachines, ncpus, memory, total_ncpus, mpiprocs, ompthreads, nnopercpu, infiniband, queue, status, walltime, cluster_name, cluster_dir, cluster_fluidity_dir, error_status, sim_clean_exit


  def run_monitoring(self):
    """ This method starts the method to loop over all simulations,
        while this method mainly is to catch all possible exceptions 
        that were raised in main_monitoring_loop, that way we can
        do some post-exception tasks and also watch the main loop for
        any custom-defined exception as well as other exception, such
        as KeyboardInterrupt/SystemExit and others.
    """
    # Try running the program and catch certain events:
    try:

      self.main_monitoring_loop()

    except WaitBetweenQueryException:
      # Log/error files have been written and sent out already,
      # here nothing else needs to be done:
      msg = '# Program exited safely #'
      hashes = self.get_hashes(msg)
      msg = hashes+'\n'+msg+'\n'+hashes
      subject = 'Program exited safely'
      msgtype='log'
      exit()
    except CheckClusterForSimulationRunningException:
      # Exception occured during "qstat -a" on the cluster:
      msg = 'Error: A crucial Exception/Error occured during method "check_cluster_for_simulation_running".\nProgram exiting...'
      subject = 'Exception during check_cluster_for_simulation_running'
      msgtype='err'
      raise SystemExit()
    except SCPDataFromClusterException:
      # Unknown exception/error occured during the method 'scp_data_from_cluster'.
      msg = 'Error: Unknown Exception/Error occured during method "scp_data_from_cluster".\nProgram exiting...'
      subject = 'Exception during scp_data_from_cluster'
      msgtype='err'
      raise SystemExit()
    except CheckForSimulationErrorException:
      # Error during checking for simulation errors was found:
      msg = 'Error: An error occured during the process of checking if an error occured during the runtime of the simulation.\nProgram exiting...'
      subject = 'Exception during check_for_simulation_error'
      msgtype='err'
      raise SystemExit()
    except CleanClusterDirException:
      # Error during checking for simulation errors was found:
      msg = 'Error: A crucial error occured during the process of removing the directory on the cluster.\nProgram exiting...'
      subject = 'Exception during clean_cluster_dir'
      msgtype='err'
      raise SystemExit()
    except SystemExit:
      msg = '# ERROR: SystemExit signal received #'
      hashes = self.get_hashes(msg)
      msg = hashes+'\n'+msg+'\n'+hashes
      subject = 'SystemExit caught'
      msgtype='err'
      raise SystemExit()
    except KeyboardInterrupt:
      msg = '# ERROR: KeyboardInterrupt signal received #'
      hashes = self.get_hashes(msg)
      msg = hashes+'\n'+msg+'\n'+hashes
      subject = 'KeyboardInterrupt Exception caught'
      msgtype='err'
      raise SystemExit()
    except:
      msg = '# ERROR: Unknown exception caught in "run_monitoring" #'
      hashes = self.get_hashes(msg)
      msg = hashes+'\n'+msg+'\n'+hashes
      subject = 'Unknown Exception caught'
      msgtype='err'
      raise SystemExit()
    else:
      # Monitoring is done, postprocessing all the results can start:
      msg = '# All simulations have successfully finished #'
      hashes = self.get_hashes(msg)
      msg = hashes+'\n'+msg+'\n'+hashes
      subject = 'All simulations finished'
      msgtype='log'
    # In any case, do:
    finally:
      # Get current dictionary:
      mydict = self.get_dict()
      # Setting the status clean_exit of all other simulations to 'True':
      for dir in mydict.keys():
        if (not (dir == self.dir)):
          self.update_sim_properties(dir=dir, sim_clean_exit=True)
          # And update dict-file of that directory/simulation:
          self.write_simulation_status_to_file(dir=dir)
      # Update local dictionary:
      mydict = self.get_dict()
      # Also, update the pgf table:
      self.write_dict_status_pgftable(mydict, printcols=self.table_header, pdflatex=True, pdfcrop=True)
      attachment = 'logfiles/cropped_dict_status_table.pdf'
      # Distribute the error assembled message:
      self.messaging.message_handling(self.dir, msg, 0, msgtype=msgtype, subject=subject, attachment=attachment)



  def main_monitoring_loop(self):
    """ This method loops over all entries in the dictionary,
        thus over all directories associated with this script/operation,
        and it also catches user-defined exceptions from within called
        methods in order to catch certain events. In such cases, it
        throws another exception to the method which calls this one,
        which then can do further error-handling. This allows to get 
        a proper error-handling and based on that, reports will identify
        which operation in which called method caused trouble. 
        A proper error handling for this script is more than important,
        as this script might run for months at a time. Thus other methods
        are also in place in case the script crashes/is stopped/the machine
        is rebooted, and the script is able to pick up the monitoring from 
        where it stopped. Exactly for achieving a 'clean exit' the
        many different exception are raised in order to pin point the error
        and do certain steps after exceptions occured.
        This method has no input and no return values.
    """
    all_simulation_finished = False
    waittime_between_query = self.query_waittime

    ran_previously = self.check_if_previously_ran()
    first_iteration = True
    #first_run = not ran_previously
    first_run = True

    # Get dictionary:
    mydict = self.get_dict()

    # Loop until all simulation in all subdirectories have finished:
    while (not all_simulation_finished):
      # Loop over all directories in the current directory:
      for dir in sort_string_list(mydict.keys()):

        # set first_run boolean, to check if this simulation has run before:
        if (first_iteration):
          first_run = not self.check_if_previously_ran(dir)

        # Update the current simulation properties, and dictionary
        self.set_sim_properties_from_dict(dir)
        # Get paramerters of the current simulation:
        (simname, jobid, cluster_status, cluster_walltime, time,
              simulation_running, simulation_crashed, simulation_finished,
              pbs_walltime, nmachines, ncpus, memory, total_ncpus, mpiprocs,
              ompthread, nnopercpu, infiniband, queue, cluster_name, cluster_dir,
              cluster_fluidity_dir, error_status, sim_clean_exit) = self.get_sim_properties(dir)


        # If the simulation has been flagged as finished, continue:
        if (simulation_finished):
          continue

        # Now set the sim_clean_exit status for this simulation to False:
        if (not first_iteration):
          sim_clean_exit = False
          self.update_sim_properties(dir=dir, sim_clean_exit=sim_clean_exit)
          self.write_simulation_status_to_file(dir=dir) # And write this to file!

        # Get "qstat -a" from cluster to check which simulations are running:
        # simulation_running = True/False
        if (error_status in [0, 1]):
          try:
            (simulation_running, status) = self.check_cluster_for_simulation_running()
          except SSHConnectionException:
            # This exception means that the service is currently either not available,
            # or hammered and thus is too busy to respond in time, so set 
            # error_status accordingly and skip next steps in the monitoring:
            error_status = 1
            # And skip the rest of routine calls:
            continue
          except SSHQstatException:
            # This exception was thrown because the output from "qstat -a" did not 
            # contain excepted substrings, thus something went wrong, and we should
            # check again later...
            error_status = 1
            # And skip the rest of routine calls:
            continue
          except SSHCrucialConnectionException:
            # This exception indicates that there is sth seriously wrong, e.g.
            # username, clustername, etc.
            # Thus in such an event, quit the program and give the user an appropriate
            # error message:
            error_status = 1; sim_clean_exit = True
            # Raise the exception that will be caught in the main loop:
            raise CheckClusterForSimulationRunningException
          except:
            # Unexpected exception caught, set variables and throw exception for this operation:
            error_status = 1; sim_clean_exit = True
            raise CheckClusterForSimulationRunningException
          else: # If no exception was caught:
            if (status != 0): error_status = 1
            else: error_status = 0
            sim_clean_exit = True
          finally: # In any case, update error_status and sim_clean_exit:
            # Update error status and sim_clean_exit status in Monitoring class
            self.update_sim_properties(dir, simulation_running=simulation_running, error_status=error_status, sim_clean_exit=sim_clean_exit)
            # Write status to file:
            self.write_simulation_status_to_file(dir=dir)
          # skip to next simulation if this simulation is marked as "running":
          if (simulation_running):
            sim_clean_exit = True
            # skip next steps only if running on cx1:
            if ('cx1' in cluster_name.lower()):
              continue

        # Print directory that is being processed in the terminal:
        print "\n\n"
        terminalmsg = "| Processing dir = %s |" % dir
        terminaloutline = self.get_ascii_string(terminalmsg, character='=')
        print terminaloutline+'\n'+terminalmsg+'\n'+terminaloutline

        # If simulation is not running, scp data/results to local machine
        if (not simulation_crashed and not first_run and error_status in [0, 2]):
          try:
            status = self.scp_data_from_cluster(cluster_name, self.cluster_dir, dir, simname, running=simulation_running)
          except (SSHConnectionException, SCPException, LocalOperationException, TarCrucialException):
            # These exceptions are just an indicator for the cluster not responding,
            # or that the just scp'ed file was not found on the local machine
            # so set error_status and skip following task, until the next iteration 
            # when this process will be repeated:
            error_status = 2
            # And skip the rest of routine calls:
            continue
          except (SSHCrucialConnectionException, SCPCrucialException, DiskQuotaException):
            # These exceptions indicate that the setup/permissions must be wrong, or the
            # disk quota on the cluster is exceeded, or an unknown error was found
            # during the operation.
            # This can only be fixed by the user/through debugging:
            error_status = 2; sim_clean_exit = True
            # Exit program:
            raise SCPDataFromClusterException
          except:
            # Any other exception/error that occured during that operation:
            error_status = 2; sim_clean_exit = True
            raise SCPDataFromClusterException
          else: # If no exception was caught:
            if (status != 0): error_status = 2
            else: error_status = 0
          finally: # In any case, update error_status and sim_clean_exit:
            # Update error status and sim_clean_exit status in Monitoring class
            self.update_sim_properties(dir, error_status=error_status, sim_clean_exit=sim_clean_exit)
            # Write status to file:
            self.write_simulation_status_to_file(dir=dir)
            # skip to next simulation if this simulation is still "running":
          if (simulation_running):
            sim_clean_exit = True
            continue


        # Check for simulation failure:
        if (not simulation_crashed and not first_run and error_status in [0, 3]):
          # Check for simulation crash:
          try:
            simulation_crashed = self.check_for_simulation_error(dir)
            # If simulation_crashed is true, raise exception:
            if (simulation_crashed):
              raise SimulationError
          except SimulationError:
            # Set error_status to 3:
            error_status = 3
            # And if an error was found, set simulation_crashed to True,
            # plus skip/continue to the next iteration, as the simulation must be fixed manually!
            simulation_crashed = True
            continue
          except:
            # Either any exception was caught, or disk quota was exceeded:
            error_status = 3; sim_clean_exit = True
            raise CheckForSimulationErrorException # Program will end!
          else:
            error_status = 0
          finally: # In any case, update error_status and sim_clean_exit:
            # Update error status and sim_clean_exit status in Monitoring class
            self.update_sim_properties(dir, error_status=error_status, sim_clean_exit=sim_clean_exit)
            # Write status to file:
            self.write_simulation_status_to_file(dir=dir)
        # If simulation has been flagged as crashed previously, check if it has been taken care of manually:
        elif (simulation_crashed and error_status in [0, 3, 4, 6]): 
          simulation_crashed = self.check_fixed_sim(dir)
          if (simulation_crashed): error_status = 3 # sim is still flagged as crashed
          else:
            error_status = 0 # sim was manually fixed!
            # Update simulation_crashed and error_status in Monitoring class:
            self.update_sim_properties(dir, error_status=error_status, simulation_crashed=simulation_crashed)
            # Write status to file:
            self.write_simulation_status_to_file(dir=dir)
            # Also, remove fluidity output files from 'dir' that belong the previous run (the one that crashed!):
            self.remove_previous_fluidity_output_files(dir=dir)

##########################################
# Continue here!                         #
##########################################
        # Append data from stat/detector files to previous files:
        if (not simulation_crashed and not first_run):
          if (error_status in [0, 4]):
            simulation_crashed = self.append_resfiles(dir, simname)
            if (simulation_crashed): error_status = 4
    #          errormsg = 'Error: An error occured during the attempt to append results from stat/detector files.'
    #          subject = 'Error'
    #          monitor.send_email(dir, email, errormsg='err', subject=subject)
    #          monitor.notify_popup(subject, errormsg)
            else: error_status = 0
            # Update error status in Monitoring class
            self.update_sim_properties(dir, error_status=error_status)
          if (error_status in [0, 5]):
            # Rename checkpoint:
            status = self.renaming_checkpoint(dir, simname, ncpus)
            if (status != 0): error_status = 5
            else: error_status = 0
            # Update error status in Monitoring class
            self.update_sim_properties(dir, error_status=error_status)

        # Check if the simulation has finished finished, plus get latest checkpoint flml filename:
        if (not simulation_crashed and error_status in [0, 6]):
          # Make some required changes, e.g. change flml in pbs-script, append stat-file to previous-statfile,
          # change simulation name in checkpointed flml-file, rename vtu files such that they are 
          # corresponding to the previous run, copy bkup files to ./dir/bkup/ ...:
          try:
            (simulation_finished, tar_filename) = self.postprocess_simulation(dir, cluster_name=cluster_name)
          except SSHConnectionException:
            error_status = 6
            continue
          except SSHCrucialConnectionException:
            error_status = 6; sim_clean_exit = True
            raise CleanClusterDirException
          except:
            # Unexpected exception caught, set variables and throw exception for this operation:
            error_status = 6; sim_clean_exit = True
            raise CleanClusterDirException
          else: # If no exception was caught:
            error_status = 0
          finally: # In any case, update error_status and sim_clean_exit:
            # Update error status and sim_clean_exit and status in Monitoring class
            self.update_sim_properties(dir, error_status=error_status, sim_clean_exit=sim_clean_exit)
            # Write status to file:
            self.write_simulation_status_to_file(dir=dir)

        # Send the tar file to cluster and submit job to the queue:
        if (not simulation_crashed and not simulation_finished and error_status in [0, 7]):
          # If error_status is 7, make sure the tar_filename is set correctly (otherwise it would crash when restarting the script with error status being 7)
          if (error_status == 7):
            tar_filename = dir+'.tar' # default value of tar_filename
          try:
            (jobid, simulation_crashed, status) = self.submit_on_cluster(cluster_name, self.cluster_dir, dir, tar_filename)
          except DiskQuotaException:
            print 'Exiting program. Fix disk quota on cluster '+cluster_name
            exit()
          except:
            print 'Error: Unknown error found during submit_on_cluster'
            exit()
          if (status != 0): error_status = 7
          else: error_status = 0
          # Update error status in Monitoring class
          self.update_sim_properties(dir, error_status=error_status)
          if (error_status == 0):
            simulation_running = True
            # Clean up the directory on local machine, and make copy of tarfile and stat/detectors* files in ./dir/bkup/:
            self.clean_and_bkup_local_dir(dir, tar_filename)
          else:
            simulation_running = False
        elif (simulation_finished and error_status == 0):
          # Final clean up of local directory:
          self.clean_and_bkup_local_dir(dir, tar_filename)

        # If it reaches here, the current simulation finished its iteration without exceptions/error:
        # Setting sim_clean_exit variable for this simulation to True:
        self.update_sim_properties(dir=dir, sim_clean_exit=True)
        # End of for loop: Store values in dictionary:
#        self.update_dict(dir=dir, jobid=jobid, simulation_running=simulation_running, simulation_crashed=simulation_crashed, simulation_finished=simulation_finished)
        # Update this directory:
        mydict = self.get_dict()

        # Write status to file:
        self.write_simulation_status_to_file(dir=dir)


      # Update table for overall status/overview:
      self.write_dict_status_pgftable(mydict, printcols=self.table_header, pdflatex=True, pdfcrop=True)


      # Loop over all entries in the dictionary and find out if all simulations
      # have been finished, and if so, exit the while loop and start the 
      # analysis:
      simulations_finished = []
      for name in mydict.keys():
        # assembling the list of simulation_finished status:
        simulations_finished.append(mydict[name]['simulation_finished'])
      # Make absolutely sure, that the entries are only true, if the entry in the dictionary
      # was set to 'True', otherwise, it should be 'False'
      simulations_finished = [True if i==True else False for i in simulations_finished]
      if (all(simulations_finished)):
        all_simulation_finished = True


      if (not all_simulation_finished):
        # Wait condition, so that we do not hammer the cluster with queries:
        try:
          self.wait_between_query(waittime=waittime_between_query)
        except WaitBetweenQueryException:
          errormsg = 'WaitBetweenQueryException caught. Clean exit.'
          # Write dictionary status to files for safely continueing to monitor
          # all simulations later:
          # Not needed anymore, as we dump a status file at the end of each iteration
          # that way we are always up to date with the status files, and moreover,
          # in case sth goes wrong, the status file is already in place
          # self.write_dict_status_to_file()
          # Assemble report:
          message = '# Clean exit: Status files of simulations have been dumped to ./logfiles/dict_status_* #'
          hashes = self.get_hashes(message)
          message = hashes+'\n'+message+'\n'+hashes
          self.messaging.message_handling('.', message, 0, msgtype='log', subject='Clean exit')
          # raise the same exception again:
          raise WaitBetweenQueryException
        except: # Should never get here!
          print 'Other unknown exception caught'
          # Exit the program:
          exit()

        # End of while loop, now all simulation have been set up:
        first_run = False
        first_iteration = False

  # End of main monitoring loop


  def get_simname_walltime_ncpus_pbs(self, dir=None, pbs_filename='pbs.sh'):
    """ Parses a given pbs-script to find the pbs-simname, 
        and the specified number of cpus, and returns the
        both, simname and total number of processes the
        simulation in running on, which is number of 
        machines * number of cpus (per machine)
        Input:
         dir: String of the directory name where the pbs
           script is in.
         pbs_filename(optional): overwrites the default value
           'pbs.sh' in case the filename of the pbs script
           is not 'pbs.sh'.
        Output:
         pbs_simname: String of the set simname in the pbs.sh
         pbs_walltime: String of the walltime in the pbs.sh
         nmachines: Integer of how many machines/nodes are used
         ncpus: Integer of how many cores per machines/nodes are used
         memory: String of how much memory should be used
         total_ncpus: Integer of the total number of 
           processes the simulation runs on
         mpiprocs: Integer of how many mpiprocs should be used per node
         ompthreads: Integer of how many omp threads should be used per proc per node
         queue: String of the queue the simulation should run on,
           if it was set in the pbs script
         status: Integer which is 0, if the simname and ncpus 
           were successfully extracted from the pbs-script.
    """
    if (dir is None):
      dir = self.dir
    # Check if this is for cx1/2 or hector:
    if ('cx1' in self.cluster_name or 'cx2' in self.cluster_name):
      ict = True; hector = False
    elif ('hector' in self.cluster_name):
      ict = False; hector = True
    else:
      raise SystemExit("In 'get_simname_walltime_ncpus_pbs', could not recognize value of 'cluster_name': "+str(self.cluster_name))
    # Start processing:
    # Initializing some job specific variables in case they are not read from the pbs file:
    nmachines=self.nmachines; ncpus=self.ncpus; memory=self.memory
    mpiprocs=self.mpiprocs; ompthreads=self.ompthreads
    # status variable and initializing total number of cores used:
    status = 1; total_ncpus = -1
    searchstring_simname = '#PBS -N' # search for pbs simname
    searchstring_walltime = '#PBS -l walltime='
    if (ict):
      searchstring_ncpus = '#PBS -l select' # search for this in the pbs script
    elif (hector):
      searchstring_nprocs = '#PBS -l mppwidth' # search for this in the pbs script
      searchstring_ncpupn = '#PBS -l mppnppn' # search for this in the pbs script
    searchstring_queue = '#PBS -q'
    queue_string_found = False
    if (ict):
      all_searchstrings = [searchstring_simname, searchstring_walltime, searchstring_ncpus, searchstring_queue]
    elif (hector):
      all_searchstrings = [searchstring_simname, searchstring_walltime, searchstring_nprocs, searchstring_ncpupn, searchstring_queue]

    # Load in lines of pbs file:
    pbsfile = open(dir+'/'+pbs_filename, 'r')
    pbslines = pbsfile.readlines()
    pbsfile.close()

    # Now loop over lines, and search for 'searchstring':
    for line in pbslines:
      line = line.strip()
      if (not (any([(searchstring in line) and True for searchstring in all_searchstrings]))):
        continue
      if (line.find(searchstring_simname) >= 0):
        pbs_simname = line.split('#PBS -N')[-1].split(' ')[-1]
      elif (searchstring_walltime in line):
        pbs_walltime = line.split('#PBS -l walltime=')[-1].split('#')[0]
      elif (searchstring_queue in line):
        # Setting specific pbs queue:
        if (line.startswith(searchstring_queue)):
          queue_string_found = True
          if (str(self.queue) == 'None'):
            queue = line.split(searchstring_queue)[-1].split('#')[0]
          else: queue = str(self.queue)
      elif ((ict and searchstring_ncpus in line) or (hector and searchstring_ncpupn in line or hector and searchstring_nprocs in line)):
        # first, check for ICT clusters:
        if (ict):
          if (not ('ncpus' in line)):
            continue # if 'ncpus' is not part of 'line', skip this line as well!
          else: # This line now has the number of cpus and machines:
            try:
              # Get number of machines the sim is running on:
              nmachines = int(line.split('select=')[-1].split(':')[0])
              # And the number of cpus per machine:
              ncpus = int(line.split('ncpus=')[-1].split(':')[0])
              # The following two are optional and in general only valid for cx2:
              if (line.find('mpiprocs=')>=0):
                # And mpiprocs:
                mpiprocs = int(line.split('mpiprocs=')[-1].split(':')[0])
              else:
                mpiprocs = ncpus
              if (line.find('ompthreads=')>=0):
                # And ompthreads:
                ompthreads = line.split('ompthreads=')[-1].split(':')[0]
              else:
                ompthreads = 1
              # And the memory:
              memory = line.split('mem=')[-1].split(':')[0]
              if (ncpus == mpiprocs): actual_ncpus_pnode = ncpus
              else: actual_ncpus_pnode = mpiprocs
              total_ncpus = nmachines * actual_ncpus_pnode
              # Set status = 0, indicating successful operation:
              status = 0
            except:
              errormsg = 'Error: Could not converts nmachines, ncpus found in pbs script to integers!'
              self.messaging.write_to_log_err_file(dir, errormsg, msgtype='err')
        elif (hector):
          if (not ('mppwidth' in line or 'mppnppn' in line)):
            continue # skip lines without those strings in it
          else: # This line now has the number of total cpus or cpus per machine:
            try:
              # Get the total number of processes the sim is running on:
              if (searchstring_nprocs in line):
                total_ncpus = int(line.split('mppwidth=')[-1])
              # And the number of cpus per machine:
              elif (searchstring_ncpupn in line):
                ncpus = int(line.split('mppnppn=')[-1])
              # Now compute the number of machines we are requesting:]
              nmachines = int(total_ncpus/float(ncpus))
              memory = 'NAN'
              mpiprocs = ncpus; ompthreads = 1
              # Set status = 0, indicating successful operation:
              status = 0
            except:
              errormsg = 'Error: Could not converts nmachines, ncpus found in pbs script to integers!'
              self.messaging.write_to_log_err_file(dir, errormsg, msgtype='err')
    if (not queue_string_found):
      queue = str(self.queue)
    return pbs_simname, pbs_walltime, nmachines, ncpus, memory, total_ncpus, mpiprocs, ompthreads, queue, status


  def check_for_simulation_error(self, dir=None):
    """ This subroutines parses the stdout and stderr
        files for distinctive strings that indicate
        a simulation crash
        Input:
         dir: String of the directory to check for 
           stdout and stderr files
        Output:
         simulation_crashed: Logical which is True if an error
           occured.
    """
    if (dir is None):
      dir = self.dir
    # Logical for errors, true if sign of error was found:
    error_found = False
    # First check if stdout and stderr are present:
    (filenames, status) = find_file_names(dir, 'stdout stderr')
    if (status != 0):
      error_found = True
      errormsg = "ERROR: Files 'stdout/stderr' were not found!"
    # Now check stdout/stderr for distinctive strings indicating errors:
    if (not error_found):
      cmd = 'fgrep "caused collective abort" '+dir+'/stdout'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.rfind("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: 'Collective abort' found in file: "+dir+"/stdout"
    # Second check the stderr file for any signs of errors
    if (not error_found):
      cmd = 'fgrep "*** ERROR ***" '+dir+'/stderr'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.rfind("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: '*** ERROR ***' found in file: "+dir+"/stderr"
    # Also the fluidity error file of course
    if (not error_found):
      cmd = 'fgrep "*** ERROR ***" '+dir+'/fluidity.err-*'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.rfind("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: '*** ERROR ***' found in file: "+dir+"/fluidity.err-*"
    if (not error_found):
      cmd = 'fgrep "error" '+dir+'/fluidity.err-*'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.rfind("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: 'error' found in file: "+dir+"/fluidity.err-*"
    # different kinds of errors we can expect:
    if (not error_found):
      cmd = 'fgrep "ERROR:" '+dir+'/stderr'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.rfind("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: 'ERROR:' found in file: "+dir+"/stderr"
    # Checking if executable could not be run:
    if (not error_found):
      cmd = 'fgrep "cannot be run." '+dir+'/stdout'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.find("No such file or directory") == -1):
        error_found = True
        errormsg = "ERROR: 'Executable could not be run' found in file: "+dir+"/stdout"
#    # And checking, if PBS allocated nodes for the job, if not, it didn't run at all:
#    if (not error_found):
#      cmd = 'fgrep "PBS has allocated the following nodes:" '+dir+'/stdout'
#      shellout = commands.getoutput(cmd)
#      if (shellout == '' or shellout.find("PBS has allocated the following nodes:") == -1):
#        error_found = True
#        errormsg = "ERROR: 'PBS did not allocate any nodes; file: "+dir+"/stdout"
    # And finally, check for exceeded disk quota error:
    # Also check the stderr for an error message indicating the memory limit was exceeded:
    if (not error_found):
      cmd = 'fgrep "PBS: job killed: mem" '+dir+'/stderr | grep "exceeded limit"'
      shellout = commands.getoutput(cmd)
      if ('PBS: job killed: mem' in shellout):
        error_found = True
        errormsg = "ERROR: Memory limit was exceeded."
    if (not error_found):
      cmd = 'fgrep "Disk quota exceeded" '+dir+'/stdout '+dir+'/stderr'
      shellout = commands.getoutput(cmd)
      if (shellout != '' and shellout.find("Disk quota exceeded:")>=0):
        # Update simulation properties:
        self.update_sim_properties(dir, jobid='---', cluster_status='E', simulation_crashed=simulation_crashed)
        # Give an appropriate error message:
        # Disk quota on cluster exceeded, so raise exception and quit program as this needs to be solved manually
        errormsg = 'Error: Disk quota on '+cluster_name+' was exceeded. Clean up your space.'
        # Get current dictionary:
        mydict = self.get_dict()
        # Also, update the pgf table:
        self.write_dict_status_pgftable(mydict, printcols=self.table_header, pdflatex=True, pdfcrop=True)
        attachment = 'logfiles/cropped_dict_status_table.pdf'
        self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject='DiskQuotaException caught', attachment=attachment)
        # This is the most crucial case, as if this occurs, the program should stop,
        # as this has to be fixed manually by deleting some other stuff on the cluster.
        # Thus raise an appropriate exception which will be dealt with in the main loop:
        raise DiskQuotaException

    # Check if the string "Job terminated normally" can be found in stdout:
    if (not error_found):
      if ('cx1' in self.cluster_name):
        searchstring = "Job terminated normally"
        cmd = 'fgrep "'+searchstring+'" '+dir+'/stdout'
        shellout = commands.getoutput(cmd)
        if (shellout == ''):
          error_found = True
      elif ('cx2' in self.cluster_name):
        searchstrings = ["aborting job", "terminated", "Killed"]
        for ss in searchstrings:
          cmd = 'fgrep "'+ss+'" '+dir+'/stdout'
          shellout = commands.getoutput(cmd)
          if (shellout != ''):
            error_found = True
      if (error_found): # If error was found based on stdout/log, find out if it might be due to memory issues:
        # So in this case, check for the following:
        # If at this point, no error was detected from the stdout/stderr files, let's dig a bit deeper, 
        # and check the simulation time, walltime limit settings and check if the simulation
        # ended before any of the above were reached.... which then indicates an error:
        last_flml_filename = self.parse_flml_files(dir)
        current_simtime = self.get_current_time_from_flml(dir, last_flml_filename)
        finish_simtime = self.get_finish_time_from_flml(dir, last_flml_filename)
        walltime_limit = self.get_walltime_limit_from_flml(dir, last_flml_filename)
        # Now compare those to get an idea if the simulation crashed without error message:
        # converting current walltime to seconds:
        try:
          current_walltime_h = float(self.cluster_walltime.split(':')[0])
          current_walltime_min = float(self.cluster_walltime.split(':')[-1])
          current_walltime = current_walltime_h*3600.0 + current_walltime_min*60.0
          # Since we only the simulations every once in a while, take that into accout:
          current_walltime = current_walltime + float(self.query_waittime)
          # Now the same for the pbs_walltime
          pbs_walltime_h = float(self.pbs_walltime.split(':')[0])
          pbs_walltime_min = float(self.pbs_walltime.split(':')[1])
          pbs_walltime_s = float(self.pbs_walltime.split(':')[-1])
          pbs_walltime = pbs_walltime_h*3600.0 + pbs_walltime_min*60.0 + pbs_walltime_s
          # For the pbs_walltime, we allow 15min grace, since that is an option in the pbs-script:
          pbs_walltime = pbs_walltime - 15*60.0
          # Also subtract the query_waittime from the walltime limit set in the flml,
          # otherwise we might run into a problem we shouldn't:
          walltime_limit = walltime_limit - 2*float(self.query_waittime)
          

          # First we need to check if the finish time in the schema was reached:
          check_pbs_walltime = False
          if (current_simtime < finish_simtime):
            if (not (walltime_limit == False) ): # walltime_limit is False, if no walltime_limit was set in the schema
              # Then checking if the walltime_limit is smaller than the pbs_walltime:
              if (walltime_limit < pbs_walltime):
                # Now we can check if the current walltime is less than the walltime_limit:
                if (current_walltime < walltime_limit):
                  # Then we suspect this simulation to have exited for the wrong reason!
                  error_found = True
              else:
                # Here we have to check against the pbs_walltime instead:
                if (current_walltime < pbs_walltime):
                  # Then we suspect this simulation to have exited for the wrong reason!
                  error_found = True
            elif (current_walltime < pbs_walltime):
              # Then we suspect this simulation to have exited for the wrong reason!
              error_found = True
          # Appropriate error message:
          if (error_found):
            errormsg = 'I have a strong suspicion that the simulation in directory '+dir+' crashed for\n'
            errormsg = errormsg+'some reason. It did not reach the finish time, nor the walltime limit or pbs walltime limit.'
        except:
          errormsg = 'Error: Could not convert current walltime/pbs_walltime of dictionary into seconds.'
          errormsg = errormsg+'\nA crucial error might have occured or not.'

    if (error_found):
      simulation_crashed = True
      # Also set the class variables jobid, cluster_status, and simulation_crashed:
      self.update_sim_properties(dir, jobid='---', cluster_status='E', simulation_crashed=simulation_crashed)
      # Error message:
      errormsg = '***Error: Simulation in '+dir+' CRASHED\n***Has to be fixed manually!\nError: This Simulation has been flagged as crashed and has to be taken care of manually!\nThe following error was found:\n'+errormsg
      # Get current dictionary:
      mydict = self.get_dict()
      # Also, update the pgf table:
      self.write_dict_status_pgftable(mydict, printcols=self.table_header, pdflatex=True, pdfcrop=True)
      pdftable = 'logfiles/cropped_dict_status_table.pdf'
      self.messaging.message_handling(dir, errormsg, 0, msgtype='err', attachment=dir+'/stdout '+dir+'/stderr '+pdftable, subject='Error')
      # Now raise an exception which indicates that an error was found during the process of checking the 
      # stdout and stderr files:
      raise SimulationError
    else:
      simulation_crashed = False
      # Set the class variables jobid, cluster_status, and simulation_crashed:
      self.update_sim_properties(dir, jobid='---', cluster_status='---', simulation_crashed=simulation_crashed)
      # Log message:
      msg = 'Simulation in '+dir+' exited normally'
      self.messaging.message_handling(dir, msg, 2, msgtype='log', subject='Sim ran normally')
    # If it gets here, no exceptions were thrown, meaning no simulation error should have been found:
    return simulation_crashed


  def get_res_file_extension(self, dir=None):
    """ This subroutines looks for possible files with data
        in the given directory 'dir' and passes back a list
        of the found file extensions that are present in the
        directory.
        Input:
         dir: String of the directory to check for files
        Output:
         extensions: List of the found file extensions in 
           the directory 'dir'
    """
    if (dir is None):
      dir = self.dir
    status = 0
    extensions = []
    (statfiles, status) = get_file_names(dir+'/*stat')
    if (status == 0):
      extensions.append('stat')
    (detfiles, status) = get_file_names(dir+'/*detectors')
    if (status == 0):
      extensions.append('detectors')
    (detfiles, status) = get_file_names(dir+'/*detectors.dat')
    if (status == 0):
      extensions.append('detectors.dat')
    return extensions


  def parse_flml_files(self, dir=None):
    """ This subroutines finds and parses all
        flml files in the input argument and
        identifies and returns the filename of
        the flml file with the largest current time.
        Input:
         dir: name of the directory where the flml
           files are in
        Output:
         checkpoint_flml: String of the flml-filename
           with the largest current_time.
    """
    if (dir is None):
      dir = self.dir
    highest_current_time = -1.0
    (flml_files, status) = get_file_names(dir+'/*flml')
    if (status == 0):
      for flml in flml_files:
        # Get current time...
        current_time = self.get_current_time_from_flml(dir, flml)
        # ... and finish time
        #finish_time = self.get_finish_time_from_flml(dir, flml)
        # Save the flml file with the largest current time, as this might be
        # checkpointed:
        if (current_time > highest_current_time):
          highest_current_time = current_time
          checkpoint_flml = flml
    else: 
      errormsg = 'Error: Could not find flml files in directory '+dir
      printc(errormsg, 'red', False); print
      checkpoint_flml = ''
    # Return value:
    return checkpoint_flml


  def check_simulation_finished(self, dir, flml_filename):
    """ This subroutines load the option in the given 
        'flml_filename' and checks if the set finish_time
        has been reached. The return value is a logical 
        which is True if the finish time in the flml file
        has been reached and False otherwise.
        Input:
         dir: name of the directory where the flml
           files are in
         flml_filename: String of the flml filename
        Output:
         sim_finished: Logical which is True, if simulation
           has been finished, or False otherwise
    """
    sim_finished = False
    simbasename = self.get_sim_name_from_flml(dir, flml_filename)
    if (simbasename.endswith('_checkpoint')):
      origsimbasename = simbasename.replace('_checkpoint','')
    else:
      origsimbasename = simbasename
    # Get current time...
    # first from statfile,
    if (not 'checkpoint' in simbasename):
      # in this case, there was no checkpoint dumped, thus we'll obtain the 
      # current time from the stat file
      (current_time, status) = self.get_current_time_from_stat(dir, origsimbasename)
    if (status != 0 or 'checkpoint' in simbasename):
      # at least one checkpoint was dumped (or from stat failed),
      # obtaining current time from the corresponding flml file (last checkpoint):
      current_time = self.get_current_time_from_flml(dir, flml_filename)
    # Set the time for the dictionary:
    self.sim_time = current_time
    # ... and finish time
    finish_time = self.get_finish_time_from_flml(dir, flml_filename)
    if (float(current_time) >= float(finish_time)):
      sim_finished = True
      # Message handling:
      msg = 'Simulation in '+dir+' has reached its final time: FINISHED'
    # Also:
    # Check if steady state has been reached:
    steadystatestr = "Steady state has been attained, exiting the timestep loop"
    cmd = 'fgrep "'+steadystatestr+'" '+dir+'/fluidity.err-*'
    shellout = commands.getoutput(cmd)
    if (steadystatestr in shellout):
      sim_finished = True
      # Message handling:
      msg = 'Simulation in '+dir+' has reached steady state: FINISHED'
    # Update status:
    if (sim_finished):
      # Set jobid, cluster status, and elapsed walltime appropriately:
      self.update_sim_properties(dir, jobid='---', cluster_status='F', cluster_walltime='---', simulation_finished=True)
      # Message handling:
      subject = 'Simulation finished'
      # Get current dictionary:
      mydict = self.get_dict()
      # Also, update the pgf table:
      self.write_dict_status_pgftable(mydict, printcols=self.table_header, pdflatex=True, pdfcrop=True)
      attachment = 'logfiles/cropped_dict_status_table.pdf'
      self.messaging.message_handling(dir, msg, 0, msgtype='log', subject=subject, attachment=attachment)
    # Return value:
    return sim_finished


  def get_sim_name_from_flml(self, dir, flml_filename):
    """ This subroutines reads in the simulation set in a
        given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         simname: String of simulation name set in the
           given flml file.
    """
    simname = self.get_option_from_flml(dir, flml_filename, 'simulation_name')
    return simname

  def get_current_time_from_flml(self, dir, flml_filename):
    """ This subroutines reads in the current time
        set in a given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         current_time: String of the current time set in the
           given flml file.
    """
    current_time = self.get_option_from_flml(dir, flml_filename, 'timestepping/current_time')
    return current_time

  def get_finish_time_from_flml(self, dir, flml_filename):
    """ This subroutines reads in the finish time
        set in a given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         finish_time: String of the finish time set in the
           given flml file.
    """
    finish_time = self.get_option_from_flml(dir, flml_filename, 'timestepping/finish_time')
    return finish_time

  def get_walltime_limit_from_flml(self, dir, flml_filename):
    """ This subroutines reads in the set walltime limit
        set in a given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         walltime_limit: String of the finish time set in the
           given flml file.
    """
    walltime_limit = self.get_option_from_flml(dir, flml_filename, '/timestepping/wall_time_limit')
    return walltime_limit

  def get_final_timestep_from_flml(self, dir, flml_filename):
    """ This subroutines reads in the set final timestep
        set in a given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         final_timestep: String of the finish time set in the
           given flml file.
    """
    final_timestep = self.get_option_from_flml(dir, flml_filename, '/timestepping/final_timestep')
    return final_timestep

  def check_fsi_model_from_flml(self, dir, flml_filename):
    """ This subroutines checks if the given flml file
        enables the FSI model and gives back a logical.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
        Output:
         fsi_model: Logical, true if the FSI model is enabled
           in 'flml_filename', and false otherwise
    """
    fsi_model = self.get_option_from_flml(dir, flml_filename, '/embedded_models/fsi_model')
    return fsi_model

  def get_option_from_flml(self, dir, flml_filename, option_string):
    """ This subroutines reads in the finish time
        set in a given flml file, and returns the string.
        Input:
         dir: Name of the directory where the flml
           file is in
         flml_filename: String of the flml filename
         option_string: String of option path in flml file
        Output:
         option_value: String of value of the requested option
    """
    try:
      libspud.clear_options()
      libspud.load_options(dir +'/' + flml_filename)
    except:
      errormsg = "ERROR: Flml file "+dir+"/"+flml_filename+" could not be loaded. Trying again..."
      print errormsg
      raise Exception('Exception caught in "get_option_from_flml": '+errormsg)
    try:
      if (option_string == '/embedded_models/fsi_model'):
        option_value = libspud.have_option(option_string)
      else:
        if (libspud.have_option(option_string)):
          option_value = libspud.get_option(option_string)
        else:
          option_value = False
    except:
      errormsg = 'ERROR: '+option_string+' of flml "'+dir+'/'+flml_filename+'" could not be read in!'
      if (option_string == 'embedded_models/fsi_model'):
        option_value = False
      else:
        option_value = errormsg
      print errormsg
      raise Exception('Exception caught in "get_option_from_flml": '+errormsg)
    return option_value
  
  
  def get_current_time_from_stat(self, dir, simbasename):
    """ This subroutines reads in the current time (time in the last row)
        from a stat file.
        Input:
         dir: Name of the directory where the stat
           file is in
         simbasename: String of the simulation basename
        Output:
         current_time: String of the current time set in the
           given flml file.
         status: Integer which is 0 if no error occured, and
           non-zero otherwise
    """
    status = 1
    statfilename = simbasename + '.stat'
    try:
      cmd = 'tail -1 '+dir+'/'+statfilename
      out = commands.getoutput(cmd)
      current_time = out.strip().split(' ')[0] # current time is the first column
      if (not ('tail' in current_time)):
        status = 0
      else:
        current_time = -666
    except:
      current_time = -666
    return current_time, status


  def archive_simulation(self, dir, flml_filename):
    """ This subroutines creates an archive of 
        the necessary files in order to start the
        simulation. Based on the current_time in
        the flml-file, either all files are archived
        (if current_time == 0.0) or only the checkpoint
        files are archived (if current_time > 0.0).
        Input:
         dir: name of the directory where the flml
           file is in
         flml_filename: string of the flml filename
        Output:
         tar_filename: String of the tar_filename which 
           contains all the neccessary files to run
           the simulation, except for the fluidity
           binary.
    """
    # Return string:
    tar_filename = dir+'.tar'
    # Get current_time of input flml file:
    current_time = self.get_current_time_from_flml(dir, flml_filename)
#    # And the checkpoint simulation name from flml:
#    checkpoint_simname = self.get_sim_name_from_flml(dir, flml_filename)
    # If current_time == 0.0, we assume this is the initial run:
    if (current_time == 0.0):
      cmd = "tar --exclude '"+dir+"/bkup' -cvf "+tar_filename+" "+dir+"/"
      out = commands.getoutput(cmd)
    elif (current_time > 0.0):
      # Get strings for simulation-basename and ending to create archive:
      checkpoint_name = flml_filename.split('.flml')[0]
      checkpoint_number = checkpoint_name.split('_checkpoint')[0].split('_')[-1]
      checkpoint_basename = checkpoint_name.split('_'+checkpoint_number+'_checkpoint')[0]
      # Make tar-archive of complete directory for checkpointed setup:
      cmd = "tar --exclude '"+dir+"/bkup' -cvf "+tar_filename+" "+dir+"/"+checkpoint_basename+"*"+checkpoint_number+"_checkpoint*"+" "+dir+"/pbs.sh "+dir+"/Makefile"
      out = commands.getoutput(cmd)
    else:
      errormsg = 'ERROR: Flml file "'+dir+'/'+flml_filename+'" has a current_time < 0'
      print errormsg
    return tar_filename


  def check_cluster_for_simulation_running(self, cluster_name=None, myusername=None, jobid=None):
    """ This subroutines logs onto the cluster which name is given as
        an input argument, and checks if the given jobid is still running
        Input:
         cluster_name: String of address of the cluster, e.g. 
           cx1.hpc.ic.ac.uk
         user: String of the user's username
         jobid: String of the Job ID of the simulation
           running in 'cluster_dir/dir'
        Output:
         sim_running: Logical which is true, if the given jobid
           is still active on the cluster
         status: 0 if no error was encountered, 1 otherwise
    """
    # Optional arguments:
    if (cluster_name is None):
      cluster_name = self.cluster_name
    if (myusername is None):
      myusername = self.username
    if (jobid is None):
      jobid = self.jobid

    # Initialization:
    # Set to previous value, and later to true/false based on what is found:
    sim_running = self.simulation_running

    error = True; cnt = 0
    # we'll use this ls command as a trial if we get an answer from the cluster:
    trial_ls_cmd = 'ssh '+myusername+'@'+cluster_name+' "ls .bashrc"'
    qstat_cluster_cmd = 'ssh '+myusername+'@'+cluster_name+' "qstat -a"'
    while (cnt < self.errmaxcnt and error):
      trial_cluster_out = commands.getoutput(trial_ls_cmd)
      # only execute the qstat query if the ls command gives us the .bashrc file:
      if (trial_cluster_out.strip() == '.bashrc'):
        cluster_qstat = commands.getoutput(qstat_cluster_cmd)
        try:
          self.check_for_ssh_errors(cluster_qstat, calling_fun='check_cluster_for_simulation_running')
          self.check_for_ssh_qstat_error(cluster_qstat)
        except SSHQstatException:
          # the expected output from "qstat -a" was not found:
          # raise the same exception again and handle it later:
          raise SSHQstatException
        except SSHConnectionException:
          # Connection is currently not available, raise exception again:
          raise SSHConnectionException
        except SSHCrucialConnectionException:
          # Crucial error appeared, quit the program as this exception deals
          # with error such as wrong username, wrong cluster name, Permission
          # issues etc. This has to be fixed by the user:
          # Thus raise the same exception again.
          raise SSHCrucialConnectionException
        else:
          error = False # ssh operation was successful
          break
      # Increase counter of trials and wait a tiny bit until the next query:
      cnt = cnt+1
      if (cnt > self.errmaxcnt):
        raise SSHConnectionException
      if (error):
        time.sleep(self.errwaittime)
    # No error/exception occured, analyse cluster_qstat:
    if (not error):
      # First of all, let's remove unneccessary lines from qstat's output:
      qstat_lines = self.strip_qstat_output(cluster_qstat)
      # qstat was performed with success, thus set
      # sim_running to false, and true if jobid was found:
      sim_running = False
      # Then if output was not empty:
      if (cluster_qstat):
        for qstat_line in qstat_lines:
          # Seperate line of info into a list filled with elements
          qstat_linesplit = qstat_line.split(None)
          # Now check if listed job is your own (username), 
          # e.g. required for cx2 (not cx1 though):
          if (not myusername == qstat_linesplit[1]):
            continue
          # get jobid:
          cluster_qstat_jobid = qstat_linesplit[0]
          if (cluster_qstat_jobid == jobid):
            sim_running = True
            # Set cluster status and elapsed time on cluster:
            cluster_status=qstat_linesplit[9]
            cluster_walltime=qstat_linesplit[10]
            # setting cluster walltime to zero, if it's queueing, which prevents a conversion exception for runs 
            # that finish/crash within the time of the query_time:
            if (cluster_walltime == '--'): cluster_walltime = '00:00'
            self.update_sim_properties(self.dir, cluster_status=cluster_status, cluster_walltime=cluster_walltime)
            break
        # If simulation is not running anymore, reset cluster jobid and status :
        if (not sim_running):
          self.update_sim_properties(self.dir, jobid='---', cluster_status='---')
      # Update status simulation_running of Monitoring class:
      self.update_sim_properties(self.dir, simulation_running=sim_running)
    # Set status to 1, if an error occured:
    if (error): status = 1
    else: status = 0
    return sim_running, status


  def strip_qstat_output(self, qstat_output):
    """ This subroutine removes irrelevant lines from the output 
        from "qstat -a"
        Input:
         qstat_output: String of the output from "qstat -a"
        Output:
         rel_output: Output of "qstat -a" without irrelevant lines         
    """
    rel_output = []
    for line in qstat_output.split('\n'):
      if (self.username in line):
        rel_output.append(line)
    return rel_output


  def get_inexclude_lists(self, dir):
    """ This subroutine assembles lists of which files to include/exclude
        from the rsync operation.
        Input:
         dir: String of the directory name of the current simulation
        Output:
         include: List of file basenames to include
         exclude: List of file basenames to exclude
    """
    include = []; exclude = ['bkup', '*']
    # get the latest (checkpointed) flml filename:
    flml_filename = self.parse_flml_files(dir)
    current_time = self.get_current_time_from_flml(dir, flml_filename)
    # If current_time == 0.0, we assume this is the initial run:
    if (current_time == 0.0):
      include.append('*')
    elif (current_time > 0.0):
      # Get strings for simulation-basename and ending:
      checkpoint_name = flml_filename.split('.flml')[0]
      checkpoint_number = checkpoint_name.split('_checkpoint')[0].split('_')[-1]
      checkpoint_basename = checkpoint_name.split('_'+checkpoint_number+'_checkpoint')[0]
      # Now we can add the relevant file-basenames to the list of included files:
      include.append(checkpoint_basename+'*'+checkpoint_number+'_checkpoint*')
      include.append('pbs.sh')
    else:
      errormsg = 'ERROR: Flml file "'+dir+'/'+flml_filename+'" has a current_time < 0'
      print errormsg
    return (include, exclude)


  def submit_on_cluster(self, cluster_name=None, cluster_dir=None, dir=None, tar_filename=None):
    """ This subroutines cleans up the given directory on the cluster,
        meaning the directory 'dir' (if present) is deleted in the
        first place. Secondly relevant files are synced between the local
        machine and the cluster directory. Finally the simulation is
        submitted to the queue. Return value is a string with the
        Job ID on the cluster.
        Input:
         cluster_name: Address of the cluster, e.g. 
           cx1.hpc.ic.ac.uk
         cluster_dir: Parent directory on the cluster where the 
           convergence analysis is carried out
         dir: Name of the directory where the simulation files
           are in
         tar_filename: String of the filename of the archive 
           to be sent to the cluster
        Output:
         jobid: String of the Job ID of the simulation
           running in 'cluster_dir/dir'
         simulation_crashed: Boolean which is True in case of extreme
           failures which could happen due to connection issues
         status: 0 if everything went smoothly, and 1 if any kind of
           error occured.         
    """
    # Set simulation_crashed to False, only setting it to True in some rare cases:
    simulation_crashed = False
    # Define values for optional arguments:
    if (cluster_name is None):
      cluster_name = self.cluster_name
    if (cluster_dir is None):
      cluster_dir = self.cluster_dir
    if (dir is None):
      dir = self.dir
    if (tar_filename is None):
      tar_filename = self.dir+'.tar'
    
    # Start processing directories on the cluster:

    # Do the following steps in a loop, in case the job was not successfully submitted to the queue:
    ############
    # SSH      #
    ############
    error = True; cnt = 0
    # Remove corresponding directory on cluster:
    while (cnt < self.errmaxcnt and error):
      cmd = 'ssh '+self.username+'@'+cluster_name+' "rm -rf '+cluster_dir+'/'+dir+'"'
      out = commands.getoutput(cmd)
      print out
      if (out.find("Connection closed by") == -1 and out.find("lost connection") == -1 and out.find("ssh_exchange_identification") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1):
        error = False # ssh operation was successful
        break
      elif (out.find("Connection closed by") >= 0):
        # Connection is currently not available, so skip following processes:
        break
      cnt = cnt+1
      if (cnt >= self.errmaxcnt):
        errormsg = "Error: "+out+". Tried "+str(errmaxcnt)+" times to connect to "+cluster_name+":"+cluster_dir+" via ssh, but could not establish connection!"
        subject = 'Error: SSH'
        self.messaging.message_handling(dir, errormsg, 2, msgtype='err', subject=subject)
      if (error):
        time.sleep(waittime)


    #############
    # rsync     #
    #############
    if (not error):
      # First, determine which file basenames we want to include/exclude from the syncing process:
      (files_include, files_exclude) = self.get_inexclude_lists(dir)
      # Add those lists to a dictionary for in-/exclude file-basenames:
      rsync_files = {'include' : files_include, 'exclude' : files_exclude}
      # Now construct the string for executing rsync (breaking it down into substrings):
      inclstr = '--include='; exclstr = '--exclude=';
      rsync_includes = ' '.join([inclstr+'"'+i+'"' for i in rsync_files['include']])
      rsync_excludes = ' '.join([exclstr+'"'+i+'"' for i in rsync_files['exclude']])
      # Assembling the full rsync command:
      rsync_cmd = 'rsync -e ssh -arvq '+rsync_includes+' '+rsync_excludes+' '+dir+'/ '+self.username+'@'+cluster_name+':'+cluster_dir+'/'+dir+'/'
      # Now start the rsync process to the cluster:"+self.username+"@"+cluster_name+":"+cluster_dir+"/"
      error = True; cnt = 0
      while (cnt < self.errmaxcnt and error):
        # the following lines are commented out as they refer to the old method, using scp:
        #cmd = "scp "+tar_filename+" "+self.username+"@"+cluster_name+":"+cluster_dir+"/"
        #if (out.find("Connection closed by") == -1 and out.find("No such file or directory") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1 and out.rfind("Disk quota exceeded")==-1):
        out = commands.getoutput(rsync_cmd)
        if (out == ''):
        #if (out.find("Connection closed by") == -1 and out.find("No such file or directory") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1 and out.rfind("Disk quota exceeded")==-1):
          #self.notify_popup('SCP successful', 'SCP simulation to cluster into directory '+dir)
          msg = 'rsync simulation to cluster into directory '+dir
          subject = 'rsync successful'
          self.messaging.message_handling(dir, msg, 2, msgtype='log', subject=subject)
          error = False # rsync operation was successful
          break
        elif (out.find("Connection closed by") >= 0):
          # Connection is currently not available, so skip following processes:
          break
        elif (out.rfind("Disk quota exceeded") >= 0):
          # Disk quota on cluster exceeded, so raise exception and quit program as this needs to be solved manually
          errormsg = 'Error: Disk quota on '+cluster_name+' was exceeded. Clean up your space.'
          raise DiskQuotaException
        else:
          errormsg = 'Unknown error during rsync found: '+out
        cnt = cnt+1
        if (cnt >= self.errmaxcnt and not error):
          errormsg = "Error: "+out+". Tried "+str(self.errmaxcnt)+" times to rsync to "+cluster_name+":"+cluster_dir+" via rsync, but could not copy files."
          subject = 'Error: rsync'
          self.messaging.message_handling(dir, errormsg, 2, msgtype='err', subject=subject)
        if (error):
          time.sleep(self.errwaittime)


#    #############
#    # SSH untar #
#    #############
#    if (not error):
#      error = True; cnt = 0
#      while (cnt < self.errmaxcnt and error):
#        # Untar archive on cluster:'+self.username+'@'+cluster_name+'
#        cmd = 'ssh '+self.username+'@'+cluster_name+' "cd '+cluster_dir+'/; tar -xf '+tar_filename+'; rm '+tar_filename+'"'
#        out = commands.getoutput(cmd)
#
#        if (out.find("Connection closed by") == -1 and out.find("lost connection") == -1 and out.find("ssh_exchange_identification") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1 and out.find("No such file or directory") == -1 and out.find("cannot remove") == -1 and out.find("Cannot open") == -1):
#          error = False # ssh operation was successful
#          break
#        elif (out.find("Connection closed by") >= 0):
#          # Connection is currently not available, so skip following processes:
#          break
#        elif (out.rfind("Disk quota exceeded") >= 0) :
#          # Disk quota on cluster exceeded, so raise exception and quit program as this needs to be solved manually
#          errormsg = 'Error: Disk quota on '+cluster_name+' was exceeded. Clean up your space.'
#          raise DiskQuotaException
#        cnt = cnt+1
#        if (cnt >= self.errmaxcnt):
#          errormsg = "Error: "+out+". Tried "+str(self.errmaxcnt)+" times to connect to "+cluster_name+"/"+cluster_dir+" via ssh, but could not establish connection!"
#          subject = 'Error: SSH untar'
#          self.messaging.message_handling(dir, errormsg, 2, msgtype='err', subject=subject)
#        if (error):
#          time.sleep(self.errwaittime)

    ########################
    # copy fluidity binary #
    ########################
    if (not error):
      error = True; cnt = 0
      while (cnt < self.errmaxcnt and error):
        # Copy fluidity binary into simulation directory:
        cmd = 'ssh '+self.username+'@'+cluster_name+' "cp '+self.cluster_fluidity_dir+'/bin/fluidity '+cluster_dir+'/'+dir+'/ "'
        out = commands.getoutput(cmd)

        if (out.find("Connection closed by") == -1 and out.find("lost connection") == -1 and out.find("ssh_exchange_identification") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1 and out.find("No such file or directory") == -1 and out.find("cannot remove") == -1 and out.find("Cannot open") == -1):
          error = False # ssh operation was successful
          break
        elif (out.find("Connection closed by") >= 0):
          # Connection is currently not available, so skip following processes:
          break
        elif (out.rfind("Disk quota exceeded") >= 0) :
          # Disk quota on cluster exceeded, so raise exception and quit program as this needs to be solved manually
          errormsg = 'Error: Disk quota on '+cluster_name+' was exceeded. Clean up your space.'
          raise DiskQuotaException
        cnt = cnt+1
        if (cnt >= self.errmaxcnt):
          errormsg = "Error: "+out+". Tried "+str(self.errmaxcnt)+" times to connect to "+cluster_name+"/"+cluster_dir+" via ssh, but could not establish connection!"
          subject = 'Error: SSH untar'
          self.messaging.message_handling(dir, errormsg, 2, msgtype='err', subject=subject)
        if (error):
          time.sleep(self.errwaittime)

    ##############
    # SSH Submit #
    ##############
    if (not error):
      # Now submit the job t  o cluster:
      error = True; cnt = 0
      while (cnt < self.errmaxcnt and error):
        cmd = 'ssh '+self.username+'@'+cluster_name+' "cd '+cluster_dir+'/'+dir+'; qsub pbs.sh"'
        jobid = commands.getoutput(cmd)

        if ((not jobid == '' and not jobid == ' ' and not jobid == ('qsub: Access to queue is denied') and jobid.find("No such file or directory") == -1 and jobid.find("Connection closed by") == -1 and jobid.find("lost connection") == -1 and jobid.find("ssh_exchange_identification") == -1 and out.find("Connection timed out")==-1 and out.find("Name or service not known")==-1)):
          error = False # successfully submitted the job to the queue
          # Update certain cluster simulation parameters:
          self.update_sim_properties(dir, jobid=jobid, cluster_status='Q', cluster_walltime='00:00', simulation_running=True)
          break

        elif (jobid.find("Connection closed by") >= 0): # Means, connection is temporarily clocked, thus simulation_crashed = False
          # Connection is currently not available, so skip following processes:
          # error stays true, but we break out of the loop, thus this stage will be tried again at the next
          # monitoring iteration
          break

        elif (jobid == 'qsub: Access to queue is denied'): # Then it will never work, thus simulation_crashed = True
          errormsg = 'Error: Access to queue is denied\nError: This Simulation has been flagged as crashed and has to be taken care of manually!'
          self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject='Access to queue denied')
          # Update certain cluster simulation parameters:
          jobid = '---'
          simulation_crashed = True
          self.update_sim_properties(dir, jobid=jobid, simulation_crashed=simulation_crashed)
          break

        cnt = cnt + 1

        if (cnt >= self.errmaxcnt): # Maximum number of trials reached, try again at next monitoring iteration:
          # old message:
          # errormsg = 'Error: Job of '+cluster_name+':'+cluster_dir+'/'+dir+' could not be successfully submitted to the queue.\nError: This Simulation has been flagged as crashed and has to be taken care of manually!'
          errormsg = 'Error: Job of '+cluster_name+':'+cluster_dir+'/'+dir+' could not be successfully submitted to the queue.\nTrying again at the next monitoring iteration...\nLast output from \'qsub pbs.sh\' was: '+jobid
          subject = 'Error: SSH submit'
          self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject=subject)
          # Update certain cluster simulation parameters:
          jobid = '---'
          #simulation_crashed = True
          self.update_sim_properties(dir, jobid=jobid)

        if (error):
          time.sleep(self.errwaittime)

    # End of processing cluster directories and submitting the job, if no error was encountered in the meantime

    # Error handling:
    if (error): # If an error occured at any time in the method:
      status = 1
      # Update certain cluster simulation parameters if an error occured at any time:
      jobid = '---'
      self.update_sim_properties(dir, jobid=jobid, cluster_status='E', cluster_walltime='---')
      # Proper error message was given when error was encountered
    else: # Else, everything worked out smoothly:
      status = 0
      # cluster simulation parameters are already updated at this stage
      # Message handling:
      msg = 'Simulation of '+dir+' was successfully submitted.\nJobID: '+jobid
      subject = 'Job submitted'
      self.messaging.message_handling(dir, msg, 0, msgtype='log', subject=subject)

    # Return values:
    return jobid, simulation_crashed, status


  def scp_data_from_cluster(self, cluster_name=None, cluster_dir=None, dir=None, simname=None, running=False):
    """ This subroutines packages the relevant data on the cluster,
        and sends it back into the corresponding directory on the
        local machine, where the archive is unpacked and ready for 
        inspection.
        Input:
         cluster_name: Address of the cluster, e.g. 
           cx1.hpc.ic.ac.uk
         cluster_dir: Parent directory on the cluster where the 
           convergence analysis is carried out
         dir: Name of the directory where the simulation files
           are in
         simname: String of the simulation name set in the flml
           file
         running: Boolean indicating if the simulation is still
           running on the cluster or not, default: False
        Output:
          status: 0 if no error occured, 1 otherwise
    """
    if (cluster_name is None):
      cluster_name = self.cluster_name
    if (cluster_dir is None):
      cluster_dir = self.cluster_dir
    if (dir is None):
      dir = self.dir
    if (simname is None):
      simname = self.simname

    #################
    # rsync results #
    #################
    error = False
    if (not error):
      # First, determine which file basenames we want to include/exclude from the syncing process:
      if (running): files_include = [simname+'*', 'first_timestep_adapted_mesh*', 'pbs.sh']
      else: files_include = [simname+'*', 'stdout', 'stderr', 'fluidity.*', 'first_timestep_adapted_mesh*', 'pbs.sh']
      files_exclude = ['*'] # exlude everything else!
      # Add those lists to a dictionary for in-/exclude file-basenames:
      rsync_files = {'include' : files_include, 'exclude' : files_exclude}
      # Now construct the string for executing rsync (breaking it down into substrings):
      inclstr = '--include='; exclstr = '--exclude=';
      rsync_includes = ' '.join([inclstr+'"'+i+'"' for i in rsync_files['include']])
      rsync_excludes = ' '.join([exclstr+'"'+i+'"' for i in rsync_files['exclude']])
      # Assembling the full rsync command:
      rsync_cmd = 'rsync -e ssh -arvq '+rsync_includes+' '+rsync_excludes+' '+self.username+'@'+cluster_name+':'+cluster_dir+'/'+dir+'/'+' '+dir+'/'
      # Syncing results from cluster with corresponding directory on local machine:
      error = True; cnt = 0
      while (cnt < self.errmaxcnt and error):
        out = commands.getoutput(rsync_cmd)
        try:
          self.check_for_scp_errors(out, dir=dir, calling_fun='scp_data_from_cluster')
        except SCPException:
          # Minor exception was caught during scp operation
          raise SCPException
        except SCPCrucialException:
          # More crucial exception was caught:
          raise SCPCrucialException
        else:
          # Checking if the output from command line is an empty string (as it should be):
          if (out == ''):
            error = False # syncing operation was successful
            msg = 'Synced results from cluster into directory '+dir
            self.messaging.message_handling(dir, msg, 2, msgtype='log', subject='SCP successful')
            break
        # Increase counter of trials and wait a tiny bit until the next trial:
        cnt = cnt+1
        if (cnt > self.errmaxcnt):
          errormsg = "Error: "+out+". Tried "+str(self.errmaxcnt)+" times to sync from from "+cluster_name+"/"+cluster_dir+" via rsync, but could not sync files."
          self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject='Error: SCP res')
          raise SCPException
        if (error):
          time.sleep(self.errwaittime)

    # In case everything went smoothly OR sth else went wrong, and an error was
    # found without an exception:
    if (not error):
      status = 0
      msg = 'Data was copied from the cluster to the local machine.'
      self.messaging.message_handling(dir, msg, 2, msgtype='log', subject='SCP_data_from_cluster successful')
    else:
      status = 1
      # Error message:
      errormsg = 'Error: An unknown error was caught during scp_data_from_cluster. This should never happen.\nNeed to debug code!'
      self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject='Error: SCP_data_from_cluster unsuccessful')
      raise SCPDataFromClusterException
    return status


  def postprocess_simulation(self, dir, cluster_name=None):
    """ Once the results are copied from the cluster, the results
        are postprocessed in this method. Here the simulation
        name in the flml file is slightly modified, the pbs-script
        is updated with the latest checkpoint-flml-filename,
        the data of the received .stat and .detectors (.detectors.dat)
        are appended to the previous .stat and .detectors file,
        the vtu files are renamed such that they corresond to the
        previous run, redundant checkpoint files are removed, 
        and it is also checked if the simulation has finished.
        Input:
         dir: Name of the directory where the results are to be
           postprocessed
         cluster_name: String of the name/address of the cluster.
        Output:
         simulation_finished: Boolean, True if simulation is finished.
         tar_filename: String of the archive's filename.
    """
    if (cluster_name is None):
      cluster_name = self.cluster_name
    # Make some required changes, e.g. change flml in pbs-script, append stat-file to previous-statfile,
    # change simulation name in checkpointed flml-file, rename vtu files such that they are 
    # corresponding to the previous run ...:

    # Get the latest (checkpoint) flml filename:
    checkpoint_flml_filename = self.parse_flml_files(dir)
    # After finding the checkpoint_flml, set self.sim_time:
    current_time = self.get_current_time_from_flml(dir, checkpoint_flml_filename)
    self.update_sim_properties(dir, sim_time=current_time)

    # Setup up pbs-script and simname in flml for next run:
    self.setup_pbs_script(dir, checkpoint_flml_filename)
    # Method below modifies simname if '_checkpoint' is in simname:
    self.change_simname_in_flml(dir, checkpoint_flml_filename)
    # Remove "adapt_at_first_timestep" if it is in the checkpointed flml:
    if ('checkpoint' in checkpoint_flml_filename):
        self.remove_adapt_first_timestep_in_flml(dir, checkpoint_flml_filename)
    # Check if simulation has been finished:
    simulation_finished = self.check_simulation_finished(dir, checkpoint_flml_filename)
    # If simulation is flagged as finished, remove the directory on the cluster:
    if (simulation_finished):
      self.clean_cluster_dir(dir, cluster_name=cluster_name)
      # Create tarfile of neccessary files to restart/continue the simulation/and/or to backup:
    tar_filename = self.archive_simulation(dir, checkpoint_flml_filename)

    # Return simulation_finished and tar_filename:
    return simulation_finished, tar_filename


  def remove_adapt_first_timestep_in_flml(self, dir, flml_filename):
    """ This subroutine removes the option "adapt_at_first_timestep" from
        a checkpointed flml option tree.
        Input:
         dir: Name of the corresponding directory
         flml_filename: Most recent simulation name that ran of this
           particular simulation (in directory 'dir')
    """
    if (libspud.have_option('/mesh_adaptivity/hr_adaptivity/adapt_at_first_timestep')):
        libspud.delete_option('/mesh_adaptivity/hr_adaptivity/adapt_at_first_timestep')
        libspud.write_options(dir+'/'+flml_filename)
        libspud.clear_options()
    # End of remove_adapt_first_timestep_in_flml


  def renaming_checkpoint(self, dir=None, simname=None, ncpus=None):
    """ Renaming checkpointed fluid and solid vtu files.
        Input:
         dir: String of the name of the directory where
           the vtu files are in
         simname: Most recent simulation name that ran of 
           this particular simulation (in directory 'dir')
         ncpus: Number of processes this simulation ran on
         flml_filename: String of a flml file
        Output:
         status: 0 if no error occured, 1 otherwise
    """
    if (dir is None):
      dir = self.dir
    if (simname is None):
      simname = self.simname
    if (ncpus is None):
      ncpus = self.ncpus
    status = 0
    rename_checkpoint = False
    # First of all, check if we have to run rename_checkpoint at all:
    if (simname.find('_autocheckp') >= 0):
      simbasename = simname.split('_autocheckp')[0]
      rename_checkpoint = True

    # Let's check if there are any dump files to rename:
    if (rename_checkpoint):
      searchstring = simbasename+'_autocheckp*vtu -not -name "*solid*" -not -name "*checkpoint*"'
      (list_prev_fluid_vtus, status) = find_file_names(dir, searchstring)
      if (status != 0): # If no such file was found, we don't need to rename any dump files:
        rename_checkpoint = False

    if (rename_checkpoint):
      ########################
      # For fluid vtu files: #
      ########################
      # Find last fluid vtu file of previous run:
      searchstring = simbasename+'*vtu -not -name "*autocheckp*" -not -name "*solid*" -not -name "*checkpoint*"'
      (list_prev_fluid_vtus, status) = find_file_names(dir, searchstring)
      if (status == 0):
        # Initialisation of variables for finding the largest
        # dump-number of the vtu files in dir: 
        dumpno_tmp = 0; dumpno = 0;
        # Looping over all vtu files found that are from the previous run (and fluid):
        # Goal: Find largest dump number of the previous run:
        for line in list_prev_fluid_vtus:
          # Now cut the string, and get string with only the dump number:
          # Assumption that is valid for Fluidity dump files:
          # Split 'line' at each '_', whereas after the last '_' character
          # in 'line', is the dump number followed by '.(p)vtu'
          index = str(line.split('_')[-1][:-(len(line.split('.')[-1])+1)])
          try:
            dumpno_tmp = int(index)
          except ValueError:
            errormsg = "Error: Could not find the max dump number of vtu files!"
            printc(errormsg, "red", False); print
            break
          except:
            errormsg = "Error: An unexpected error occured during the trial of converting a string, which should be an integer, into an integer"
            printc(errormsg, "red", False); print
            break
          # If a larger dumpno was found, save it in dumpno:
          if (dumpno_tmp > dumpno):
            dumpno = dumpno_tmp
        # Largest dumpno is found at this point:
        # Now find the vtu files that we have to rename:
        searchstring = simbasename+'*_autocheckp_*vtu  -not -name "*solid*" -not -name "*checkpoint*"'
        (list_new_fluid_vtus, status) = find_file_names(dir, searchstring)
        if (status == 0):
          list_new_fluid_vtus.sort(key=lambda x: int(x.split('_')[-1][:-(len(x.split('.')[-1])+1)]))
          for newvtu in list_new_fluid_vtus:
            new_fluid_dumpno = 0; offset = 1 # offset of 1, as new dump file start at 0, best with "disable dump at start".
            # get index new(p)vtu:
            newindex = str(newvtu.split('_')[-1][:-(len(newvtu.split('.')[-1])+1)])
            try:
              new_fluid_dumpno = int(newindex) + dumpno + offset
            except ValueError:
              errormsg = "Error: Could not find the dump number of a fluid (p)vtu file!"
              printc(errormsg, "red", False); print
              break
            except:
              errormsg = "Error: An unexpected error occured during the trial of converting a string, which should be an integer, into an integer"
              printc(errormsg, "red", False); print
              break
            # newvtufilename is valid for both, serial and parallel runs:
            newvtufilename = simbasename+'_'+str(new_fluid_dumpno)+'.'+newvtu.split('.')[-1]
            cmd = 'cd '+dir+'; mv '+newvtu+' '+newvtufilename
            out = commands.getoutput(cmd)
            if (ncpus > 1): # For parallel runs, also change directory names, its content, and pvtu content:
              newdirname = simbasename+'_'+str(new_fluid_dumpno)
              # pvtu files are renamed, now go into old folder-name, and change vtu files in there:
              to_be_changed_dir_name = newvtu.split('.')[0] #assuming, there is no '.' in the simname!
              (vtus_in_subdir, status) = find_file_names(dir+'/'+to_be_changed_dir_name, '*')
              for vtu_subdir in vtus_in_subdir:
                newsubdirfilename = newdirname+'_'+vtu_subdir.split('_')[-1]
                cmd = 'cd '+dir+'/'+to_be_changed_dir_name+'/; mv '+vtu_subdir+' '+newsubdirfilename
                out = commands.getoutput(cmd)
                # Now change entries in the pvtu file:
                cmd = "cd "+dir+"; sed -i 's/"+to_be_changed_dir_name+"/"+newdirname+"'/g "+newdirname+'.'+newvtu.split('.')[-1]
                out = commands.getoutput(cmd)
              # All changes in subdir done and pvtu file in parent dir done, now change folder name:
              cmd = 'cd '+dir+'; mv '+to_be_changed_dir_name+' '+newdirname
              out = commands.getoutput(cmd)
      # Renaming vtus for fluid dumps are done.

      ########################
      # For Solid vtu files: #
      ########################
      # Check if this is a FSI simulation, and if so,
      # do the same for solid vtu files:
      (flml_files, status) = get_file_names(dir+'/*flml')
      if (status == 0):
        flml_filename = flml_files[0]
        fsi_model = self.check_fsi_model_from_flml(dir, flml_filename)
      else:
        errormsg = "Error: Could not find or open flml file in "+dir+". Not renaming vtus of solid dumps!"
        printc(errormsg, "red", False); print
        fsi_model = False
      if (fsi_model):
        # Find last solid vtu file of previous run:
        searchstring = simbasename+'*solid*vtu -not -name "*autocheckp*"'
        (list_prev_solid_vtus, status) = find_file_names(dir, searchstring)
        if (status == 0):
          # Sort the list based on dump-numbers:
          list_prev_solid_vtus.sort(key=lambda x: int(x.split('_')[-1][:-(len(x.split('.')[-1])+1)]))
        else:
          raise SystemExit('Could not find any solid vtu files in dir: '+dir)
        # Now determine the solid names:
        solid_names = []
        for vtu in list_prev_solid_vtus:
          solid_name = vtu.split(simbasename+'_solid_')[-1].split('_')[0]
          if (not solid_name in solid_names):
            solid_names.append(solid_name)
        for solid_name in solid_names:
          # Solid basename:
          solid_basename = simbasename+'_solid_'+solid_name
          # Updating the vtu list:
          searchstring = solid_basename+'*vtu -not -name "*autocheckp*"'
          (list_prev_solid_vtus, status) = find_file_names(dir, searchstring)
          if (status == 0):
            # Sort the list based on dump-numbers:
            list_prev_solid_vtus.sort(key=lambda x: int(x.split('_')[-1][:-(len(x.split('.')[-1])+1)]))
          else:
            raise SystemExit('Could not find any solid vtu file with name '+solid_name+' in dir: '+dir)
          if (status == 0):
            # Then process the vtu files in dir one solid at a time:
            # Initialisation of variables for finding the largest
            # dump-number of the vtu files in dir: 
            dumpno_tmp = 0; dumpno = 0;
            for line in list_prev_solid_vtus:
              index = str(line.split('_')[-1][:-(len(line.split('.')[-1])+1)])
              try:
                dumpno_tmp = int(index)
              except ValueError:
                errormsg = "Error: Could not find the max dump number of vtu files!"
                printc(errormsg, "red", False); print
                break
              except:
                errormsg = "Error: An unexpected error occured during the trial of converting a string, which should be an integer, into an integer"
                printc(errormsg, "red", False); print
                break
              # If a larger dumpno was found, save it in dumpno:
              if (dumpno_tmp > dumpno):
                dumpno = dumpno_tmp
              # Largest dumpno is found at this point:
            # These are the checkpointed dumps that we need to renumber:
            # find *autocheckp_solid*vtu -not -name "*checkpoint*"
            solid_autocheckp_basename = simbasename+'_autocheckp_solid_'+solid_name
            searchstring = solid_autocheckp_basename+'*vtu -not -name "*checkpoint*"'
            (list_new_solid_vtus, status) = find_file_names(dir, searchstring)
            if (status == 0):
              list_new_solid_vtus.sort(key=lambda x: int(x.split('_')[-1][:-(len(x.split('.')[-1])+1)]))
              for newvtu in list_new_solid_vtus:
                new_solid_dumpno = 0; offset = 1 # offset of 1, as new dump file start at 0, best with "disable dump at start".
                # get index new(p)vtu:
                newindex = str(newvtu.split('_')[-1][:-(len(newvtu.split('.')[-1])+1)])
                try:
                  new_solid_dumpno = int(newindex) + dumpno + offset
                except ValueError:
                  errormsg = "Error: Could not find the dump number of a solid (p)vtu file!"
                  printc(errormsg, "red", False); print
                  break
                except:
                  errormsg = "Error: An unexpected error occured during the trial of converting a string, which should be an integer, into an integer"
                  printc(errormsg, "red", False); print
                  break
                # Solid dump files are always in serial (for now):
                cmd = 'cd '+dir+'; mv '+newvtu+' '+solid_basename+'_'+str(new_solid_dumpno)+'.'+newvtu.split('.')[-1]
                out = commands.getoutput(cmd)
                #if (ncpus == 1):
                #  cmd = 'cd '+dir+'; mv '+newvtu+' '+solid_basename+'_'+str(dumpno+new_solid_dumpno)+'.'+newvtu.split('.')[-1]
                #  out = commands.getoutput(cmd)
                #elif (ncpus > 1):
                #  newdirname = solid_basename+'_'+str(dumpno+new_solid_dumpno)
                #  cmd = 'cd '+dir+'; mv '+newvtu+' '+newdirname+'.'+newvtu.split('.')[-1]
                #  out = commands.getoutput(cmd)
                #  # pvtu files are renamed, now go into old folder-name, and change vtu files in there:
                #  to_be_changed_dir_name = newvtu.split('.')[0]
                #  (vtus_in_subdir, status) = find_file_names(dir+'/'+to_be_changed_dir_name, '*')
                #  for vtu_subdir in vtus_in_subdir:
                #    newsubdirfilename = newdirname+'_'+vtu_subdir.split('_')[-1]
                #    cmd = 'cd '+dir+'/'+to_be_changed_dir_name+'/; mv '+vtu_subdir+' '+newsubdirfilename+';'
                #    out = commands.getoutput(cmd)
                #    # Now change entries in the pvtu file:
                #    cmd = "cd "+dir+"; sed -i 's/"+to_be_changed_dir_name+"/"+newdirname+"'/g "+newdirname+'.'+newvtu.split('.')[-1]
                #    out = commands.getoutput(cmd)
                #  # All changes in subdir done and pvtu file in parent dir done, now change folder name:
                #  cmd = 'cd '+dir+'; mv '+to_be_changed_dir_name+' '+newdirname+';'
                #  out = commands.getoutput(cmd)
    
    if (not(rename_checkpoint)):
      status = 0
    return status


  def append_resfiles(self, dir=None, simname=None):
    """ This subroutine appends results from the file
        'simname'.'ext' to the previous file with the
        same file extension in the directory 'dir'.
        Input:
         dir: Name of the directory where the statfile is in
         simname: Most recent simulation name that ran of this
           particular simulation (in directory 'dir')
        Output:
         simulation_crashed: Boolean, True if error occured,
           False otherwise
    """
    if (dir is None):
      dir = self.dir
    if (simname is None):
      simname = self.simname
    # If statfile: search for data in newfile, and append only data to oldfile
    # If detectors, and no detectors.dat file present, do same as for statfile
    # If detectors, and detectors.dat present: cat newfile >> oldfile for detectors.dat files!
    # Done
  #  printc("In append_resfiles.", "green", True); print
    status = 0; error = False
    append_file = False;
    # First of all, get all the file extensions that are present in directory dir:
    extensions = self.get_res_file_extension(dir)
    if (status == 0):
      for ext in extensions:
        (filelist, status) = get_file_names(dir+'/*'+ext)
        if (len(filelist) == 2):
          append_file = True
  #       printc("2 statfiles found", "green", True); print
        elif (len(filelist) <= 1):
  #        printc("1 or no statfile found. Nothing to append.", "red", False); print
          append_file = False
          continue
        else:
#          errormsg = 'Error: In append_resfiles: More than 2 stat/detectors-files found. Something went wrong, probably forgot to move/remove old statfile'
#          printc(errormsg, 'red', True); print
#          self.write_to_log_err_file(dir, errormsg, msgtype='err')
          append_file = False
          error = True
          break
        # Find new and oldfile:
        newfilename = simname+'.'+ext
        # Find name of oldfile:
        if (append_file):
          for file in filelist:
            if (file != newfilename):
              oldfilename = file
        # The following only applies to stat and ASCII detector files:
        if (ext == 'stat' or ext == 'detectors'): 
          # Open newfile and remove the header from the file:
          if (append_file):
            newf = open(dir+'/'+newfilename, 'r')
          # Parse the data in the new/most recent statfile and
          # create list containing only the data:
          newdata = []
          for line in newf: # more memory efficient than newf.readlines()
            if (line.find("<") >=0):
              # this line belongs to the header, so skip it
              continue
            newdata.append(line)
          # newdata has been assembled, now close the new file:
          newf.close()
          # Append to previous statfile:
          python_append_to_file(dir+'/'+oldfilename, newdata)
        # Finished appending to stat and detector files
        # Now append binary detectors.dat files
        elif (ext == 'detectors.dat'):
          status = file_append_to_file(dir+'/'+oldfilename, dir+'/'+newfilename)
        else:
          error = True
          print "Error: Should never get here."
          break
    if (error):
      # This is a very crucial error, thus handle with caution: simulation_crashed = True
      simulation_crashed = True
      self.update_sim_properties(dir, simulation_crashed=simulation_crashed)
      # Error message:
      errormsg = 'Error: An error occured during the attempt to append results from stat/detector files.'
      subject = 'Error: Results'
      self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject=subject)
    else:
      simulation_crashed = False
    return simulation_crashed


  def setup_pbs_script(self, dir, flml_filename):
    """ This subroutine simple makes use of sed to udpate the
        pbs-script with the new flml filename.
        Input:
         dir: Name of the directory where the pbs-script is in
         flml_filename: Most recent simulation name that ran of this
           particular simulation (in directory 'dir')
    """
    # In pbs-script, replacing line where PROJECT is defined, with new flml-filename:
    cmd = 'cd '+dir+'; sed -i "/PROJECT=/c\PROJECT='+flml_filename+'" pbs.sh'
    out = commands.getoutput(cmd)
    # Also replace the Fluidity dir:
    cmd = 'cd '+dir+'; sed -i "/FLUIDITY_DIR=/c\export FLUIDITY_DIR='+self.cluster_fluidity_dir+'" pbs.sh'
    out = commands.getoutput(cmd)

    # Check if this is for cx1/2 or hector:
    if ('cx1' in self.cluster_name or 'cx2' in self.cluster_name):
      ict = True; hector = False
    elif ('hector' in self.cluster_name):
      ict = False; hector = True
    else:
      raise SystemExit("In 'get_simname_walltime_ncpus_pbs', could not recognize value of 'cluster_name': "+str(self.cluster_name))


    # Load current pbs file in order to check for number of nodes, machines, cpus:
    # First: get the statfile, to extract the current number of nodes:
    (statfile, status) = find_file_names(dir, '*.stat -maxdepth 0 -not -name "*autocheckp*.stat"')
    if (status == 0):
      statfilename = statfile[0]
      # Now find the column number of the coordinate mesh nodes:
      cmd = 'head -50 '+dir+'/'+statfilename
      out = commands.getoutput(cmd)
      # loop over 'head' output:
      for line in out.strip().split('\n'):
        # process the line with number of nodes:
        if ('CoordinateMesh' in line and 'nodes' in line):
          ls = line.strip().split('<field column=')
          for j in ls:
            if (not (j.isspace() or j == '')):
              node_col_num = j.split('"')
              node_col_num = node_col_num[1].strip()
              break
          break
      # Process last line of that statfile, to get the current number of nodes:
      cmd = 'tail -1 '+dir+'/'+statfilename
      out = commands.getoutput(cmd)
      num_nodes = out.split()[int(node_col_num)-1]
      new_total_ncpus = int(round(float(num_nodes)/float(self.nnopercpu)))
      #if ('cx1' in self.cluster_name):
      #  if (new_total_ncpus > 72):
      #    new_total_ncpus = 72
    else: # statfile could not be opened, probably it doesn't exist
      new_total_ncpus = self.total_ncpus
    # check if the simulation in running in serial, and keep it that way:
    if (self.total_ncpus == 1):
      new_total_ncpus = self.total_ncpus

    # Now that the current number of nodes are known, load pbs files, and process it:
    infile = open(dir+'/pbs.sh', 'r')
    lines = infile.readlines()
    infile.close()

    searchstring_pbswalltime = '#PBS -l walltime=' # search for this in the pbs script
    searchstring_queue = '#PBS -q'
    if (ict):
      searchstring_ncpus = '#PBS -l select' # search for this in the pbs script
    elif (hector):
      searchstring_nprocs = '#PBS -l mppwidth' # search for this in the pbs script
      searchstring_ncpupn = '#PBS -l mppnppn' # search for this in the pbs script
    queue = str(self.queue)
    queue_string_found = False
    searchstring_mpiexec = 'mpiexec'
    searchstring_pbsexec = 'pbsexec'
    searchstring_aprun = 'aprun -n'
    searchstring_cpfluidity = 'cp $FLUIDITY_DIR/bin/fluidity $PBS_O_WORKDIR/'
    searchstring_cpflredecomp = 'cp $FLUIDITY_DIR/bin/flredecomp $PBS_O_WORKDIR/'
    if (ict):
      all_searchstrings = [searchstring_pbswalltime, searchstring_ncpus, searchstring_queue, searchstring_mpiexec, searchstring_pbsexec, searchstring_cpfluidity, searchstring_cpflredecomp]
    elif (hector):
      all_searchstrings = [searchstring_pbswalltime, searchstring_nprocs, searchstring_ncpupn, searchstring_aprun, searchstring_cpfluidity, searchstring_cpflredecomp]

    # newlines are the lines to be written to the pbs file:
    newlines = []
    for line in lines:
      line = line.strip()
      if (not (any([(searchstring in line) and True for searchstring in all_searchstrings]))):
        newlines.append(line+'\n')
        continue
      if (searchstring_pbswalltime in line):
        # Setting the pbswalltime for this simulation:
        newlines.append('#PBS -l walltime='+self.pbs_walltime+'\n')
        continue
      # Setting specific pbs queue:
      if (ict and line.startswith(searchstring_queue)):
        queue_string_found = True
        if (str(self.queue) == 'None'):
          queue = line.split(searchstring_queue)[-1].split('#')[0]
          newlines.append('#PBS -q '+queue+'\n')
        else:
          if (not (self.queue == '---' or self.queue.strip() == '')): # meaning, we don't want a specific queue
            queue = str(self.queue)
            newlines.append('#PBS -q '+queue+'\n')
        continue
      if ((ict and (searchstring_ncpus in line)) or (hector and (searchstring_nprocs in line or searchstring_ncpupn in line))):
        ## Get number of machines the sim is running on (cx1/2 only):
        if (ict and self.nmachines == '---'): # thus it was not set by user
          nmachines = line.split('select=')[-1].split(':')[0]
        else: nmachines = self.nmachines
        ## And the number of cpus per machine:
        if (self.ncpus == '---'): # thus it was not set by user
          if (ict):
            ncpus = line.split('ncpus=')[-1].split(':')[0]
          elif (hector and searchstring_ncpupn in line):
            ncpus = line.split('mppnppn=')[-1]
        else: ncpus = self.ncpus
        # And the memory (cx1/2 only):
        if (self.memory == '---'): # thus it was not set by user
          if (ict):
            memory = line.split('mem=')[-1].split(':')[0]
          elif (hector): memory = 'NAN'
        else: memory = self.memory
        # And the infiniband (cx1 only):
        if (ict and self.infiniband == '---'): # thus it was not set by user
          infiniband = 'true' == line.split('icib=')[-1].split(':')[0].split('#')[0].lower()
        else: infiniband = self.infiniband
        # For hector, get the number of total processes:
        if (hector and searchstring_nprocs in line):
          total_ncpus = line.split('mppwidth=')[-1]

        # Try to compute new pbs parameters:
        try:
          if ('cx1' in self.cluster_name or hector): actual_ncpus_pnode = ncpus
          elif ('cx2' in self.cluster_name): actual_ncpus_pnode = self.mpiprocs
          if (ict):
            total_ncpus = int(nmachines) * int(actual_ncpus_pnode)
          elif (hector):
            nmachines = int(round(float(total_ncpus)/float(ncpus)))
          # Now compute the new number of machines for the checkpointed simulation:
          newnmachines = int(round(float(new_total_ncpus) / float(ncpus)))
          if ('cx1' in self.cluster_name): 
            if (newnmachines > 6):
              newnmachines = 6 # have to cap as 6 nodes are the maximum on cx1
          elif ('cx2' in self.cluster_name):
            if (newnmachines > 72):
              newnmachines = 72 # have to cap as 72 nodes are the maximum on cx2
          elif (hector):
            # Just for safety sake, once I want to hit that limit, I'll take this if clause out:
            if (newnmachines > 1024):
              newnmachines = 1024 # have to cap as 72 nodes are the maximum on cx2
              raise SystemExit()
          elif (newnmachines == 0):
            newnmachines = 1

          # Let's not allow the number of processors to decrease:
          if (newnmachines < int(nmachines)):
            newnmachines = int(nmachines)
          new_total_ncpus = int(newnmachines) * int(actual_ncpus_pnode)
          # Update ncpus registered for this simulation:
          self.update_sim_properties(dir, nmachines=newnmachines, ncpus=ncpus, memory=memory, infiniband=infiniband, total_ncpus=new_total_ncpus, queue=queue)
        except SystemExit:
          errormsg = 'Error: Wanted to request more than 1024 machines on HECToR!\nExit...'
          self.messaging.write_to_log_err_file(dir, errormsg, msgtype='err')
          raise SystemExit()
        except:
          errormsg = 'Error: Could not convert nmachines, ncpus found in pbs script to integers!'
          self.messaging.write_to_log_err_file(dir, errormsg, msgtype='err')
        # new PBS command:
        if (ict):
          if ('cx1' in self.cluster_name):
            if (str(infiniband).lower() == 'true' or infiniband):
              pbscmd = "#PBS -l select="+str(newnmachines)+":ncpus="+str(ncpus)+":mem="+memory+':icib='+str(infiniband).lower()
            else:
              pbscmd = "#PBS -l select="+str(newnmachines)+":ncpus="+str(ncpus)+":mem="+memory
          elif ('cx2' in self.cluster_name):
            pbscmd = "#PBS -l select="+str(newnmachines)+":ncpus="+str(ncpus)+":mpiprocs="+str(self.mpiprocs)+":ompthreads="+str(self.ompthreads)+":mem="+memory
        elif (hector):
          if (searchstring_nprocs in line):
            pbscmd = "#PBS -l mppwidth="+str(new_total_ncpus)
          elif (searchstring_ncpupn in line):
            pbscmd = "#PBS -l mppnppn="+str(ncpus)
        # append/replace command to pbs file:
        newlines.append(pbscmd+'\n')
        continue
      else:
        if ('cp $FLUIDITY_DIR/bin/fluidity' in line):
          newlines.append(line+'\n')
          if (newnmachines > int(nmachines)):
            # copying flredecomp into working directory:
            newlines.append('cp $FLUIDITY_DIR/bin/flredecomp $PBS_O_WORKDIR/'+' \n')
          continue
        elif('cp $FLUIDITY_DIR/bin/flredecomp $PBS_O_WORKDIR/' in line):
          continue
        elif ((searchstring_pbsexec in line or searchstring_mpiexec in line or searchstring_aprun in line) and 'flredecomp' in line):
          continue
        elif ((searchstring_mpiexec in line or searchstring_aprun in line) and 'fluidity' in line and not line.startswith('#')):
          # this is the line for running the simulations:
          # IF new number of nodes is greater than old number of nodes, then redecomp the mesh:
          if (new_total_ncpus > total_ncpus):
            # First assemble the line for flredecomp:
            oldflmlfilename = flml_filename
            newflmlfilename = oldflmlfilename.replace('.flml', '_redecomped.flml')
            flredecompcmd = ''
            if (ict):
              flredecompcmd = flredecompcmd+'pbsexec mpiexec '
            elif (hector):
              flredecompcmd = flredecompcmd+'aprun -n '+str(new_total_ncpus)+' -N '+str(ncpus)+' '
            flredecompcmd = flredecompcmd+'./flredecomp -v -l -i '+str(total_ncpus)+' -o '+str(new_total_ncpus)+' '+oldflmlfilename.replace('.flml','')+' '+newflmlfilename.replace('.flml', '')+'; '
            # cx1 specific:
            if ('cx1' in self.cluster_name):
              flredecompcmd = flredecompcmd+'pbsdsh2 cp -rpf $TMPDIR/\* $PBS_O_WORKDIR/; cd $PBS_O_WORKDIR; '
            flredecompcmd = flredecompcmd+'mv '+newflmlfilename+' '+oldflmlfilename+'; '
            # again, cx1 specific:
            if ('cx1' in self.cluster_name):
              flredecompcmd = flredecompcmd+'pbsdsh2 cp -rpf $PBS_O_WORKDIR/\* $TMPDIR/; cd $TMPDIR'
            newlines.append(flredecompcmd+'\n')
          # Now that we dealt with flredecomp, for HECToR we also need to modify the line in which we start fluidity IFF new_total_ncpus != total_ncpus:
          if (hector):
            if (new_total_ncpus > total_ncpus):
              runline = 'aprun -n '+str(new_total_ncpus)+' -N '+str(ncpus)+' ./fluidity '+line.split('/fluidity')[-1]
            else:
              runline = line
          elif (ict): runline = line  
          newlines.append(runline+'\n')
          continue

    # Before we start writing the assembled information to the pbs.sh file, let's check if this simulation 
    # should run on a specific queue, but the corresponding string was not found in the preset pbs.sh file:
    if (not (queue_string_found) and 'cx1' in self.cluster_name):
      if (not (str(self.queue) == 'None' or self.queue == '---' or self.queue.strip() == '')):
        for i in range(len(newlines)):
          if (searchstring_pbswalltime in newlines[i]):
            newlines[i] = newlines[i]+'#PBS -q '+self.queue+'\n'
            break

    # Newlines of pbs script have been assembled, now write to file:
    outfile = open(dir+'/pbs.sh', 'w')
    pbslines = ''.join(newlines)
    outfile.write(pbslines)
    outfile.close()



  def change_simname_in_flml(self, dir, flml_filename):
    """ This subroutine simply makes use of libspud in order to update
        the simulation name in the given flml_filename.
        Input:
         dir: Name of the directory where the flml is in.
         flml_filename: Most recent flml filename that ran 
         in directory 'dir'
    """
    status = 0
    simulation_name = self.get_sim_name_from_flml(dir, flml_filename)
    if (simulation_name.find('_checkpoint') >= 0):
      automated_checkpointed_simname = simulation_name.split('_checkpoint')[0].split('_autocheckp')[0]+'_autocheckp'
      # Change simulation name and write to file:
      libspud.set_option("simulation_name", automated_checkpointed_simname)
      libspud.write_options(dir+'/'+flml_filename)
      libspud.clear_options()
      # Also: Update simname in the Monitoring class:
      self.update_sim_properties(dir, simname=automated_checkpointed_simname)
    else:
      # Also: Update simname in the Monitoring class:
      self.update_sim_properties(dir, simname=simulation_name)
    self.write_simulation_status_to_file(dir=dir)
    # End of change_simname_in_flml


  def clean_cluster_dir(self, dir, cluster_name=None):
    """ This method removes/deletes the directory 'dir' on the cluster
        Input:
         dir: String of the directory the simulation is in
         cluster_name: String of the name/address of the cluster
    """
    if (cluster_name is None):
      cluster_name = self.cluster_name
    #####################
    # Rm dir on cluster #
    #####################
    error = True; cnt = 0
    # Remove corresponding directory on cluster:
    while (cnt < self.errmaxcnt and error):
      cmd = 'ssh '+self.username+'@'+cluster_name+' "rm -rf '+self.cluster_dir+'/'+dir+'"'
      out = commands.getoutput(cmd)
      # This is a normal ssh problem:
      try:
        self.check_for_ssh_errors(out, calling_fun='clean_cluster_dir')
      except SSHConnectionException:
        # Connection is currently not available, raise exception again:
        raise SSHConnectionException
      except SSHCrucialConnectionException:
        # Crucial error appeared, quit the program as this exception deals
        # with error such as wrong username, wrong cluster name, Permission
        # issues etc. This has to be fixed by the user:
        # Thus raise the same exception again.
        raise SSHCrucialConnectionException
      else:
        error = False # ssh rm operation was successful
        break
      if (cnt >= self.errmaxcnt):
        errormsg = "Error: "+out+". Tried "+str(self.errmaxcnt)+" times to connect to "+cluster_name+"/"+self.cluster_dir+" via ssh, but could not establish connection!"
        self.messaging.message_handling(dir, errormsg, 0, msgtype='err', subject='Error: SSH rm dir')
        raise SSHConnectionException
      if (error):
        time.sleep(self.errwaittime)
    


  def clean_and_bkup_local_dir(self, dir, tar_filename):
    """ This subroutine copies the latest checkpoint into subdirectory 'bkup'
        and cleans up the mess in 'dir' a bit.
        Input:
         dir: Name of the directory to clean up
         tar_filename: String of the tar_filename which 
           contains all the neccessary files to continue
           the simulation, except for the fluidity binary.
    """
    # remove all checkpoints in 'dir', as at this time, the latest checkpoint
    # has been archived and is in the parent directory:
    cmd = 'cd '+dir+'; rm -rf *_checkpoint*'
    out = commands.getoutput(cmd) # Again, errors from shell do not matter here.
    # Before copying the tarfile with the latest checkpoint, rename previous checkpoint bkup tarfile:
    cmd = 'mv '+dir+'/bkup/most_recent_checkpoint.tar.gz '+dir+'/bkup/previous_checkpoint.tar.gz'
    out = commands.getoutput(cmd) # Again, errors from shell do not matter here.
    # Now copy the latest checkpoint to the bkup directory:
    cmd = 'mv '+tar_filename+' '+dir+'/bkup/most_recent_checkpoint.tar.gz'
    out = commands.getoutput(cmd) # Again, errors from shell do not matter here.
    # bkup stat/detectors/detectors.dat files:
    # first, work out the index the result file should have in the bkup folder:
    (statfiles, status) = find_file_names(dir+'/', '*.stat')
    if (status == 0):
      # Simulation basename:
      simbasename = self.simname.split('_autocheckp')[0]
      # Now that index has been set, copy merged files (preserving timestamps etc):
      cmd = 'cp -p '+dir+'/'+simbasename+'.stat '+dir+'/bkup/'; out = commands.getoutput(cmd)
      cmd = 'cp -p '+dir+'/'+simbasename+'.detectors '+dir+'/bkup/'; out = commands.getoutput(cmd)
      cmd = 'cp -p '+dir+'/'+simbasename+'.detectors.dat '+dir+'/bkup/'; out = commands.getoutput(cmd)
      # For safety reasons, copy checkpointed statfiles to /bkup/, and give them an index:
      (bkupstatfiles, status) = find_file_names(dir+'/bkup/', '*.stat')
      index = len(bkupstatfiles) -1
      if (index == 0):
        resfilebasename = simbasename
      else:
        resfilebasename = self.simname
      # If there are more than 1 statfile in the directory, copy the checkpointed files, and give them an index
      cmd = 'cp -p '+dir+'/'+resfilebasename+'.stat '+dir+'/bkup/'+self.simname+'_'+str(index)+'.stat'; out = commands.getoutput(cmd)
      cmd = 'cp -p '+dir+'/'+resfilebasename+'.detectors '+dir+'/bkup/'+self.simname+'_'+str(index)+'.detectors'; out = commands.getoutput(cmd)
      cmd = 'cp -p '+dir+'/'+resfilebasename+'.detectors.dat '+dir+'/bkup/'+self.simname+'_'+str(index)+'.detectors.dat'; out = commands.getoutput(cmd)
    # remove checkpointed *stat and *detectors and *detectors.dat files, and possibly
    # log and error files:
    cmd = 'cd '+dir+'; rm *autocheckp.stat *autocheckp.detectors* fluidity.*'
    out = commands.getoutput(cmd) # Doesn't matter if we get back a 'No such file or directory' error
    # Also copy the appended version of result files to bkup:
    cmd = 'cp -p '+dir+'/*stat '+dir+'/*detectors* '+dir+'/bkup/'
    out = commands.getoutput(cmd)
    # And, if still there, remove tarfile in parent directory:
    #cmd = 'rm '+tar_filename
    #out = commands.getoutput(cmd) # Again, errors from shell do not matter here.
    msg = 'Local directory has been cleaned up, and most recent checkpoint, plus stat/detectors-files have been copied to '+dir+'/bkup/'
    self.messaging.message_handling(dir, msg, 3, msgtype='log', subject='Cleaned up')


  def check_fixed_sim(self, dir=None):
    """ This subroutine checks if a crashed simulation in 
        'dir' has been taken care of manually, and if so, it
        expects a file 'is_fixed' in its local directory.
        Input:
         dir: String of the directory name.
        Output:
         simulation_crashed: False if simulation was fixed
           by the user, True otherwise
    """
    if (dir is None):
      dir = self.dir
    status = 1
    (file, status) = find_file_names(dir, 'is_fixed')
    if (status == 0):
      # remove file and old log/error files from cluster:
      out = commands.getoutput('cd '+dir+'; rm is_fixed; rm stdout stderr')
      # And update the class variable:
      simulation_crashed = False
      self.update_sim_properties(dir, simulation_crashed=simulation_crashed)
      # Message report:
      msg = 'Simulation has been flagged as fixed. Script will take it from here...'
      self.messaging.message_handling(dir, msg, 0, msgtype='err', subject='Simulation fixed')
    else:
      simulation_crashed = True
    return simulation_crashed


  def remove_previous_fluidity_output_files(self, dir=None):
    """ This method should be executed after a crashed simulation has been manually fixed,
        in order to get rid of the previous output files, as those were/might have been
        corrupted anyway.
        Input:
         dir: String of the directory name of the current simulation (being processed).
    """
    if (dir is None):
      dir = self.dir
    # First, find the flml file that was used to run the simulation the last time
    # That flml file can be easily found within the pbs script:
    # Assume the first '.flml' found within the pbs script is actually the flml
    # file, thus this does not work, if another '.flml' is somewhere within the 
    # pbs script before the actual used flml file:
    out = commands.getoutput('cd '+dir+'/; grep .flml pbs.sh')
    # Check for valid output:
    if (len(out.split('\n')) == 1):
      # Now, in case there is a '=' in that line, assume the name of the 
      # flml file is on the right side of that '=' sign:
      out = out.split('=')[-1] # if there is no '=', out stays the same!
      # Now strip white space from both ends:
      out = out.strip()
      # Out should now contain only the flml filename!
      flmlfilename = out
      # Get the simname from that flml file:
      prev_simname = self.get_sim_name_from_flml(dir, flmlfilename)
      # Now based on the simulation name in that flml file, 
      # we know which files to remove from the directory 'dir':
      cmd = 'cd '+dir+'/; rm '+prev_simname+'*'
      out = commands.getoutput(cmd)
      


# Methods for checking scp and ssh etc errors:
  def check_for_ssh_errors(self, string, dir=None, calling_fun=None):
    """ This function checks for common ssh errors in a given string
        and raises an user-defined exception if such an error was found.
        Input:
         string: A string, should be the output string of a ssh operation.
         dir: String of the directory for which ssh errors are checked.
         calling_fun: String of the calling function, which is used for
           an error message
    """
    # Taking care of optional argument:
    if (dir is None):
      dir = self.dir
    # Common SSH errors:
    ssh_errors = ['Connection closed by', 'Connection timed out', 'lost connection', 'ssh_exchange_identification', 'Name or service not known', 'Permission denied']
    # Loop over defined common ssh_errors, and check if a common string
    # from ssh_errors is found in the given string:
    for error in ssh_errors:
      if (string.find(error)>=0):
        # Find out which exception to raise:
        if (error in ['Connection closed by', 'Connection timed out', 'lost connection']):
          # These errors are not so crucial, thus the program will keep running
          # when the following exception is raised:
          # Error message:
          errmsg = 'SSHConnectionException caught during "'+calling_fun+'".\nCluster probably too busy right now, will try again later...'
          self.messaging.message_handling(dir, errmsg, 2, msgtype='err', subject='SSH Connection not established')
          # Raise exception:
          raise SSHConnectionException
        if (error in ['ssh_exchange_identification', 'Name or service not known', 'Permission denied']):
          # This error is crucial, and will never work unless the user fixes the issue,
          # e.g. wrong username, wrong cluster name, ...
          # Error message:
          errmsg = 'SSHCrucialConnectionException caught during "'+calling_fun+'". Something is wrong with the setup, e.g. wrong username/clustername, or permission issues.\nFix this issue.\nProgram will exit now!'
          self.messaging.message_handling(dir, errmsg, 0, msgtype='err', subject='SSH setup is wrong')
          raise SSHCrucialConnectionException

  def check_for_ssh_qstat_error(self, string):
    """ This function checks if the given string contains common strings
        from the output of "qstat -a" and raises an user-defined exception
        if no such substring was found.
        Input:
         string: The string of the output from "qstat -a"
    """
    # Common qstat -a output substrings:
    qstat_sstrings = ['Job ID', 'Username', 'Queue', 'Jobname', 'SessID', 'NDS', 'TSK', 'Memory', 'Time', 'S']
    # If the cluster is cx1, we can skip the following operation, as cx1 only gives back a list of the jobs
    # belonging to the user "username" when executing "qstat -a".
    # REMEMBER: We do run "qstat -a" instead of "qstat -a -u username" or "qstat -a | grep username" on purpose, 
    # in order to check if the returned output contains typical "qstat -a" substrings or not. If not, it means
    # that something went wrong and we should run the command again. Exception is however cx1 which only returns
    # the user's jobs, and if none are running (anymore) an empty string from "qstat -a" is expected and thus valid.
    # Loop over lines of the given string, and check if we find any "qstat -a" substrings:
    corr_output = []
    # check if this simulation ran on cx1:
    if ('cx1' in self.cluster_name.lower()):
      corr_output.append(True)
    else: # else we have to check for the output from "qstat -a":
      for line in string.split('\n'):
        if (line.startswith(qstat_sstrings[0])): # this is the line we want to check:
          for sstring in qstat_sstrings[1:]:
            corr_output.append(sstring in line)
          # After finishing checking the line for all expected substrings, break out of the loop:
          break
    # Now we can check if all entries of the boolean list are True or not:
    if (not (all(corr_output))):
      raise SSHQstatException

  def check_for_scp_errors(self, string, dir=None, calling_fun=None):
    """ This method checks for common scp errors in a given string
        and raises an user-defined exception if such an error was found.
        Input:
         string: A string, should be the output string of a scp operation.
         dir: String of the directory for which ssh errors are checked.
         calling_fun: String of the calling function, which is used for
           an error message
    """
    # Taking care of optional argument:
    if (dir is None):
      dir = self.dir
    # Common SCP errors:
    scp_errors = ['Connection closed by', 'Connection timed out', 'lost connection', 'Name or service not known', 'No such file or directory', 'Permission denied']
    # Loop over defined common scp_errors, and check if a common string
    # from scp_errors is found in the given string:
    for error in scp_errors:
      if (string.find(error)>=0):
        # Find out which exception to raise:
        if (error in ['Connection closed by', 'Connection timed out', 'lost connection']):
          # Errormessage:
          if (not (calling_fun is None)):
            # Error message:
            errmsg = 'Minor exception caught during "'+calling_fun+'".\nCluster probably too busy right now, will try again later...'
            self.messaging.message_handling(dir, errmsg, 2, msgtype='err', subject='Connection not established')
          # Raise exception
          raise SCPException
        if (error in ['Name or service not known', 'Permission denied']):
          # This error is crucial, and will never work unless the user fixes the issue,
          # e.g. wrong username, wrong cluster name, ...
          # Errormessage:
          if (not (calling_fun is None)):
            errmsg = 'SCPCrucialException caught during "'+calling_fun+'". Something is wrong with the setup, e.g. wrong username/clustername, or permission issues.\nFix this issue.\nProgram will exit now!'
            self.messaging.message_handling(dir, errmsg, 0, msgtype='err', subject='SSH setup is wrong')
          # Raise exception
          raise SCPCrucialException

  def check_for_ssh_tar_errors(self, string, dir=None, calling_fun=None):
    """ This function checks for common ssh errors, tar errors and
        disk quota errors in a given string and raises an user-defined
        exception if such an error was found.
        Input:
         string: A string, should be the output string of a ssh operation.
         dir: String of the directory for which ssh errors are checked.
         calling_fun: String of the calling function, which is used for
           an error message
    """
    # Boolean to check if tar error is based on "file not found" error
    filenotfound = False
    filecrucial = False # Boolean to determine if file is crucial!
    unknowntarerror = False
    # Taking care of optional argument:
    if (dir is None):
      dir = self.dir
    # Check for common ssh exceptions:
    self.check_for_ssh_errors(string, dir=dir, calling_fun=calling_fun)
    # If that went well, check for disk quota and tar errors:
    cluster_tar_errors = ['Disk quota exceeded', 'Cannot stat: No such file or directory', 'tar: Exiting with failure status']
    # Loop over defined common cluster_tar_errors, and check if a common string
    # from cluster_tar_errors is found in the given string:
    for error in cluster_tar_errors:
      if (string.find(error)>=0):
        # Find out which exception to raise:
        if (error in ['Disk quota exceeded']):
          # Crucial error: This should cause the program to end, as this is sth
          # the user has to fix on the cluster, and subsequent iterations will
          # run into the same error:
          # Error message:
          errmsg = 'Error: DiskQuotaException caught during "'+calling_fun+'".\nClean up your space.'
          self.messaging.message_handling(dir, errmsg, 2, msgtype='err', subject='DiskQuotaException caught')
          # Raise exception:
          raise DiskQuotaException
        elif (error in ['Cannot stat: No such file or directory']):
          # This means that at least one expected file was not found on the cluster: Now work out the exact
          # error message from tar and find out if a crucial files was not found:
          tarerrormsg = ''
          stringlist = string.split('\n')
          filenotfound = True
          for line in stringlist:
            if (line.startswith('tar:') and line.endswith('No such file or directory')):
              # Append this line to tarerrormsg:
              tarerrormsg = tarerrormsg+'\n'+line
              # Also check if the current simname is part of this line, if so, this is a more crucial error:
              if (line.find(self.simname) >= 0):
                filecrucial = True
        elif (error in ['tar: Exiting with failure status']):
          unknowntarerror = True

    # After for loop, raise the right tar exception:
    if (filenotfound and not filecrucial):
      # Error message:
      errmsg = 'Error: TarException caught during "'+calling_fun+'".\nThis means that at least one file was not found on the cluster.\nThe tar error was:\n'+tarerrormsg
      self.messaging.message_handling(dir, errmsg, 2, msgtype='err', subject='TarException on cluster caught')
    elif (unknowntarerror and filenotfound and filecrucial):
      # This means that a crucial file was not found, a crucial file is simname*
      # Error message:
      errmsg = 'Error: TarCrucialException caught during "'+calling_fun+'".\nCould not find any file that starts with the simulation name '+self.simname+'.'
      self.messaging.message_handling(dir, errmsg, 0, msgtype='err', subject='TarCrucialException on cluster caught')
      raise TarCrucialException
    elif (not filenotfound and unknowntarerror):
      # This is an unknown tar error, give error report and raise crucial exception:
      # Error message:
      errmsg = 'Error: TarCrucialException caught during "'+calling_fun+'".\nCould not figure out what went wrong with this. Please check yourself.'
      self.messaging.message_handling(dir, errmsg, 0, msgtype='err', subject='TarCrucialException on cluster caught')
      raise TarCrucialException


  def write_dict_status_pgftable(self, dict=None, printcols=None, string_replace=None, postprocessing=None, pdflatex=True, pdfcrop=True):
    """ This method assembles lists of the content of the given dictionary
        and then calls methods to write pgf data files of the dictionary,
        and to update the pdf showing the table.
        Input:
         dict: 2D Dictionary of which all content will be written to file
         printcols: List of columns to print in the table, whereas the elements
           of 'printcols' refer to the strings of the column labels of the datafile
         printcolnames: 1D dictionary of column labels as they appear in the
           datafile, and their values being the string that should be printed instead.
         string_replace: List of lists, with the inner list having n elements,
           with the first element being the string of the the affected columnname,
           and the following elements being lists of two elements each, with the
           first element of those list being the text to be replaced, and the
           second the text that should appear in the table instead.
           Example: [
                     ['col1', ['replace', 'write-this'], ['replace_this_too', 'this-instead']],
                     ['col2', ['replace-here', 'this-is-good']]
                    ]
         postprocessing: List of lists, whereas inner list has 4 elements:
           1: column name to postprocess, 2: LaTeX code to add to the column,
           3: must either be 'unit' and 4: is either True or False, determining
           if the second element is supposed to be a unit or not.
         pdflatex: Boolean determining if pdflatex should run on the
           generated texfile
         pdfcrop: Boolean determining if pdfcrop should run on the
          generated pdf
    """
    # Define colors:
    color_err = '\\color{red!60!black}'
    color_run = '\\color{blue!60!black}'
    color_que = '\\color{magenta!90!black}'
    color_fin = '\\color{green!60!black}'

    # If not given, assemble a list of postprocessing entries in the table:
    if (postprocessing is None):
      postprocessing = [
             ['sim_time', 's', 'unit', True],
             ['status', '\\bfseries', 'unit', False]
           ]

    # If not given, assemble a default list of replacing entries in the table:
    if (string_replace is None):
      string_replace = [
             ['status', ['Q', color_que+'Q'], ['R', color_run+'R'], ['F', color_fin+'F'], ['E', color_err+'E'], ['H', color_err+'H'] ],
             ['simulation_running', ['False', color_err+'\\texttimes'], ['True', color_fin+'\\checkmark'] ],
             ['simulation_crashed', ['False', color_fin+'\\texttimes'], ['True', color_err+'\\checkmark'] ],
             ['simulation_finished', ['False', color_err+'\\texttimes'], ['True', color_fin+'\\checkmark'] ],
             ['sim_clean_exit', ['False', color_err+'\\texttimes'], ['True', color_fin+'\\checkmark'] ],
             ['infiniband', ['False', color_err+'\\texttimes'], ['True', color_fin+'\\checkmark'] ],
             ['memory', ['NAN', '---'], ['NaN', '---'], ['Nan', '---'], ['nan', '---'] ]
           ]
      for i in range(7):
        if (i == 0):
          appendlist = ['error_status', [i, color_fin+'$\\mathbf{'+str(i)+'}$']]
        else:
          appendlist = ['error_status', [i, color_err+'$\\mathbf{'+str(i)+'}$']]
        string_replace.append(appendlist)
    # Start processing the dictionary:
    if (dict is None):
      dict = self.dict
    # First assemble the header of the table:
    #for dir in sorted_nicely(dict.iterkeys()):
    for dir in sorted(dict.iterkeys()):
      array_labels = ['dirname']
      for key, value in sorted(dict[dir].items()):
        # Key is pratically the header of our table, with a leading
        # 'dirname', as the directory name of the simulation is not
        # stored in 'key', but in 'dir'. value is the content of the
        # table.
        array_labels.append(key)
      break
    
    # Now the content of the table, each row below the header:
    table_rows = [[0 for j in range(len(array_labels))] for i in range(len(dict.keys()))]
    i = 0
    #for dir in sorted_nicely(dict.iterkeys()):
    for dir in sorted(dict.iterkeys()):
      for key, value in sorted(dict[dir].items()):
        j = 0
        # Set different colors depending on simulation crashed/running/finished
        color = ''
        if (dict[dir]['simulation_crashed'] == True or dict[dir]['status'] == 'E' or dict[dir]['status'] == 'H' or dict[dir]['sim_clean_exit'] == False):
          color = color_err        
        elif (dict[dir]['simulation_running'] == True):
          if (dict[dir]['status'] == 'R'):
            color = color_run
          elif (dict[dir]['status'] == 'Q'):
            color = color_que
        elif (dict[dir]['simulation_finished'] == True and dict[dir]['status'] == 'F'):
          color = color_fin
        table_rows[i][j] = str(dir)
        for key, value in sorted(dict[dir].items()):
          j = j + 1
          table_rows[i][j] = str(value)
      # For this dirname, add an entry into string_replace,
      # in order to add color and proper \_ for the table:
      string_replace.append(['dirname', [dir, color+remove_underscore_preserve_math_mode(dir, replace_char='\_')]])
      i = i + 1
    # Write datafile:
    pgfdat_filename = 'logfiles/dict_status_table.pgfdat'
    write_pgfplots_data_file(pgfdat_filename, table_rows, array_labels=array_labels)
    # Now write texfile to generate the pdf with the status-table:
    texfile = 'logfiles/dict_status_table.tex'
    # Get pwd:
    pwd = commands.getoutput('pwd')
    caption = 'Status of running simulations in: \\texttt{'+remove_underscore_preserve_math_mode(pwd, replace_char='\_')+'}'

    # If this method was given a specific header, meaning a specific order of printing the columns
    # in the table, then this list should be given to the texfile, rather than the unsorted columnlist
    # that was obtained from the dictionary.
    if (printcols is None):
      printcols = array_labels

    # Assemble dictionary for printcolnames (only if we want to change the column name):
    printcolnames = {'nmachines' : 'nodes', 'ncpus' : 'cpus', 'total_ncpus' : 'ncpus', 'memory' : 'mem', 'infiniband' : 'icib', 'sim_time' : 'time', 'error_status' : 'error', 'walltime' : 'wt', 'mpiprocs' : 'mpi'}

    # sorting the table by column total_ncpus:
    #sort_colname = 'total_ncpus'

    # Write to texfile:
    write_pgfplotstable_tex_file(texfile, pgfdat_filename, array_labels, table_rows, printcols=printcols, printcolnames=printcolnames, 
                                 string_replace=string_replace, postprocessing=postprocessing, caption=caption)
    if (pdflatex):
      # Produce pdf:
      (dir, texfile) = convert_filename_to_path_and_filename(texfile)
      run_latex(dir, texfile)
      if (pdfcrop):
        # Crop white space from pdf:
        run_pdfcrop(dir, texfile[:-3]+'pdf', 'cropped_'+texfile[:-3]+'pdf')


  def write_dict_status_to_file(self):
    """ This method dumps the crucial status information of each simulation
        in an extra file ./logfiles/dict_status_dirname.
    """
    # Assemble status text to be written to file:
    # Assemble status of all registered simulations of the current pwd, 
    # and write status to status files:
    for dir in sorted_nicely(self.dict.keys()):
      self.write_simulation_status_to_file(dir=dir)


  def write_simulation_status_to_file(self, dir=None):
    """
        Write the status of one simulation to its corresponding status file
        Input:
         dir: String of the directory name the simulation sits in
    """
    # Write status of the given simulation (corresponding to 'dir')
    # to its status file:
    if (dir is None):
      dir = self.dir
    # Get 1D dictionary with all the properties for this 'dir':
    dir_dict = self.get_dict(dir=dir)
    statusfile = 'logfiles/dict_status_'+dir
    # Assembling content of the file:
    status = 'directory: ' + dir + '\n'
    for key, value in sorted(dir_dict.items()):
      status = status + str(key) + ': ' + str(value) + '\n'
    # Write simulation status to file:
    string_append_to_file(status, statusfile, append=False)


  def get_hashes(self, msg):
    """ This method simply creates a string of hashes, that is as
        long as the input argument string 'msg'.
        Input:
         msg: String of an arbitrarily long string. Its length is
           evaluated in order to generate a string of hashes with
           the same length
        Output:
         hashes: String of hashes that is as long as the input argument.
    """
    hashes = ''
    for i in range(len(msg)):
      hashes = hashes+'#'
    return hashes
  
  
  def get_ascii_string(self, msg, character='#'):
    """ This method generates a line of the given character, which
        is as long as the string given in the input argument 'msg'.
        Input:
         msg: String of an arbitrarily long string. Its length is
           evaluated in order to generate a string of hashes with
           the same length
         character: A line of only this character is generated, its
           default value is the hash character '#'
        Output:
         line: Generated string of only character of the given
           optional input argument 'character'.
    """
    line = ''
    for i in range(len(msg)):
      line = line+character
    return line


  def wait_between_query(self, waittime=None):
    """ This method simple waits until the next round of checking all registered
        simulations in the subdirectories starts. The time is given by
        waittime.
        Input:
         waittime: Integer of seconds to wait.
    """
    try:
      if (waittime is None):
        waittime = self.query_waittime
      # Wait the given time and update the standard output with the
      # countdown until the next round starts:
      outputtext = ' Seconds to wait until next iteration: '
      for i in range(waittime+1):
        output = '\r'+outputtext+str(waittime-i)
        # Append blanks to the end of the output, such that previous digits are overwritten:
        for i in range(len(str(waittime)) - len(str(i)) ):
          output = output+' '
        printc(output, 'blue', False),
        sys.stdout.flush()
        time.sleep(1)
    except:
      errormsg = 'Error: Exception caught during time.sleep()'
      raise WaitBetweenQueryException(errormsg)



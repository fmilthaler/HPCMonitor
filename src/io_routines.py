from numpy import *
import os
import commands
import sys
import re
import fluidity_tools

"""
   Module for IO routines, i.e. reading input from files,
   writing output to files and/or the screen
"""


def get_dictionary_from_datafile(csvfile, firstcolname=None, separator=','):
    """ This method assembles a 2D dictionary from the content of a standard csv file.
        Requirement: The datafile must be a comma seperated table, and (if given),
        the first column name must match the given firstcolname (uppper and lower letters
        are allowed). If a first column name is not given, then the dictionary
        is still going to be assembled in the same way, but the first column name
        is not checked for. Note: The first column name will not appear in the dictionary,
        but the content of the first column are used as keys for the outer dictionary.
        Input:
         csvfile: String of the datafile to process
         firstcolname: String of the first column name expected and therefore allowed,
           optional argument, default value: None
         separator: Separator character used in the csv file, default is ','
        Output:
         dict: 2D dictionary, with the content of the datafile.
    """
    # Read in information from table showing esesis id and name/cid
    infile = open(csvfile)

    header = infile.readline().strip() # header of table
    if (not (firstcolname is None)):
        if (not (header.split(separator)[0].lower().startswith(firstcolname.lower()))):
            raise Exception('This script assumes the first column to be '+firstcolname+', this seems not to be the case. Do you load the correct datafile? Or is your assumed first column name wrong?')

    # Assemble keys of dictionary:
    keys = []
    for key in range(len(header.split(separator))):
        keys.append(header.split(separator)[key])
    # Initialise dictionary:
    dict = {}
    for line in infile:
        line = line.strip()
        info = line.split(separator)
        if (len(line) > 0):
            dict.update({info[0] : {}})
            # Now fill students entry with rest of info:
            for i in range(1, len(keys), 1):
                dict[info[0]].update({keys[i].replace(' ','') : info[i].strip().replace(' ','').replace("'",'').replace('"','')})
    # Closing file:
    infile.close()
    # return assembled dictionary:
    return dict


# Function taken from:
# http://blog.paphus.com/blog/2012/09/04/simple-ascii-tables-in-python/
def print_ascii_table(data, separate_head=True):
    """Prints a formatted table given a 2 dimensional array"""
    #Count the column width
    widths = []
    for row in data:
        for i,size in enumerate([len(str(x)) for x in row]):
            while i >= len(widths):
                widths.append(0)
            if size > widths[i]:
                widths[i] = size
    #Generate the format string to pad the columns
    print_string = ""
    for i,width in enumerate(widths):
        print_string += "{" + str(i) + ":" + str(width) + "} | "
    if (len(print_string) == 0):
        return
    print_string = print_string[:-3]
    #Print the actual data
    for i,row in enumerate(data):
        print(print_string.format(*row))
        if (i == 0 and separate_head):
            print("-"*(sum(widths)+3*(len(widths)-1)))


def file_append_to_file(firstfile, secondfile):
  """ This subroutine uses the linux command 'cat' in
      order to append the content of the secondfile
      to the firstfile.
      Input:
       firstfile: String of the filename of the file
         to which we want to append data to.
       secondfile: String of the filename of the file we
         wish to append to firstfile.
  """
  status = 0
  cmd = "cat "+secondfile+" >> "+firstfile
  out = commands.getoutput(cmd)
  if (out.find("No such file or directory") >= 0):
    errormsg = "Error: Could not append "+secondfile+" to "+firstfile+" via the 'cat' command. Error was: "+out+"."
    printc(errormsg, 'red', False); print
    status = 1
  return status


def string_append_to_file(data, file, append=True):
  """ This subroutine uses the linux command 'echo' in
      order to append a string to the file 'file'.
      Input:
       data: String of some text that should be appended
         to the file 'file'.
       file: String of the filename to which we append
         'data'.
       append: Boolean, true if data should be appended to
         existing file, and false if the file should be
         overwritten.
  """
  if (append):
    tofile = '>>'
  else:
    tofile = '>'
  cmd = 'echo -e "'+data+'" '+tofile+' '+file
  out = commands.getoutput(cmd)


def python_append_to_file(filename, data, append=True):
  """ This subroutine appends data to an existing file. 
      Therefore the filename and the data to be appended
      have to be given via input arguments.
      Input:
       filename: String of the filename the data is appended.
       data: List of data that is appended to file, of which
         each element of the list represents one line in 
         the file.
       append: Boolean, if True, data is appended to the file,
         else the file is overwritten (default: True).
  """
  if (append):
    file = open(filename, 'a')
  else:
    file = open(filename, 'w')
  # Parse the data in the new/most recent statfile:
  for line in data:
    # Append line to end of oldstatfile:
    file.write(line)
  file.close()


def find_file_dir_name(dir, searchstring, type, depth=None):
  """
     This routine takes in a searchstring for the shell command
     'find' as well as its optional argument of which type it 
     is supposed to look for, e.g. 'd' for directory
     Input:
      dir: String of the directory name where it should look for the files.
      searchstring: String of what 'find' should search for
      type: character defining the type of files 'find' should look for
     Output:
      files: List of strings with the found directories/files in 'dir'
      status: Status is 0 when file were found that match the searchstring,
        and 1 if no such files or directories were found.
  """
  status = 0
  if (depth is None):
    cmd = 'cd '+dir+'; find '+searchstring+' -type '+type
  else:
    try:
      depth = int(depth)
    except:
      errormsg = "input argument 'depth' must be an integer number!"
      print errormsg
      raise SystemExit()
    #cmd = 'cd '+dir+'; find '+searchstring+' -maxdepth '+str(depth)+' -type '+type
    cmd = 'cd '+dir+'; find -maxdepth '+str(depth)+' -name "'+searchstring+'" -type '+type
  files = commands.getoutput(cmd)
  if (files.rfind("No such file or directory") >= 0 or files == ""):
    errormsg = 'ERROR: Could not find any '
    if (type == 'd'): 
      errormsg = errormsg+'directory'
    elif (type == 'f'):
      errormsg = errormsg+'file'
    elif (type == 'l'):
      errormsg = errormsg+'link'
    errormsg = errormsg+' that matches input searchstring: '+searchstring
    printc(errormsg, 'red', False); print
    status = 1
  return files, status


def find_dir_names(dir, searchstring, depth=None):
  dirname = []
  (dirs, status) = find_file_dir_name(dir, searchstring, 'd', depth)
  if (status != 0):
      # Try symlinks instead:
      (dirs, status) = find_file_dir_name(dir, searchstring, 'l', depth)
  if (status == 0):
    for i in range(len(dirs.split('\n'))):
      dir = dirs.split('\n')[i]
      dirname.append(dir)
    # Removing duplicates in dirname
    correct_dirname = list(set(dirname))
  else:
    correct_dirname = '';
  return correct_dirname, status


def find_link_names(dir, searchstring, depth=None):
  dirname = []
  (dirs, status) = find_file_dir_name(dir, searchstring, 'l', depth)
  if (status == 0):
    for i in range(len(dirs.split('\n'))):
      dir = dirs.split('\n')[i]
      dirname.append(dir)
    # Removing duplicates in linkname
    correct_dirname = list(set(dirname))
  else:
    correct_dirname = '';
  return correct_dirname, status


def find_file_names(dir, searchstring, depth=None):
  filename = []
  (files, status) = find_file_dir_name(dir, searchstring, 'f', depth)
  if (status == 0):
    for i in range(len(files.split('\n'))):
      file = files.split('\n')[i]
      filename.append(file)
    # Removing duplicates in filename
    correct_filename = list(set(filename))
  else:
    correct_filename = '';
  return correct_filename, status


def get_file_names(searchstring):
  status = 0
  filename = []
  files = commands.getoutput('ls '+searchstring)
  files = files.split('\n')
  for i in files:
    try:
      file = i.split('/')[-1]
    except:
      file = i
    filename.append(file)
  # Removing duplicates in filename:
  correct_filename = list(set(filename))
  if (correct_filename[0].find("No such file or directory") >= 0):
    # Error occured:
    errormsg = 'Error: Trying to find files with '+searchstring+' but none were found!'
    printc(errormsg, 'red', False); print
    correct_filename = ''; 
    status = 1
  return correct_filename, status


def remove_checkpointed_files_from_statfile_list(filenamelist):
  correct_filename = []
  for file in filenamelist:
    if (not file.endswith("checkpoint.stat")):
      correct_filename.append(file)
  return correct_filename


def generate_list_statfiles(listfilename, searchstring):
  ## Get name of file where all the filenames will be stored,
  ## and a searchstring, the string for which will be searched
  cmd = 'ls -rt '+searchstring+' > ' +listfilename
  out = commands.getoutput(cmd)


def sort_reverse_string_list(stringlist):
  stringlist.sort()
  stringlist.reverse()
  return stringlist


def sort_string_list(stringlist):
  stringlist.sort()
  return stringlist

# Function taken from:
# http://stackoverflow.com/questions/2669059/how-to-sort-alpha-numeric-set-in-python
def sorted_nicely(l):
    """ Sort the given iterable in the way that humans expect."""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

# sort-function interface:
# determines wheter it should sort alphnumerically or purely numerically:
def sortdiff(l):
    try:
        j=[isinstance(float(i),float) for i in l]
    except:
        j = [False]
    # if only numeric values in l:
    if (all(j)):
        return sorted(l)
    else:
        return sorted_nicely(l)


def convert_filename_to_path_and_filename(file):
  """ This method takes in a string of a file, which
      could or could not contains it's absolute/relative
      path. The return values are the path to the directory
      in which the file is in, plus the filename.
      Input:
       file: String of a file, with/without it's path
      Output:
       dir: String of the file's directory
       filename: String of the file's filename
  """
  if ('/' in file):
    dir = '/'.join(file.split('/')[:-1])
    filename = file.split('/')[-1]
  else:
    dir = '.'
    filename = file
  return dir, filename


def get_relative_path(path1, path2):
  """ This method returns the relative path of path2 to path1
      Input:
       path1: String of base path
       path2: String of the second path
      Output:
       rel_path: String of the relative path between path1 and path2,
         rel_path = path pointing from path1 to path2
  """
  # adding / at end of string:
  if (not path1.endswith('/')): path1 = path1+'/'
  if (not path2.endswith('/')): path2 = path2+'/'
  # Also check if either path1 or path2 point to the cwd/pwd
  newpaths = []
  for path in [path1, path2]:
    if (path.startswith('.') or path.startswith('./')):
      if (len(path) <= 2): newpaths.append('')
      else: newpaths.append(path[2:])
    else: newpaths.append(path)
  path1 = newpaths[0]; path2 = newpaths[1]

  # Check if the path1 and path2 are exactly the same:
  if (path1 == path2):
    rel_path = './'
  else:
    dirs1 = path1.split('/')
    num_dirs1 = len(dirs1)-1
    dirs2 = path2.split('/')
    num_dirs2 = len(dirs2)-1
    rel_path = ''
    # list of boolean values, indicating if the subfolder is shared between path1 and path2:
    shared_dir = []; shared = True
    for i in range(num_dirs1):
      if (dirs1[i] == dirs2[i] and shared):
        shared_dir.append(True)
        continue
      else:
        shared = False
        shared_dir.append(False)
        rel_path = rel_path + '../'
    for i in range(num_dirs2):
      if (i < len(shared_dir)):
        if (shared_dir[i]):
          continue
        else:
          rel_path = rel_path+dirs2[i]+'/'
      else:
        rel_path = rel_path+dirs2[i]+'/'
  return rel_path


def get_csv_sepcharacter(filename):
  """ This function returns the seperation character
      used in a csv file.
      Input:
       filename: String of the filename of the datafile to read data from
      Output:
       sepchar: Character used in the csv to seperate the columns
       status: Integer determining the status:
          0: no error
          1: error occured during the operation of this function
  """
  status = 0; sepchar = ''
  try:
    datafile = open(filename, 'r')
    firstline = datafile.readline().strip()
    secondline = datafile.readline().strip()
    # Get a first guess of what seperation character is used in that datafile:
    sepchars = [' ', ',', '\t', ';', '&', ':'] # in order of how likeliness
    l1count = []; l2count = []
    for char in sepchars:
      # count how many of each possible character was found in line one and two:
      l1count.append(firstline.count(char))
      l2count.append(secondline.count(char))
    # Now check the counts from first and second line and determine potential characters:
    pot_index = []; char_count = [];
    for i in range(len(sepchars)):
      if (l1count[i] == l2count[i] and l1count[i] > 0):
        pot_index.append(i)
        char_count.append(l1count[i])
    # Finally, we can now determine the seperation character:
    # We'll assume the character with the most occurences in line 1 and 2
    # is the seperation character, provided the count of that character is
    # the same on those two lines of course:
    max_count = max(char_count)
    pot_index_max_count = char_count.index(max_count)
    sepchars_index = pot_index[pot_index_max_count]
    sepchar = sepchars[sepchars_index]
  except:
    sepchar = ''
    status = 1
  return (sepchar, status)


###################
# From stat files #
###################

# Get time from stat file(s):
def read_time_from_stat(statfilename):
  """
     reads the time from a .stat file and stores it in
     an one-dimensional array 'time'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising time as an empty array:
  time = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        time.extend(stat['ElapsedTime']['value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    time.extend(stat['ElapsedTime']['value'])
  return time


# Get timestep from stat file(s):
def read_timestep_from_stat(statfilename):
  """
     reads the timestep from a .stat file and stores it in
     an one-dimensional array 'timestep'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising timestep as an empty array:
  timestep = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in timestep values, append them to 'timestep'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        timestep.extend(stat['dt']['value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    timestep.extend(stat['dt']['value'])
  return timestep


# Get walltime from stat file(s):
def read_walltime_from_stat(statfilename, totalwt=False):
  """
     reads the walltime from a .stat file and stores it in
     an one-dimensional array 'walltime'
     Input: 
      statfilename: String of the statfile
      totalwt: locigal, if True, the overall walltime is computed
        otherwise the walltime of each timestep is given back.
     
  """
  #Initialising walltime as an empty array:
  walltime = []; walltime_tmp = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        if (totalwt):
          # if totalwt == True, then compute the total walltime
          # of all (checkpointed) statfiles
          walltime_tmp = stat['ElapsedWallTime']['value']
          if (walltime):
            walltime_tmp = walltime_tmp + walltime[-1]
          walltime.extend(walltime_tmp)
        else:
          walltime.extend(stat['ElapsedWallTime']['value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    walltime.extend(stat['ElapsedWallTime']['value'])
  return walltime


# Correcting the walltime in a statfile that was merged from several statfiles:
def get_correct_walltime(walltime, totalwt=False):
  """
     reads the walltime from a .stat file and stores it in
     an one-dimensional array 'walltime'
     Input: 
      statfilename: String of the statfile
      totalwt: locigal, if True, the overall walltime is computed
        otherwise the walltime of each timestep is given back.
  """
  #Initialising walltime as an empty array:
  walltime_tmp = []
  if (totalwt):
      offset = 0
      # Append first value:
      walltime_tmp.append(walltime[0])
      # Loop except for first element of walltime:
      for i in range(1, len(walltime)):
          if (walltime[i] > walltime[i-1]):
             None# do nothing
          elif (walltime[i] < walltime[i-1]):
              offset = offset + walltime[i-1]
          elif (walltime[i] == walltime[i-1]):
             print "Error: Previous walltime == current walltime, should never happen!"
             exit()
          # Appending correct walltime
          walltime_tmp.append(walltime[i] + offset)
  else:
      walltime_tmp.append(walltime[0])
      for i in range(1, len(walltime)):
          if (walltime[i] > walltime[i-1]):
              walltime_tmp.append(walltime[i] - walltime[i-1])
          elif (walltime[i] < walltime[i-1]):
              walltime_tmp.append(walltime[i])
  return walltime_tmp


# Get number of nodes from stat file(s):
def read_num_of_nodes_from_stat(statfilename):
  """
     reads the number of nodes from a .stat file and stores it in
     an one-dimensional array 'num_nodes'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising num_nodes as an empty array:
  num_nodes = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        num_nodes.extend(stat['CoordinateMesh']['nodes'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    num_nodes.extend(stat['CoordinateMesh']['nodes'])
  return num_nodes


# Get number of elements from stat file(s):
def read_num_of_elements_from_stat(statfilename):
  """
     reads the number of elements from a .stat file and stores it in
     an one-dimensional array 'num_elem'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising num_elem as an empty array:
  num_elem = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        num_elem.extend(stat['CoordinateMesh']['elements'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    num_elem.extend(stat['CoordinateMesh']['elements'])
  return num_elem


# Get u from stat file(s):
def read_u_from_stat(statfilename):
  """
     reads the velocity from a .stat file and stores it in
     an two-dimensional array 'u'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising pmin and pmax as empty arrays:
  umin = []; umax=[]
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        umin.extend(stat['fluid']['Velocity%magnitude']['min'])
        umax.extend(stat['fluid']['Velocity%magnitude']['max'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    umin.extend(stat['fluid']['Velocity%magnitude']['min'])
    umax.extend(stat['fluid']['Velocity%magnitude']['max'])
  return umin, umax


# Get p from stat file(s):
def read_p_from_stat(statfilename):
  """
     reads the pressure from a .stat file and stores it in
     an two-dimensional array 'p'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising pmin and pmax as empty arrays:
  pmin = []; pmax=[]
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        pmin.extend(stat['fluid']['Pressure']['min'])
        pmax.extend(stat['fluid']['Pressure']['max'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    pmin.extend(stat['fluid']['Pressure']['min'])
    pmax.extend(stat['fluid']['Pressure']['max'])
  return pmin, pmax


# Get p l2 norm from stat file(s):
def read_p_l2norm_from_stat(statfilename):
  """
     reads the L2 norm of pressure from a .stat file
     and stores it in an one-dimensional array 'p_l2norm'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising pmin and pmax as empty arrays:
  p_l2norm = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        p_l2norm.extend(stat['fluid']['Pressure']['l2norm'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    p_l2norm.extend(stat['fluid']['Pressure']['l2norm'])
  return p_l2norm


# Get p from stat file(s):
def read_p_int_from_stat(statfilename):
  """
     reads the integral of pressure from a .stat file
     and stores it in an one-dimensional array 'p_int'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising pmin and pmax as empty arrays:
  p_int = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in time values, append them to 'time'
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        p_int.extend(stat['fluid']['Pressure']['integral'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    p_int.extend(stat['fluid']['Pressure']['integral'])
  return p_int


# Get integral of specific vector component of solidforce from stat file(s):
def read_int_solidforce_comp_from_stat(statfilename, solidname='', component=1):
  """
     reads the integral of the vector 'component' of the
     solidforce field from a .stat file and stores it in
     an one-dimensional array 'int_solidforce_comp'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  if (component=='x' or component==1 or component=='1'):
    comp='1'
  elif (component=='y' or component==2 or component=='2'):
    comp='2'
  elif (component=='z' or component==3 or component=='3'):
    comp='3'
  else:
    comp='1'

  #Initialising int_solidforce_comp as empty arrays:
  int_solidforce_comp = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in the values
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        int_solidforce_comp.extend(stat['fluid'][solidname+'SolidForce%'+str(comp)]['integral'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    int_solidforce_comp.extend(stat['fluid'][solidname+'SolidForce%'+str(comp)]['integral'])
  return int_solidforce_comp


# Get integral of solidconcentration from stat file(s):
def read_int_solidconcentration_from_stat(statfilename, solidname=''):
  """
     reads the integral of the solidconcentration field
     from a .stat file and stores it in
     an one-dimensional array 'int_alpha'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising int_alpha as empty arrays:
  int_alpha = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    # Read in the values
    # over all .stat files listed in 'statlistfilename'
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        int_alpha.extend(stat['fluid'][solidname+'SolidConcentration']['integral'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    int_alpha.extend(stat['fluid'][solidname+'SolidConcentration']['integral'])
  return int_alpha


# Get drag force (IMB) from stat file(s):
def read_immersed_df_from_stat(statfilename):
  """
     reads the drag force from an immersed body
     from a .stat file and stores it in
     an one-dimensional array 'df'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising df as an empty array:
  df = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        df.extend(stat['Force1']['Value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    df.extend(stat['Force1']['Value'])
  return df


# Get drag force (FSI Model) from stat file(s):
def read_fsi_model_df_from_stat(statfilename, component=1, solidmeshname=''):
  """
     reads the drag force from an immersed body
     (fsi_model) from a .stat file and stores it in
     an one-dimensional array 'df'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising df as an empty array:
  df = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        df.extend(stat['ForceOnSolid_'+str(solidmeshname)+str(component)]['Value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    df.extend(stat['ForceOnSolid_'+str(solidmeshname)+str(component)]['Value'])
  return df


# Get drag force (void) from stat file(s):
def read_void_df_from_stat(statfilename, surfacename, component=1):
  """
     reads the drag force from a void body
     from a .stat file and stores it in
     an one-dimensional array ''
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising time as an empty array:
  df = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        df.extend(stat['fluid']['Velocity']['force_'+surfacename+'%'+str(component)])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    df.extend(stat['fluid']['Velocity']['force_'+surfacename+'%'+str(component)])
  return df


# Get pressure component of drag force (void) from stat file(s):
def read_void_df_pressurecomponent_from_stat(statfilename, surfacename, component=1):
  """
     reads the pressure component of the drag force
     from a void body from a .stat file and stores it in
     an one-dimensional array ''
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising time as an empty array:
  df_pcmp = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        df_pcmp.extend(stat['fluid']['Velocity']['pressure_force_'+surfacename+'%'+str(component)])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    df_pcmp.extend(stat['fluid']['Velocity']['pressure_force_'+surfacename+'%'+str(component)])
  return df_pcmp


# Get viscous component of drag force (void) from stat file(s):
def read_void_df_viscouscomponent_from_stat(statfilename, surfacename, component=1):
  """
     reads the viscous component of the drag force
     from a void body from a .stat file and stores it in
     an one-dimensional array ''
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising time as an empty array:
  df_vsccmp = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        df_vsccmp.extend(stat['fluid']['Velocity']['viscous_force_'+surfacename+'%'+str(component)])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    df_vsccmp.extend(stat['fluid']['Velocity']['viscous_force_'+surfacename+'%'+str(component)])
  return df_vsccmp


# Get dragforce from file 'drag_force':
def read_forces_from_drag_force(df_filename):
  """
     Reading in the forces acting on a solid body
     due to the surrounding flow
  """
  forces_on_solid_body = genfromtxt(df_filename)
#  z=0
#  for row in df:
#    x = sqrt(row[0]**2 + row[1]**2 + row[2]**2) #compute norm of vector
#    fds[z,0] = x #store norm in fds
#    z+=1 #increase counter by 1
  return forces_on_solid_body


#######################
# From detector files #
#######################
# Get position from detector with name 'detname':
def read_position_from_detector(detfilename, detname):
  """
     reads the position from a detector file and stores it in
     an 'pos'
     input: is the filename of the detector file,
     and the name of the detector
  """
  #Initialising velocity as an empty array:
  pos = []; dummy = [];
  # Get string-array with stat filenames:
  if (detfilename.startswith('statfiles/list_')):
    f = open(detfilename)
    detfiles = f.readlines()
    f.close()
    for filename in detfiles:
        filename = filename[0:len(filename)-1]
        detectors = fluidity_tools.stat_parser(filename)
        if (len(pos) == 0):
            pos = detectors[detname]['position']
        else:
            pos = column_stack((pos,detectors[detname]['position']))
  else:
    # Get velocity
    detectors = fluidity_tools.stat_parser(detfilename)
    pos = detectors[detname]['position']
  return pos

# Get pressure from detector with name 'detname':
def read_pressure_from_detector(detfilename, detname):
  """
     reads the pressure from a detector file and stores it in
     an one-dimensional array 'p'
     input: is the filename of the detector file,
     and the name of the detector
  """
  #Initialising pressure as an empty array:
  p = []
  # Get string-array with stat filenames:
  if (detfilename.startswith('statfiles/list_')):
    f = open(detfilename)
    detfiles = f.readlines()
    f.close()
    for filename in detfiles:
        filename = filename[0:len(filename)-1]
        detectors = fluidity_tools.stat_parser(filename)
        p.extend(detectors['fluid']['Pressure'][detname])
  else:
    # Get pressure
    detectors = fluidity_tools.stat_parser(detfilename)
    p = detectors['fluid']['Pressure'][detname]
  return p

# Get velocity from detector with name 'detname':
def read_velocity_from_detector(detfilename, detname):
  """
     reads the velocity from a detector file and stores it in
     an 'v'
     input: is the filename of the detector file,
     and the name of the detector
  """
  #Initialising velocity as an empty array:
  v = []; dummy = [];
  # Get string-array with stat filenames:
  if (detfilename.startswith('statfiles/list_')):
    f = open(detfilename)
    detfiles = f.readlines()
    f.close()
    for filename in detfiles:
        filename = filename[0:len(filename)-1]
        detectors = fluidity_tools.stat_parser(filename)
        if (len(v) == 0):
            v = detectors['fluid']['Velocity'][detname]
        else:
            v = column_stack((v,detectors['fluid']['Velocity'][detname]))
  else:
    # Get velocity
    detectors = fluidity_tools.stat_parser(detfilename)
    v = detectors['fluid']['Velocity'][detname]
  return v

# Get SolidVolumeFraction from detector with name 'detname':
def read_solid_volumefraction_from_detector(detfilename, detname):
  """
     reads the solid volume fraction from a detector file 
     and stores it in an one-dimensional vector 'alpha'
     input: is the filename of the detector file,
     and the name of the detector
  """
  #Initialising velocity as an empty array:
  alpha = []
  # Get string-array with stat filenames:
  if (detfilename.startswith('statfiles/list_')):
    f = open(detfilename)
    detfiles = f.readlines()
    f.close()
    for filename in detfiles:
        filename = filename[0:len(filename)-1]
        detectors = fluidity_tools.stat_parser(filename)
        alpha.extend(detectors['fluid']['SolidConcentration'][detname])
  else:
    # Get volume fraction:
    detectors = fluidity_tools.stat_parser(detfilename)
    alpha = detectors["fluid"]["SolidConcentration"][detname]
  return alpha


# Get solid volume fraction from stat file(s):
def read_fsi_model_solidvolume_from_stat(statfilename, solidmeshname):
  """
     reads the solidvolume from an immersed body
     (fsi_model) from a .stat file and stores it in
     an one-dimensional array 'solidvolume'
     input: is a file containing a list of .stat files
     in the directory 'statfiles/'
  """
  #Initialising solidvolume as an empty array:
  solidvolume = []
  # Get string-array with stat filenames:
  if (statfilename.startswith('statfiles/list_')):
    f = open(statfilename)
    statfiles = f.readlines()
    f.close()
    for filename in statfiles:
        filename = filename[0:len(filename)-1]
        stat = fluidity_tools.stat_parser(filename)
        solidvolume.extend(stat['VolumeOfSolid_'+str(solidmeshname)]['Value'])
  else:
    stat = fluidity_tools.stat_parser(statfilename)
    solidvolume.extend(stat['VolumeOfSolid_'+str(solidmeshname)]['Value'])
  return solidvolume


######################
# Print out in color #
######################
def printc(string, color, highlight):
  if color=='gray':
    if highlight==True:
      color='\033[1;47m'
    else:
      color='\033[1;30m'
  elif color=='red':
    if highlight==True:
      color='\033[1;41m'
    else:
      color='\033[1;31m'
  elif color=='green':
    if highlight==True:
      color='\033[1;42m'
    else:
      color='\033[1;32m'
  elif color=='yellow':
    if highlight==True:
      color='\033[1;43m'
    else:
      color='\033[1;33m'
  elif color=='blue':
    if highlight==True:
      color='\033[1;44m'
    else:
      color='\033[1;34m'
  elif color=='magenta':
    if highlight==True:
      color='\033[1;45m'
    else:
      color='\033[1;35m'
  elif color=='cyan':
    if highlight==True:
      color='\033[1;46m'
    else:
      color='\033[1;36m'
  elif color=='white':
    color='\033[1;37m'
  elif color=='crimson':
    if highlight==True:
      color='\033[1;48m'
    else:
      color='\033[1;38m'
  else:
    print "ERROR: Wrong input for printc"
# Modify string:
  string = color+string+'\033[1;m'
  print string,

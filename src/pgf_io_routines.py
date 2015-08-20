## This module comprehends some routines to generate a simple datafile
## with/without header, that can be read in by pgfplots
## and routines to write a tex file to plot from a given file
import os
import commands
from io_routines import convert_filename_to_path_and_filename, sorted_nicely, sortdiff, get_relative_path, get_csv_sepcharacter
import numpy as np


###########################
# Generic pgfplot routine #
###########################

# Write array to a file, to use for pgfplots:
def write_pgfplots_data_file(filename, array, array_labels=[]):
  """
     writes the elements of array into a file. If array_labels
     is passed, the first row of the datafile will have names
     for the columns.
  """
  sepchar = '\t' # default seperator charactor
  # First, remove underscore sign from strings, as those give LaTeX problems in words,
  # plus preserve the LaTeX math mode:
  array_labels = remove_underscore_preserve_math_mode(', '.join(array_labels).strip(), replace_char='_')
  array_labels = array_labels.split(', ')
  # The same for the data stored in 'array', as this could be strings for tables:
  for i in range(len(array)):
    if (isinstance(array[i],(np.ndarray, list))):
      # For numpy arrays and lists, do this:
      tmp = str(list(array[i])).replace('[','').replace(']','')
    else:
      tmp = ', '.join(str(array[i]))
    tmp = pgfplots_friendly_data([tmp])[0]
    tmp = remove_underscore_preserve_math_mode(tmp, replace_char='_')
    tmp = tmp.split(', ')
    for j in range(len(tmp)):
      array[i][j] = tmp[j]
  # Successfully removed underscore signs and preserved LaTeX math mode from header and data!
  # Continue:
  if (array_labels and (len(array[0]) != len(array_labels))):
    print "#################################################"
    print "# Length of array and array_labels are unequal! #"
    print "#################################################"
  # Write to file:
  datafile = open(filename, "w")
  # If array labels are given, write header:
  if (array_labels):
    for i in range(len(array_labels)):
      datafile.write(array_labels[i])
      if (i < len(array_labels)-1):
        datafile.write(sepchar)
      else:
        datafile.write('\n')
  # Assumption that all columns of array are of same length!
  rows = len(array)
  cols = len(array[0])
  # Write data to file:
  for i in range(rows):
    for j in range(cols):
      datafile.write(str(array[i][j]))
      datafile.write(sepchar) #seperation by default seperator character
    datafile.write('\n') #newline after all columns in array are written
  datafile.closed



# Write x and y coordinates to a file, to use for pgfplots:
def write_pgfplots_data_file_simple(filename, x, y, array_labels=[]):
  """
     writes the elements of two input arrays
     (both assumed to be 1-dimensional)
     into the file 'filename'
  """
  sepchar = '\t' # default seperator charactor
  if (array_labels and (len(array_labels) != 2)):
    print "#####################################"
    print "# Length of array_labels must be 2! #"
    print "#####################################"
  # Write to file:
  datafile = open(filename, "w")
  # If array labels are given, write header:
  if (array_labels):
    for i in range(len(array_labels)):
      datafile.write(array_labels[i])
      if (i < len(array_labels)-1):
        datafile.write(sepchar)
      else:
        datafile.write('\n')
  # Assumption that columns of x and y are of same length!
  for i in range(len(x)):
    datafile.write(str(x[i]))
    datafile.write(sepchar)
    datafile.write(str(y[i]))
    datafile.write('\n')
  datafile.closed


# Writes header of pgfplots data file, that will be extended through 
# append_pgfplots_data_file_simple(filename, array)
def write_pgfplots_data_file_header_simple(filename, array_labels):
  """
     writes the header information of a pgfplots datafile
     that can be extended through 
     append_pgfplots_data_file_simple(filename, array)
  """
  sepchar = '\t' # default seperator charactor
  # Write to file:
  datafile = open(filename, "w")
  # If array labels are given, write header:
  for i in range(len(array_labels)):
    datafile.write(array_labels[i])
    if (i < len(array_labels)-1):
      datafile.write(sepchar)
    else:
      datafile.write('\n')
  datafile.closed


# Appends one-dimensional array as a row to a datafile:
def append_pgfplots_data_file_simple(filename, array):
  """
     appends the 1-dimensional array 'array'
     to the datafile 'filename'.
  """
  # Get the seperation character used in the datafile:
  (sepchar, status) = get_csv_sepcharacter(filename)
  if (not (status == 0)):
    sepchar = '\t'
    #raise Exception('Seperation character of csv file "'+filename+'" could not be determined.')
  # Write to file:
  datafile = open(filename, "a")
  for i in range(len(array)):
    datafile.write(array[i])
    if (i < len(array)-1):
      datafile.write(sepchar)
    else:
      datafile.write('\n')
  datafile.closed


# Appends a single column to a pgfdat file, including the header
def append_column_pgfplots_data_file_simple(filename, col):
  """
     appends a column of data including a header
     describing what kind of data the column
     holds to the file 'filename'. The given
     array 'col' must contain the same number of 
     elements as the existing file 'filename'
     has rows.
  """
  # Open filename for reading and get all lines:
  file = open(filename, 'r')
  alllines = file.readlines()
  file.close()
  # Get the seperation character used in the datafile:
  (sepchar, status) = get_csv_sepcharacter(filename)
  if (not (status == 0)):
    raise Exception('Seperation character of csv file "'+filename+'" could not be determined.')
  # Checking the consistency of number of rows in filename
  # with number of elements in col:
  if (len(alllines) != len(col)):
    printc("The given column has an insufficient number of elements compared to the data in "+filename+" and hence cannot be added to the file.", "red", False); print
  else:
    # Assemble new lines, including the new column:
    z = 0
    newlines = []
    #for line in file:
    for line in alllines:
        newlines.append(line.strip()+sepchar+str(col[z])+'\n')
        z = z+1
    # Now write the assembled lines with new column to the file on the disk:
    file = open(filename, 'w')
    for newline in newlines:
      file.write(newline)
    file.close()


def csv_2_pgfplots_csv_file(filename):
  """ This function reads in a csv file, and removes
      certain characters from the first line, which should
      contain the column labels. This should ensure the csv
      to be read in by pgfplots routines.
      The modified content is then written to disk by overwriting
      the file.
      Input:
       filename: String of the csv filename
      Output:
       status: 0 if no error occured, and 1 otherwise.
  """
  # reading in data:
  infile = open(filename, 'r')
  lines = infile.readlines()
  infile.close()
  # removing characters:
  modlines = pgfplots_friendly_data(lines)
  # writing to file:
  outfile = open(filename, 'w')
  outfile.write(''.join(modlines))
  outfile.close()


def pgfplots_friendly_data(instrings):
  """ This function removes certain characters, which most likely
      cause problems in pgfplots, from a list of strings.
      Input:
       instrings: A list of strings from which certain characters
         are removed
      Output:
       outstrings: List of modified strings
  """
  # defining a list of characters that should be removed from a
  # pgfplots compatible csv datafile:
  rmchars = ['"', '\''] # rmchars = ['"', '\'',':']
  # removing characters:
  outstrings = []
  for instring in instrings:
    for rmchar in rmchars:
      instring = instring.replace(rmchar,'')
    outstrings.append(instring)
  return outstrings


def sepchar2pgfplotsstring(sepchar):
  """ This function translate the actual seperator character,
      e.g. of a csv datafile, into the corresponding string
      used for pgfplots routines
      Input:
       sepchar: Character of which the corresponding pgfplots
         strings is returned
      Output:
       pgfsepstring: Pgfplots string of a seperator used in a csv file
  """
  pgfsepstring = ''
  if (sepchar == ' '): pgfsepstring = 'space'
  elif (sepchar == ','): pgfsepstring = 'comma'
  elif (sepchar == ';'): pgfsepstring = 'semicolon'
  elif (sepchar == ':'): pgfsepstring = 'colon'
  elif (sepchar == '\t'): pgfsepstring = 'tab'
  elif (sepchar == '&'): pgfsepstring = '&'
  return pgfsepstring


def get_pgf_sepchar(filename):
  """ This function determines the seperator character of a csv file,
      and returns the corresponding pgfplots string of that seperator
      Input:
       filename: String of the filename of the datafile to read data from
      Output:
       pgfsepstring: Pgfplots string of a seperator used in a csv file
  """
  pgfsepstring = ''
  # Get the seperation character used in the datafile:
  (sepchar, status) = get_csv_sepcharacter(filename)
  if (not (status == 0)):
    raise Exception('Seperation character of csv file "'+filename+'" could not be determined.')
  pgfsepstring = sepchar2pgfplotsstring(sepchar)
  return pgfsepstring


def read_column_names_pgfplots_data_file(filename):
  """ This method reads in the first line (column names) of a csv/pgfplots datafile.
      Thus it is assumed the datafile has column names in the first line.
      Input:
        filename: String of the filename.
      Output:
        colnames: List of strings
        status: Integer determining the status:
          0: no error
          1: error occured during the reading in of data
  """
  status = 0
  colnames = []
  try:
    datafile = open(filename, 'r')
    colnames = datafile.readline().strip()
    # Get the seperation character used in the datafile:
    (sepchar, status) = get_csv_sepcharacter(filename)
    if (not (status == 0)):
      raise Exception('Seperation character of csv file "'+filename+'" could not be determined.')
    # Splitting the line where sepchar appears:
    colnames = colnames.split(sepchar)
  except:
    status = 1
  return (colnames, status)


def read_column_pgfplots_data_file(filename, colname):
  """ This method reads in the data of a specific column in a csv/pgfplots datafile.
      The datafile must have column names in the first line, with the corresponding 
      data in the lines below.
      Input:
        filename: String of the filename of the datafile to read data from
        colname: String of the corresponding column name we want the data from
      Output:
        data: List of values from the datafile
        status: Integer determining the status:
          0: no error
          1: column with given colnames was not found
          2: error occured during the reading in of data
  """
  status = 0
  datafile = open(filename, 'r')
  # Check the first line for the column names, to find out which columns we have to extract:
  colindex = -1
  colnames = datafile.readline().strip()
  # Get a first guess of what seperation character is used in that datafile:
  # Get the seperation character used in the datafile:
  (sepchar, status) = get_csv_sepcharacter(filename)
  if (not (status == 0)):
    raise Exception('Seperation character of csv file "'+filename+'" could not be determined.')
  # Splitting the line where sepchar appears:
  colnames = colnames.split(sepchar)
  for i in range(len(colnames)):
    if (colnames[i] == colname):
      colindex = i
  if (colindex < 0):
    status = 1
    print "--------------------------------------------------------------------------------------------"
    print "Error: column with label \""+colname+"\" could not be found in the header of file "+filename+"."
  # Now read in the data and store it in arrays:
  if (status == 0):
    data = []
    for line in datafile:
      if (len(line.strip()) > 0):
        try:
          line = line.strip().split(sepchar)
          data.append(float(line[colindex]))
        except:
          print "--------------------------------------------------------------------------------------------"
          print "Error, could not convert data in file "+filename+" into a floating point number!"
          print "Number was: "+line[colindex]+"."
          status = 2
          break
  # Done processing the datafile, so close it:
  datafile.close()
  return data, status


def remove_underscore_preserve_math_mode(string, replace_char='_'):
  """Checks if string contains underscore signs outside math mode and replaces those"""
  if (replace_char == '' or replace_char is None):
    replace_char == ' '
  num_dollar = string.count('$')
  num_undscr = string.count('_')
  num_slashdollar = string.count('\$')
  # subtracting num_slashdollar from num_dollar
  num_dollar = num_dollar - num_slashdollar
  # Check if the number of dollar signs is a factor of 2:
  if (not (num_dollar%2 == 0)):
    # throw an exception:
    errormsg = "Found "+str(num_dollar)+" $ signs in the string:\n "+string+"\nThe number of $ signs is supposed to be an even number as it is used for LaTeX math mode."
    raise Exception(errormsg)
  ind_dollar = []
  modstring = ''
  if (num_undscr != 0):
    if (num_dollar != 0):
      index = string.find('$')
      for z in range(num_dollar):
        ind_dollar.append(index)
        index = string.find('$', index+1)
      tmp = (string[0:ind_dollar[0]].replace('_',replace_char)) #starting point
      modstring = modstring+tmp
      for i in range(len(ind_dollar)):
        if (i%2 == 0): #beginning of mathmode found --> skip substring
          tmp = (string[ind_dollar[i]:ind_dollar[i+1]+1])
          modstring = modstring+tmp # this is the mathmode string
        else:  # append underscore-free string outside mathmode
          if (i != len(ind_dollar)-1):
            tmp = (string[ind_dollar[i]+1:ind_dollar[i+1]].replace('_',replace_char))
          else:
            tmp = (string[ind_dollar[i]+1:].replace('_',replace_char))
          modstring = modstring+tmp
    else:
      # No mathmode found, just replace underscores with spaces:
      modstring = string.replace('_', replace_char)
  else: # No underscore sign found:
    modstring = string
  return modstring


def write_pgfplot_tex_file_header(texfilename, defaultfontsize='11pt', title='', axis='axis',
                                  xmode='normal', ymode='normal', log_basis_x='', log_basis_y='',
                                  xlabel='xlabel', ylabel='ylabel', label_font=None,
                                  xmin='', xmax='', ymin='', ymax='', xprecision='', yprecision='',
                                  plotwidth='', plotheight='',
                                  minor_tick_num='0', xtick=None, ytick=None, x_tick_label_font=None, y_tick_label_font=None,
                                  legendpos='north east', legend_columns='', legendfontsize='small', legend_entries='',
                                  grid='major', grid_style=None,
                                  restrict_x=False, restrict_y=False,
                                  cycle_list='',
                                  x_axis_reverse=False, y_axis_reverse=False):
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  title = remove_underscore_preserve_math_mode(title, replace_char='\_')
  xlabel = remove_underscore_preserve_math_mode(xlabel, replace_char='\_')
  ylabel = remove_underscore_preserve_math_mode(ylabel, replace_char='\_')
  legend_entries = remove_underscore_preserve_math_mode(legend_entries.strip(), replace_char='\_')
  if(legend_entries.endswith(',')):
    # remove last comma:
    legend_entries = legend_entries[: len(legend_entries)-1]
  # Open texfile in write modus:
  texfile = open(texfilename, "w")
  # Write to the texfile:
  print>>texfile, "%% Generated file to plot data from a datafile using pgfplots"
  print>>texfile, ""
  print>>texfile, "%================================================================================"
  print>>texfile, "%|                                                                              |"
  print>>texfile, "%| If you plot a huge amount of data, and TeX runs out on its main memory,      |"
  print>>texfile, "%| you have two options that are suggested by pgfplots' manual:                 |"
  print>>texfile, "%|  1. You could try lualatex instead of pdflatex                               |"
  print>>texfile, "%|  2. You could modify some of latex's settings in the texmf.cnf. How to do    |"
  print>>texfile, "%|     for your LaTeX distrobution, Google is your friend.                      |"
  print>>texfile, "%|                                                                              |"
  print>>texfile, "%| The documentclass 'standalone' is used to crop white space, if that is not   |"
  print>>texfile, "%| working for you, you can use article as your document class, and  uncomment  |"
  print>>texfile, "%| the 3 lines for using the package 'tightpage'. As a last resort, you can     |"
  print>>texfile, "%| always use the command-line tool 'pdfcrop'.                                  |"
  print>>texfile, "%| The 'Preview package is used to remove white space around the tikzpicture    |"
  print>>texfile, "%| environment. If this fails for you, and/or alternatively you can comment     |"
  print>>texfile, "%| the relevant lines just above the '\\begin{document}' command                 |"
  print>>texfile, "%| and make use of the external tool pdfcrop.                                   |"
  print>>texfile, "%|                                                                              |"
  print>>texfile, "%================================================================================"
  print>>texfile, ""
  print>>texfile, "\\documentclass["+defaultfontsize+"]{standalone}"
  print>>texfile, "%\\documentclass["+defaultfontsize+"]{article}"
  print>>texfile, ""
  print>>texfile, "% Set page legths (uncomment for using article and tightpage/pdfcrop):"
  print>>texfile, "%\\special{papersize=50cm,50cm}"
  print>>texfile, "%\\hoffset-0.8in"
  print>>texfile, "%\\voffset-0.8in"
  print>>texfile, "%\\setlength{\\paperwidth}{50cm}"
  print>>texfile, "%\\setlength{\\paperheight}{50cm}"
  print>>texfile, "%\\setlength{\\textwidth}{45cm}"
  print>>texfile, "%\\setlength{\\textheight}{45cm}"
  print>>texfile, "%\\topskip0cm"
  print>>texfile, "%\\setlength{\\headheight}{0cm}"
  print>>texfile, "%\\setlength{\\headsep}{0cm}"
  print>>texfile, "%\\setlength{\\topmargin}{0cm}"
  print>>texfile, "%\\setlength{\\oddsidemargin}{0cm}"
  print>>texfile, "% set the pagestyle to empty (removing pagenumber etc)"
  print>>texfile, "\\pagestyle{empty}"
  print>>texfile, ""
  print>>texfile, "% load packages:"
  print>>texfile, "\\usepackage{amsmath}"
  print>>texfile, "\\usepackage{amssymb}"
  print>>texfile, "\\usepackage{amstext}"
  print>>texfile, "\\usepackage{amsfonts}"
  print>>texfile, "\\usepackage{textcomp}"
  print>>texfile, ""
  print>>texfile, "\\usepackage{tikz}"
  print>>texfile, "\\usepackage{pgfplots}"
  print>>texfile, "%\\usepgfplotslibrary{external}"
  print>>texfile, "%\\tikzexternalize"
  print>>texfile, ""
  print>>texfile, "% Use newest spacing options (from v. 1.3 on)"
  print>>texfile, "\\pgfplotsset{compat=1.10}"
  if (plotwidth != ''):
    print>>texfile, "\\pgfplotsset{width="+plotwidth+"}"
  else:
    print>>texfile, "% You can set your plotwidth below:"
    print>>texfile, "%\\pgfplotsset{width=5cm}"
  if (plotheight != ''):
    print>>texfile, "\\pgfplotsset{height="+plotheight+"}"
  else:
    print>>texfile, "% You can set your plotheight below:"
    print>>texfile, "%\\pgfplotsset{height=5cm}"

  print>>texfile, ""
  print>>texfile, "\\pgfplotsset{grid style={solid}}"
  print>>texfile, ""
  print>>texfile, "% Removing white space by using 'standalone' as the document class, uncomment the following as an alternative:"
  print>>texfile, "% Remove white space from generated pdf,"
  print>>texfile, "% thus otaining a pdf with only the picture that can"
  print>>texfile, "% easily be included in a(nother) tex-document via the usual \includegraphic command."
  print>>texfile, "% Benefit: 1. you can keep your pictures organised in a subfolder and"
  print>>texfile, "%          2. the picture remains a vector graphic :)"
  print>>texfile, "%\\usepackage[active, tightpage]{preview}"
  print>>texfile, "%\\PreviewEnvironment{tikzpicture}"
  print>>texfile, "%\\setlength\PreviewBorder{0pt}"
  print>>texfile, "% Alternatively, delete the three lines above and run 'pdfcrop filename.pdf',"
  print>>texfile, "% the result should be the same."
  print>>texfile, ""
  print>>texfile, "\\begin{document}"
  print>>texfile, ""
  print>>texfile, "\\centering"
  print>>texfile, ""
  print>>texfile, "\\begin{tikzpicture}"
  print>>texfile, "  \\begin{axis}[" # axis should always be axis, if we want a semilogaxis, or loglogaxis, we'll handle that in the axis options below
  print>>texfile, "        axis background/.style={fill=gray!20},"
  print>>texfile, "        axis x line*=bottom, axis y line*=left,"
  # Check if it is a semi- or log-axis:
  if (axis == 'loglogaxis' or (xmode == 'log' and ymode == 'log')):
    print>>texfile, "        xmode=log, ymode=log, % logarithmic x and y axis"
    print>>texfile, "        log basis x="+str(log_basis_x)+", log basis y="+str(log_basis_y)+", % log basis, if empty the natural logarithm is used"
  elif (axis == 'semilogxaxis' or xmode == 'log'):
    print>>texfile, "        xmode=log, % logarithmic x axis"
    print>>texfile, "        log basis x="+str(log_basis_x)+", % log basis, if empty the natural logarithm is used"
  elif (axis == 'semilogyaxis' or ymode == 'log'):
    print>>texfile, "        ymode=log, % logarithmic y axis"
    print>>texfile, "        log basis y="+str(log_basis_y)+", % log basis, if empty the natural logarithm is used"
  print>>texfile, "        % If more precision on x or y axis is needed, uncomment the relevant lines below:"
  if (xprecision == ''):
    print>>texfile, "        % scaled x ticks=false,"
    print>>texfile, "        % x tick label style={/pgf/number format/fixed, /pgf/number format/precision=3}, % 3 for 3 floating point digits"
  elif (xprecision != ''):
    print>>texfile, "        scaled x ticks=false,"
    print>>texfile, "        x tick label style={/pgf/number format/fixed, /pgf/number format/precision="+str(xprecision)+"},"
  if (yprecision == ''):
    print>>texfile, "        % scaled y ticks=false,"
    print>>texfile, "        % y tick label style={/pgf/number format/fixed, /pgf/number format/precision=3}, % 3 for 3 floating point digits"
  elif (yprecision != ''):
    print>>texfile, "        scaled y ticks=false,"
    print>>texfile, "        y tick label style={/pgf/number format/fixed, /pgf/number format/precision="+str(yprecision)+"},"
  if (not (x_tick_label_font is None)):
    # Now checking if there is a special character in the string, e.g. to be expected are \t and \f:
    spec_char = ['\t', '\f']
    for sc in spec_char:
      if (sc in x_tick_label_font):
        # In this case, split the string where there is a \t, \f character and repair the string:
        if ('\t' in sc): rep_char = '\\t'
        else: rep_char = '\\f'
        x_tick_label_font = rep_char.join(x_tick_label_font.split(sc))
    # Now we can write the (modified or not) string to disk:
    print>>texfile, "        x tick label style={font="+x_tick_label_font.strip()+"},"
  if (not (y_tick_label_font is None)):
    # Now checking if there is a special character in the string, e.g. to be expected are \t and \f:
    spec_char = ['\t', '\f']
    for sc in spec_char:
      if (sc in y_tick_label_font):
        # In this case, split the string where there is a \t, \f character and repair the string:
        if ('\t' in sc): rep_char = '\\t'
        else: rep_char = '\\f'
        y_tick_label_font = rep_char.join(y_tick_label_font.split(sc))
    # Now checking if there is a tabular character in the string:
    if ('\t' in y_tick_label_font):
      # In this case, split the string where there is a tabular character and repair the string:
      y_tick_label_font = '\\t'.join(y_tick_label_font.split('\t'))
    # Now we can write the (modified or not) string to disk:    
    print>>texfile, "        y tick label style={font="+y_tick_label_font.strip()+"},"
  print>>texfile, "        scale only axis, % might get 'dimension too large' error if switched on"
  print>>texfile, "        minor tick num="+str(minor_tick_num)+","
  if (cycle_list != ''):
    print>>texfile, "        cycle list name="+str(cycle_list_name)+", % When using a list, do not use [] after \\addplot command or your options from the list will be overwritten!"
  if (title != ''):
    print>>texfile, "        title={"+title+"},"
#  if (not (xmin == '' and xmax == '')):
  if (not (xmin == '' and xmax == '')):
    print>>texfile, "        xmin="+str(xmin)+", xmax="+str(xmax)+","
  elif (not (xmin == '')):
    print>>texfile, "        xmin="+str(xmin)+","
  elif (not (xmax == '')):
    print>>texfile, "        xmax="+str(xmax)+","
  if (not (ymin == '' and ymax == '')):
    print>>texfile, "        ymin="+str(ymin)+", ymax="+str(ymax)+","
  elif (not (ymin == '')):
    print>>texfile, "        ymin="+str(ymin)+","
  elif (not (ymax == '')):
    print>>texfile, "        ymax="+str(ymax)+","
  if (restrict_x and (not (xmin == '' or xmax == ''))):
    # Compute min and max val for x:
    if (xmin > 0):
      xminrest = xmin*0.75
    else:
      xminrest = xmin*1.33
    if (xmax > 0):
      xmaxrest = xmax*1.33
    else:
      xmaxrest = xmax*0.75      
    print>>texfile, "        restrict x to domain="+str(xminrest)+":"+str(xmaxrest)+", % use this if you get a 'dimension too large' error"
  else:
    print>>texfile, "        % restrict x to domain=-10:10, % use this if you get a 'dimension too large' error"
  if (restrict_y and (not (ymin == '' and ymax == ''))):
    # Compute min and max val for y:
    if (ymin > 0):
      yminrest = ymin*0.75
    else:
      yminrest = ymin*1.33
    if (ymax > 0):
      ymaxrest = ymax*1.33
    else:
      ymaxrest = ymax*0.75      
    print>>texfile, "        restrict y to domain="+str(yminrest)+":"+str(ymaxrest)+", % use this if you get a 'dimension too large' error"
  else:
    print>>texfile, "        % restrict y to domain=-10:10, % use this if you get a 'dimension too large' error"
  print>>texfile, "        xlabel={"+xlabel+"},"
  print>>texfile, "        ylabel={"+ylabel+"},"
  if (not (label_font is None)):
    # Now checking if there is a special character in the string, e.g. to be expected are \t and \f:
    spec_char = ['\t', '\f']
    for sc in spec_char:
      if (sc in label_font):
        # In this case, split the string where there is a \t, \f character and repair the string:
        if ('\t' in sc): rep_char = '\\t'
        else: rep_char = '\\f'
        label_font = rep_char.join(label_font.split(sc))
    # Now we can write the (modified or not) string to disk:
    print>>texfile, "        label style={font="+label_font.strip()+"},"
  if (not xtick is None):
    if (isinstance(xtick,str)):
      if (xtick == 'data'):
        print>>texfile, "        xtick="+xtick+", % ticks will exactly appear as your data on the x-axis"
      else:
        print>>texfile, "        xtick={"+xtick+"}," # trusting the user with pgfplots valid string
        #print "ERROR: \"xtick\" was given as a String, but it was not \"data\", which is the only allowed String here."
        #raise SystemExit()
    elif (isinstance(xtick, list) or isinstance(xtick, np.ndarray)):
      # Convert the list/array into a String of its elements/numbers:
      try:
        xtick = ','.join([str(e) for e in xtick])
        print>>texfile, "        xtick={"+xtick+"},"
      except:
        print "ERROR: The list/array \"xtick\" could not be converted into a string."
        raise SystemExit()
  if (not ytick is None):
    if (isinstance(ytick,str)):
      if (ytick == 'data'):
        print>>texfile, "        ytick="+ytick+", % ticks will exactly appear as your data on the y-axis"
      else:
        print>>texfile, "        ytick={"+ytick+"}," # trusting the user with pgfplots valid string
        #print "ERROR: \"ytick\" was given as a String, but it was not \"data\", which is the only allowed String here."
        #raise SystemExit()
    elif (isinstance(ytick, list) or isinstance(ytick, np.ndarray)):
      # Convert the list into a String of its elements/numbers:
      try:
        ytick = ','.join([str(e) for e in ytick])
        print>>texfile, "        ytick={"+ytick+"},"
      except:
        print "ERROR: The list \"ytick\" could not be converted into a string."
        raise SystemExit()
  if (x_axis_reverse==True):
    print>>texfile, "        x dir=reverse,"
  if (y_axis_reverse==True):
    print>>texfile, "        y dir=reverse,"
  # Legend options:
  print>>texfile, "        legend cell align=left, % best if aligned left"
  if (legendpos == 'outer north'):
    print>>texfile, "        legend style={at={(0.5,1.1)},anchor=south," # outer north
  elif (legendpos == 'outer south'):
    print>>texfile, "        legend style={at={(0.5,-0.1)},anchor=north," # outer south
  else:
    print>>texfile, "        legend style={legend pos="+legendpos+"," # inside axis and outside west/east
  if (not (legend_columns == '')):
    print>>texfile, "                      legend columns="+str(legend_columns)+","
  print>>texfile, "                      % specify legend entries:"
  if (not (legend_entries=='')):
    print>>texfile, "                       legend entries={"+str(legend_entries)+"},"
  else:
    print>>texfile, "                      % example: legend entries={entry1, entry2, entry3},"
  print>>texfile, "                      % if legend entries are too long, specify max text width/depth:"
  print>>texfile, "                      % nodes={text width=30pt,text depth=40},"
  print>>texfile, "                      % if you want to put the legend outside the figure envirmonent, do:"
  print>>texfile, "                      % legend to name=legendlabel,"
  print>>texfile, "                      % and then '\\ref{legendlabel}' where you want the legend to appear"
  print>>texfile, "                      % don't forget to run pdflatex twice for it to pick up the changed reference!"
  if (not (legendfontsize == '')):
    print>>texfile, "                      font=\\"+legendfontsize+"},"
  else:
    print>>texfile, "                      },"
  if (not grid_style is None):
    print>>texfile, "        grid style={"+grid_style+"},"    
  print>>texfile, "        grid="+grid
  print>>texfile, "        ]"
  texfile.closed


def write_pgfplot_tex_file_plot_example(datafile, texfilename):
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  print>>texfile, "    % Example of a plot with specified marker, linestyle and line join:"
  print>>texfile, "    %\\addplot[color=red, mark=o, linestyle=solid] plot file {datafilename};"
  texfile.closed

def write_pgfplot_tex_file_plot(datafile, texfilename, color='blue', fill=None, fillopacity='1', mark='', linestyle='solid', linewidth='', line_join='', legendentry=''):
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  legendentry = remove_underscore_preserve_math_mode(legendentry, replace_char='\_') # the other strings should not have underscores anyway!
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  texfile.write("    \\addplot[color="+color+", "+linestyle)
  if (not (fill is None)):
    texfile.write(", fill="+str(fill)+", fill opacity="+str(fillopacity))
  if (linewidth != ''):
    texfile.write(", "+linewidth)
  if (mark != ''):
    texfile.write(", mark="+mark)
  if (line_join != ''):
    texfile.write(", line join="+str(line_join))
  texfile.write("] ")
  texfile.write("plot file {"+datafile+"};\n")
  if (legendentry != ''):
    texfile.write("    \\addlegendentry{"+legendentry+"};\n")
  texfile.closed


def write_pgfplot_tex_file_plot_table_example(datafile, texfilename):
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  print>>texfile, "    % Example of a plot with specified marker, linestyle and line join:"
  print>>texfile, "    %\\addplot[color=red, mark=square*, linestyle=solid, line join=round] table[x index=0, y index=1] {datafilename};"
  print>>texfile, "    % Example of a plotting a table by index, seperator of csv file is 'space':"
  print>>texfile, "    %\\addplot[color=red] table[x index=0, y index=1, col sep=space] {datafilename};"
  print>>texfile, "    % Example of a plotting a table by label, seperator of csv file is a comma: ',' :"
  print>>texfile, "    %\\addplot[color=red, mark=o, linestyle=solid, line join=round] table[x=xlabel, y index=ylabel, col sep=comma] {datafilename};"
  texfile.closed


def write_pgfplot_tex_file_plot_table_by_index(datafile, texfilename, xindex=0, yindex=1, color='blue', fill=None, fillopacity='1', mark='', linestyle='solid', linewidth='', line_join='', legendentry=''):
  # Get pgf seperator string, of seperator char used in "datafile":
  pgfsepcharstring = get_pgf_sepchar(datafile)
  # First of all, examine texfile and datafile strings, and find relative paths of them:
  (texfile_path, texfilenameonly) = convert_filename_to_path_and_filename(texfilename)
  (datafile_path, datafile) = convert_filename_to_path_and_filename(datafile)
  # Check if path of datafile is same path as texfile:
  rel_path = get_relative_path(texfile_path, datafile_path)
  if (rel_path.endswith('/')): rel_path = rel_path[:-1]
  # Now set the datafile to be the relative path from the texfile pointing to the datafile:
  datafile = rel_path + '/' + datafile
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  legendentry = remove_underscore_preserve_math_mode(legendentry, replace_char='\_') # the other strings should not have underscores anyway!
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  texfile.write("    \\addplot[color="+color+", "+linestyle)
  if (not (fill is None)):
    texfile.write(", fill="+str(fill)+", fill opacity="+str(fillopacity))
  if (linewidth != ''):
    texfile.write(", "+linewidth)
  if (mark != ''):
    texfile.write(", mark="+mark)
  if (line_join != ''):
    texfile.write(", line join="+str(line_join))
  texfile.write("] ")
  # Now the rest of the plot command and finish the line:
  texfile.write("table[x index="+str(xindex)+", y index="+str(yindex)+", col sep="+pgfsepcharstring+"] {"+datafile+"};\n")
#  print>>texfile, "    \\addplot[color="+color+"] table[x index="+str(xindex)+", y index="+str(yindex)+"] {"+datafile+"};"
  if (legendentry != ''):
    texfile.write("    \\addlegendentry{"+legendentry+"};\n")
  texfile.closed


def write_pgfplot_tex_file_plot_table_by_label(datafile, texfilename, xlabel, ylabel, color='blue', fill=None, fillopacity='1', mark='', linestyle='solid', linewidth='', line_join='', legendentry=None, onlymarks=False, yerrorbars=False, y_errorbar=None, xerrorbars=False, x_errorbar=None):
  # Get pgf seperator string, of seperator char used in "datafile":
  pgfsepcharstring = get_pgf_sepchar(datafile)
  # First of all, examine texfile and datafile strings, and find relative paths of them:
  (texfile_path, texfilenameonly) = convert_filename_to_path_and_filename(texfilename)
  (datafile_path, datafile) = convert_filename_to_path_and_filename(datafile)
  # Check if path of datafile is same path as texfile:
  rel_path = get_relative_path(texfile_path, datafile_path)
  if (rel_path.endswith('/')): rel_path = rel_path[:-1]
  # Now set the datafile to be the relative path from the texfile pointing to the datafile:
  datafile = rel_path + '/' + datafile
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  if (not legendentry is None):
    legendentry = remove_underscore_preserve_math_mode(legendentry, replace_char='\_') # the other strings should not have underscores anyway!
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  texfile.write("    \\addplot[color="+color+", "+linestyle)
  if (not (fill is None)):
    texfile.write(", fill="+str(fill)+", fill opacity="+str(fillopacity))
  if (linewidth != ''):
    texfile.write(", "+linewidth)
  if (mark != ''):
    texfile.write(", mark="+mark)
  if (line_join != ''):
    texfile.write(", line join="+str(line_join))
  if (onlymarks):
    texfile.write(", only marks")
  if (yerrorbars):
    texfile.write(", error bars/.cd, y dir=both, y explicit")
  elif (xerrorbars):
    texfile.write(", error bars/.cd, x dir=both, x explicit")
  texfile.write("] ")
  # Now the rest of the plot command and finish the line:
  if (y_errorbar is None and x_errorbar is None):
    texfile.write("table[x="+xlabel+", y="+ylabel+", col sep="+pgfsepcharstring+"] {"+datafile+"};\n")
  else:
    if (x_errorbar is None):
      texfile.write("table[x="+xlabel+", y="+ylabel+", y error="+y_errorbar+", col sep="+pgfsepcharstring+"] {"+datafile+"};\n")
    else:
      texfile.write("table[x="+xlabel+", y="+ylabel+", x error="+x_errorbar+", col sep="+pgfsepcharstring+"] {"+datafile+"};\n")
  if (not legendentry is None):
    texfile.write("    \\addlegendentry{"+legendentry+"};\n")
  texfile.closed


def write_pgfplot_tex_file_plot_coordinates(texfilename, x, y, color='blue', fill=None, fillopacity='1', mark='', linestyle='solid', linewidth='', line_join='', legendentry=''):
  # First of all, let's check the input arguments x, y if they are lists, or numbers, and store values in xx,yy list variables:
  z = 0; xx=[]; yy=[];
  for i in [x,y]:
    if (isinstance(i, list) or isinstance(i, tuple)):
      # For now, let's only allow lists with 2 elements:
      if (not (len(i) == 2)):
        errmsg = 'ERROR: arguments x and y must be of length 2 if given as list or tuple!'
        printc(errmsg, 'red', False)
        raise SystemExit()
      else:
        for j in i:
          # The elements of x/y must be integer or float numbers:
          if (not (isinstance(j, int) or isinstance(j,float))):
            errmsg = 'ERROR: elements of x and y must be integers or float numbers'
            printc(errmsg, 'red', False)
            raise SystemExit()
      # Store this value in the xx/yy list as min and max value:
      if (z == 0): xx = [x[0], x[1]]
      else: yy = [y[0], y[1]]
    else: # if x or y is not given as a list or tuple:
      if (not (isinstance(i,int) or isinstance(i,float))):
        errmsg = 'ERROR: If x or y is not given as a list or tuple, they must be of type integer or float'
        printc(errmsg, 'red', False)
        raise SystemExit()
      else:
        # Store this value in the xx/yy list as min and max value:
        if (z == 0): xx = [x, x]
        else: yy = [y, y]
    z = z+1
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  legendentry = remove_underscore_preserve_math_mode(legendentry, replace_char='\_') # the other strings should not have underscores anyway!
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write the texfile:
  texfile.write("    \\addplot[color="+color+", "+linestyle)
  if (not (fill is None)):
    texfile.write(", fill="+str(fill)+", fill opacity="+str(fillopacity))
  if (linewidth != ''):
    texfile.write(", "+linewidth)
  if (mark != ''):
    texfile.write(", mark="+mark)
  if (line_join != ''):
    texfile.write(", line join="+str(line_join))
  texfile.write("] ")
  texfile.write("plot coordinates { ("+str(xx[0])+","+str(yy[0])+") ("+str(xx[1])+","+str(yy[1])+")};\n")
  # the following is commented out as it is replaced by the above line making use of more consistent argument pairs:
  #texfile.write("plot coordinates { ("+str(xmin)+","+str(y)+") ("+str(xmax)+","+str(y)+")};\n")
  if (legendentry != ''):
    texfile.write("    \\addlegendentry{"+legendentry+"};\n")
  texfile.closed


def write_pgfplot_tex_file_plot_gaussian(texfilename, mean, std, samples='100', color='blue', fill=None, fillopacity='1', mark='', linestyle='solid', linewidth='', line_join='', legendentry=''):
  # LaTeX does not like underscores, as it assumes to put the following character as subscript, which is only allowed in mathsmode,
  # thus replace underscores with spaces:
  legendentry = remove_underscore_preserve_math_mode(legendentry, replace_char='\_') # the other strings should not have underscores anyway!
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write the texfile:
  # First write out the newcommand for the gaussian function:
  texfile.write("    \\newcommand\gauss[2]{1/(#2*sqrt(2*pi))*exp(-((x-#1)^2)/(2*#2^2))}\n")
  # Now add the plot:
  texfile.write("    \\addplot[color="+color+", "+linestyle)
  if (not (fill is None)):
    texfile.write(", fill="+str(fill)+", fill opacity="+str(fillopacity))
  if (linewidth != ''):
    texfile.write(", "+linewidth)
  if (mark != ''):
    texfile.write(", mark="+mark)
  if (line_join != ''):
    texfile.write(", line join="+str(line_join))
  texfile.write(", samples="+str(samples)+", smooth] ")
  texfile.write("{\gauss{"+str(mean)+"}{"+str(std)+"}};\n")
  if (legendentry != ''):
    texfile.write("    \\addlegendentry{"+legendentry+"};\n")
  texfile.closed


def write_pgfplot_tex_file_close_axis(texfilename, axis='axis'):
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  print>>texfile, "  \\end{"+str(axis)+"}"
  print>>texfile, ""
  texfile.closed


#def write_pgfplot_tex_file_spy_scope(texfile, color='blue', magnification=3):
#  # Open texfile in write modus:
#  texfile = open(texfile, "a")
  


def write_pgfplot_tex_file_close_plot(texfilename):
  # Open texfile in write modus:
  texfile = open(texfilename, "a")
  # Write to the texfile:
  print>>texfile, "  \\end{axis}"
  print>>texfile, "\\end{tikzpicture}"
  print>>texfile, ""
  print>>texfile, "\\end{document}"
  texfile.closed


#####################
# Obsolete routines #
#####################

## Obsolete, check routine above using an array
## Write x and y coordinates to a file, to use for pgfplots:
#def write_pgfplots_data_file(x, y, filename):
#  datafile = open(filename, "w")
#  z=0
#  for i in x:
#    print>>datafile, x[z], " ", y[z]
#    z=z+1
#  datafile.closed

## Obsolete, check routine above
#def write_pgfplot_tex_file(datafile, texfilename, title, xlabel, ylabel, color, mark, linestyle, xmin, xmax, ymin, ymax, legendentry, legendpos, plotwidth, plotheight, minref, maxref):
#  # Open texfile in write modus:
#  texfile = open(texfilename, "w")
#  # Write the texfile:
#  print>>texfile, "%% Generated file to plot data from a datafile using pgfplots"
#  print>>texfile, "\\documentclass[a4paper, 11pt]{article}"
#  print>>texfile, "% load packages:"
#  print>>texfile, "\\usepackage{tikz}"
#  print>>texfile, "\\usepackage{pgfplots}"
#  print>>texfile, "% set the pagestyle to empty (removing pagenumber etc)"
#  print>>texfile, "\\pagestyle{empty}"
#  print>>texfile, ""
#  print>>texfile, "\\begin{document}"
#  print>>texfile, ""
#  print>>texfile, "\\begin{tikzpicture}"
#  print>>texfile, "  \\begin{axis}["
#  print>>texfile, "        title=", title, ","
#  print>>texfile, "        xmin=",xmin,",xmax=",xmax,","
#  print>>texfile, "        ymin=",ymin,",ymax=",ymax,","
#  print>>texfile, "        xlabel=",xlabel,","
#  print>>texfile, "        ylabel=",ylabel,","
#  print>>texfile, "        legend pos=",legendpos,","
#  print>>texfile, "        width=",plotwidth,","
#  print>>texfile, "        height=",plotheight
#  print>>texfile, "        ]"
#  print>>texfile, "    %\\addplot[color=",color,",mark=",mark,",",linestyle,"] plot file {",datafile,"};"
#  print>>texfile, "    \\addplot[color=",color,"] plot file {",datafile,"};"
#  print>>texfile, "    \\addlegendentry{",legendentry,"};"
#  print>>texfile, "    \\addplot[color=red,thick,dashed] plot coordinates { (",xmin,",",minref,") (",xmax,",",minref,")};"
#  print>>texfile, "    \\addplot[color=red,thick,dashed] plot coordinates { (",xmin,",",maxref,") (",xmax,",",maxref,")};"
#  print>>texfile, "    \\addlegendentry{Min,Max References};"
#  print>>texfile, "  \\end{axis}"
#  print>>texfile, "\\end{tikzpicture}"
#  print>>texfile, "\\end{document}"


##########################
# PGFPlotsTable Methods: #
##########################

def write_pgfplotstable_tex_file(texfile, datafile, datacolnames=None, data=None, printcols=None, printcolnames=None, precision=None, string_replace=None, postprocessing=None, sort_colname=None, ignore_chars=None, caption=None):
  """ This method generates a tex file for a pgfplotstable, whereas
      the content and description/header is given in a file, which
      filename is given by an input argument.
      Input:
       texfile: Name of the texfile to be written to.
       datafile: Name of the pgfdatafile in which the table's content
         is stored.
       datacolnames: List of column names/header in the datafile
       data: 2D list, that contains the data to be printed, this is only
         used in order to work out the type of the element, such that
         we can automatically set the pgfplotstable setting for that column
       printcols: List of columns to print in the table, whereas the elements
         of 'printcols' refer to the strings of the column labels of the datafile
       printcolnames: 1D dictionary of column labels as they appear in the
         datafile, and their values being the string that should be printed instead.
       precision: 2D List of two elements, first is a string of the corresponding column
         name, second is a string of column data type and numerical precision entries
       string_replace: List of lists, with the inner list having n elements,
         with the first element being the string of the the affected columnname,
         and the following elements being lists of two elements each, with the
         first element of those list being the text to be replaced, and the
         second the text that should appear in the table instead.
         Example: [
                   ['col1', ['replace', 'write-this'], ['replace_this_too', 'this-instead']],
                   ['col2', ['replace-here', 'this-is-good']],
                   ...
                  ]
       postprocessing: List of lists, whereas inner list has 4 elements:
         1: column name to postprocess, 2: LaTeX code to add to the column,
         3: must either be 'unit' or 'trailing' and 4: is either True or False, determining
         if the second element is supposed to be a unit or not.
       sort_colname: String of the column label (of the csv datafile) that the table should
         be sorted by
       caption: String of the caption to be printed below the table.
  """
  # First of all, examine texfile and datafile strings, and find relative paths of them:
  (texfile_path, texfile) = convert_filename_to_path_and_filename(texfile)
  (datafile_path, datafile) = convert_filename_to_path_and_filename(datafile)
  # Check if path of datafile is same path as texfile:
  rel_path = get_relative_path(texfile_path, datafile_path)
  if (rel_path.endswith('/')): rel_path = rel_path[:-1]
  # pgftable_name is the name that will refer to the data of the table
  # in LaTeX/PGF:
  pgftable_name = 'pgftable' + texfile[:-4]
  # Get rid of digits in pgftable_name, as digits are not allowed in LaTeX variable names:
  pgftable_name = pgftable_name.replace('0','').replace('1','').replace('2','').replace('3','').replace('4','').replace('5','').replace('6','').replace('7','').replace('8','').replace('9','').replace('_','').replace('-','')
  # If datacolnames is not given, extract the data from the datafile:
  if (datacolnames is None):
    # If however the argument "printcols" is given, datacolnames can be set to printcols:
    if (not (printcols is None)):
      datacolnames = printcols
    else: # extract it from the datafile:
      (datacolnames, status) = read_column_names_pgfplots_data_file(datafile_path+'/'+datafile)
      if (not (status == 0)):
        raise SystemExit('Could not read in the column names from datafile "'+datafile+'" correctly. Exiting...')
  # Also, if the data array "array" was not given, assemble it with the given information:
  if (data is None):
    data = []
    for colname in datacolnames:
      (coldata, status) = read_column_pgfplots_data_file(datafile_path+'/'+datafile, colname)
      if (status == 0):
        data.append(coldata)
      else:
        raise SystemExit('Error occured while reading in the data of column "'+colname+'" from file "'+datafile+'".')
  # Determine the seperation character of the datafile:
  sepchar_string = get_pgf_sepchar(datafile_path+'/'+datafile)

  # Now start writing files:
  file = open(texfile_path+'/'+texfile, "w")
  print>>file, "%% Generated file to generate a table data from a pgfdatafile using pgfplotstable"
  print>>file, ""
  print>>file, "\\documentclass[11pt]{article}"
  print>>file, "% Set page legths"
  print>>file, "\\special{papersize=550cm,550cm}"
  print>>file, "\\hoffset-0.8in"
  print>>file, "\\voffset-0.8in"
  print>>file, "\\setlength{\\paperwidth}{550cm}"
  print>>file, "\\setlength{\\paperheight}{550cm}"
  print>>file, "\\setlength{\\textwidth}{545cm}"
  print>>file, "\\setlength{\\textheight}{545cm}"
  print>>file, "\\topskip0cm"
  print>>file, "\\setlength{\\headheight}{0cm}"
  print>>file, "\\setlength{\\headsep}{0cm}"
  print>>file, "\\setlength{\\topmargin}{0cm}"
  print>>file, "\\setlength{\\oddsidemargin}{0cm}"
  print>>file, "% set the pagestyle to empty (removing pagenumber etc)"
  print>>file, "\\pagestyle{empty}"
  print>>file, ""
  print>>file, "% Additional packages:"
  print>>file, "\\usepackage{amsmath}"
  print>>file, "\\usepackage{amssymb}"
  print>>file, "\\usepackage{textcomp}"
  print>>file, "\\usepackage{units}"
  print>>file, "\\usepackage[english]{babel}"
  print>>file, "\\usepackage[babel]{csquotes}"
  print>>file, "\\usepackage{color}"
  print>>file, "\\usepackage{pdflscape}"
  print>>file, ""
  print>>file, "% PGF:"
  print>>file, "\\usepackage{tikz}"
  print>>file, "% \\usepackage{pgfplots}"
  print>>file, "\\usepackage{pgfplotstable}"
  print>>file, "\\pgfplotsset{compat=1.10}"
  print>>file, ""
  print>>file, "% recommended:"
  print>>file, "\\usepackage{booktabs}"
  print>>file, "\\usepackage{array}"
  print>>file, "\\usepackage{colortbl}"
  print>>file, ""
  print>>file, "\\begin{document}"
  print>>file, ""
  print>>file, "\\begin{landscape}"
  print>>file, ""
  print>>file, "% Load table settings:"
  print>>file, "\\input{pgftablesettings_"+texfile+"}"
  print>>file, "% Load table data:"
  print>>file, "\\pgfplotstableread{"+rel_path+"/"+datafile+"}\\"+pgftable_name
  print>>file, ""
  if (not (caption is None)): # Caption given, so print caption, and create table environment
    print>>file, "\\begin{table}"
  else:
    None # Just create the table, without table environment, and without caption and label, that should be done in the 
  print>>file, "  \\centering"
  # Make a string, seperated by commas, of the given list 'printcols'
  # First, remove underscore signs from printcols:
  # Remove underscore signs from datacolnames:
  if (not (printcols is None)):
    printcols = remove_underscore_preserve_math_mode(','.join(printcols).strip(), replace_char='_')
  else:
    printcols = remove_underscore_preserve_math_mode(','.join(datacolnames).strip(), replace_char='_')
  print>>file, "  \\pgfplotstabletypeset[columns={"+printcols+"},"
  if (not (sort_colname is None)):
    print>>file, "                         sort, sort key={"+str(sort_colname)+"},"
  print>>file, "  ]\\"+pgftable_name
  # Add caption and label:
  if (not (caption is None)):
    print>>file, "  \\caption{"+caption+"}"
    print>>file, "  \\label{tab:"+texfile[:-4]+"}"
  # End of table environment:
  if (not (caption is None)):
    print>>file, "\\end{table}"
  print>>file, ""
  print>>file, "\\end{landscape}"
  print>>file, ""
  print>>file, "\\end{document}"
  # Close texfile:
  file.closed

  # Now write the pgftable settings file:

  file = open(texfile_path+"/pgftablesettings_"+texfile, "w")
  print>>file, "% PGFPlotsTable settings are defined below."
  print>>file, "% To load them:"
  print>>file, "% \\input{"+texfile_path+"/pgftablesettings_"+texfile+"}"
  print>>file, ""
  print>>file, "\\pgfplotstableset{"
  print>>file, "    %    col sep=&,row sep=\\\\"
  print>>file, "    %    col sep=space, ignore chars={(,),\ ,\#}"
  print>>file, "    col sep="+sepchar_string+","
  if (not (ignore_chars is None)):
    ignore_chars_string = ','.join(ignore_chars)
    print>>file, "    ignore chars={"+ignore_chars_string+"},"
  print>>file, "    % Coloring:"
  print>>file, "    every even row/.style={before row={\\rowcolor[gray]{0.85}}}," # \\rowcolor[blue]{0.5}
  print>>file, "    % Table header:"
  print>>file, "    every head row/.style={before row=\\toprule,after row=\midrule},"
  print>>file, "    every last row/.style={after row=\\bottomrule},"
  print>>file, "    % Set column parameters:"
  # Remove underscore signs from datacolnames:
  datacolnames = remove_underscore_preserve_math_mode(', '.join(datacolnames).strip(), replace_char='_')
  datacolnames = datacolnames.split(', ')
  # Now define the column names/strings, as they should appear in the document:
  colprintnames = remove_underscore_preserve_math_mode(', '.join(datacolnames).strip(), replace_char='\_')
  colprintnames = colprintnames.split(', ')
  print>>file, "    columns={"+', '.join(datacolnames)+"},"
  # Depending on the type of element in 
  for j in range(len(datacolnames)):
    string = False
    # Set entry for current column, and define column name:
    # First, find out if datacolnames[j] is found in printcolnames, if so, the name of the column was set to change:
    if (not (printcolnames is None) and datacolnames[j] in printcolnames):
      printcolname = printcolnames[datacolnames[j]]
      # remove unwanted characters from that string:
      printcolname = remove_underscore_preserve_math_mode(printcolname.strip(), replace_char='\_')
    else:
      printcolname = colprintnames[j]
    print>>file, "    columns/"+datacolnames[j]+"/.style={column name="+printcolname+","
    # Finding out if the data of this column is a number, or a string:
    # First, check if a precision was specified for this column:
    precision_entry_found = False
    if (not (precision is None)):
      for i in range(len(precision)):
        if (datacolnames[j] == precision[i][0]):
          # Then print that entry:
          print>>file, "        "+precision[i][1]+","
          precision_entry_found = True
          # And break out of the loop:
          break
    if (not precision_entry_found):
      try:
        tmp = float(data[0][j])
        # For this particular case, we want strings only, although most entries are actually numbers:
        #raise Exception # raising an exception will force the entry to be treated as a string!
        # If we were able to convert, then tell pgfplotstable to use format numbers:
        # Now find out if it is an integer or float:
        # First of all, if the current column name is in string_replace, raise an exception:
        for i in string_replace:
          if (any([datacolnames[j] in string_replace_item for string_replace_item in string_replace])):
            raise Exception
        # If no entry of this column is in string_replace or precision, continue to convert the string into a number:
        try:
          tmp = int(data[0][j])
          # This is an integer:
          print>>file, "        sci,"
          print>>file, "        precision=0, fixed,"
        except:
          # This is a floating point number:
          print>>file, "        sci, sci zerofill,"
          print>>file, "        precision=3, fixed,"
        if (not (postprocessing is None)):
          # Check if postprocessing is done later for this column, 
          # and if so, fill empty decimal points with zeros:
          if (not (any([datacolnames[j] in postitem for postitem in postprocessing]))):
            print>>file, "        dec sep align,"
          else: # also align by decimal point, but fill zeros:
            print>>file, "        dec sep align, fixed zerofill,"
        else: # If postprocessing is None (not given by user, use dec sep align):
            print>>file, "        dec sep align,"
      except:
        string = True
        # If that failed, it is a string:
        print>>file, "        string type,"
        # Now, if present, write string replace information to the texfile:
        boolean = False
        if (not (string_replace is None)):
          for item in string_replace:
            if (item[0] == datacolnames[j]): # item[0] is the column name
              for replace in item[1:]: # in replace are the replacement strings
                print>>file, "        string replace={"+str(replace[0])+"}{"+str(replace[1])+"},"
                # Check if there is an entry of a boolean, because booleans should be
                # centered, whereas strings should be left aligned
                if (replace[0] == 'True' or replace[0] == 'False'):
                  boolean = True
    # If this is the first column, add a vertical line in the table:
    if (j==0):
      print>>file, "        column type={l|},"
    else:
      if (string and not boolean):
        print>>file, "        column type=r," #lets assume, we want the strings to be right aligned
      elif (string and boolean):
        print>>file, "        column type=c,"
    # Add postprocessing entries (for now only units possible):
    if (not (postprocessing is None)):
      for item in postprocessing:
        if (item[0] == datacolnames[j]):
          if (item[2] != 'code'):
            print>>file, "        postproc cell content/.append code={" #still using pgfplotstable code argument here
            print>>file, "            \ifnum1=\pgfplotstablepartno"
            # print>>file, "        postproc cell content/.append style={"
            if (item[2] == 'unit' and item[3] == True):
              print>>file, "              \pgfkeysalso{@cell content/.add={$\unit[}{]{"+item[1]+"}$}}%"
              #print>>file, "            /pgfplots/table/@cell content/.add={$\unit[}{]{"+item[1]+"}$},"
            elif (item[2] !='unit' and item[2] !='trailing' or item[3] == False) :
              print>>file, "              \pgfkeysalso{@cell content/.add={"+item[1]+"}{}}%"
              #print>>file, "            /pgfplots/table/@cell content/.add={"+item[1]+"}{},"
            elif (item[2] =='trailing' and item[3] == True):
              print>>file, "            \pgfkeysalso{@cell content/.add={}{"+item[1]+"}}%"
              #print>>file, "            /pgfplots/table/@cell content/.add={}{"+item[1]+"},"
            print>>file, "            \\fi"
            #print>>file,
          elif (item[2] =='code' and item[3] == True):
            # This inner list append pgf code to the postprocessing in pgf, thus this list has six element
            print>>file, "            postproc cell content/.append code={"
            print>>file, "                \ifnum\pgfplotstablerow="+str(item[1])
            print>>file, "                    \pgfkeysalso{/pgfplots/table/@cell content/.add={}{"+str(item[4])+"}}"
            print>>file, "                \else"
            print>>file, "                    \pgfkeysalso{/pgfplots/table/@cell content/.add={}{"+str(item[5])+"}}"
            print>>file, "                \\fi"
          print>>file, "        },"
    print>>file, "    },"
  print>>file, "}"
  file.closed
  # Now that the (standalone) file has been written, write another file that can be included
  # in another latex document with \input{..}
  # First read in the file that was just written to disk:
  infile = open(texfile_path+'/'+texfile, 'r')
  outfile = open(texfile_path+'/'+texfile.replace('.tex','')+'_include.tex', 'w')
  write_to_file = False
  for line in infile:
    if ('% Load table settings' in line):
      write_to_file = True
      outfile.write('% Load this file in your LaTeX document with:\n')
      outfile.write('% \input{'+texfile.replace('.tex','')+'_include.tex'+'}\n\n')
    elif (not (caption is None) and '\end{table}' in line): # \end{table} is only part of the output if caption was given!
      write_to_file = False
      outfile.write(line)
    elif (caption is None and '\end{landscape}' in line):
      write_to_file = False
    if (write_to_file):
      outfile.write(line)
  outfile.close()  
  infile.close()


def prevent_dimension_too_large_error(dir, texfilename):
  """ This method is executed if the string '! Dimension too large'
      was found in pdflatex's output. It tries to make minor modifications
      to the given tex file in order to prevent this error from happening.
      Input:
       dir: Directory name where the tex file is in
       texfilename: Name of the tex file to run
  """
  # Dictionary to store relevant data for each datafile we find in texfilename:
  datadict = {}
  # First, let's find out the relevant datafiles we have to check:
  # Open texfile:
  texfile = open(dir+'/'+texfilename, 'r')
  texfile_lines = texfile.readlines()
  texfile.close()
  # Assemble a list of addplot commands in the texfile, those are the lines
  # we have to process:
  curve_cmds = []
  for line in texfile_lines:
    if (line.strip().startswith('\\addplot')):
      curve_cmds.append(line.strip())
  for line in curve_cmds:
    # Get the datafilename:
    datafilename = line.split('{')[-1].split('}')[0]
    # And get the relevant columns of that datafile:
    colnames = line.split('table[')[-1].split(']')[0]
    colnames = colnames.split(',')
    for col in colnames:
        col = col.replace(' ','')
        if ('x=' in col):
          xcolname = col.split('=')[-1].strip()
        elif ('y=' in col):
          ycolname = col.split('=')[-1].strip()
    # Now add column labels into datadict:
    datadict.update({datafilename : {'xcolname' : xcolname, 'ycolname' : ycolname}})

  # Now scan the data of relevant columns to find min/max x/y values of each plot in texfilename
  for datafilename in sorted(datadict.iterkeys()):
    # Open datafile:
    # Now get the corresponding column names:
    xcolname = datadict[datafilename]['xcolname']
    ycolname = datadict[datafilename]['ycolname']
    # Potential error message for reading in data from the datafile:
    datafile_errmsg = "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    datafile_errmsg = datafile_errmsg+"\nSerious error was found. Please check your datafile"
    datafile_errmsg = datafile_errmsg+"\n   \""+datafilename+"\""
    datafile_errmsg = datafile_errmsg+"\nfor valid floating point numbers and"
    datafile_errmsg = datafile_errmsg+"\nthat the column labels are as they are supposed to be."
    datafile_errmsg = datafile_errmsg+"\nSkipping this datafile!"
    # Now read data from datafile:
    (xdata, status) = read_column_pgfplots_data_file(datafilename, xcolname)
    if (status != 0):
      # Error occured, so skip this datafile
      print datafile_errmsg
      continue
    (ydata, status) = read_column_pgfplots_data_file(datafilename, ycolname)
    if (status != 0):
      # Error occured, so skip this datafile
      print datafile_errmsg
      continue
    # Now find the min/max values:
    xmin = min(xdata); xmax = max(xdata)
    ymin = min(ydata); ymax = max(ydata)
    # Now that we have the min/max values of the relevant datacolumns in datafile, 
    # store those min/max values in the dict:
    datadict[datafilename].update({'xmin':xmin, 'xmax':xmax, 'ymin':ymin, 'ymax':ymax})

  # Now that we have all the data we need, lets modify the texfile with the pgfplot commands slightly
  # in order to prevent the '! dimension too large error':
  xmin = 10e15; xmax = -10e15; ymin = 10e15; ymax = -10e15
  for datafilename in sorted(datadict.iterkeys()):
    print "datafilename = ", datafilename
    # Now determine the xmin/xmax and ymin/ymax values of the entire plot:
    if (datadict[datafilename]['xmin'] < xmin): xmin = datadict[datafilename]['xmin']
    if (datadict[datafilename]['xmax'] > xmax): xmax = datadict[datafilename]['xmax']
    if (datadict[datafilename]['ymin'] < ymin): ymin = datadict[datafilename]['ymin']
    if (datadict[datafilename]['ymax'] > ymax): ymax = datadict[datafilename]['ymax']
  # The lines of the texfile are still stored in the variable 'texfile_lines'
  new_texfile_lines = []
  for line in texfile_lines:
    # Find line starting with 'scale only axis':
    if (line.strip().startswith('scale only axis')):
      # Commenting out 'scale only axis command:
      new_texfile_lines.append(line.split('scale only axis')[0]+'% scale only axis'+line.split('scale only axis')[-1])
    elif (line.strip().startswith('restrict x to domain') or line.strip().replace(' ','').startswith('%restrictxtodomain')):
      precmndstring = line.split('restrict x to domain')[0].split('%')[0]
      new_texfile_lines.append(precmndstring+'restrict x to domain='+str(xmin)+':'+str(xmax)+', % use this if you get a \'dimension too large\' error\n')
    elif (line.strip().startswith('restrict y to domain') or line.strip().replace(' ','').startswith('%restrictytodomain')):
      precmndstring = line.split('restrict y to domain')[0].split('%')[0]
      new_texfile_lines.append(precmndstring+'restrict y to domain='+str(ymin)+':'+str(ymax)+', % use this if you get a \'dimension too large\' error\n')
    else:
      new_texfile_lines.append(line)
  # Now the new lines of the texfile have been assembled, write them to disk:
  texfile = open(texfilename, 'w')
  for new_line in new_texfile_lines:
    texfile.write(new_line)
  texfile.close()


def run_latex(dir, filename):
  """ This method runs pdflatex on the given filename
      in directory dir and if successful produces a pdf
      Input:
       dir: Directory name where the tex file is in
       filename: Name of the tex file to run
  """
  cmd = 'cd '+dir+'; pdflatex -interaction=nonstopmode '+filename
  shellout = commands.getoutput(cmd)
  # For testing only:
  # Printing out shellout:
  if ('! Dimension too large.' in shellout):
    print "=============================================================="
    #print "Dimension too large error found in pdflatex output. Making a few"
    #print "adjustments on the given tex file to prevent this error."
    #print "filename: ", filename
    prevent_dimension_too_large_error(dir, filename)
    #for line in shellout:
    #  print "line: ", line
    #  print "shellout: "
    #  print shellout
    print "=============================================================="
  # Check we have to rerun, because of labels:
  if (shellout.find('LaTeX Warning: Label(s) may have changed.') >= 0):
    shellout = commands.getoutput(cmd)


def run_pdfcrop(dir, filename, newfilename):
  """
      Runs pdfcrop on a pdf, in order to remove white space
      Input:
       dir: String of the directory where the pdf is in
       filename: String of the pdf filename
       newfilename: String of the cropped version of 'filename'
  """
  cmd = 'cd '+dir+'; pdfcrop '+filename+' '+newfilename
  shellout = commands.getoutput(cmd)


def write_dict_status_pgftable(directory, texfilename, dict, first_colname, printcols=None, printcolnames=None, precision=None, string_replace=None, postprocessing=None, caption=None, pdflatex=True, pdfcrop=True):
  """ This method assembles lists of the content of the given dictionary
      and then calls methods to write pgf data files of the dictionary,
      and to update the pdf showing the table.
      Input:
       directory: The directory in which the table should be written to
       texfilename: String of the filename of the pgf-tex-table.
       dict: 2D Dictionary of which all content will be written to file
       first_colname: String of the name of the first column, e.g. 'simulation name'
       printcols: List of columns to print in the table, whereas the elements
         of 'printcols' refer to the strings of the column labels of the datafile
       printcolnames: 1D dictionary of column labels as they appear in the
         datafile, and their values being the string that should be printed instead.
       precision: 2D List of two elements, first is a string of the corresponding column
         name, second is a string of column data type and numerical precision entries
       string_replace: List of lists, with the inner list having n elements,
         with the first element being the string of the the affected columnname,
         and the following elements being lists of two elements each, with the
         first element of those lists being the text to be replaced, and the
         second the text that should appear in the table instead.
         Example: [
                   ['col1', ['replace', 'write-this'], ['replace_this_too', 'this-instead']],
                   ['col2', ['replace-here', 'this-is-good']]
                  ]
       postprocessing: List of lists, whereas inner list has 4 elements:
         1: column name to postprocess, 2: LaTeX code to add to the column,
         3: must either be 'unit' or 'trailing' and 4: is either True or False, determining
         if the second element is supposed to be a unit or not.
       pdflatex: Boolean determining if pdflatex should run on the
         generated texfile
       pdfcrop: Boolean determining if pdfcrop should run on the
        generated pdf
  """
  # First assemble the header of the table:
#  for dir in sorted_nicely(dict.iterkeys()):
#  for dir in sortdiff(dict.keys()):
  for dir in sorted(dict.keys()):
    datadict = dict[dir]
    array_labels = [first_colname]
    for key, value in datadict.items():
      # Key is pratically the header of our table, with a leading
      # 'dirname', as the directory name of the simulation is not
      # stored in 'key', but in 'dir'. value is the content of the
      # table.
      array_labels.append(key)
    break
  # Now the content of the table, each row below the header:
  if (string_replace is None):
    string_replace = []
  table_rows = [[0 for j in range(len(array_labels))] for i in range(len(dict.keys()))]
  i = 0
  # find out if all top level dict.iterkeys() are numbers:
  numbers=[]
  for dir in dict.keys():
    try:
      float(dir)
      numbers.append(True)
    except:
      numbers.append(False)
  if (all(numbers)):
    for dir in sorted_nicely(dict.iterkeys()):
      datadict = dict[dir]
      j = 0
      table_rows[i][j] = str(dir)
      for key, value in datadict.items():
        j = j + 1
        table_rows[i][j] = str(value)
      # For this dirname, add an entry into string_replace,
      # in order to add color and proper \_ for the table:
      string_replace.append([first_colname, [dir, remove_underscore_preserve_math_mode(dir, replace_char='\_')]])
      i = i + 1
  else:
#  for dir in sortdiff(dict.keys()):
    for dir in sorted(dict.keys()):
      datadict = dict[dir]
      j = 0
      table_rows[i][j] = str(dir)
      for key, value in datadict.items():
        j = j + 1
        table_rows[i][j] = str(value)
      # For this dirname, add an entry into string_replace,
      # in order to add color and proper \_ for the table:
      string_replace.append([first_colname, [dir, remove_underscore_preserve_math_mode(dir, replace_char='\_')]])
      i = i + 1

  # Write datafile:
  pgfdat_filename = directory+'/'+texfilename.split('.tex')[0].split('/')[-1]+'_data.pgfdat'
  write_pgfplots_data_file(pgfdat_filename, table_rows, array_labels=array_labels)
  # Now write texfile to generate the pdf with the table:
  texfile = directory+'/'+texfilename

  # If this method was given a specific header, meaning a specific order of printing the columns
  # in the table, then this list should be given to the texfile, rather than the unsorted columnlist
  # that was obtained from the dictionary.
  if (printcols is None):
    printcols = array_labels

  # Write to texfile:
  write_pgfplotstable_tex_file(texfile, pgfdat_filename, array_labels, table_rows, printcols=printcols, printcolnames=printcolnames, precision=precision, string_replace=string_replace, postprocessing=postprocessing, caption=caption)
  if (pdflatex):
    # Produce pdf:
    (dir, texfile) = convert_filename_to_path_and_filename(texfile)
    run_latex(dir, texfile)
    if (pdfcrop):
      # Crop white space from pdf:
      run_pdfcrop(dir, texfile[:-3]+'pdf', texfile[:-3]+'pdf')



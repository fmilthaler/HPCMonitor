import os
import commands
import sys
import time
sys.path.append("/data/fmilthaler/fluidity-trunk/python/")
sys.path.append("/data/fmilthaler/Projects-Code/scripting-library/python/")
#from numpy import *
from io_routines import *
from pgf_io_routines import *
from myexception import *



class Messaging:
  """ A class for printing information on the terminal, writing log/error files, sending
      crucial reports via email, and using the notify-send, a popup with short text,
      to let the user know about the certain events.
  """
  def __init__(self, verbosity, emailaddress=None, sendemail=True, popupmsg=True):
    """
        Constructor with 4 input arguments:
        Input: 
         verbosity: Integer which determines the wanted verbosity level, incoming
           messages with a verbosity above the verbosity level given here, are 
           not reported
         emailaddress: String of email addresses separated by a semicolon, or a 
           list of email addresses to send the reports to
         sendemail: Boolean if emails are wanted or not (Default: True)
         popupmsg: Boolean if popup messages of reports are wanted or not 
           (Default: True)
    """
    # Constructor
    self.verbosity = verbosity
    self.emailaddress = emailaddress
    self.sendemail = sendemail
    self.popupmsg = popupmsg
    # Check if given arguments are valid:
    (self.sendemail, self.emailaddress) = self.check_email_setup(emailaddress, sendemail)



  def update_massaging_properties(self, verbosity=None, emailaddress=None, sendemail=None, popupmsg=None):
    """
        Updating the class variables
        Input:
         verbosity: Integer which determines the verbosity level
         emailaddress: String of email addresses separated by a semicolon, or a 
           list of email addresses to send the reports to
         sendemail: Boolean if emails are wanted or not
         popupmsg: Boolean if popup messages of reports are wanted or not
    """
    if (not (verbosity is None)):
      self.verbosity = verbosity
    if (not (emailaddress is None) and not (sendemail is None)):
      # Check if email address is valid, and set class
      # variables sendemail and emailaddress:
      (self.sendemail, self.emailaddress) = self.check_email_setup(emailaddress, sendemail)
    elif (not (emailaddress is None)):
      (sendemail, self.emailaddress) = self.check_email_setup(emailaddress, True)
    elif (not (sendemail is None)):
      self.sendemail = sendemail
    elif (sendemail is None and self.sendemail is None or self.sendemail == False):
      self.sendemail = False
    if (not (popupmsg is None)):
      self.popupmsg = popupmsg


  def check_email_setup(self, recipient=None, sendemail=True):
    """ This method checks if the email address given by the user
        can be handled or not, it does not check if the email address 
        exists! A logical is set that determines whether or not
        an email will be send. Also emails are allowed to be stored
        in one string, separated by a ';', or as a list. This subroutine
        converts the given emails into a list.
        Input: 
         recipient: Either a string or list containing the email addresses
         sendemail: Boolean which determines if an email is wanted or not
        Output:
         sendemail: Logical that determines if the format/type of recipient
           email address has been given correctly or not.
         converted_emailaddress: Email addresses converted into a list.
    """
    # Return value:
    converted_emailaddress = []

    if (recipient is None):
      recipient = self.emailaddress

    # Check if input argument with email address(es) is empty/None:
    if (recipient == '' or recipient == [] or recipient is None):
      # Then set sendemail to False, as clearly emails are not wanted:
      sendemail = False
      self.sendemail = sendemail

    # Now check if it is a string/list, and if invalid 
    # email addresses are given:
    if (sendemail):
        # is recipient a list or string, or given in a
        # wrong/not acceptable type?
        if (type(recipient).__name__ == 'str'):
          # email address must be seperated by semicolon, 
          # thus convert given string into a list, that is 
          # separated by ';'
          converted_emailaddress = recipient.split(';')
          sendemail = True
        elif (type(recipient).__name__ == 'list'):
          converted_emailaddress = recipient
          sendemail = True
        else:
          errormsg = 'Error: Given argument with email address(es) is of a not acceptable type'
          self.message_handling(None, errormsg, 0, msgtype='err', attachment=None, subject=None)
          # This is flagged as an highly unwanted scenario, thus raise an exception:
          raise Email_Report_Exception()
        # Check given email addresses for invalid email
        # addresses:
        status = self.check_emailaddress_list(converted_emailaddress)
    return sendemail, converted_emailaddress


  def check_emailaddress_list(self, recipients):
    """
        Check the given list of email addresses for invalid email addresses,
        and exit the program if one invalid one was found, as this is 
        most likely highly unwanted, and this routine will be triggered when
        this class is initialized, thus the program won't run for long, and 
        the wrong email address can be fixed.
        Input:
         recipients: List of email addresses
        Output:
         status: Integer, 0 if no invalid email was found, nonzero otherwise
    """
    status = 0
    emailerrorfile = 'email-setup'
    for email in recipients:
      # First check the the whole given email address for whitespace,
      # thus, strip whitespace from beginning and end of given string,
      # then check for spaces:
      tmp = email.strip()
      if (len(tmp.split(' ')) > 1): # spaces found in email address:
        status = 1
        errormsg = 'ERROR: Spaces in email address found!\nemail "'+email+'" is NOT a valid email address!\nWill exit!'
        break
      # Now check that there is not one comma in the string/list,
      # this ensures that neither a comma is in a single email address,
      # nor that the email addresses are separated by a comma:
      if (status == 0):
        tmp = email.strip()
        if (len(tmp.split(',')) > 1): # spaces found in email address:
          status = 1
#          errormsg = 'ERROR: A comma was found in the given email addresses!\nemail "'+email+'" is NOT a valid email address!\nIf the comma was meant to be a separator, please use a ";" instead.\nWill exit!'
          errormsg = 'ERROR: A comma was found in the given email addresses!\nemail "'+email+'" is NOT a valid email address!\nIf the comma was meant to be a separator, please use a \';\' instead.\nWill exit!'
          break
      if (status == 0):
        # Next: Check for exactly one '@' sign in given email address:
        tmp = tmp.split('@')
        if (len(tmp) != 2):
          status = 1
          errormsg = 'ERROR: No or more than one \'@\' sign found in email address.\nemail "'+email+'" is NOT a valid email address!\nWill exit!'
          break
      if (status == 0):
        # Finally check for at least one '.' sign after
        # the '@' sign, and with text inbetween '@' and '.',
        # plus text following the '.'
        tmp = tmp[1].split('.')
        if (len(tmp) == 1):
          status = 1
          errormsg = 'ERROR: No \'.\' sign found behind the \'@\' sign.\nemail "'+email+'" is NOT a valid email address!\nWill exit'
          break
      if (status == 0):
        if (len(tmp[0]) == 0 or len(tmp[1]) == 0):
          status = 1
          errormsg = 'ERROR: No text found inbetween \'@\' and \'.\', or behind \'.\'.\nemail "'+email+'" is NOT a valid email address!\nWill exit!'
          break

    # If an invalid email address was found, write error to errorfile in ./logfiles
    # and exit the program:
    if (status != 0):
      self.message_handling(emailerrorfile, errormsg, 0, msgtype='err', subject='ERROR: Invalid email', sendemail=False)
      # Raise an exception, which can be dealt with later
      raise Email_Report_Exception()

    return status

    # End of method 'check_emailaddress_list'


  def message_handling(self, dir, message, verbosity, msgtype='log', attachment=None, subject=None, sendemail=True):
    """ This method handles incoming messages, in terms of printing it out
        on the screen, sending it to the log/error file writer,
        sending it via email, and/or showing it as a popup in Ubuntu/Gnome
        Input:
         dir: directory name of current simulation
         message: String describing the event
         verbosity: Integer of value 0, 1, 2, 3, indicating the verbosity
           level of the incoming message
         msgtype: String of the type, could be either 'log' or 'err'
         attachment: String of the file(s) to attach to an email
         subject: String of the subject for emails and popup messages
         sendemail: In some cases an email report might be unwanted,
           for those the optional argument 'sendemail' can be used.
           The value of this argument does not overwrite the class
           variable sendemail that was set during the initialisation
           by the user (default: True).
    """
    if (verbosity <= self.verbosity):
      if (msgtype=='log'):
        color = 'green'; highlight=False
      elif (msgtype=='err'):
        color = 'red'
        if (verbosity == 0):
          highlight=True
        else:
          highlight=False
      # Always print it out on the screen
      printc(message, color, highlight); print
      # Write to log/err files (independant of verbosity level):
      self.write_to_log_err_file(dir, message, msgtype)
      # Send email:
      if (self.sendemail and verbosity<=self.verbosity and sendemail):
        self.send_email(dir, self.emailaddress, message, attachment=attachment, subject=subject)
      # Popup message:
      if (self.popupmsg and verbosity<=self.verbosity):
        self.notify_popup(subject, message)


  def write_to_log_err_file(self, dir, msg, msgtype='log'):
    """ This subroutine appends the message 'msg' to the log/err
        files in subdirectory 'logfiles'.
        Input:       
         dir: String of directory name
         msg: String of the message to be sent in the email
         msgtype: String of either 'log' or 'err' which determines
           in which file the msg is written to.
    """
    status = 0
    logfile = 'logfiles/'+dir
    if (msgtype == 'log'):
      logfile = logfile+'.log'
    elif (msgtype == 'err'):
      logfile = logfile+'.err'
    else: 
      status = 1
    # Append to log/err file:
    if (status == 0):
      string_append_to_file(msg, logfile, append=True)
    if (msgtype == 'err'):
      string_append_to_file(msg, 'logfiles/'+dir+'.log', append=True)
    # End of write_to_log_err_file!


  def send_email(self, dir=None, recipient=None, message='', attachment=None, subject=None):
    """ This subroutine sends an automated email. Input arguments are
        the recipients email address, the email's subject and 
        the body of the email, as well as a possible attachment
        Input:
         recipient: String of the recipients email address
         subject: String of the email's subject
         message: String of the message to be sent in the email
         attachmet (optional): String of a file that should be 
           attached to the email.
    """
    # Initialization:
    if (dir is None):
      dir = self.dir
    if (recipient is None):
      recipient = self.emailaddress
    sendemail = self.sendemail
    status = 0; attach_file = False
    
    # Start processing arguments
    if (sendemail):
      if (not (attachment is None)):
        # Check if file actually exists:
        (files, status) = find_file_names('.', attachment)
        if (status == 0): # Attachment has been found/exists:
          attach_file = True
        else:
          attach_error_message = 'This email was flagged to attach the following file:\n     '+attachment+'.\nThis file does not exist/could not be found and therefore could not be attached to this email.\n'

      # Get absolute current path:
      pwd = commands.getoutput('cd '+dir+'; pwd')

      # Make header for email body:
      hashes = ''
    #  for i in str('# Automated report regarding: #\n'):
      for i in range(max(len('# Automated report regarding: #'), len('# '+pwd+'/ #'))):
        hashes = hashes+'#'
      # Now prepare report and dirlines (filling with blanks):
      blanks = ''
      if (len('# Automated report regarding: #') == len(hashes)):
        reportline = '# Automated report regarding: #'
        # Fill dirline with blanks:
        dirline = '# '+pwd+'/'
        for i in range(len(hashes) - len(dirline)-1):
          blanks = blanks+' '
        dirline = dirline+blanks+'#'
      else:
        dirline = '# '+pwd+'/ #'
        # Fill reportline with blanks:
        reportline = '# Automated report regarding: '
        for i in range(len(hashes) - len(reportline)-1):
          blanks = blanks+' '
        reportline = reportline+blanks+'#'
      emailbody = hashes+'\n'
      emailbody = emailbody+reportline+'\n'
      emailbody = emailbody+dirline+'\n'  
      emailbody = emailbody+hashes+'\n\n'

      # Prepare subject, if it was not passed to this subroutine:
      if (subject is None):
        subject = 'Monitoring Report: '
        if (message.find('Error') >= 0):
          subject = subject+'Error encountered'
        elif (message.find('flagged as fixed') >= 0):
          subject = subject+'Simulation manually fixed'
        elif (message.find('submitted to the queue') >= 0):
          subject = subject+'Successful submission to queue'
        elif (message.find('reached its final time: FINISHED') >= 0):
          subject = subject+'Simulation finished'
        elif (message.find('All simulations have been finished') >= 0):
          subject = subject+'All simulations finished'
        elif (message.find('Analysis finished') >= 0):
          subject = subject+'Analysis finished'
        else:
          subject = subject+'Regarding '+pwd
      else:
        # Useful for email filtering:
        subject = 'Monitoring Report: '+subject

      # Prepare emailbody:
      if (message.startswith('Error')):
        emailbody = emailbody+'The following error was encountered:\n'
      elif (message.find('reached its final time: FINISHED') >= 0):
        emailbody = emailbody+'The following simulation has reached its finish time:\n'
      elif (message.find('Analysis finished') >= 0):
        emailbody = emailbody+'The postprocessing script of the entire convergence analysis has been finished:\n'
        emailbody = emailbody+'     '+pwd+'/\n'

      # Append emailbody by given message:
      emailbody = emailbody+message+'\n'
      # Append error due to false file attachment:
      if (not (attachment is None) and not attach_file):
        emailbody = emailbody+attach_error_message

      # Write the text of the email body to a file which is required for mutt:
      cmd = 'echo "'+emailbody+'" > '+pwd+'/autoemailbody'
      out = commands.getoutput(cmd)

      # Prepare string for the mutt command, send one email per given email address:
      cmd = 'mutt -s "'+subject+'" '
      for email in recipient:
        cmd = cmd + email + ' '
      cmd = cmd + '< '+pwd+'/autoemailbody'
      if (attach_file):
        cmd = cmd+' -a '+attachment
      # Everything is done, now send it:
      out = commands.getoutput(cmd)

      # Now remove the file that we created:
      out = commands.getoutput('rm '+pwd+'/autoemailbody')
      # Now delete the sent file, this prevends it from becoming to big and compiz wasting cpu usage
      out = commands.getoutput('rm ~/sent')




  def notify_popup(self, subject, message):
    """ This subroutine uses the program 'notify-send' in order
        to show a popup showing some event.
        Input:
         subject: String of the subject of the popup
         message: String of message showing in the popup
    """
    # Example:
    # notify-send "some title" "some text" -i image.png
    urgency = 'low'
    if (subject == 'Error'):
      urgency = 'critical'
    elif (subject == 'Simulation fixed'):
      urgency = 'normal'
    elif (subject == 'Job submitted'):
      urgency = 'normal'
    elif (subject == 'Sim ran normally'):
      urgency = 'normal'
    elif (subject == 'Cleaned up'):
      urgency = 'low'
    elif (subject == 'Simulation finished'):
      urgency = 'critical'
    elif (subject == 'All simulations finished'):
      urgency = 'critical'
    elif (subject == 'Analysis finished'):
      urgency = 'low'
    # Finally, removing leading/trailing spaces and hashes from the strings,
    # as we only have limited space for the message:
    subject = subject.strip().strip('#').strip().strip('#').strip().strip('#')
    message = message.strip().strip('#').strip().strip('#').strip().strip('#')
    cmd = 'notify-send "'+subject+'" "'+message+'" --urgency='+urgency
    out = commands.getoutput(cmd)




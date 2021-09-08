# rbk_bulk_restore
Scripts to do a bulk restore based on a list

rbk_bulk_restore.py

This goal of this script is to take a list of files from a NAS backup, find them on the Rubrik, then restore those files to a specific location.
The files could live across multiple shares, filesets, and individual backups.  It will always restore the latest copy.

Note: The requirements came from a specific customer but it could be useful to others.  I'm open to issues/contributions to expand the use cases if there is interast.  Feel free to fork or file issues with ideas.

Syntax is as follows:
<pre>
Usage: rbk_bulk_restore.py -i file -p protocol [-hDtv] [-c creds] [-r location] rubrik
-h | --help : Prints usage.
-i | --input : Specify file that contains files to restore.
-r | --restore_to : Specify where to restore the files [server:share:folder]
-D | --debug : Prints debug information.  Troubleshooting use only
-t | --test : Test Mode.  Does everything but the actual restore
-p | --protocol : Specify a prtocol.  Only needed for test mode without -r
-c | --creds : Allows cluster name and password [user:password].
-v | --verbose : Prints the filenames in each backup
rubrik : Name/IP of Rubrik Cluster
-i and rubrik are required.  All others are optional
User will be prompted for any required information not provided in CLI</pre>

The script works with Python 2 or 3.  Most of the libraries are standard however the Rubrik Python SDK is required to run the script.  This can be easily installed via pip:  pip install rubrik-cdm

The script first gathers fileset and backup information from the Rubrik.  Then it searches all of those filesets and backups to find the files listed in the input file.  While this scan is going on, the script will output a . for every 100 files and a * every 1000 files to show progress.
After that, the script will bunch up the files based on fileset, backup, and path.  Those groups of files will then be sent in serial to the Rurbik clsuter to restore those files.  The restores will create the directory structure in the restore location.

There is a "test mode" which will do everything execpt do the actual restore.  When this is used, specifying a restore location is optional since a real restore won't happen.  If no restore location is specified for a test run, the protocol (NFS or SMB/CIFS) must be specified.  Anytime a restore location is specified, the protocol is discovered based on the name of the share (a share name that starts with / is presumed to be NFS, otherwise it's SMB).

There is a verbose mode that will show the naems of the files associated with each restore session.  Otherwise, the script will just say how many files it is backing up from each fileset.


----

splunk_rbk_bulk_restore.py

This script was bulit for a specific customer so may not be as useful out of the box as others.  It reads a specific file format specified by the customer to find a specific directory and restore it.  Therefore, it is not recommended to run this in a generic environment, but feel free to use the code for other projects.  That's what open source is all about.

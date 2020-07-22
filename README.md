# rbk_bulk_restore
A script to do a bulk restore based on a list

This goal of this script is to take a list of files from a NAS backup, find them on the Rubrik, then restore those files to a specific location.
The files could live across multiple shares, filesets, and individual backups.  It will always restore the latest copy.

Note: The requirements came from a specific customer but it could be useful to others.  I'm open to issues/contributions to expand the use cases if there is interast.  Feel free to fork or file issues with ideas.

Syntax is as follows:
<pre>
Usage: rbk_bulk_restore.py -i file -p protocol [-hDt] [-c creds] [-r location] rubrik
-h | --help : Prints usage.
-i | --input : Specify file that contains files to restore.
-p | --protocol : Specify protocol: nfs smb|cifs
-r | --restore_to : Specify where to restore the files [server:share:folder]
-D | --debug : Prints debug information.  Troubleshooting use only
-t | --test : Test Mode.  Does everything but the actual restore
-c | --creds : Allows cluster name and password [user:password].
rubrik : Name/IP of Rubrik Cluster
-i, -p and rubrik are required.  All others are optional
User will be prompted for any required information not provided in CLI
</pre>

The script works with Python 2 or 3.  Most of the libraries are standard however the Rubrik Python SDK is required to run the script.  This can be easily installed via pip:  pip install rubrik-cdm

#!/usr/bin/python

from __future__ import print_function
import sys
import rubrik_cdm
import getopt
import getpass
import urllib3
import datetime
import time
urllib3.disable_warnings()

def usage():
    sys.stderr.write("Usage: rbk_bulk_restore.py -i file -p protocol [-hDt] [-c creds] [-r location] rubrik\n")
    sys.stderr.write("-h | --help : Prints usage.\n")
    sys.stderr.write("-i | --input : Specify file that contains files to restore.\n")
    sys.stderr.write("-p | --protocol : Specify protocol: nfs smb|cifs\n")
    sys.stderr.write("-r | --restore_to : Specify where to restore the files [server:share:folder]\n")
    sys.stderr.write("-D | --debug : Prints debug information.  Troubleshooting use only\n")
    sys.stderr.write("-t | --test : Test Mode.  Does everything but the actual restore\n")
    sys.stderr.write("-c | --creds : Allows cluster name and password [user:password].\n")
    sys.stderr.write("rubrik : Name/IP of Rubrik Cluster\n")
    sys.stderr.write("-i, -p and rubrik are required.  All others are optional\n")
    sys.stderr.write("User will be prompted for any required information not provided in CLI\n")
    exit(0)

def dprint(message):
    if DEBUG:
        print(message)

def python_input(message):
    if int(sys.version[0]) > 2:
        val = input (message)
    else:
        val = raw_input(message)
    return (val)

def valid_restore_location(host, share, rubrik):
    hs_data = rubrik.get('internal', '/host/share')
    for sh in hs_data['data']:
        if sh['hostname'] == host and sh['exportPoint'] == share:
            return(sh['hostId'], sh['id'])
    return("", "")

def find_file(file, fs_list, snap_list, rubrik):
    fileset = ""
    snapshot = ""
    dprint("Processing " + file)
    inst = 0
    for fs in fs_list.keys():
        dprint ("Checking " + fs_list[fs]['hostName'] + ":" + str(fs_list[fs]['name']))
        search = rubrik.get('v1', '/fileset/' + str(fs) + '/search?path=' + file)
        dprint(search)
        if search['total'] == 1:
            if search['data'][0]['path'] != file:
                return("","")
            dprint("Found " + file + " in " + fs_list[fs]['name'])
            inst += 1
            fileset = fs
            latest_snap_time = datetime.datetime(1970,1,1,1,0,0)
            snapshot = ""
            for snap in search['data']:
                backups = snap['fileVersions']
                for b in backups:
                    if snap_list[b['snapshotId']] > latest_snap_time:
                        snapshot = b['snapshotId']
                        latest_snap_time = snap_list[b['snapshotId']]
        elif search['total'] > 1:
            sys.stderr.write("Warning: Found multiple instances of " + file + " in " +fs_list[fs]['hostname'] + ":" + str(fs_list[fs]['name']) + '\n')
            return ("", "")
    if inst == 0:
        sys.stderr.write("Can't find " + file + "\n")
        return ("","")
    if inst > 1:
        sys.stderr.write("Warning: multiple instances of " + file + " across backups\n")
        return ("","")
    return (fileset, snapshot)

if __name__ == "__main__":
    DEBUG = False
    TEST = False
    rubrik_node = ""
    user = ""
    password = ""
    fs_list = {}
    snap_list = {}
    restore_job = {}
    failed_files = []
    restore_location = ""
    restore_host = ""
    restore_share = ""
    restore_path = ""
    infile = ""
    protocol = ""
    delim = ""

    optlist, args = getopt.getopt(sys.argv[1:], 'hDc:i:r:p:t', ['help', 'debug', 'creds=', 'input=', 'restore_to=', 'protocol=', 'test'])
    for opt, a in optlist:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-D', '--debug'):
            DEBUG = True
        if opt in ('-c', '--creds'):
            user, password = a.split(':')
        if opt in ('-i', '--input'):
            infile = a
        if opt in ('-r', '--restore_to'):
            restore_location = a
        if opt in ('-p', '--protocol'):
            protocol = a.upper()
            if protocol == "CIFS":
                protocol = "SMB"
        if opt in ('-t', '--test'):
            TEST = True
    if infile == "":
        usage()
    try:
        rubrik_node = args[0]
    except:
        usage()
    if not user:
        user = python_input("User: ")
    if not password:
        password = getpass.getpass("Password:")
    if not protocol:
        protocol = python_input("Protocol: ").upper()
    if protocol == "NFS":
        delim = "/"
    elif protocol == "SMB":
        delim = "\\"
    else:
        sys.stderr.write("Protocol must be nfs, smb, or cifs\n")
        exit (5)
    if not restore_location:
        restore_location = python_input("Restore Location [host:share:path]: ")
    rubrik = rubrik_cdm.Connect(rubrik_node, user, password)
    try:
        (restore_host, restore_share, restore_path) = restore_location.split(':')
    except:
        sys.stderr.write("Restore Location Malfomed. Format is host:share:path\n")
        exit(3)
    if not restore_host or not restore_share or not restore_path:
        sys.stderr.write("Restore Location Malfomed. Format is host:share:path\n")
        exit(3)
    if not restore_path.startswith(delim):
        restore_path = delim + restore_path
    restore_host_id, restore_share_id = valid_restore_location(restore_host, restore_share, rubrik)
    if not restore_share_id:
        sys.stderr.write("Can't find restore location: " + restore_host + " : " + restore_share + "\n")
        exit(4)
    done = False
    if TEST:
        print("TESTING...no Restores will be done.")
    offset = 0
    print("Gathering info from cluster...")
    while not done:
        fs_data = rubrik.get('v1', '/fileset?offset=' + str(offset))
        for fs in fs_data['data']:
            offset += 1
            fs_info = {}
            if fs['shareId'] == "":
                continue
            p_check = rubrik.get('internal', '/host/share/' + str(fs['shareId']))
            if p_check['shareType'] != protocol:
                continue
            fs_info = {'shareId': fs['shareId'], 'hostId': fs['hostId'], 'hostName': fs['hostName'], 'name': fs['name']}
            fs_list[fs['id']] = fs_info
            fs_snaps = rubrik.get('v1', '/fileset/' + str(fs['id']))
            for snap in fs_snaps['snapshots']:
                snap_list[str(snap['id'])] = datetime.datetime.strptime(snap['date'][:-5], '%Y-%m-%dT%H:%M:%S')
        if not fs_data['hasMore']:
            done = True
    dprint(fs_list)
    dprint(snap_list)
    file_count = 0
    with open(infile) as fp:
        file = fp.readline()
        print("Searching for files in backups.....")
        while file:
            if file.startswith("#") or file == "":
                file = fp.readline()
                continue
            file = file.replace('"', '')
            file = file.rstrip("\n")
            if not file.startswith(delim):
                file = delim + file
            (file_fs, file_snap) = find_file(file, fs_list, snap_list, rubrik)
            dprint("File:" + file)
            dprint ("FS: " + file_fs)
            dprint ("SNAP: " + file_snap)
            if file_fs:
                file_count += 1
                try:
                    restore_job[file_fs].append({'file': file, 'snapshot': file_snap})
                except KeyError:
                    restore_job[file_fs] = []
                    restore_job[file_fs].append({'file': file, 'snapshot': file_snap})
            else:
                failed_files.append(file)
            if file_count % 100 == 0:
                sys.stdout.write(". ")
                sys.stdout.flush()
            file = fp.readline()
    fp.close()
    print()
    print ("Found " + str(file_count) + " files")
    if len(failed_files):
        print("Failed to find:")
        for f in failed_files:
            print (f)
    dprint("JOBS: " + str(restore_job))
    dprint("FAILS: " + str(failed_files))
    dprint("FS_RESTORE: " + str(restore_job))

    for fs_res in restore_job.keys():
        print("Restoring " + str(len(restore_job[fs_res])) + " files from " + fs_list[fs_res]['hostName'] + ":" + fs_list[fs_res]['name'])
        restore_files = {}
        for f in restore_job[fs_res]:
            try:
                restore_files[f['snapshot']].append({'srcPath': f['file'], 'dstPath': restore_path})
            except KeyError:
                restore_files[f['snapshot']] = []
                restore_files[f['snapshot']].append({'srcPath': f['file'], 'dstPath': restore_path})
        restore_count = 0
        for job in restore_files.keys():
            restore_count += 1
            print("    Starting Restore " + str(restore_count) + "/" + str(len(restore_files)))
            restore_config = {'exportPathPairs': restore_files[job], 'hostId': restore_host_id, 'shareId': restore_share_id}
            dprint("RES_CONFIG: " + str(restore_config))
            if not TEST:
                restore = rubrik.post('internal', '/fileset/snapshot/' + str(job) + "/export_files", restore_config)
                job_status_url = str(restore['links'][0]['href']).split('/')
                job_status_path = "/" + "/".join(job_status_url[5:])
                done = False
                while not done:
                    restore_job_status = rubrik.get('v1', job_status_path)
                    job_status = restore_job_status['status']
                    dprint ("Status = " + job_status)
                    if job_status in ['RUNNING', 'QUEUED', 'ACQUIRING', 'FINISHING']:
                        print("    Progress: " + str(restore_job_status['progress']) + "%")
                        time.sleep(5)
                        continue
                    elif job_status == "SUCCEEDED":
                        print ("Done")
                    elif job_status == "TO_CANCEL" or 'endTime' in job_status:
                        sys.stderr.write("Job ended with status: " + job_status + "\n")
                    else:
                        print ("Status: " + job_status)
                    done = True


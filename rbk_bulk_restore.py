#!/usr/bin/python

from __future__ import print_function
import sys
import rubrik_cdm
import getopt
import getpass
import urllib3
import datetime
urllib3.disable_warnings()

def usage():
    print("Usage goes here!")
    exit(0)

def dprint(message):
    if DEBUG:
        print(message)

def vprint(message):
    if VERBOSE:
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
            return(sh['id'])
    return("")

def find_file(file, fs_list, snap_list, rubrik):
    fileset = ""
    snapshot = ""
    dprint("Processing " + file)
    inst = 0
    for fs in fs_list.keys():
        dprint ("Checking " + fs_list[fs]['hostName'] + ":" + str(fs_list[fs]['name']))
        inst = 0
        search = rubrik.get('v1', '/fileset/' + str(fs) + '/search?path=' + file)
        dprint(search)
        if search['total'] == 1:
            dprint("Found " + file + " in " + fs_list[fs]['name'])
            inst += 1
            fileset = fs
            latest_snap_time = datetime.datetime(1970,1,1,1,0,0)
            snapshot = ""
            for snap in search['data']:
                backups = snap['fileVersions']
                for b in backups:
                    if snap_list[b['snapshotId']] > latest_snap_time:
                        print("UPDATE")
                        snapshot = b['snapshotId']
                        latest_snap_time = snap_list[b['snapshotId']]
        elif search['total'] > 1:
            sys.stderr.write("Warning: Found multiple instances of " + file + " in " +fs_list[fs]['hostname'] + ":" + str(fs_list[fs]['name']) + '\n')
            return ("", "")
    if inst == 0:
        sys.stderr.write("Can't find " + file)
    if inst > 1:
        sys.stderr.write("Warning: multiple instances of " + file + " across backups\n")
        return ("","")
    return (fileset, snapshot)

if __name__ == "__main__":
    DEBUG = False
    VERBOSE = False
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

    optlist, args = getopt.getopt(sys.argv[1:], 'hDc:i:r:v', ['help', 'debug', 'creds=', 'input=', 'restore_to=', '-versose'])
    for opt, a in optlist:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-D', '--debug'):
            DEBUG = True
            VERBOSE = True
        if opt in ('-v' , '--verbose'):
            VERBOSE = True
        if opt in ('-c', '--creds'):
            user, password = a.split(':')
        if opt in ('-i', '--input'):
            infile = a
        if opt in ('-r', '--restore_to'):
            restore_location = a
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
    restore_share_id = valid_restore_location(restore_host, restore_share, rubrik)
    if not restore_share_id:
        sys.stderr.write("Can't find restore location: " + restore_host + " : " + restore_share + "\n")
        exit(4)
    done = False
    offset = 0
    while not done:
        fs_data = rubrik.get('v1', '/fileset?offset=' + str(offset))
        for fs in fs_data['data']:
            offset += 1
            fs_info = {}
            if fs['shareId'] == "":
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
    with open(infile) as fp:
        file = fp.readline()
        while file:
            if file.startswith("#") or file == "":
                file = fp.readline()
                continue
            file = file.replace('"', '')
            file = file.rstrip("\n")
            if not file.startswith('/') and not file.startswith('\\'):
                file = "\\" + file
            (file_fs, file_snap) = find_file(file, fs_list, snap_list, rubrik)
            dprint("File:" + file)
            dprint ("FS: " + file_fs)
            dprint ("SNAP: " + file_snap)
            if file_fs:
                try:
                    restore_job[file_fs].append({'file': file, 'snapshot': file_snap})
                except KeyError:
                    restore_job[file_fs] = []
                    restore_job[file_fs].append({'file': file, 'snapshot': file_snap})
            else:
                failed_files.append(file)
            file = fp.readline()
    fp.close()
    dprint("JOBS: " + str(restore_job))
    dprint("FAILS: " + str(failed_files))

##TODO Restore
##TODO Report Only Flag
##TODO Usage and Cleanup

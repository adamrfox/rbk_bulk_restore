#!/usr/bin/python3

import sys
import rubrik_cdm
import getopt
import getpass
import urllib3
from datetime import datetime
import time
import pytz
urllib3.disable_warnings()

def usage():
    sys.stderr.write("Usage: splunk_rbk_bulk_restore.py [-Dh] [-c creds] [-t token] -i input_file rubrik\n")
    sys.stderr.write("-h | --help : Prints this message\n")
    sys.stderr.write("-D | --DEBUG : Debug mode.  Provides verbose output for debugging\n")
    sys.stderr.write("-c | --creds= : Specify the Rubrik credentials [user:password]\n")
    sys.stderr.write("-t | --token= : Specify a Rubrik API token\n")
    sys.stderr.write("-i | --infile= : Input file used for bulk restores [required]\n")
    sys.stderr.write("rubrik : Hostname or IP of a Rubrik cluster\n")
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

def get_from_file(file):
    job_data = []
    job = {}
    fp = open(file, "r")
    for line in fp:
        if not line[0].isdigit():
            continue
        line = line.rstrip()
        job_data = line.split(',')
        job = {'time': job_data[0], 'src_host': job_data[1], 'bucket': job_data[3], 'restore_host': job_data[6], 'restore_path': job_data[7]}
        job_list.append(job)
    return(job_list)

def find_snap_id(bucket_data, timestamp):
    for snap in bucket_data['data'][0]['fileVersions']:
        snap_data = rubrik.get('v1', '/fileset/snapshot/' + snap['snapshotId'] + '?verbose=false', timeout=timeout)
        snap_id = snap_data['id']
        dprint("SNAP_ID: + " + snap_id + " @ " + snap_data['date'])
#        snap_dt = datetime.strptime(snap_data['date'], "%Y-%m-%dT%H:%M:%S.000%z")
        snap_dt_naive = datetime.strptime(snap_data['date'][:-5], "%Y-%m-%dT%H:%M:%S")
        snap_epoch = (snap_dt_naive - epoch_naive).total_seconds()
        dprint("TARGET: " + str(timestamp) + " // SNAP: " + str(snap_epoch) + " : " + snap_id + " @ " + snap_data['date'])
        if snap_epoch >= timestamp:
            return(snap_id, snap_dt_naive)
    return ("")

if __name__ == "__main__":
    DEBUG = False
    rubrik_node = ""
    user = ""
    password = ""
    token = ""
    infile = ""
    job_list = []
    timeout = 360
    host_id_list = {}
    epoch = datetime.strptime("1970-01-01T00:00:00.000+0000", "%Y-%m-%dT%H:%M:%S.000%z")
    epoch_naive = datetime.strptime("1970-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")
    restore_job_list = []
    relic_host_list = []

    optlist, args = getopt.getopt(sys.argv[1:], 'Dhc:t:i:', ['--DEBUG', '--verbose', '--help', '--creds=', '--token=', '--infile='])
    for opt, a in optlist:
        if opt in ('-D', '--DEBUG'):
            DEBUG = True
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-c', '--creds'):
            (user, password) = a.split(':')
        if opt in ('-t', '--token'):
            token = a
        if opt in ('-i', '--infile'):
            infile = a

    if not infile:
        usage()
    job_list = get_from_file(infile)
    dprint (job_list)
    try:
        rubrik_node = args[0]
    except:
        usage()
    if not token:
        if not user:
            user = python_input("User: ")
        if not password:
            password = getpass.getpass("Password: ")
        rubrik = rubrik_cdm.Connect(rubrik_node, user, password)
    else:
        rubrik = rubrik_cdm.Connect(rubrik_node, api_token=token)
    rubrik_config = rubrik.get('v1', '/cluster/me', timeout=timeout)
    rubrik_tz = rubrik_config['timezone']['timezone']
    local_zone = pytz.timezone(rubrik_tz)
    for job in job_list:
        print("Processing bucket: " + job['src_host'] + " : " + job['bucket'])
        try:
            host_id_list[job['src_host']]
        except:
            host_data = rubrik.get('v1', '/fileset?host_name=' + job['src_host'], timeout=timeout)
#            host_data = rubrik.get('v1', '/host?name=' + job['src_host'], timeout=timeout)
            try:
                host_id_list[job['src_host']] = host_data['data'][0]['hostId']
                if host_data['data'][0]['isRelic'] == True:
                    relic_host_list.append(job['src_host'])
            except:
                sys.stderr.write("Can't find host: " + job['src_host'] + '\n')
                continue
        dprint("HOST: " + job['src_host'] + ' // ' + host_id_list[job['src_host']])
        target_dt = datetime.strptime(job['time'], "%Y-%m-%dT%H:%M:%S.000%z")
        target_epoch = (target_dt - epoch).total_seconds()
        bucket_data = rubrik.get('v1', '/host/' + host_id_list[job['src_host']] + '/search?path=' + job['bucket'], timeout=timeout)
        if bucket_data['total'] == 0:
            sys.stderr.write("Bucket not found: " + job['src_host'] + " : " + job['bucket'] + "\n")
            continue
        elif bucket_data['total'] > 1:
            sys.stderr.write("Ambiguous bucket path [" + str(bucket_data['total'] + "]: " + job['src_host'] + " : " + job['bucket']) + "\n")
            continue
        (snap_id, snap_dt) = find_snap_id(bucket_data, target_epoch)
        snap_dt = pytz.utc.localize(snap_dt).astimezone(local_zone)
        snap_dt_s = snap_dt.strftime('%Y-%m-%d %H:%M:%S')
        if snap_id == "":
            sys.stderr.write("Can't find a valid backup for " + job['bucket'] + "\n")
            continue
        res_job = {'snap_id': snap_id, 'bucket': job['bucket'], 'src_path': bucket_data['data'][0]['path'], 'dest_path': job['restore_path'],
                   'src_host': job['src_host'], 'restore_host': job['restore_host'], 'time': snap_dt_s}
        restore_job_list.append(res_job)
    dprint(restore_job_list)
    dprint("RELIC_HOST_LIST: " + str(relic_host_list))
    for restore in restore_job_list:
        print("Restoring " + restore['src_host'] + " : " + restore['bucket'] + " from " + restore['time'])
        if restore['restore_host'] in relic_host_list:
            sys.stderr.write("Can't restore to a relic host...skipping\n")
            continue
        if restore['src_host'] == restore['restore_host']:
            payload = {'restoreConfig': [{'path': restore['src_path'], 'restorePath': restore['dest_path']}], 'ignoreErrors': True}
            dprint("RESTORE_PAYLOAD: " + str(payload))
            res_data = rubrik.post('internal', '/fileset/snapshot/' + restore['snap_id'] + '/restore_files', payload, timeout=timeout)
        else:
            res_host_data = rubrik.get('v1', '/host?name=' + restore['restore_host'], timeout=timeout)
            dprint("RHD: " + str(res_host_data))
            try:
                payload = {'exportPathPairs': [{'srcPath': restore['src_path'], 'dstPath': restore['dest_path']}],
                           'ignoreErrors': True, 'hostId': res_host_data['data'][0]['id']}
            except:
                sys.stderr.write("Can't find restore host: " + restore['restore_host'] + "\n")
                continue
            dprint("EXPORT_PAYLOAD:" + str(payload))
            res_data = rubrik.post('internal', '/fileset/snapshot/' + restore['snap_id'] + '/export_files', payload, timeout=timeout)
        job_status_url = str(res_data['links'][0]['href']).split('/')
        job_status_path = "/" + "/".join(job_status_url[5:])
        done = False
        while not done:
            restore_job_status = rubrik.get('v1', job_status_path, timeout=timeout)
            job_status = restore_job_status['status']
            dprint("Status = " + job_status)
            if job_status in ['RUNNING', 'QUEUED', 'ACQUIRING', 'FINISHING']:
                print("    Progress: " + str(restore_job_status['progress']) + "%")
                time.sleep(10)
                continue
            elif job_status == "SUCCEEDED":
                print("Done")
            elif job_status == "TO_CANCEL" or 'endTime' in job_status:
                sys.stderr.write("Job ended with status: " + job_status + "\n")
            else:
                print("Status: " + job_status)
            done = True











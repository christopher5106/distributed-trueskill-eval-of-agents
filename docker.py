import argparse
import os
import subprocess
import tempfile


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
NAME = "distributed"

def call(cmd, return_out=False, error_ok=False, **kwargs):
    try:
        if return_out:
            return subprocess.check_output(
                cmd, cwd=SCRIPT_DIR, universal_newlines=True, **kwargs)
        else:
            subprocess.check_call(cmd, cwd=SCRIPT_DIR, **kwargs)
    except subprocess.CalledProcessError:
        if not error_ok:
            raise


def update_lines_matching(file_path, patterns, ensure_appears_once=True):
    if not os.path.exists(file_path + ".original"):
        os.rename(file_path, file_path + ".original")
    pattern_updates = [0 for _ in patterns]
    with open(file_path + ".original", "rt") as f_original:
        with open(file_path, "wt") as f_modified:
            for line in f_original:
                for i, (pattern, updated_line) in enumerate(patterns):
                    if pattern in line:
                        if not ensure_appears_once or pattern_updates[i] == 0:
                            f_modified.write(updated_line + "\n")
                        pattern_updates[i] += 1
                        break
                else:
                    f_modified.write(line)
            if ensure_appears_once:
                for i, (pattern, updated_line) in enumerate(patterns):
                    if pattern_updates[i] == 0:
                        f_modified.write(updated_line + "\n")


def setup_ssh():
    server_patterns = [
        ("PasswordAuthentication", "PasswordAuthentication yes"),
        ("PermitEmptyPasswords", "PermitEmptyPasswords yes"),
        ("PermitRootLogin", "PermitRootLogin yes")
    ]
    client_patterns = [
        ("StrictHostKeyChecking", "StrictHostKeyChecking no"),
    ]
    update_lines_matching("/etc/ssh/sshd_config", server_patterns)
    update_lines_matching("/etc/ssh/ssh_config", client_patterns)

    update_lines_matching("/etc/pam.d/common-auth", [
        ("nullok_secure", "auth    [success=1 default=ignore]  pam_unix.so nullok"),
    ])
    subprocess.check_output(['passwd', 'root', '-d'])
    subprocess.check_output(['update-rc.d', 'ssh', 'defaults'])


class Container(object):
    @staticmethod
    def build():
        call(["docker", "build", ".", "-t", NAME])

    def __init__(self, command, logfile):
        cmd = ["docker", "run", "-d", "--rm",
               NAME,
               "/bin/bash", "-c",
               "/etc/init.d/ssh start && {}".format(command)]
        self._cid = call(cmd, return_out=True).strip()
        self._logfile = open(logfile, "wt")
        cmd = ["docker", "logs", "-f", self._cid]
        self._logprocess = subprocess.Popen(cmd,
                                            stdout=self._logfile,
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)

    def ip(self):
        cmd = ["docker", "inspect",
               "--format", "{{ .NetworkSettings.IPAddress }}",
               self._cid]
        return call(cmd, return_out=True).strip()

    def cp_to_container(self, local_fro, container_to):
        cmd = ["docker", "cp", local_fro, "{}:{}".format(self._cid, container_to)]
        call(cmd, stdout=subprocess.DEVNULL)

    def wait(self):
        cmd = ["docker", "wait", self._cid]
        call(cmd, error_ok=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def __del__(self):
        self._logprocess.kill()
        self._logfile.close()
        cmd = ["docker", "kill", self._cid]
        call(cmd, error_ok=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num-machines', type=int, default=2,
                        help="number of machines to create")
    parser.add_argument('--command', type=str, default='ls -l && cat ips.txt && sleep 60m',
                        help="command to run on each machine")
    parser.add_argument('--logdir', type=str, default=SCRIPT_DIR + "/logs",
                        help="location of the folder where logs will be stored")
    return parser.parse_args()


WAIT_FOR_IPS = "while [ ! -f /root/ips.txt ]; do sleep 1s; done"


def main():
    args = parse_args()
    Container.build()
    os.makedirs(os.path.expanduser(args.logdir), exist_ok=True)

    dockers = []
    for idx in range(args.num_machines):
        logfile = os.path.join(os.path.expanduser(args.logdir), "machine_{}.txt".format(idx))
        command = "{} && {}".format(WAIT_FOR_IPS, args.command)
        dockers.append(Container(command, logfile))

    print("To ssh to the containers run: ")
    for idx, docker in enumerate(dockers):
        ip = docker.ip()
        print("Container {}:\n    ssh -o StrictHostKeyChecking=no root@{}".format(idx, ip))

    with open( SCRIPT_DIR + "/ips.txt" , "wt") as f:
        f.write("\n".join([docker.ip() for docker in dockers]) + "\n")
        f.flush()
        for docker in dockers:
            docker.cp_to_container(f.name, "/root/ips.txt")

    print("Waiting for commands to finish. "
          "Use Control-C to stop this server and shut down all machines.")

    for docker in dockers:
        docker.wait()


if __name__ == '__main__':
    main()

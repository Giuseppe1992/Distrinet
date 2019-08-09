import paramiko
from functools import partial
from subprocess import TimeoutExpired
import shlex
from functools import partial

from mininet.log import info, error, debug, warn

from time import sleep

import re
from re import findall


import random
def waitSessionReadable( session, timeoutms=None ):
    """Wait until session's output is readable.
       timeoutms: timeout in ms or None to wait indefinitely.
       returns: result False if not ready. Otherwise, returns True"""
    step = 1.0
    steps = 1 if timeoutms is None else int (timeoutms / step)
    while not session.recv_ready() and steps > 0:
        sleep(step / 1000.0)
        if timeoutms is not None:
            steps -= 1
    return session.recv_ready()

def waitSessionWritable( session, timeoutms=None ):
    """Wait until session's input is writable.
       timeoutms: timeout in ms or None to wait indefinitely.
       returns: result False if not ready. Otherwise, returns True"""
    step = 1.0
    steps = 1 if timeoutms is None else int (timeoutms / step)
    while not session.send_ready() and steps > 0:
        sleep(step / 1000.0)
        if timeoutms is not None:
            steps -= 1
    return session.send_ready()

class RemotePopen (object):
    def __init__(self, args, server, user, jump=None):
        # allow args either sting
        if isinstance(args, str):
            self.cmd = args
            self.args = shlex.split(args)
        # or array
        else:
            self.args = args
            self.cmd = " ".join(args)

        self.jump = jump
        self.server = server
        self.user = user

        self.pid = -1
        self.returncode = None

        self.outs = bytes()
        self.errs = bytes()

        # establish connection with the server
        self._connect()

        # execute the command
        self._pexec()

    def _connect(self):
        try:
            self.ssh = sshConnect(server=self.server, user=self.user, jump=self.jump)
        except EOFError as error:
###            print ("Error", error)
###            print ("Try aggain")
            self._connect()


    def _pexec(self):
        # Execute the command
        self.session = sshSendCommand(self.ssh, self.cmd)

        self.stdout = self.session.makefile()
        self.stderr = self.session.makefile_stderr()
        self.stdin = None       ## DSA - CHANGE

    def poll(self):
        """
        Check if child process has terminated. Set and return returncode
        attribute. Otherwise, returns None.
        """
        if self.session.exit_status_ready():
            self.returncode = self.session.exit_status
            return self.returncode
        return None

    def wait(self, timeout=None):
        """
        Wait for child process to terminate. Set and return returncode
        attribute.

        If the process does not terminate after timeout seconds, raise a
        TimeoutExpired exception. It is safe to catch this exception and retry
        the wait.
        """
        remaining = timeout
        step = 0.01
        while self.poll() == None and (remaining == None or remaining > 0.0):
            sleep(step)
            if timeout is not None:
                remaining = remaining - step
       
        # check if the child process effectively terminated
        if self.poll() == None:
            cmd = " ".join(self.args)
            raise TimeoutExpired(cmd=cmd,timeout=timeout)

        return self.returncode

    # DSA - TODO - doesn't return in string... alway bytes
    # DSA - TODO - make sleep nicer
    def communicate(self, input=None, timeout=None):
        """
        Interact with process: Send data to stdin. Read data from stdout and
        stderr, until end-of-file is reached. Wait for process to terminate.
        The optional input argument should be data to be sent to the child
        process, or None, if no data should be sent to the child. If streams
        were opened in text mode, input must be a string. Otherwise, it must be
        bytes.

        communicate() returns a tuple (stdout_data, stderr_data). The data will
        be strings if streams were opened in text mode; otherwise, bytes.
        """
        if input:
            waitSessionWritable(self.session, timeoutms=timeout*1000.0)
            self.session.send(input)

        self.wait(timeout=timeout)

        while self.session.recv_ready():
            self.outs += self.session.recv(1024)
        while self.session.recv_stderr_ready():
            self.errs += self.session.recv_stderr(1024)
        return self.outs, self.errs
        

    def send_signal(self, signal=3):
        """
        Sends the signal signal to the child.
        """
        sleep(0.1)
        waitSessionWritable(self.session)
        self.session.send(chr(signal))
        print ("signal sent indeed")

    def terminate(self):
        """
        Stop the child. The method sends SIGTERM to the child.
        """
        self.send_signal(3)
    
    def kill(self):
        """
        Kills the child. The method sends SIGKILL to the child.
        """
        self.close()

    def close(self):
        """
        Gracefully close the SSH session
        """
        self.session.close()
        self.ssh.close()
# #########


def makeSshJump(jump, destination, jumpport=22, destinationport=22, user="root"):
    """
    Create a SSH channel to reach destination in SSH by host jumping via jump
    machine.
    """
    jumpHost = paramiko.SSHClient()
    jumpHost.load_system_host_keys()
    jumpHost.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jumpHost.connect(hostname=jump, username=user)

    jumpHostTransport = jumpHost.get_transport()
    dest_addr = (destination, destinationport)
    local_addr = (jump, jumpport)
    jumpHostChannel = jumpHostTransport.open_channel("direct-tcpip", dest_addr, local_addr)

    return jumpHostChannel

def sshConnect(server, user, jump=None):
#    print ("server:", user, "@", server, " (jump:", jump,")")
    # make only one SSH client per server
    if server in sshConnect.clients:
        return sshConnect.clients[server]

    # Connect to the SSH jump
    if jump:
        sock = makeSshJump(jump=jump, user=user, destination=server)

    # Connect to the server
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())


    print ("jump:", jump, "server:", server)
    connect = partial(ssh.connect, server, username=user)
    #   via a jump if requested
    if jump:
        connect = partial(connect, sock = sock)
    connect()

    sshConnect.clients[server] = ssh
    return ssh
sshConnect.clients = {}     # lost of SSH clients already running

def sshSendCommand(ssh, cmd):
    transport = ssh.get_transport()
    if not transport.active:
        raise Exception("Not connected to SSH server")

    def _executeCommand(transport, cmd):
        session = transport.open_session()
        session.setblocking(0)
        session.get_pty()
        session.exec_command(cmd)
        return session

    import time
    session = None
    tried = 1
    while session is None:
        try:
            session = _executeCommand(transport, cmd)
        except paramiko.ssh_exception.ChannelException:
            tried = tried + 1 
            if tried > 60:
                raise Exception("Server overloaded, could not execute ", ssh, cmd)

            warn ("Server overloaded, trying again in 1s...\n", ssh, cmd)
            time.sleep(1)
       
    print ("command:", cmd)
    return session



def _findNameIP(name):
    """
    Resolves name to IP as seen by the eyeball
    """
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    # First, check for an IP address
    ipmatch = _ipMatchRegex.findall( name )
    if ipmatch:
        return ipmatch[ 0 ]
    # Otherwise, look up remote server
    popen = RemotePopen('getent ahostsv4 %s' % name, server=name2IP.eyeball, user=name2IP.user)

    output, err = popen.communicate()
    ips = _ipMatchRegex.findall( output.decode('utf-8') )

    ip = ips[ 0 ] if ips else None
    return ip

def name2IP(name):
    ip = name2IP.clusterIPs.get(name, None)
    if ip is None:
        ip = _findNameIP(name)
        name2IP.clusterIPs[name] = ip
    return ip
name2IP.clusterIPs = {}
name2IP.eyeball = None
name2IP.user = None


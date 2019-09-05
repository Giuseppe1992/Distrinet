import os
import pty
import re
import signal
import select
from subprocess import Popen, PIPE
from time import sleep

from mininet.log import info, error, warn, debug
from mininet.util import ( quietRun, errRun, errFail, moveIntf, isShellBuiltin,
                           numCores, retry, mountCgroups, BaseString, decode,
                           encode, Python3, which )
from mininet.moduledeps import moduleDeps, pathCheck, TUN
from mininet.link import Link, Intf, TCIntf, OVSIntf

def info(*args, **kwargs):
    pass

###
import asyncio
from threading import Thread
import time

from mininet.assh import ASsh

# XXX TODO DSA - make it clean
# #####################
intfnum=0
def genIntfName():
    global intfnum
    intfnum = intfnum + 1
    return "intf{}".format(intfnum)

from mininet.node import Node
from mininet.cloudlink import CloudLink

# #####################
class LxcNode (Node):
    """
    SSH node

    Attributes
    ----------
    name : str
        name of the node
    run : bool
        whether or not the node runs
    loop : asyncio.unix_events._UnixSelectorEventLoop
        the asyncio loop to work with
    admin_ip : str
        IP address to use to administrate the machine
    target : str 
        name of the LXC machine that runs the node
    port : int
        SSH port number
    username : str
        username used to connect to the host
    client_keys : list
        list of private key filenames to use to connect to the host
    bastion : str
        hostname of the bastion (i.e., SSH relay)
    bastion_port : int
        SSH port number of the bastion
    task : _asyncio.Task
        current task under execution
    waiting : bool
        waiting for a command to be executed
    readbuf : str
        command result buffer
    shell : asyncssh.process.SSHClientProcess
        Shell process
    stdin : asyncssh.stream.SSHWriter
        STDIN of the process
    stdout : asyncssh.stream.SSHReader
        STDOUT of the process
    stderr : asyncssh.stream.SSHReader
        STDERR of the process

    master : ASsh
        SSH connection to the master
    containerInterfaces : dict
        container interfaces
    """

    adminNetworkCreated = False
    connectedToAdminNetwork = {}

    def __init__(self, name, loop,
                       admin_ip,
                       master,
                       target=None, port=22, username=None, pub_id=None,
                       bastion=None, bastion_port=22, client_keys=None,
                       waitStart=True,
                       **params):
        """
        Parameters
        ----------
        name : str
            name of the node
        loop : asyncio.unix_events._UnixSelectorEventLoop
            the asyncio loop to work with.
        admin_ip : str
            IP address to use to administrate the node
        master : str
            hostname of the master node
        target : str
            name of the LXC machine that runs the node
        port : int
            SSH port number to use (default is 22).
        username : str
            username to use to connect to the host. If None, current username
            is used (default is None).
        bastion : str
            name of the bastion (i.e., SSH relay) to use to connect to
            `host`:`port` when this one cannot be accessed directly. If None,
            no bastion is used (default is None).
        bastion_port : int
            SSH port number to use to connect to the bastion (default is 22).
        client_keys : list
            list of private key filenames to use to connect to the host
        waitStart : bool
            should we block while waiting for the node to be started (default is True)
        """

        # name of the node
        self.name = params.get('name', name)

        # the node runs
        self.run = True

        # asyncio loop
        self.loop = loop

        # LXC host information
        self.target = target
        self.port = port
        self.username = username
        self.pub_id = pub_id
        self.client_keys = client_keys

        # ssh bastion information
        self.bastion = bastion
        self.bastion_port = bastion_port

        # current task in execution
        self.task = None

        # are we waiting for a task to be executed
        self.waiting = False

        self.readbuf = ''

        # Shell and its I/Os
        self.shell = None
        self.stdin = None
        self.stdout = None
        self.stderr = None

        # IP address to use to administrate the machine
        self.admin_ip = admin_ip

        self.masternode = master
        self.containerInterfaces = {}
        self.containerLinks = {}

        self.image = params.get("image", None)
        self.memory = params.get("memory", None)
        self.cpu = params.get("cpu", None)

        # network devices created on the target
        self.devices = []
        self.devicesMaster = []

        ## == mininet =========================================================
        # Make sure class actually works
        self.checkSetup()

        self.name = params.get( 'name', name )
        self.privateDirs = params.get( 'privateDirs', [] )
        # self.inNamespace = params.get( 'inNamespace', inNamespace )

        # Python 3 complains if we don't wait for shell exit
        self.waitExited = params.get( 'waitExited', Python3 )

        # Stash configuration parameters for future reference
        self.params = params

        self.intfs = {}  # dict of port numbers to interfaces
        self.ports = {}  # dict of interfaces to port numbers
                         # replace with Port objects, eventually ?
        self.nameToIntf = {}  # dict of interface names to Intfs

        # Make pylint happy
        ( self.shell, self.execed, self.pid, self.stdin, self.stdout,
            self.lastPid, self.lastCmd, self.pollOut ) = (
                None, None, None, None, None, None, None, None )
        self.waiting = False
        self.readbuf = ''


        self.inNamespace = False
#####        # Start command interpreter shell
#####        self.master, self.slave = None, None  # pylint

        # SSH with the target
        if self.target:
            self.targetSsh = ASsh(loop=self.loop, host=self.target, username=self.username, bastion=self.bastion, client_keys=self.client_keys)
        # when no target, use the master node as anchor point
        else:
            assert (False)
            self.targetSsh = ASsh(loop=self.loop, host=self.masternode.host, username=self.username, bastion=self.bastion, client_keys=self.client_keys)
        # SSH with the node
        admin_ip = self.admin_ip
        if "/" in admin_ip:
                admin_ip, prefix = admin_ip.split("/")
        self.ssh = ASsh(loop=self.loop, host=admin_ip, username=self.username, bastion=self.bastion, client_keys=self.client_keys)

        if waitStart:
            
            info ("{} Connecting to the target {}".format(self, self.target))
            self.connectTarget()
            self.waitConnectedTarget()
            info (" connected ")

            self.createContainer(**params)
            self.waitCreated()
            self.addContainerInterface(intfName="admin", brname="admin-br")
            self.connectToAdminNetwork(master=self.masternode.host, target=self.target, link_id=CloudLink.newLinkId(), admin_br="admin-br")

            self.configureContainer()
            self.connect()
            self.waitConnected()
            self.startShell(waitStart=waitStart)
            info (" started\n")
            
        ## ====================================================================
# ===================================<??????????????????

    def whereIsDeployed(self):
        """
        Returns
        -------
        str
            on which host in the LXC cluster the node is deployed
        """

        cmd = "lxc info %s | grep 'Location' | awk '{print $2}'" % (self.name)
        res = self.targetSsh.cmd(cmd)
        return res.rstrip()


    def configureContainer(self, adminbr="admin-br", wait=True):
#        # connect the node to the admin network
#        self.addContainerInterface(intfName="admin", brname=adminbr)

        # connect the target to the admin network
#        if not self.target in self.__class__.connectedToAdminNetwork:
#            print (self.target, "not connected yet to admin")
#            self.connectToAdminNetwork(master=self.masternode.host, target=self.target, link_id=CloudLink.newLinkId(), admin_br=adminbr)
#            self.__class__.connectedToAdminNetwork[self.target] = True
#        else:
#            print (self.target, "already connected to admin")

        # configure the node to be "SSH'able"
        cmds = []
        # configure the container to have
        #       an admin IP address
        cmds.append("lxc exec {} -- ifconfig admin {}".format(self.name, self.admin_ip))
        #       a public key
        cmds.append("lxc exec {} -- bash -c 'echo \"{}\" >> /root/.ssh/authorized_keys'".format(self.name, self.pub_id))
        #       a ssh server
        cmds.append("lxc exec {} -- service ssh start".format(self.name))

        cmd = ';'.join(cmds)
        if wait:
            self.targetSsh.cmd(cmd)
        else:
            self.targetSsh.sendCmd(cmd)

    @classmethod
    def createMasterAdminNetwork(cls, master, brname="admin-br", ip="192.168.42.1/24", **params):
        cmds = []
        cmds.append("brctl addbr {}".format(brname))
        cmds.append("ifconfig {} {}".format(brname, ip))
        cmd = ";".join(cmds)
        master.cmd(cmd)

    import re

    def _findNameIP(self, name):
        """
        Resolves name to IP as seen by the eyeball
        """
        _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

        # First, check for an IP address
        ipmatch = _ipMatchRegex.findall( name )
        if ipmatch:
            return ipmatch[ 0 ]
        # Otherwise, look up remote server
        output = self.masternode.cmd('getent ahostsv4 {}'.format(name))

        ips = _ipMatchRegex.findall( output )

        ip = ips[ 0 ] if ips else None
        return ip

    def addContainerLink(self, target1, target2, link_id, bridge1, bridge2, iface1=None,
                         vxlan_dst_port=4789, **params):
        """Add the link between 2 containers"""
        vxlan_name = "vx_{}".format(link_id)
        cmds = self.createContainerLinkCommandList(target1, target2, link_id, vxlan_name, bridge1, bridge2,
                                                           iface1=iface1, vxlan_dst_port=vxlan_dst_port, **params)

        cmd = ';'.join(cmds)
        self.targetSsh.cmd(cmd)
        link = params["link"]
        self.containerLinks[link] = vxlan_name

        self.devices.append(vxlan_name)

    def deleteContainerLink(self, link, **kwargs):
        self.targetSsh.cmd("ip link delete {}".format(self.containerLinks[link]))

    def createContainerLinkCommandList(self, target1, target2, vxlan_id, vxlan_name, bridge1, bridge2, iface1=None,
                                       vxlan_dst_port=4789, **params):
        cmds = []
        if target1 != target2:
            ip1 = self._findNameIP(target1)
            ip2 = self._findNameIP(target2)
            if ip1 == ip2:
                return cmds
            comm = "ip link add {} type vxlan id {} remote {} local {} dstport {}".format(vxlan_name, vxlan_id, ip2,
                                                                                          ip1, vxlan_dst_port)
            if iface1:
                comm += " dev {}".format(iface1)

            cmds.append(comm)
            cmds.append("ip link set up {}".format(vxlan_name))
            cmds.append('brctl addif {} {}'.format(bridge1, vxlan_name))
            cmds.append('ip link set up {}'.format(bridge1))


            self.devices.append(vxlan_name)
            self.devices.append(bridge1)

        else:
            if bridge1 != bridge2:
                'the containers are in different bridge, we need to create 2 virtual interface to attach the two bridges'
                v_if1 = "v{}".format(bridge1)
                v_if2 = "v{}".format(bridge2)
                cmds.append('ip link add {} type veth peer name {}'.format(v_if1, v_if2))
                cmds.append('brctl addif {} {}'.format(bridge1, v_if1))
                cmds.append('brctl addif {} {}'.format(bridge2, v_if2))
                cmds.append('ip link set up {}'.format(v_if1))
                cmds.append('ip link set up {}'.format(v_if2))


                self.devices.append(v_if1)
                self.devices.append(v_if2)
                self.devices.append(bridge1)
                self.devices.append(bridge2)
        return cmds 

    def connectToAdminNetwork(self, master, target, link_id, admin_br, wait=True, **params):
        cmds = []
        if not self.target in self.__class__.connectedToAdminNetwork:
            self.__class__.connectedToAdminNetwork[self.target] = True

            # no need to connect admin on the same machine or if it is already connected
            vxlan_name = "vx_{}".format(link_id)

            # locally
            # DSA - TODO - XXX beurk bridge2 = None
            cmds = self.createContainerLinkCommandList(target, master, link_id, vxlan_name, bridge1=admin_br, bridge2=None)
            cmd = ';'.join(cmds)

            if wait:
                self.targetSsh.cmd(cmd)
            else:
                self.targetSsh.sendCmd(cmd)

            # on master
            # DSA - TODO - XXX beurk bridge2 = None
            cmds = self.createContainerLinkCommandList(master, target, link_id, vxlan_name, bridge1=admin_br, bridge2=None)
            cmd = ';'.join(cmds)
            self.devicesMaster.append(vxlan_name)

            self.devices.append(vxlan_name)
#            print ("master".format(vxlan_name),cmd)
#            if wait:
#                self.masternode.cmd(cmd)
#                cmds = []
        return cmds


    def connectTarget(self):
        self.targetSsh.connect()
    def waitConnectedTarget(self):
        self.targetSsh.waitConnected()

    def createContainer(self, **params): 
################################################################################        time.sleep(1.0)
        info ("create container ({} {} {}) ".format(self.image, self.cpu, self.memory))
        cmds = []
        # initialise the container
        cmd = "lxc init {} {} ".format(self.image, self.name)
        info ("{}\n".format(cmd))
        cmds.append(cmd)

        # limit resources
        if self.cpu:
            cmds.append("lxc config set {} limits.cpu {}".format(self.name, self.cpu))
        if self.memory:
            cmds.append("lxc config set {} limits.memory {}".format(self.name, self.memory))

        # start the container
        cmds.append("lxc start {}".format(self.name))

        cmd = ";".join(cmds)
        self.targetSsh.sendCmd(cmd)

    def targetSshWaitOutput(self):
        """
        Wait for output on targetSsh
        """
        if self.targetSsh is not None:
            self.targetSsh.waitOutput()

    def waitCreated(self):
        self.targetSshWaitOutput()
        info ("container created")


    def addContainerInterface(self, intfName, devicename=None, brname=None, wait=True, **params):
        """
        Add the interface with name intfName to the container that is
        associated to the bridge named name-intfName-br on the host
        """
        if devicename is None:
            devicename = genIntfName()
        if brname is None:
            brname = genIntfName()
        cmds = []
        cmds.append("brctl addbr {}".format(brname))
        cmds.append("lxc network attach {} {} {} {}".format(brname, self.name, devicename, intfName))
        cmds.append("ip link set up {}".format(brname))

        cmd = ";".join(cmds)

        if wait:
            self.targetSsh.cmd(cmd)
        else:
            self.targetSsh.sendCmd(cmd)

        self.containerInterfaces[intfName] = brname

        return brname


    def deleteContainerInterface(self, intf, **kwargs):
        if intf.name in self.containerInterfaces:
            self.targetSsh.cmd("ip link delete {}".format(self.containerInterfaces[intf.name]))

# ======================================??????????????????????????>
    def createTunnel(self):
        """
        Creates a tunnel with the bastion if needed (i.e., a bastion is
        specified).
        """
        self.ssh.createTunnel()

    def connect(self):
        """
        Establishes an SSH connection to the host
        """

        self.ssh.connect()

    def waitTunneled(self):
        """
        Waits that the tunnel is established (if needed) and updates `_host`
        and `_port` attributes to use it instead of having a direct connection
        to the host
        """
        self.ssh.waitTunneled()

    ## == mininet =============================================================

    # XXX - OK
    # Command support via shell process in namespace
    def startShell( self, mnopts=None, waitStart=True):
        """
        Starts a shell on the node

        Parameters
        ----------
        waitStart : bool
            block until the shell is actually started (default is True).
        
        NOTE
        ----
        If waitStart is False, make sure to wait for the shell to start before
        using it (e.g., by calling the `node.waitStarted()`) and to run
        `node.finalizeStartShell()` once started and before using the shell.
        """
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
##        # mnexec: (c)lose descriptors, (d)etach from tty,
##        # (p)rint pid, and run in (n)amespace
##        opts = '-cd' if mnopts is None else mnopts
##        if self.inNamespace:
##            opts += 'n'
##        # bash -i: force interactive
##        # -s: pass $* to shell, and make process easy to find in ps
##        # prompt is set to sentinel chr( 127 )
##        cmd = [ 'mnexec', opts, 'env', 'PS1=' + chr( 127 ),
##                'bash', '--norc', '--noediting',
##                '-is', 'mininet:' + self.name ]
##

##        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
##        # in the subprocess and insulate it from signals (e.g. SIGINT)
##        # received by the parent
##        self.master, self.slave = pty.openpty()
##        self.shell = self._popen( cmd, stdin=self.slave, stdout=self.slave,
##                                  stderr=self.slave, close_fds=False )
##        # XXX BL: This doesn't seem right, and we should also probably
##        # close our files when we exit...
##        self.stdin = os.fdopen( self.master, 'r' )
##        self.stdout = self.stdin
##        self.pid = self.shell.pid
##        self.pollOut = select.poll()
##        self.pollOut.register( self.stdout )
##        # Maintain mapping between file descriptors and nodes
##        # This is useful for monitoring multiple nodes
##        # using select.poll()
##        self.outToNode[ self.stdout.fileno() ] = self
##        self.inToNode[ self.stdin.fileno() ] = self

        assert self.ssh.connected()

        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''

        # == start the shell
        task = self.loop.create_task(self._startShell())

        # Wait for prompt
        if waitStart:
            self.waitStarted()
            self.finalizeStartShell()

    def _popen( self, cmd, **params ):
        """Internal method: spawn and return a process
            cmd: command to run (list)
            params: parameters to Popen()
            
        Raises
        ------
        NotImplementedError
            the method makes no sense in this context
            """
        
        raise NotImplementedError("Doesn't make sense in a remote environment")

    # XXX - OK
    def cleanup( self ):
        "Help python collect its garbage."
        self.task = None
        self.waiting = False
        self.conn = None                                                                                                       
        self.run = False
        self.shell = None
        self.devices = None

    # Subshell I/O, commands and control

    # XXX - TODO - OK
    # XXX DSA - ATTENTION ignores maxbytes
    def read( self, maxbytes=1024, timeout=None ):
        """Buffered read from node, potentially blocking.
           maxbytes: maximum number of bytes to return"""
        task = self.loop.create_task(self._read(maxbytes=maxbytes, timeout=timeout))
        while not task.done():
            time.sleep(0.0001)
        return task.result()

    # XXX - OK
    def write( self, data ):
        """Write data to node.
           data: string"""
        self.stdin.write(data)

    # XXX - OK
    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        self.unmountPrivateDirs()

        cmds = []
        # destroy the container
        cmds.append("lxc delete {} --force".format(self.name))
#        self.targetSsh.cmd("lxc delete {} --force".format(self.name))

        # remove all locally made devices
        for device in self.devices:
            cmds.append("ip link delete {}".format(device))
#            self.targetSsh.cmd("ip link delete {}".format(device))

        cmd = ";".join(cmds)
        self.targetSsh.sendCmd(cmd)

        # close the SSH connection
        self.ssh.close()

#        # close the SSH tunnel
#        if self.tunnel:
#            self.tunnel.close()

        # cleanup variables
        self.cleanup()

     # XXX - OK
     # TODO DSA - should find a wait to do it correctly
    def waitReadable( self, timeoutms=None ):
        """
        Wait until node's output is readable.
        timeoutms: timeout in ms or None to wait indefinitely.
        
        Raises
        ------
        NotImplementedError
            not needed so not implemented
        """

        raise NotImplementedError("not implemented yet (not needed)")

    # XXX - OK
    def sendCmd(self, *args, **kwargs):
        """
        Runs command `cmd` on the node. The call is non blocking. The command
        can be controlled via the `task` attribute.

        Parameters 
        ----------
        cmd : str
            command to execute on the node.
        
        Raises
        ------
        NotImplementedError
            If printPid is requested
        """

        if 'printPid' in kwargs:
            raise NotImplementedError("printPid is not supported")

        assert not self.waiting

        printPid = kwargs.get( 'printPid', False )
        # Allow sendCmd( [ list ] )
        if len( args ) == 1 and isinstance( args[ 0 ], list ):
            cmd = args[ 0 ]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len( args ) > 0:
            cmd = args
        # Convert to string
        if not isinstance( cmd, str ):
            cmd = ' '.join( [ str( c ) for c in cmd ] )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        self.lastCmd = cmd
        cmd = cmd + "\necho -n '\x7f'\n"
       
        self.write(cmd)
        self.lastPid = None
        self.waiting = True

    # XXX - DSA - quick hack to deal with OpenSSH bug regarding signals...
    async def _sendInt(self):
        await self.ssh.conn.run("killall -g --signal INT bash")

    # XXX - TODO - OK
    def sendInt( self, intr=chr( 3 ) ):
        "Interrupt running command."
        debug( 'sendInt: writing chr(%d)\n' % ord( intr ) )
#        self.shell.send_signal(intr)
        task = self.loop.create_task(self._sendInt())
        while not task.done():
            time.sleep(0.0001)
        return task.result()

    ## TODO - XXX - OK
    ## Have to be able to deal with the PID
    def monitor( self, timeoutms=None, findPid=True ):
        """Monitor and return the output of a command.
           Set self.waiting to False if command has completed.
           timeoutms: timeout in ms or None to wait indefinitely
           findPid: look for PID from mnexec -p"""
#        ready = self.waitReadable( timeoutms )
#        if not ready:
#            return ''
        timeout = timeoutms/1000.0 if timeoutms is not None else None
        data = self.read( 1024, timeout=timeout )

        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    # XXX - OK
    def popen( self, *args, **kwargs ):
        """
        Raises
        ------
        NotImplementedError
            the method makes no sense in this context
        """
        raise NotImplementedError("Doesn't make sense in a remote environment")

    # XXX - OK
    def pexec(self, *args, **kwargs ):
        """Execute a command using popen
           returns: out, err, exitcode"""
        task = self.loop.create_task(self._pexec(*args, **kwargs))
        while not task.done():
            time.sleep(0.001)
        out,err, exitcode = task.result()
        return out.replace( chr( 127 ), '' ).rstrip(), err.replace( chr( 127 ), '' ), exitcode

    ####################################################################

    # XXX - OK
    # TODO DSA we should check on machines but it would slow down
    @classmethod
    def setup( cls ):
        "Make sure our class dependencies are available"
        pass

    ##############################

    # == New methods ==========================================================
    def finalizeStartShell(self):
        # XXX - TODO - DSA should be file numbers 
        self.outToNode[ self.stdout ] = self
        self.inToNode[ self.stdin ] = self 

        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

        self.mountPrivateDirs()

    def waitConnected(self):
        """
        Blocking until the node is actually started
        """

        self.ssh.waitConnected()

    def waitStarted(self):
        """
        Blocking until the node is actually started
        """

        while self.stdin is None:
            time.sleep(0.001)
   # =========================================================================

    # == Time for coroutines black magic ======================================
    # TODO DSA make it cleaner, but asyncssh read works with EOF only...
    async def _read(self, maxbytes=1024, timeout=None):
        r = ''
        while maxbytes > 0:
            try:
                c = await asyncio.wait_for(self.stdout.read(n=1), timeout=timeout)
                r = r + c
                if c == '\x7f':
                    return r
            except asyncio.TimeoutError:
                return r
            maxbytes -= 1
        return r
#        return await self.stdout.readuntil(separator='\x7f')

    # XXX - OK
    async def _pexec(self, *args, **kwargs):
        """Execute a command using popen
        returns: out, err, exitcode"""

        defaults = { 'stdout': PIPE, 'stderr': PIPE}
        defaults.update( kwargs )
        shell = defaults.pop( 'shell', False )
        if len( args ) == 1:
            if isinstance( args[ 0 ], list ):
                # popen([cmd, arg1, arg2...])
                cmd = args[ 0 ]
            elif isinstance( args[ 0 ], BaseString ):
                # popen("cmd arg1 arg2...")
                cmd = [ args[ 0 ] ] if shell else args[ 0 ].split()
            else:
                raise Exception( 'popen() requires a string or list' )
        elif len( args ) > 0:
            # popen( cmd, arg1, arg2... )
            cmd = list( args )
        if shell:
            cmd = [ os.environ[ 'SHELL' ], '-c' ] + ['"',' '.join( cmd ), '"']
        # Attach to our namespace  using mnexec -a
        cmd = ' '.join(cmd)

#        process = await self.conn.create_process(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        process = await self.ssh.createProcess(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        out, err = await process.communicate()
        exitcode = process.returncode
        
        return out, err, exitcode

    # XXX - OK
    async def _startShell(self):
        bash = "bash --rcfile <( echo 'PS1=\x7f') --noediting -is mininet:{}".format(self.name)

#        self.shell = await self.conn.create_process(bash, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.shell = await self.ssh.createProcess(bash, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        self.stdin = self.shell.stdin
        self.stdout = self.shell.stdout
        self.stderr = self.shell.stderr

        while True:
            await asyncio.sleep(1)
    # =========================================================================


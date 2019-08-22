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


###
import asyncio
from threading import Thread
import time

from assh import ASsh

# XXX TODO DSA - make it clean
# #####################
intfnum=0
def genIntfName():
    global intfnum
    intfnum = intfnum + 1
    return "intf{}".format(intfnum)

from mininet.node import Node
from cloudlink import CloudLink

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

        self.master = master
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
            print ("Il y a un taret", self.target)
            self.targetSsh = ASsh(loop=self.loop, host=self.target, username=self.username, bastion=self.bastion, client_keys=self.client_keys)
        # when no target, use the master node as anchor point
        else:
            assert (False)
            self.targetSsh = ASsh(loop=self.loop, host=self.master.host, username=self.username, bastion=self.bastion, client_keys=self.client_keys)
        # SSH with the node
        admin_ip = self.admin_ip
        if "/" in admin_ip:
                admin_ip, prefix = admin_ip.split("/")
        self.ssh = ASsh(loop=self.loop, host=admin_ip, username=self.username, bastion=self.bastion, client_keys=self.client_keys)

        if waitStart:
            print ("#[")
            
            print ("\tconnecting to the target")
            self.connectTarget()
            self.waitConnectedTarget()
            print ("\tconnected")

            self.createContainer(**params)
            print ("X")
            self.waitCreated()
            print ("YES")
            self.addContainerInterface(intfName="admin", brname="admin-br")
            self.connectToAdminNetwork(master=self.master.host, target=self.target, link_id=CloudLink.newLinkId(), admin_br="admin-br")

            self.configureContainer()
            self.connect()
            self.waitConnected()
            self.startShell(waitStart=waitStart)
            print (self, "started")
            print ("#]")
            
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
#            self.connectToAdminNetwork(master=self.master.host, target=self.target, link_id=CloudLink.newLinkId(), admin_br=adminbr)
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
        output = self.master.cmd('getent ahostsv4 {}'.format(name))

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
            print ("ips",ip1,ip2)
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
            print ("target {}:".format(target),cmd)

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
#                self.master.cmd(cmd)
#                cmds = []
        return cmds


    def connectTarget(self):
        self.targetSsh.connect()
    def waitConnectedTarget(self):
        self.targetSsh.waitConnected()

    def createContainer(self, **params): 
################################################################################        time.sleep(1.0)
        print ("\tcreate container ({} {} {})".format(self.image, self.cpu, self.memory))
        cmds = []
        # initialise the container
        cmd = "lxc init {} {} ".format(self.image, self.name)
        # specify a target
#XXX        if self.target is not None:
#XXX            cmd += " --target {}".format(self.target)
        print (">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", cmd)
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

    def waitCreated(self):
        self.targetSsh.waitOutput()
        print ("\tcontainer created")
#        self.configureContainer()
#        print ("master configured")
#        print ("]")


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
    # File descriptor to node mapping support
    # Class variables and methods

    inToNode = {}  # mapping of input fds to nodes
    outToNode = {}  # mapping of output fds to nodes
    ## ========================================================================

    # XXX - SAME
    @classmethod
    def fdToNode( cls, fd ):
        """Return node corresponding to given file descriptor.
           fd: file descriptor
           returns: node"""
        node = cls.outToNode.get( fd )
        return node or cls.inToNode.get( fd )


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

    # XXX - SAME
    def mountPrivateDirs( self ):
        "mount private directories"
        # Avoid expanding a string into a list of chars
        assert not isinstance( self.privateDirs, BaseString )
        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                # mount given private directory
                privateDir = directory[ 1 ] % self.__dict__
                mountPoint = directory[ 0 ]
                self.cmd( 'mkdir -p %s' % privateDir )
                self.cmd( 'mkdir -p %s' % mountPoint )
                self.cmd( 'mount --bind %s %s' %
                               ( privateDir, mountPoint ) )
            else:
                # mount temporary filesystem on directory
                self.cmd( 'mkdir -p %s' % directory )
                self.cmd( 'mount -n -t tmpfs tmpfs %s' % directory )

    # XXX - SAME
    def unmountPrivateDirs( self ):
        "mount private directories"
        for directory in self.privateDirs:
            if isinstance( directory, tuple ):
                self.cmd( 'umount ', directory[ 0 ] )
            else:
                self.cmd( 'umount ', directory )

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
    def read( self, maxbytes=1024 ):
        """Buffered read from node, potentially blocking.
           maxbytes: maximum number of bytes to return"""
        task = self.loop.create_task(self._read(maxbytes=maxbytes))
        while not task.done():
            time.sleep(0.0001)
        return task.result()

    ## XXX - SAME
    def readline( self ):
        """Buffered readline from node, potentially blocking.
           returns: line (minus newline) or None"""
        self.readbuf += self.read( 1024 )
        if '\n' not in self.readbuf:
            return None
        pos = self.readbuf.find( '\n' )
        line = self.readbuf[ 0: pos ]
        self.readbuf = self.readbuf[ pos + 1: ]
        return line

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


    # XXX - SAME
    def stop( self, deleteIntfs=False ):
        """Stop node.
           deleteIntfs: delete interfaces? (False)"""
        if deleteIntfs:
            self.deleteIntfs()
        self.terminate()

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

    # XXX - TODO - OK
    def sendInt( self, intr=chr( 3 ) ):
        "Interrupt running command."
###        debug( 'sendInt: writing chr(%d)\n' % ord( intr ) )
        self.shell.send_signal(intr)

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
        data = self.read( 1024 )

        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    ## XXX - SAME
    def waitOutput( self, verbose=False, findPid=True ):
        """Wait for a command to complete.
           Completion is signaled by a sentinel character, ASCII(127)
           appearing in the output stream.  Wait for the sentinel and return
           the output, including trailing newline.
           verbose: print output interactively"""
#        log = info if verbose else debug
        output = ''
        while self.waiting:
            data = self.monitor( findPid=findPid )
            output += data
#            log( data )
        return output

    ## XXX - SAME:
    def cmd( self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
#        log = info if verbose else debug
#        log( '*** %s : %s\n' % ( self.name, args ) )
        if self.shell:
            self.sendCmd( *args, **kwargs )
            return self.waitOutput( verbose )
        else:
            warn( '(%s exited - ignoring cmd%s)\n' % ( self, args ) )

    # XXX - SAME
    def cmdPrint( self, *args):
        """Call cmd and printing its output
           cmd: string"""
        return self.cmd( *args, **{ 'verbose': True } )

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

    # Interface management, configuration, and routing

    # BL notes: This might be a bit redundant or over-complicated.
    # However, it does allow a bit of specialization, including
    # changing the canonical interface names. It's also tricky since
    # the real interfaces are created as veth pairs, so we can't
    # make a single interface at a time.

    # XXX - SAME
    def newPort( self ):
        "Return the next port number to allocate."
        if len( self.ports ) > 0:
            return max( self.ports.values() ) + 1
        return self.portBase

    # XXX - SAME
    def addIntf( self, intf, port=None, moveIntfFn=moveIntf ):
        """Add an interface.
           intf: interface
           port: port number (optional, typically OpenFlow port number)
           moveIntfFn: function to move interface (optional)"""
        if port is None:
            port = self.newPort()
        self.intfs[ port ] = intf
        self.ports[ intf ] = port
        self.nameToIntf[ intf.name ] = intf
        debug( '\n' )
        debug( 'added intf %s (%d) to node %s\n' % (
                intf, port, self.name ) )
        if self.inNamespace:
            debug( 'moving', intf, 'into namespace for', self.name, '\n' )
            moveIntfFn( intf.name, self  )

    # XXX - SAME
    def delIntf( self, intf ):
        """Remove interface from Node's known interfaces
           Note: to fully delete interface, call intf.delete() instead"""
        port = self.ports.get( intf )
        if port is not None:
            del self.intfs[ port ]
            del self.ports[ intf ]
            del self.nameToIntf[ intf.name ]

    # XXX - SAME
    def defaultIntf( self ):
        "Return interface for lowest port"
        ports = self.intfs.keys()
        if ports:
            return self.intfs[ min( ports ) ]
        else:
            warn( '*** defaultIntf: warning:', self.name,
                  'has no interfaces\n' )

    # XXX - SAME
    def intf( self, intf=None ):
        """Return our interface object with given string name,
           default intf if name is falsy (None, empty string, etc).
           or the input intf arg.

        Having this fcn return its arg for Intf objects makes it
        easier to construct functions with flexible input args for
        interfaces (those that accept both string names and Intf objects).
        """
        if not intf:
            return self.defaultIntf()
        elif isinstance( intf, BaseString):
            return self.nameToIntf[ intf ]
        else:
            return intf

    # XXX - SAME
    def connectionsTo( self, node):
        "Return [ intf1, intf2... ] for all intfs that connect self to node."
        # We could optimize this if it is important
        connections = []
        for intf in self.intfList():
            link = intf.link
            if link:
                node1, node2 = link.intf1.node, link.intf2.node
                if node1 == self and node2 == node:
                    connections += [ ( intf, link.intf2 ) ]
                elif node1 == node and node2 == self:
                    connections += [ ( intf, link.intf1 ) ]
        return connections

    # XXX - SAME
    def deleteIntfs( self, checkName=True ):
        """Delete all of our interfaces.
           checkName: only delete interfaces that contain our name"""
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off removing them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow,
        # at least with Linux kernels before 2.6.33
        for intf in list( self.intfs.values() ):
            # Protect against deleting hardware interfaces
            if ( self.name in intf.name ) or ( not checkName ):
                intf.delete()
                info( '.' )

    # Routing support

    # XXX - SAME
    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as string
           mac: MAC address as string"""
        result = self.cmd( 'arp', '-s', ip, mac )
        return result

    # XXX - SAME
    def setHostRoute( self, ip, intf ):
        """Add route to host.
           ip: IP address as dotted decimal
           intf: string, interface name"""
        return self.cmd( 'route add -host', ip, 'dev', intf )

    # XXX - SAME
    def setDefaultRoute( self, intf=None ):
        """Set the default route to go through intf.
           intf: Intf or {dev <intfname> via <gw-ip> ...}"""
        # Note setParam won't call us if intf is none
        if isinstance( intf, BaseString ) and ' ' in intf:
            params = intf
        else:
            params = 'dev %s' % intf
        # Do this in one line in case we're messing with the root namespace
        self.cmd( 'ip route del default; ip route add default', params )

    # Convenience and configuration methods

    # XXX - SAME
    def setMAC( self, mac, intf=None ):
        """Set the MAC address for an interface.
           intf: intf or intf name
           mac: MAC address as string"""
        return self.intf( intf ).setMAC( mac )

    # XXX - SAME
    def setIP( self, ip, prefixLen=8, intf=None, **kwargs ):
        """Set the IP address for an interface.
           intf: intf or intf name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs
           kwargs: any additional arguments for intf.setIP"""
        return self.intf( intf ).setIP( ip, prefixLen, **kwargs )

    # XXX - SAME
    def IP( self, intf=None ):
        "Return IP address of a node or specific interface."
        return self.intf( intf ).IP()

    # XXX - SAME
    def MAC( self, intf=None ):
        "Return MAC address of a node or specific interface."
        return self.intf( intf ).MAC()

    # XXX - SAME
    def intfIsUp( self, intf=None ):
        "Check if an interface is up."
        return self.intf( intf ).isUp()

    # The reason why we configure things in this way is so
    # That the parameters can be listed and documented in
    # the config method.
    # Dealing with subclasses and superclasses is slightly
    # annoying, but at least the information is there!

    # XXX - SAME
    def setParam( self, results, method, **param ):
        """Internal method: configure a *single* parameter
           results: dict of results to update
           method: config method name
           param: arg=value (ignore if value=None)
           value may also be list or dict"""
        name, value = list( param.items() )[ 0 ]
        if value is None:
            return
        f = getattr( self, method, None )
        if not f:
            return
        if isinstance( value, list ):
            result = f( *value )
        elif isinstance( value, dict ):
            result = f( **value )
        else:
            result = f( value )
        results[ name ] = result
        return result

    # XXX - SAME
    def config( self, mac=None, ip=None,
                defaultRoute=None, lo='up', **_params ):
        """Configure Node according to (optional) parameters:
           mac: MAC address for default interface
           ip: IP address for default interface
           ifconfig: arbitrary interface configuration
           Subclasses should override this method and call
           the parent class's config(**params)"""
        # If we were overriding this method, we would call
        # the superclass config method here as follows:
        # r = Parent.config( **_params )
        r = {}
        self.setParam( r, 'setMAC', mac=mac )
        self.setParam( r, 'setIP', ip=ip )
        self.setParam( r, 'setDefaultRoute', defaultRoute=defaultRoute )
        # This should be examined
        self.cmd( 'ifconfig lo ' + lo )
        return r

    # XXX - SAME
    def configDefault( self, **moreParams ):
        "Configure with default parameters"
        self.params.update( moreParams )
        self.config( **self.params )

    # XXX - SAME
    # This is here for backward compatibility
    def linkTo( self, node, link=Link ):
        """(Deprecated) Link to another node
           replace with Link( node1, node2)"""
        return link( self, node )

    # Other methods

    # XXX - SAME
    def intfList( self ):
        "List of our interfaces sorted by port number"
        return [ self.intfs[ p ] for p in sorted( self.intfs.keys() ) ]

    # XXX - SAME
    def intfNames( self ):
        "The names of our interfaces sorted by port number"
        return [ str( i ) for i in self.intfList() ]


    # XXX - SAME
    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )
    
    # XXX - SAME
    def __str__( self ):
        "Abbreviated string representation"
        return self.name

    # Automatic class setup support
    # XXX - SAME
    isSetup = False

    # XXX - SAME
    @classmethod
    def checkSetup( cls ):
        "Make sure our class and superclasses are set up"
        while cls and not getattr( cls, 'isSetup', True ):
            cls.setup()
            cls.isSetup = True
            # Make pylint happy
            cls = getattr( type( cls ), '__base__', None )

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

    async def _read(self, maxbytes=1024):
        return await self.stdout.readuntil(separator='\x7f')

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


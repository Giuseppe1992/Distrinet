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
                           encode, getincrementaldecoder, Python3, which )
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
                       waitStart=True, inNamespace=False,
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
        # == distrinet
        self._preInit(loop=loop,
                   admin_ip=admin_ip,
                   master=master,
                   target=target, port=port, username=username, pub_id=pub_id,
                   bastion=bastion, bastion_port=bastion_port, client_keys=client_keys,
                   waitStart=waitStart,
                   **params)
        # =====================================================================

        # good old Mininet
        super(LxcNode, self).__init__(name=name, inNamespace=inNamespace, **params)

        ## ====================================================================

    def _preInit(self,
                   loop,
                   admin_ip,
                   master,
                   target=None, port=22, username=None, pub_id=None,
                   bastion=None, bastion_port=22, client_keys=None,
                   waitStart=True,
                   **params):
        self.run = True
        # asyncio loop
        self.loop = loop

        # are we blocking
        self.waitStart = waitStart

        # LXC host information
        self.target = target
        self.port = port
        self.username = username
        self.pub_id = pub_id
        self.client_keys = client_keys

        # ssh bastion information
        self.bastion = bastion
        self.bastion_port = bastion_port

        # IP address to use to administrate the machine
        self.admin_ip = admin_ip

        self.masternode = master
        self.containerInterfaces = {}
        self.containerLinks = {}

        # constraints on the deployment
        self.image = params.get("image", None)
        self.memory = params.get("memory", None)
        self.cpu = params.get("cpu", None)

        # network devices created on the target
        self.devices = []
        self.devicesMaster = []

        # prepare the machine
        # SSH with the target
        if self.target:
            self.targetSsh = ASsh(loop=self.loop, host=self.target, username=self.username, bastion=self.bastion, client_keys=self.client_keys)
        # SSH with the node
        admin_ip = self.admin_ip
        if "/" in admin_ip:
                admin_ip, prefix = admin_ip.split("/")
        self.ssh = ASsh(loop=self.loop, host=admin_ip, username=self.username, bastion=self.bastion, client_keys=self.client_keys)

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

    def startShell( self, mnopts=None):
        if self.waitStart:
            # TODO DSA - be backward compatible with sequential deployment
            info ("{} Connecting to the target {}".format(self, self.target))
            self.connectTarget()
            self.waitConnectedTarget()
            info (" connected ")

            self.createContainer(**self.params)
            self.waitCreated()
            self.addContainerInterface(intfName="admin", brname="admin-br")
            self.connectToAdminNetwork(master=self.masternode.host, target=self.target, link_id=CloudLink.newLinkId(), admin_br="admin-br")

            self.configureContainer()
            self.connect()
            self.waitConnected()
            self.asyncStartShell()
            self.waitStarted()
            self.finalizeStartShell()
            info (" started\n")


    # Command support via shell process in namespace
    def asyncStartShell( self, mnopts=None ):

        async def run_shell():
            async def trick(shell, stdin):
                while self.run:
                    c = await shell.stdout.read(n=1)
                    os.write(stdin.fileno(), c.encode('utf-8'))

            # Spawn a shell subprocess in a pseudo-tty, to disable buffering
            # in the subprocess and insulate it from signals (e.g. SIGINT)
            # received by the parent
            self.master, self.slave = pty.openpty()

            bash = "bash --rcfile <( echo 'PS1=\x7f') --noediting -is mininet:{}".format(self.name)
            self.shell = await self.ssh.conn.create_process(bash, stdin=self.slave, stdout=self.slave, stderr=self.slave)

            self.stdin = os.fdopen(self.master, 'r')
            self.stdout = self.stdin

            self.pollOut = select.poll()
            self.pollOut.register( self.stdout )

            # Maintain mapping between file descriptors and nodes
            # This is useful for monitoring multiple nodes
            # using select.poll()
            self.outToNode[ self.stdout.fileno() ] = self
            self.inToNode[ self.stdin.fileno() ] = self

            await trick(self.shell, self.stdin)

        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return

        self.loop.create_task(run_shell())

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
        self.waiting = False
        self.run = False
        self.conn = None                                                                                                       
        self.shell = None
        self.devices = None

    # Subshell I/O, commands and control

    # XXX - OK
    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        self.unmountPrivateDirs()

        cmds = []
        # destroy the container
        cmds.append("lxc delete {} --force".format(self.name))

        # remove all locally made devices
        for device in self.devices:
            cmds.append("ip link delete {}".format(device))

        cmd = ";".join(cmds)
        self.targetSsh.sendCmd(cmd)

        # close the SSH connection
        self.ssh.close()

        # cleanup variables
        self.cleanup()

    # XXX - DSA - quick hack to deal with OpenSSH bug regarding signals...
    async def _sendInt(self, intr):
        killcmd = 'kill -s {} -`pgrep -f "mininet:{}"`'.format(ord(intr), self.name)
        await self.ssh.conn.run(killcmd)

    # XXX - OK
    def sendInt( self, intr=chr( 3 ) ):
        "Interrupt running command."
        debug( 'sendInt: writing chr(%d)\n' % ord( intr ) )
        task = self.loop.create_task(self._sendInt(intr))
        while not task.done():
            time.sleep(0.0001)
        return task.result()

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
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''

        ## TODO DSA  - to put in finalize
        self.waitStarted()
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
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

        while (self.stdin is None) or (self.stdout is None):
            time.sleep(0.001)
   # =========================================================================

    # == Time for coroutines black magic ======================================
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

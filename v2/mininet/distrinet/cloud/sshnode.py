"""
Node objects for Mininet.

Nodes provide a simple abstraction for interacting with hosts, switches
and controllers. Local nodes are simply one or more processes on the local
machine.

Node: superclass for all (primarily local) network nodes.

Host: a virtual host. By default, a host is simply a shell; commands
    may be sent using Cmd (which waits for output), or using sendCmd(),
    which returns immediately, allowing subsequent monitoring using
    monitor(). Examples of how to run experiments using this
    functionality are provided in the examples/ directory. By default,
    hosts share the root file system, but they may also specify private
    directories.

CPULimitedHost: a virtual host whose CPU bandwidth is limited by
    RT or CFS bandwidth limiting.

Switch: superclass for switch nodes.

UserSwitch: a switch using the user-space switch from the OpenFlow
    reference implementation.

OVSSwitch: a switch using the Open vSwitch OpenFlow-compatible switch
    implementation (openvswitch.org).

OVSBridge: an Ethernet bridge implemented using Open vSwitch.
    Supports STP.

IVSSwitch: OpenFlow switch using the Indigo Virtual Switch.

Controller: superclass for OpenFlow controllers. The default controller
    is controller(8) from the reference implementation.

OVSController: The test controller from Open vSwitch.

NOXController: a controller node using NOX (noxrepo.org).

Ryu: The Ryu controller (https://osrg.github.io/ryu/)

RemoteController: a remote controller node, which may use any
    arbitrary OpenFlow-compatible controller, and which is not
    created or managed by Mininet.

Future enhancements:

- Possibly make Node, Switch and Controller more abstract so that
  they can be used for both local and remote nodes

- Create proxy objects for remote nodes (Mininet: Cluster Edition)
"""

import os
import re
import shlex
from subprocess import Popen, PIPE
from time import sleep

from mininet.log import info, error, warn, debug
from mininet.util import ( quietRun, moveIntf, isShellBuiltin,
                           numCores, retry, mountCgroups, BaseString, decode,
                           encode, Python3 )
from mininet.link import Link, Intf, TCIntf, OVSIntf
from re import findall

from mininet.node import Node

from distrinet.cloud.sshutil import (RemotePopen, waitSessionReadable, waitSessionWritable)


def findUser():
    "Try to return logged-in (usually non-root) user"
    return (
            # If we're running sudo
            os.environ.get( 'SUDO_USER', False ) or
            # Logged-in user (if we have a tty)
            ( quietRun( 'who am i' ).split() or [ False ] )[ 0 ] or
            # Give up and return effective user
            quietRun( 'whoami' ).strip() )

class SshNode( Node ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""
    portBase = 0  # Nodes always start with eth0/port0, even in OF 1.0

    # Determine IP address of local host
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    def __init__( self, name, server="localhost", admin_ip=None, user=None, jump=None, **params ):
        """name: name of node
           privateDirs: list of private directory strings or tuples
           params: Node parameters (see config() for details)"""
        # inherit from Mininet Node
        super(SshNode, self).__init__(name=name, **params)
        
        # We connect to the server by jumping a proxy
        self.jump = jump

        # We connect to servers by IP address
        self.server = server 
        self.admin_ip = ( admin_ip if admin_ip
                          else self.findServerIP( self.server ) )
        self.user = user if user else findUser()

################        self.name = name
################        self.privateDirs = params.get( 'privateDirs', [] )
################
################        # Python 3 complains if we don't wait for shell exit
################        self.waitExited = params.get( 'waitExited', Python3 )
################
################        # Stash configuration parameters for future reference
################        self.params = params
################
################        self.intfs = {}  # dict of port numbers to interfaces
################        self.ports = {}  # dict of interfaces to port numbers
################                         # replace with Port objects, eventually ?
################        self.nameToIntf = {}  # dict of interface names to Intfs
################
################        # Make pylint happy
################        ( self.shell, self.execed, self.pid, self.stdin, self.stdout,
################            self.lastPid, self.lastCmd ) = (
################                None, None, None, None, None, None, None )
################        self.waiting = False
################        self.readbuf = ''
################
################        self.startShell()
################
################        self.mountPrivateDirs()
################
################        # Make sure class actually works
################        self.checkSetup()

###    # File descriptor to node mapping support
###    # Class variables and methods
###
###    inToNode = {}  # mapping of input fds to nodes
###    outToNode = {}  # mapping of output fds to nodes
###
    @classmethod
    def fdToNode( cls, fd ):
        """Return node corresponding to given file descriptor.
           Cannot be implemented for 
           fd: file descriptor
           returns: node"""
        raise Exception("This method doesn't make sense for SSH Nodes")

    # DSA - OK - same MIXIN
    @classmethod
    def findServerIP( cls, server ):
        "Return our server's IP address"
        # First, check for an IP address
        ipmatch = cls._ipMatchRegex.findall( server )
        if ipmatch:
            return ipmatch[ 0 ]
        # Otherwise, look up remote server
        output = quietRun( 'getent ahostsv4 %s' % server )
        ips = cls._ipMatchRegex.findall( output )
        ip = ips[ 0 ] if ips else None
        return ip
       
    def _startShell( self, mnopts=None):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return

        bash = "bash --rcfile <( echo 'PS1=\x7f') --noediting -is mininet:{}".format(self.name)
        import time
        print ("       Remote Popen...ing", time.time())
        self.shell = RemotePopen(args=bash, server=self.admin_ip, user=self.user, jump=self.jump)
        print ("       Remote Popenned", time.time())
        print ("\t\t\tle shell: ", self.shell)
        self.stdin = self.shell.stdin
        self.stdout = self.shell.stdout
        self.stderr = self.shell.stderr
        self.session = self.shell.session

        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''

        # are we in blocking mode or not?
        if self.params.get("blocking", False):
            self._waitShellStarted()

    def _waitShellStarted(self):
        # Wait for prompt
        while True:
            while not self.session.recv_ready():
                print (".")
                sleep(0.01)
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

        # Get the PID of the shell
        r = self.cmd("echo $$")
        self.pid = int(r)
        self.shell.pid = self.pid

    # Command support via shell process in namespace
    def startShell( self, mnopts=None, prevent_autostart=True ):
        """
        prevent_autostart: to prevent to always start the shell when a node is
                           instantiated (trick to overcome Mininet force starting shell)
        """
        if not prevent_autostart:
            self._startShell(mnopts=mnopts)
 

    def mountPrivateDirs( self ):
        "mount private directories"
        # Avoid expanding a string into a list of chars
        assert not isinstance( self.privateDirs, BaseString )
        for directory in self.privateDirs:
            assert False, "to implement"
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

    def unmountPrivateDirs( self ):
        "mount private directories"
        for directory in self.privateDirs:
            assert False, "to implement"
            if isinstance( directory, tuple ):
                self.cmd( 'umount ', directory[ 0 ] )
            else:
                self.cmd( 'umount ', directory )

    # DSA - OK
    def cleanup( self ):
        "Help python collect its garbage."
        # We used to do this, but it slows us down:
        # Intfs may end up in root NS
        # for intfName in self.intfNames():
        # if self.name in intfName:
        # quietRun( 'ip link del ' + intfName )
        if self.shell:
#           # Close ptys
            self.shell.close()
            if self.waitExited:
                debug( 'waiting for', self.pid, 'to terminate\n' )
                self.shell.wait()
        self.shell = None

    # Subshell I/O, commands and control

    # DSA - OK
    def read( self, maxbytes=1024 ):
        """Buffered read from node, potentially blocking.
           maxbytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < maxbytes:
            if self.session.recv_ready():
                data = decode(self.session.recv(maxbytes - count))
                self.readbuf += data
        if maxbytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :maxbytes ]
            self.readbuf = self.readbuf[ maxbytes: ]
        return result

    # DSA - OK
    def readline( self ):
        """Buffered readline from node, potentially blocking.
           returns: line (minus newline) or None"""
        readbuf = self.read( 1024 )
        self.readbuf = readbuf + self.readbuf
        if '\n' not in self.readbuf:
            return None
        pos = self.readbuf.find( '\n' )
        line = self.readbuf[ 0: pos ]
        self.readbuf = self.readbuf[ pos + 1: ]
        return line

    # DSA - OK
    def write( self, data ):
        """Write data to node.
           data: string"""
        # wait before writing
        self.waitWritable()
        n = self.session.send(encode(data))

    # DSA - OK
    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        self.unmountPrivateDirs()
        if self.shell:
            if self.shell.poll() is None:
                self.shell.kill()  # DSA: a bit hardcore... better to close gently in the future
        self.cleanup()

    def stop( self, deleteIntfs=False ):
        """Stop node.
           deleteIntfs: delete interfaces? (False)"""
        if deleteIntfs:
            self.deleteIntfs()
        self.terminate()

    # DSA - OK
    def waitReadable( self, timeoutms=None ):
        """Wait until node's output is readable.
           timeoutms: timeout in ms or None to wait indefinitely.
           returns: result None if not ready. Otherwise, returns True"""
        if len( self.readbuf ) == 0:
            waitSessionReadable(self.session, timeoutms)
        return None if not self.session.recv_ready() else True

    # DSA - added to the API
    def waitWritable( self, timeoutms=None ):
        """Wait until node's input is writable.
           timeoutms: timeout in ms or None to wait indefinitely.
           returns: result None if not ready. Otherwise, returns True"""
        waitSessionWritable(self.session, timeoutms)
        return None if not self.session.send_ready() else True

    # DSA - OK
    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete.
           args: command and arguments, or string
           printPid: print command's PID? (False)"""
        assert self.shell and not self.waiting
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
        # if a builtin command is backgrounded, it still yields a PID
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            # print ^A{pid}\n so monitor() can set lastPid
            cmd += ' printf "\\001%d\\012" $! '
        elif printPid: #and not isShellBuiltin( cmd ):
###            cmd = 'mnexec -p ' + cmd
            cmd = './mnexec.py ' + shlex.quote(cmd)
#        print ("command sent:", cmd)
        cmd = cmd + "\n"
        self.write( cmd )
        self.lastPid = None
        self.waiting = True

    # DSA - OK
    def monitor( self, timeoutms=None, findPid=True ):
        """Monitor and return the output of a command.
           Set self.waiting to False if command has completed.
           timeoutms: timeout in ms or None to wait indefinitely
           findPid: look for PID from mnexec -p"""
        ready = self.waitReadable( timeoutms )
        if ready == None:
            return ''
        data = self.read( 1024 )
        pidre = r'\[\d+\] \d+\r\n'
        # Look for PID
        marker = chr( 1 ) + r'\d+\r\n'
        if findPid and chr( 1 ) in data:
            # suppress the job and PID of a backgrounded command
            if re.findall( pidre, data ):
                data = re.sub( pidre, '', data )
            # Marker can be read in chunks; continue until all of it is read
            while not re.findall( marker, data ):
                data += self.read( 1024 )
            markers = re.findall( marker, data )
            if markers:
                self.lastPid = int( markers[ 0 ][ 1: ] )
                data = re.sub( marker, '', data )
        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    # DSA - OK
    # DSA - TODO - deal with stdin,stdout, and stderr
    def popen( self, *args, **kwargs ):
        """Return a Popen() object in our namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        shell = kwargs.pop( 'shell', False )
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
            sh = os.environ.get('SHELL', '/bin/bash')
            cmd = [ sh, '-c' ] + [ shlex.quote(' '.join( cmd )) ]

        popen = RemotePopen(args=cmd, server=self.admin_ip, user=self.user, jump=self.jump)
        return popen

    # Interface management, configuration, and routing
    # DSA - OK
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

    # Automatic class setup support

    isSetup = False

    def checkSetup( self ):
        self.setup()
        self.isSetup = True

    def setup( self ):
        print ("setup de SSHnode")
        pass


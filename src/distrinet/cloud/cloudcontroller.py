from mininet.log import lg, LEVELS, info, debug, warn, error, output

from distrinet.cloud.lxc_container import (LxcNode)

class LxcController( LxcNode ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, target=None, admin_ip=None, user=None, jump=None,
                  command='controller',
                  cargs='-v ptcp:%d', cdir=None, ip="127.0.0.1",
                  port=6653, protocol='tcp', **params):
        self.command = command
        self.cargs = cargs
        self.cdir = cdir
        # Accept 'ip:port' syntax as shorthand
        if ':' in ip:
            ip, port = ip.split( ':' )
            port = int( port )
        self.ip = ip
        self.ip = admin_ip          # DSA - to change to be IP
        self.port = port
        self.protocol = protocol
        super(LxcController, self).__init__( name, target=target, admin_ip=admin_ip, user=user, jump=jump, **params  )
        self.checkListening()

    def checkListening( self ):
        "Make sure no controllers are running on our port"
        # Verify that Telnet is installed first:
        out, _err, returnCode = errRun( "which telnet" )
        if 'telnet' not in out or returnCode != 0:
            raise Exception( "Error running telnet to check for listening "
                             "controllers; please check that it is "
                             "installed." )
        listening = self.cmd( "echo A | telnet -e A %s %d" %
                              ( self.ip, self.port ) )
        if 'Connected' in listening:
            servers = self.cmd( 'netstat -natp' ).split( '\n' )
            pstr = ':%d ' % self.port
            clist = servers[ 0:1 ] + [ s for s in servers if pstr in s ]
            raise Exception( "Please shut down the controller which is"
                             " running on port %d:\n" % self.port +
                             '\n'.join( clist ) )

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        pathCheck( self.command )
        cout = '/tmp/' + self.name + '.log'
        if self.cdir is not None:
            self.cmd( 'cd ' + self.cdir )
        self.cmd( self.command + ' ' + self.cargs % self.port +
                  ' 1>' + cout + ' 2>' + cout + ' &' )
        self.execed = False

    def stop( self, *args, **kwargs ):
        "Stop controller."
        self.cmd( 'kill %' + self.command )
        self.cmd( 'wait %' + self.command )
        super( LxcNode, self ).stop( *args, **kwargs )

    def IP( self, intf=None ):
        "Return IP address of the Controller"
##        if self.intfs:
##            ip = Node.IP( self, intf )
##        else:
##            ip = self.ip
##        return ip
        return self.ip

    def __repr__( self ):
        "More informative string representation"
        return '<%s %s: %s:%s pid=%s> ' % (
            self.__class__.__name__, self.name,
            self.IP(), self.port, self.pid )
    
    def isAvailable( cls ):
        return False
##        "Is controller available?"
##        return quietRun( 'which controller' )


class LxcRyu( LxcController ):
    "Controller to run Ryu application"
    def __init__( self, name, target=None, admin_ip=None, user=None, jump=None, *ryuArgs, **kwargs ):
        """Init.
        name: name to give controller.
        ryuArgs: arguments and modules to pass to Ryu"""
        ryuCoreDir = '/usr/local/lib/python2.7/dist-packages/ryu/ryu/app/'
        if not ryuArgs:
            warn( 'warning: no Ryu modules specified; '
                  'running simple_switch only\n' )
            ryuArgs = [ ryuCoreDir + 'simple_switch.py' ]
        elif type( ryuArgs ) not in ( list, tuple ):
            ryuArgs = [ ryuArgs ]

        super(LxcRyu, self).__init__(name,
                             target=target, admin_ip=admin_ip, user=user, jump=jump,
                             command='ryu-manager',
                             cargs='--ofp-tcp-listen-port %s ' +
                             ' '.join( ryuArgs ),
                             cdir=ryuCoreDir,
                             **kwargs )

class LxcRemoteController( object ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, ip='127.0.0.1',
                  port=None, **kwargs):
        """Init.
           name: name to give controller
           ip: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        self.name = name
        # Accept 'ip:port' syntax as shorthand
        if ':' in ip:
            ip, port = ip.split( ':' )
            port = int( port )
        self.ip = ip
        self.port = port
        self.protocol = 'tcp'
        self.checkListening()
        self.waiting = False

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return

    def checkListening( self ):
        "Warn if remote controller is not accessible"
        if self.port is not None:
            self.isListening( self.ip, self.port )
        else:
            for port in 6653, 6633:
                if self.isListening( self.ip, port ):
                    self.port = port
                    info( "Connecting to remote controller"
                          " at %s:%d\n" % ( self.ip, self.port ))
                    break

        if self.port is None:
            self.port = 6653
            warn( "Setting remote controller"
                  " to %s:%d\n" % ( self.ip, self.port ))

    def isListening( self, ip, port ):
        "Check if a remote controller is listening at a specific ip and port"
#        listening = self.cmd( "echo A | telnet -e A %s %d" % ( ip, port ) )
#        if 'Connected' not in listening:
#            warn( "Unable to contact the remote controller"
#                  " at %s:%d\n" % ( ip, port ) )
#            return False
#        else:
        return True

    def IP( self, intf=None ):
        "Return IP address of the Controller"
        return self.ip 

    def intfList( self ):
            return []
    def intfNames( self ):
          return []

    def __repr__( self ):
        "More informative string representation"
        return '<%s %s: %s:%s> ' % (
            self.__class__.__name__, self.name,
            self.IP(), self.port )

    def isAvailable( cls ):
        return True

from mininet.log import lg, LEVELS, info, debug, warn, error, output

from mininet.lxc_container import (LxcNode)

from mininet.dutil import _info


class LxcController ( LxcNode ):
    def __init__( self, name,
                  loop, master, admin_ip,
                  inNamespace=False, command='controller',
                  cargs='-v ptcp:%d', cdir=None, ip="127.0.0.1",
                  port=6653, protocol='tcp',
                  target=None, ssh_port=22, username=None, pub_id=None,
                  bastion=None, bastion_port=22, client_keys=None,
                  waitStart=True,
                  **params):
        super(LxcController, self).__init__(name=name, loop=loop,
                       admin_ip=admin_ip,
                       master=master,
                       target=target, port=ssh_port, username=username, pub_id=pub_id,
                       bastion=bastion, bastion_port=bastion_port, client_keys=client_keys,
                       waitStart=waitStart,
                       **params)

        self.command = command
        self.cargs = cargs
        self.cdir = cdir
        # Accept 'ip:port' syntax as shorthand
        if ':' in ip:
            ip, port = ip.split( ':' )
            port = int( port )
        self.ip = ip
        self.port = port
        self.protocol = protocol 

    def checkListening( self ):
        """ PowerWagon DON'T CARE"""
        pass

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
        super( LxcController, self ).stop( *args, **kwargs )

    def IP( self, intf=None ):
        "Return IP address of the Controller"
        return self.ip 

    def __repr__( self ):
        "More informative string representation"
        return '<%s %s: %s:%s pid=%s> ' % (
            self.__class__.__name__, self.name,
            self.IP(), self.port, self.pid )

    @classmethod
    def isAvailable( cls ):
        "Is controller available?"
        return False


class OnosLxcController ( LxcController ):
    def __init__( self, name,
                  loop, admin_ip=None, master=None,
                  image='ubuntu-onos-2.1.0',
                  **params):
        assert (master is not None)
        assert (('ip' in params) or (admin_ip is not None)), "provide at least an ip or an admin_ip"

        if 'target' not in params:
            params.update({'target':master.host})
        if admin_ip is None:
            admin_ip = params.get('ip')
        if 'ip' not in params:
            params.update({'ip':admin_ip})

        super(OnosLxcController, self).__init__(name=name, loop=loop, admin_ip=admin_ip, master=master, image=image, **params)

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        cout = '/tmp/controller_{}.log'.format(self.name)
        info ( " starting Onos ")
        self.cmd("ln -s /root/jdk-11.0.1/bin/java /usr/bin/java")
        self.cmd("nohup /opt/onos-2.1.0/bin/onos-service start >& {} &".format(cout))
        import time
        time.sleep(25)
        info ( " installing Onos Apps")
        cmds = ["/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.openflow-base",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.openflow",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.openflow-message",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.ofagent",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.lldpprovider",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.faultmanagement",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.flowanalyzer",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.linkprops",
                "/opt/onos-2.1.0/bin/onos-app 127.0.0.1 activate org.onosproject.fwd"]
        self.cmd(";".join(cmds))
        info ( ".")

        self.execed = False

    def stop( self, *args, **kwargs ):
        self.cmd("/opt/onos-2.1.0/bin/onos-service stop") 
        super( OnosLxcController, self ).stop( *args, **kwargs )

class RyuLxcController ( OnosLxcController ):
    def __init__( self, name,
                  loop, admin_ip=None, master=None,
                  image='ubuntu-ryu-4.30',
                  **params):
        super(RyuLxcController, self).__init__(name=name, loop=loop, admin_ip=admin_ip, master=master, image=image, **params)

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        cout = '/tmp/controller_{}.log'.format(self.name)
        info ( " starting Ryu ")
        self.cmd("nohup /usr/local/bin/ryu-manager --verbose /usr/local/lib/python2.7/dist-packages/ryu/app/simple_switch_13.py &> {} &".format(cout))
        info ( ".")

        self.execed = False

    def stop( self, *args, **kwargs ):
        self.cmd("killall ryu-manager") 
        super( RyuLxcController, self ).stop( *args, **kwargs )



# TODO - DSA inherit from LxcController
class LxcRemoteController( object ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, ip='192.168.0.1',
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

        # XXX - DSA beurk
        self.devicesMaster = []

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return

    def terminate( self ):
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

    def cmd(self, cmd):
        return self.masterSsh.cmd(cmd)

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

    def targetSshWaitOutput(self):
        pass

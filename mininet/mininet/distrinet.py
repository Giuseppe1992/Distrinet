"""

    Mininet: A simple networking testbed for OpenFlow/SDN!

author: Bob Lantz (rlantz@cs.stanford.edu)
author: Brandon Heller (brandonh@stanford.edu)

Mininet creates scalable OpenFlow test networks by using
process-based virtualization and network namespaces.

Simulated hosts are created as processes in separate network
namespaces. This allows a complete OpenFlow network to be simulated on
top of a single Linux kernel.

Each host has:

A virtual console (pipes to a shell)
A virtual interfaces (half of a veth pair)
A parent shell (and possibly some child processes) in a namespace

Hosts have a network interface which is configured via ifconfig/ip
link/etc.

This version supports both the kernel and user space datapaths
from the OpenFlow reference implementation (openflowswitch.org)
as well as OpenVSwitch (openvswitch.org.)

In kernel datapath mode, the controller and switches are simply
processes in the root namespace.

Kernel OpenFlow datapaths are instantiated using dpctl(8), and are
attached to the one side of a veth pair; the other side resides in the
host namespace. In this mode, switch processes can simply connect to the
controller via the loopback interface.

In user datapath mode, the controller and switches can be full-service
nodes that live in their own network namespaces and have management
interfaces and IP addresses on a control network (e.g. 192.168.123.1,
currently routed although it could be bridged.)

In addition to a management interface, user mode switches also have
several switch interfaces, halves of veth pairs whose other halves
reside in the host nodes that the switches are connected to.

Consistent, straightforward naming is important in order to easily
identify hosts, switches and controllers, both from the CLI and
from program code. Interfaces are named to make it easy to identify
which interfaces belong to which node.

The basic naming scheme is as follows:

    Host nodes are named h1-hN
    Switch nodes are named s1-sN
    Controller nodes are named c0-cN
    Interfaces are named {nodename}-eth0 .. {nodename}-ethN

Note: If the network topology is created using mininet.topo, then
node numbers are unique among hosts and switches (e.g. we have
h1..hN and SN..SN+M) and also correspond to their default IP addresses
of 10.x.y.z/8 where x.y.z is the base-256 representation of N for
hN. This mapping allows easy determination of a node's IP
address from its name, e.g. h1 -> 10.0.0.1, h257 -> 10.0.1.1.

Note also that 10.0.0.1 can often be written as 10.1 for short, e.g.
"ping 10.1" is equivalent to "ping 10.0.0.1".

Currently we wrap the entire network in a 'mininet' object, which
constructs a simulated network based on a network topology created
using a topology object (e.g. LinearTopo) from mininet.topo or
mininet.topolib, and a Controller which the switches will connect
to. Several configuration options are provided for functions such as
automatically setting MAC addresses, populating the ARP table, or
even running a set of terminals to allow direct interaction with nodes.

After the network is created, it can be started using start(), and a
variety of useful tasks maybe performed, including basic connectivity
and bandwidth tests and running the mininet CLI.

Once the network is up and running, test code can easily get access
to host and switch objects which can then be used for arbitrary
experiments, typically involving running a series of commands on the
hosts.

After all desired tests or activities have been completed, the stop()
method may be called to shut down the network.

"""

import os
import re
import select
import signal
import random

from time import sleep
from itertools import chain, groupby
from math import ceil

from mininet.cli import CLI
from mininet.log import info, error, debug, output, warn
from mininet.node import ( Node, Host, OVSKernelSwitch, DefaultController,
                           Controller )
from mininet.nodelib import NAT
#from mininet.link import Link, Intf
from mininet.util import ( quietRun, fixLimits, numCores, ensureRoot,
                           macColonHex, ipStr, ipParse, netParse, ipAdd,
                           waitListening, BaseString, encode )
from mininet.term import cleanUpScreens, makeTerms

from mininet.link import (Intf, TCIntf)

# DSA ########################
from mininet.dutil import _info

from mininet.cloudlink import (CloudLink)
from mininet.lxc_container import (LxcNode)
from mininet.cloudswitch import (LxcSwitch)
from mininet.cloudcontroller import (LxcRemoteController)


import asyncio
import time
from threading import Thread

from mininet.ssh import SSH
##############################

# Mininet version: should be consistent with README and LICENSE
from mininet.net import VERSION as MININET_VERSION
# Distrinet version
VERSION = "2.0 (Mininet {})".format(MININET_VERSION)

from mininet.net import Mininet


class Distrinet( Mininet ):
    "Network emulation with hosts spawned in network namespaces."
    def __init__( self, topo=None, switch=LxcSwitch, host=LxcNode,
                  controller=LxcRemoteController, link=CloudLink, intf=TCIntf,
                  mapper=None,
                  build=True, xterms=False, cleanup=False, ipBase='10.0.0.0/8',
                  adminIpBase='192.168.0.1/8',
                  autoSetMacs=False, autoPinCpus=False,
                  listenPort=None, waitConnected=False, waitConnectionTimeout=5, 
                  jump=None, user="root", client_keys=None, master=None, pub_id=None,
                  **kwargs):
        """Create Mininet object.
           topo: Topo (topology) object or None
           switch: default Switch class
           host: default Host class/constructor
           controller: default Controller class/constructor
           link: default Link class/constructor
           intf: default Intf class/constructor
           ipBase: base IP address for hosts,
           mapper: mapper to map virtual topology onto physical topology
           build: build now from topo?
           xterms: if build now, spawn xterms?
           cleanup: if build now, cleanup before creating?
           inNamespace: spawn switches and controller in net namespaces?
           autoSetMacs: set MAC addrs automatically like IP addresses?
           autoStaticArp: set all-pairs static MAC addrs?
           autoPinCpus: pin hosts to (real) cores (requires CPULimitedHost)?
           listenPort: base listening port to open; will be incremented for
               each additional switch in the net if inNamespace=False
           waitConnected: wait for the switches to be connected to their controller
           waitConnectionTimeout: timeout to wait to decide if a switch is connected to its controller
           jump: SSH jump host
           master: master node"""
        self.topo = topo
        self.switch = switch
        self.host = host
        self.controller = controller
        self.link = link
        self.intf = intf
        self.ipBase = ipBase
        self.ipBaseNum, self.prefixLen = netParse( self.ipBase )
        hostIP = ( 0xffffffff >> self.prefixLen ) & self.ipBaseNum
        # Start for address allocation
        self.nextIP = hostIP if hostIP > 0 else 1


        self.adminIpBase = adminIpBase
        self.adminIpBaseNum, self.adminPrefixLen = netParse( self.adminIpBase )
        adminIP = ( 0xffffffff >> self.adminPrefixLen ) & self.adminIpBaseNum
        # Start for address allocation
        self.adminNextIP = adminIP if adminIP > 0 else 1


#        self.inNamespace = inNamespace
        self.xterms = xterms
        self.cleanup = cleanup
        self.autoSetMacs = autoSetMacs
#        self.autoStaticArp = autoStaticArp
        self.autoPinCpus = autoPinCpus
#        self.numCores = numCores()
#        self.nextCore = 0  # next core for pinning hosts to CPUs
        self.listenPort = listenPort
        self.waitConn = waitConnected
        self.waitConnectionTimeout = waitConnectionTimeout

        self.mapper = mapper
#
        self.hosts = []
        self.switches = []
        self.controllers = []
        self.links = []

        self.loop = asyncio.get_event_loop()
        def runforever(loop):
            time.sleep(0.001)       ### DSA - WTF ?????????????
            loop.run_forever()

        self.thread = Thread(target=runforever, args=(self.loop,))
        self.thread.start()


        self.jump = jump
        self.user = user
        self.pub_id = pub_id

        self.client_keys = client_keys
        self.masterhost = master
        _info ("Connecting to master node\n")
        self.masterSsh = SSH(loop=self.loop, host=self.masterhost, username=self.user, bastion=self.jump, client_keys=self.client_keys)
        self.masterSsh.connect()
        self.masterSsh.waitConnected()
        _info ("connected to master node\n")



        self.nameToNode = {}  # name to Node (Host/Switch) objects

        self.terms = []  # list of spawned xterm processes

        self.init()  # Initialize Mininet if necessary

        self.built = False
        if topo and build:
            self.build()

    # DSA - OK
    def addHost( self, name, cls=None, **params ):
        """Add host.
           name: name of host to add
           cls: custom host class/constructor (optional)
           params: parameters for host
           returns: added host"""
        # Default IP and MAC addresses
        defaults = { 'ip': ipAdd( self.nextIP,
                                  ipBaseNum=self.ipBaseNum,
                                  prefixLen=self.prefixLen ) +
                                  '/%s' % self.prefixLen}
        if "image" in self.topo.nodeInfo(name):
            defaults.update({"image":self.topo.nodeInfo(name)["image"]})

        # XXX DSA - doesn't make sense to generate MAC automatically here, we
        # keep for compatibility prurpose but never use it...
        if self.autoSetMacs:
            defaults[ 'mac' ] = macColonHex( self.nextIP )
        if self.autoPinCpus:
            raise Exception("to be implemented")
#            defaults[ 'cores' ] = self.nextCore
#            self.nextCore = ( self.nextCore + 1 ) % self.numCores
        self.nextIP += 1
        defaults.update( params )

        if not cls:
            cls = self.host

        if self.mapper:
            defaults.update({"target":self.mapper.place(name)})

        h = cls(name=name, **defaults )
        self.hosts.append( h )
        self.nameToNode[ name ] = h
        return h

    # DSA - OK
    def addSwitch( self, name, cls=None, **params ):
        """Add switch.
           name: name of switch to add
           cls: custom switch class/constructor (optional)
           returns: added switch
           side effect: increments listenPort ivar ."""
        defaults = { 'listenPort': self.listenPort}

        if "image" in self.topo.nodeInfo(name):
            defaults.update({"image":self.topo.nodeInfo(name)})
        else:
            error ("we are missing an image for {} \n".format(name))
            exit()
        
        defaults.update( params )
       
        if not cls:
            cls = self.switch


        if self.mapper:
            defaults.update({"target":self.mapper.place(name)})

        sw = cls(name=name, **defaults )
        self.switches.append( sw )
        self.nameToNode[ name ] = sw
        return sw

    def delSwitch( self, switch ):
        "Delete a switch"
        self.delNode( switch, nodes=self.switches )

    # DSA - OK
    def addController( self, name='c0', controller=None, **params ):
        """Add controller.
           controller: Controller class
           params: Parameters for the controller"""
        # Get controller class
        params.update({'pub_id':self.pub_id})
        if not controller:
            controller = self.controller
        controller_new = controller(name=name, 
                    loop=self.loop,
                    master=self.masterSsh,
                    username=self.user,
                    bastion=self.jump,
                    client_keys=self.client_keys,
                **params)
        self.controllers.append(controller_new)
        self.nameToNode[ name ] = controller_new
        
        return controller_new

    def delController( self, controller ):
        """Delete a controller
           Warning - does not reconfigure switches, so they
           may still attempt to connect to it!"""
        self.delNode( controller )

    def addNAT( self, name='nat0', connect=True, inNamespace=False,
                **params):
        """Add a NAT to the Mininet network
           name: name of NAT node
           connect: switch to connect to | True (s1) | None
           inNamespace: create in a network namespace
           params: other NAT node params, notably:
               ip: used as default gateway address"""
        nat = self.addHost( name, cls=NAT, inNamespace=inNamespace,
                            subnet=self.ipBase, **params )
        # find first switch and create link
        if connect:
            if not isinstance( connect, Node ):
                # Use first switch if not specified
                connect = self.switches[ 0 ]
            # Connect the nat to the switch
            self.addLink( nat, connect )
            # Set the default route on hosts
            natIP = nat.params[ 'ip' ].split('/')[ 0 ]
            for host in self.hosts:
                if host.inNamespace:
                    host.setDefaultRoute( 'via %s' % natIP )
        return nat

    # DSA - OK
    def addLink( self, node1, node2, port1=None, port2=None,
                 cls=None, **params ):
        """"Add a link from node1 to node2
            node1: source node (or name)
            node2: dest node (or name)
            port1: source port (optional)
            port2: dest port (optional)
            cls: link class (optional)
            params: additional link params (optional)
            returns: link object"""
        # Accept node objects or names
        node1 = node1 if not isinstance( node1, BaseString ) else self[ node1 ]
        node2 = node2 if not isinstance( node2, BaseString ) else self[ node2 ]

        options = dict( params )

        # Port is optional
        if port1 is not None:
            options.setdefault( 'port1', port1 )
        if port2 is not None:
            options.setdefault( 'port2', port2 )
        if self.intf is not None:
            options.setdefault( 'intf', self.intf )

        # Set default MAC - this should probably be in Link
        options.setdefault( 'addr1', self.randMac() )
        options.setdefault( 'addr2', self.randMac() )
       
        params1 = None
        params2 = None
        if self.mapper:
            lstr = (str(node1), str(node2))
            placement = self.mapper.placeLink( lstr)
            params1 = placement[0]
            params2 = placement[1]


##        # define the VXLAN id for the link
##        options.setdefault("link_id", self.nextLinkId)
##        self.nextLinkId += 1 

        cls = self.link if cls is None else cls
        link = cls( node1=node1, node2=node2, params1=params1, params2=params2, **options )
        self.links.append( link )
        return link

    def delLink( self, link ):
        "Remove a link from this network"
        raise Exception("Not implementedd")
        link.delete()
        self.links.remove( link )

    def delLinkBetween( self, node1, node2, index=0, allLinks=False ):
        """Delete link(s) between node1 and node2
           index: index of link to delete if multiple links (0)
           allLinks: ignore index and delete all such links (False)
           returns: deleted link(s)"""
        links = self.linksBetween( node1, node2 )
        if not allLinks:
            links = [ links[ index ] ]
        for link in links:
            self.delLink( link )
        return links

    def configHosts( self ):
        "Configure a set of hosts."
        for host in self.hosts:
            info( host.name + ' ' )
            intf = host.defaultIntf()
            if intf:
                host.configDefault()
            else:
                # Don't configure nonexistent intf
                host.configDefault( ip=None, mac=None )
            # You're low priority, dude!
            # BL: do we want to do this here or not?
            # May not make sense if we have CPU lmiting...
            # quietRun( 'renice +18 -p ' + repr( host.pid ) )
            # This may not be the right place to do this, but
            # it needs to be done somewhere.
        info( '\n' )

    # DSA - OK
    def buildFromTopo( self, topo=None ):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info( '*** Creating network\n' )

        bastion = self.jump
        waitStart = False
        _ip = "{}/{}".format(ipAdd(self.adminNextIP, ipBaseNum=self.adminIpBaseNum, prefixLen=self.adminPrefixLen), self.adminPrefixLen)
        self.adminNextIP += 1
        self.host.createMasterAdminNetwork(self.masterSsh, brname="admin-br", ip=_ip)
        _info (" admin network created on {}\n".format(self.masterhost))


        assert (isinstance(self.controllers, list))

        if not self.controllers and self.controller:
            # Add a default controller
            info( '*** Adding controller\n' )
            classes = self.controller
            if not isinstance( classes, list ):
                classes = [ classes ]
            for i, cls in enumerate( classes ):
                # Allow Controller objects because nobody understands partial()
                if isinstance( cls, Controller ):
                    self.addController( cls )
                else:
                    self.addController( 'c%d' % i, cls )

#        from ssh import SSH
        # prepare SSH connection to the master

        info( '*** Adding hosts:\n' )

        # == Hosts ===========================================================
        for hostName in topo.hosts():
            _ip = "{}/{}".format(ipAdd( self.adminNextIP, ipBaseNum=self.adminIpBaseNum, prefixLen=self.adminPrefixLen),self.adminPrefixLen)
            self.adminNextIP += 1
#            __ip= newAdminIp(admin_ip)
            self.addHost( name=hostName,
                    admin_ip= _ip,
                    loop=self.loop,
                    master=self.masterSsh,
                    username=self.user,
                    bastion=bastion,
                    client_keys=self.client_keys,
                    waitStart=waitStart,
                    **topo.nodeInfo( hostName ))
            info( hostName + ' ' )

        info( '\n*** Adding switches:\n' )
        for switchName in topo.switches():
            _ip = "{}/{}".format(ipAdd( self.adminNextIP, ipBaseNum=self.adminIpBaseNum, prefixLen=self.adminPrefixLen),self.adminPrefixLen)
            self.adminNextIP += 1
            self.addSwitch( name=switchName,
                    admin_ip=_ip,
                    loop=self.loop,
                    master=self.masterSsh,
                    username=self.user,
                    bastion=bastion,
                    client_keys=self.client_keys,
                    waitStart=waitStart,
                    **topo.nodeInfo( switchName ))
            info( switchName + ' ' )


        if not waitStart:
            nodes = self.hosts + self.switches

            _info ("[starting\n")
            for node in nodes:
                _info ("connectTarget {} ".format( node.name))
                node.connectTarget()

            for node in nodes:
                node.waitConnectedTarget()
                _info ("connectedTarget {} ".format( node.name))

            for node in nodes:
                _info ("createContainer {} ".format( node.name))
                node.createContainer()

            for node in nodes:
                node.waitCreated()
                _info ("createdContainer {} ".format(node.name))
           
            for node in nodes:
                _info ("create admin interface {} ".format( node.name))
                node.addContainerInterface(intfName="admin", brname="admin-br", wait=False)

            for node in nodes:
                node.targetSshWaitOutput()
                _info ("admin interface created on {} ".format( node.name))
            _info ("\n")

            cmds = []
            for node in nodes:
                cmds = cmds + node.connectToAdminNetwork(master=node.masternode.host, target=node.target, link_id=CloudLink.newLinkId(), admin_br="admin-br", wait=False)
            if len (cmds) > 0:
                cmd = ';'.join(cmds)
                self.masterSsh.cmd(cmd) 

            for node in nodes:
                node.configureContainer(wait=False)
            for node in nodes:
                node.targetSshWaitOutput()

            for node in nodes:
                _info ("connecting {} ".format( node.name))
                node.connect()

            for node in nodes:
                node.waitConnected()
                _info ("connected {} ".format( node.name))

            for node in nodes:
                _info ("startshell {} ".format( node.name) )
                node.asyncStartShell()
            for node in nodes:
                node.waitStarted()
                _info ("startedshell {}".format( node.name))

            for node in nodes:
                _info ("finalize {}".format( node.name))
                node.finalizeStartShell()
            _info ("\n")

        info( '\n*** Adding links:\n' )
        for srcName, dstName, params in topo.links(
                sort=True, withInfo=True ):
            self.addLink( **params )
            info( '(%s, %s) ' % ( srcName, dstName ) )
        info( '\n' )

    def configureControlNetwork( self ):
        "Control net config hook: override in subclass"
        raise Exception( 'configureControlNetwork: '
                         'should be overriden in subclass', self )

    def build( self ):
        "Build mininet."
        if self.topo:
            self.buildFromTopo( self.topo )

##            self.configureControlNetwork()
        info( '*** Configuring hosts\n' )
        self.configHosts()
##        if self.xterms:
##            self.startTerms()
#        if self.autoStaticArp:
#            self.staticArp()
        self.built = True

    def startTerms( self ):
        "Start a terminal for each node."
        if 'DISPLAY' not in os.environ:
            error( "Error starting terms: Cannot connect to display\n" )
            return
        info( "*** Running terms on %s\n" % os.environ[ 'DISPLAY' ] )
        cleanUpScreens()
        self.terms += makeTerms( self.controllers, 'controller' )
        self.terms += makeTerms( self.switches, 'switch' )
        self.terms += makeTerms( self.hosts, 'host' )

    def stopXterms( self ):
        "Kill each xterm."
        for term in self.terms:
            os.kill( term.pid, signal.SIGKILL )
        cleanUpScreens()

    def staticArp( self ):
        "Add all-pairs ARP entries to remove the need to handle broadcast."
        for src in self.hosts:
            for dst in self.hosts:
                if src != dst:
                    src.setARP( ip=dst.IP(), mac=dst.MAC() )

    # DSA - OK
    def start( self ):
        "Start controller and switches."
        if not self.built:
            self.build()
        info( '*** Starting controller\n' )
        for controller in self.controllers:
            info( controller.name + ' ')
            controller.start()
        info( '\n' )
        info( '*** Starting %s switches\n' % len( self.switches ) )
        for switch in self.switches:
            info( switch.name + ' ')
            switch.start( self.controllers )
        started = {}
        for switch in self.switches:
            success = switch.batchStartup([switch])
            started.update( { s: s for s in success } )
#        for swclass, switches in groupby(
#                sorted( self.switches,
#                        key=lambda s: str( type( s ) ) ), type ):
#            switches = tuple( switches )
#            if hasattr( swclass, 'batchStartup' ):
#                success = swclass.batchStartup( switches )
#                started.update( { s: s for s in success } )
        info( '\n' )
        if self.waitConn:
            self.waitConnected()


    def stop( self ):
        "Stop the switches, hosts and controller(s) "
        if self.terms:
            info( '*** Stopping %i terms\n' % len( self.terms ) )
            self.stopXterms()
        info( '*** Stopping %i links\n' % len( self.links ) )
        for link in self.links:
            info( '.' )
            link.stop()
        info( '\n' )
        info( '*** Stopping %i switches\n' % len( self.switches ) )
        stopped = {}
########        for switch in self.switches:
########           success = switch.batchShutdown([switch])
########            stopped.update( { s: s for s in success } )
#        for swclass, switches in groupby(
#                sorted( self.switches,
#                        key=lambda s: str( type( s ) ) ), type ):
#            switches = tuple( switches )
#            if hasattr( swclass, 'batchShutdown' ):
#                success = swclass.batchShutdown( switches )
#                stopped.update( { s: s for s in success } )
        for switch in self.switches:
            info( switch.name + ' ' )
            if switch not in stopped:
                switch.stop()
            switch.terminate()
        info( '\n' )
        info( '*** Stopping %i hosts\n' % len( self.hosts ) )
        for host in self.hosts:
            info( host.name + ' ' )
            host.terminate()

        info( '*** Stopping %i controllers\n' % len( self.controllers ) )
        for controller in self.controllers:
            info( controller.name + ' ' )
            controller.stop()
        info( '\n' )
       
        info( '*** cleaning master\n' )
        # XXX DSA need to find something nicer
        for node in self.hosts + self.switches + self.controllers:
            _info ("wait {} ".format( node ))
            node.targetSshWaitOutput()
            for device in node.devicesMaster:
                _info ("delete device {} on master ".format(device))
                self.masterSsh.cmd("ip link delete {} ".format(device))
            _info ("\n")
        _info ("\n")
        self.loop.stop()
        info( '\n*** Done\n' )

    # XXX These test methods should be moved out of this class.
    # Probably we should create a tests.py for them

    def runCpuLimitTest( self, cpu, duration=5 ):
        """run CPU limit test with 'while true' processes.
        cpu: desired CPU fraction of each host
        duration: test duration in seconds (integer)
        returns a single list of measured CPU fractions as floats.
        """
        pct = cpu * 100
        info( '*** Testing CPU %.0f%% bandwidth limit\n' % pct )
        hosts = self.hosts
        cores = int( quietRun( 'nproc' ) )
        # number of processes to run a while loop on per host
        num_procs = int( ceil( cores * cpu ) )
        pids = {}
        for h in hosts:
            pids[ h ] = []
            for _core in range( num_procs ):
                h.cmd( 'while true; do a=1; done &' )
                pids[ h ].append( h.cmd( 'echo $!' ).strip() )
        outputs = {}
        time = {}
        # get the initial cpu time for each host
        for host in hosts:
            outputs[ host ] = []
            with open( '/sys/fs/cgroup/cpuacct/%s/cpuacct.usage' %
                       host, 'r' ) as f:
                time[ host ] = float( f.read() )
        for _ in range( duration ):
            sleep( 1 )
            for host in hosts:
                with open( '/sys/fs/cgroup/cpuacct/%s/cpuacct.usage' %
                           host, 'r' ) as f:
                    readTime = float( f.read() )
                outputs[ host ].append( ( ( readTime - time[ host ] )
                                        / 1000000000 ) / cores * 100 )
                time[ host ] = readTime
        for h, pids in pids.items():
            for pid in pids:
                h.cmd( 'kill -9 %s' % pid )
        cpu_fractions = []
        for _host, outputs in outputs.items():
            for pct in outputs:
                cpu_fractions.append( pct )
        output( '*** Results: %s\n' % cpu_fractions )
        return cpu_fractions

    # BL: I think this can be rewritten now that we have
    # a real link class.
    def configLinkStatus( self, src, dst, status ):
        """Change status of src <-> dst links.
           src: node name
           dst: node name
           status: string {up, down}"""
        if src not in self.nameToNode:
            error( 'src not in network: %s\n' % src )
        elif dst not in self.nameToNode:
            error( 'dst not in network: %s\n' % dst )
        else:
            src = self.nameToNode[ src ]
            dst = self.nameToNode[ dst ]
            connections = src.connectionsTo( dst )
            if len( connections ) == 0:
                error( 'src and dst not connected: %s %s\n' % ( src, dst) )
            for srcIntf, dstIntf in connections:
                result = srcIntf.ifconfig( status )
                if result:
                    error( 'link src status change failed: %s\n' % result )
                result = dstIntf.ifconfig( status )
                if result:
                    error( 'link dst status change failed: %s\n' % result )

    def interact( self ):
        "Start network and run our simple CLI."
        self.start()
        result = CLI( self )
        self.stop()
        return result

    inited = False

    @classmethod
    def init( cls ):
        "Initialize Mininet"
        if cls.inited:
            return
        cls.inited = True


class MininetWithControlNet( Mininet ):

    """Control network support:

       Create an explicit control network. Currently this is only
       used/usable with the user datapath.

       Notes:

       1. If the controller and switches are in the same (e.g. root)
          namespace, they can just use the loopback connection.

       2. If we can get unix domain sockets to work, we can use them
          instead of an explicit control network.

       3. Instead of routing, we could bridge or use 'in-band' control.

       4. Even if we dispense with this in general, it could still be
          useful for people who wish to simulate a separate control
          network (since real networks may need one!)

       5. Basically nobody ever used this code, so it has been moved
          into its own class.

       6. Ultimately we may wish to extend this to allow us to create a
          control network which every node's control interface is
          attached to."""

    def configureControlNetwork( self ):
        "Configure control network."
        self.configureRoutedControlNetwork()

    # We still need to figure out the right way to pass
    # in the control network location.

    def configureRoutedControlNetwork( self, ip='192.168.123.1',
                                       prefixLen=16 ):
        """Configure a routed control network on controller and switches.
           For use with the user datapath only right now."""
        controller = self.controllers[ 0 ]
        info( controller.name + ' <->' )
        cip = ip
        snum = ipParse( ip )
        for switch in self.switches:
            info( ' ' + switch.name )
            link = self.link( switch, controller, port1=0 )
            sintf, cintf = link.intf1, link.intf2
            switch.controlIntf = sintf
            snum += 1
            while snum & 0xff in [ 0, 255 ]:
                snum += 1
            sip = ipStr( snum )
            cintf.setIP( cip, prefixLen )
            sintf.setIP( sip, prefixLen )
            controller.setHostRoute( sip, cintf )
            switch.setHostRoute( cip, sintf )
        info( '\n' )
        info( '*** Testing control network\n' )
        while not cintf.isUp():
            info( '*** Waiting for', cintf, 'to come up\n' )
            sleep( 1 )
        for switch in self.switches:
            while not sintf.isUp():
                info( '*** Waiting for', sintf, 'to come up\n' )
                sleep( 1 )
            if self.ping( hosts=[ switch, controller ] ) != 0:
                error( '*** Error: control network test failed\n' )
                exit( 1 )
        info( '\n' )



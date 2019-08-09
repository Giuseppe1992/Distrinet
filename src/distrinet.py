# Copyright 2018 Inria Damien.Saucez@inria.fr                                                                               
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

# XXX DSA Inspired from Mininet, see how to integrate correctly their license.

import networkx as nx
from time import sleep

def irange(i,j):
    return xrange(i,j+1)

class Topo(object):
    def __init__( self, *args, **params ):
        """Topo object.
           Optional named parameters:
           hinfo: default host options
           sopts: default switch options
           lopts: default link options
           calls build()"""
        self.g = nx.MultiGraph()
        self.hopts = params.pop( 'hopts', {} )
        self.sopts = params.pop( 'sopts', {} )
        self.lopts = params.pop( 'lopts', {} )
        self.build( *args, **params )

    def build( self, *args, **params ):
        "Override this method to build your topology."
        pass

    def addNode( self, name, **opts ):
        """Add Node to graph.
           name: name
           opts: node options
           returns: node name"""
        self.g.add_node( name, **opts )
        return name

    def addHost( self, name, **opts):
        """Convenience method: Add host to graph.
           name: host name
           opts: host options
           returns: host name"""
        if not opts and self.hopts:
            opts = self.hopts
        return self.addNode( name, **opts )

    def addSwitch( self, name, **opts ):
        """Convenience method: Add switch to graph.
           name: switch name
           opts: switch options
           returns: switch name"""
        if not opts and self.sopts:
            opts = self.sopts
        result = self.addNode( name, isSwitch=True, **opts )
        return result

#### WE DO NOT SUPPORT PORTS
    #####WHY?
    def addLink( self, node1, node2, port1=None, port2=None,
            key=None, **opts ):
        """node1, node2: nodes to link together
           port1, port2: ports (optional)
           opts: link options (optional)
           returns: link info key"""
        if port1 != None or port2 != None:
            raise Exception("Ports not supported as deprecated")
        if not opts and self.lopts:
            opts = self.lopts
        opts = dict( opts )
        opts.update( node1=node1, node2=node2 )
        self.g.add_edge( node1, node2, key=key, **opts)
        return key

    def nodes( self, sort=True ):
        "Return nodes in graph"
        if sort:
            return self.sorted( self.g.nodes() )
        else:
            return self.g.nodes()

    def isSwitch( self, n ):
        "Returns true if node is a switch."
        return self.g.node[ n ].get( 'isSwitch', False )

    def switches( self, sort=True ):
        """Return switches.
           sort: sort switches alphabetically
           returns: dpids list of dpids"""
        return [ n for n in self.nodes( sort ) if self.isSwitch( n ) ]

    def hosts( self, sort=True ):
        """Return hosts.
           sort: sort hosts alphabetically
           returns: list of hosts"""
        return [ n for n in self.nodes( sort ) if not self.isSwitch( n ) ]

    def links( self, sort=False, withKeys=False, withInfo=False ):
        """Return links
           sort: sort links alphabetically, preserving (src, dst) order
           withKeys: return link keys
           withInfo: return link info
           returns: list of ( src, dst [,key, info ] )"""
   
        _links = list(self.g.edges(data=withInfo, keys=withKeys))
        if sort:
            return self.sorted(_links)
        return _links

    def linkInfo( self, src, dst, key=None ):
        "Return link metadata dict"
        entry, key = self._linkEntry( src, dst, key )
        return entry[ key ]

#### DSA - BUG, we do not set info to info, but update info with info!!!
    def setlinkInfo( self, src, dst, info, key=None ):
        self.setLinkInfo(src, dst, info, key)

    def setLinkInfo( self, src, dst, info, key=None ):
        "Set link metadata dict"
        entry, key = self._linkEntry( src, dst, key )
        for k,v in info.items():
            entry[key][k] = v

    def nodeInfo( self, name ):
        "Return metadata (dict) for node"
        return self.g.node[ name ]

#### DSA - BUG, we do not set info to info, but update info with info!!!
    def setNodeInfo( self, name, info ):
        "Set metadata (dict) for node"
        for k,v in info.items():
            self.g.node[ name ][k] = v

    # == Methods not implemented =============================================
    def addPort( self, src, dst, sport=None, dport=None ):
        raise Exception("Not implemented as deprecated")
    def port( self, src, dst ):
        raise Exception("Not implemented as deprecated")
    def convertTo( self, cls, data=True, keys=True ):
        raise Exception("Not implemented as we are using Networkx MultiGraph")


    # == Helper ==============================================================
#### WE MAKE BASIC SORTING
    @staticmethod
    def sorted( items ):
        "Items sorted"
        return sorted( items )

    def _linkEntry( self, src, dst, key=None ):
        "Helper function: return link entry and key"
        entry = self.g[ src ][ dst ]
        if key is None:
            key = min( entry )
        return entry, key

class SingleSwitchTopo( Topo ):
    "Single switch connected to k hosts."

    def build( self, k=2, **_opts ):
        "k: number of hosts"
        self.k = k
        switch = self.addSwitch( 's1' )
        for h in irange( 1, k):
            host = self.addHost( 'h%s' % h )
            self.addLink( host, switch )


#### NOT supported!
class SingleSwitchReversedTopo( Topo ):
    """Single switch connected to k hosts, with reversed ports.
       The lowest-numbered host is connected to the highest-numbered port.
       Useful to verify that Mininet properly handles custom port
       numberings."""

    def build( self, k=2 ):
        "k: number of hosts"
        self.k = k
        switch = self.addSwitch( 's1' )
        for h in irange(1, k):
            host = self.addHost( 'h%s' % h )
            self.addLink( host, switch,
                    port1=0, port2=( k - h + 1 ) )

class MinimalTopo( SingleSwitchTopo ):
    "Minimal topology with two hosts and one switch"
    def build( self ):
        return SingleSwitchTopo.build( self, k=2 )

class LinearTopo( Topo ):
    "Linear topology of k switches, with n hosts per switch."

    def build( self, k=2, n=1, **_opts):
        """k: number of switches
           n: number of hosts per switch"""
        self.k = k
        self.n = n

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % ( j, i )

        lastSwitch = None
        for i in irange( 1, k ):
            # Add switch
            switch = self.addSwitch( 's%s' % i )
            # Add hosts to switch
            for j in irange( 1, n ):
                host = self.addHost( genHostName( i, j ) )
                self.addLink( host, switch )
            # Connect switch to previous
            if lastSwitch:
                self.addLink( switch, lastSwitch )
            lastSwitch = switch

# == Spine&Leaf topology =====================================================
class SpineAndLeafTopo(Topo):
    """Implements a Spine&Leaf topology of degree k

    - k/2 spine switches
    - k leaf switches, each switch connected to all the spine switches
    - k/2 hosts per leaf switch
    """
    def spineName(self, seq):
        return "Ss%d" % (seq)

    def leafName(self, seq):
        return "Ls%d" % (seq)

    def hostName(self, leaf, seq):
        name = "Hl%ds%d" % (leaf, seq)

        assert len(name) <= 8 # stupid distem bug
        return name

    def build(self, k=2, **_opts):
        if k % 2 is not 0:
            raise Exception("k must be a multiple of 2")
        
        self.k = k
        k2 = int( k/2 )   # k/2

        # build spine
        for spine in irange(1, k2):
            spinename = self.spineName(spine)
            self.addSwitch(spinename)

        # build the leaves
        for leaf in irange(1, k):
            leafname = self.leafName(leaf)
            self.addSwitch(leafname)
            
            # connect the leaf to every spine
            for spine in irange(1, k2):
                spinename = self.spineName(spine)
                self.addLink(leafname, spinename)

            # Create k/2 hosts and connect them to the leaf
            for host in irange(1, k2):
                hostname = self.hostName(leaf, host)
                self.addNode(hostname)

                self.addLink(hostname, leafname)

# == Fat-Tree topology =======================================================
class FatTreeTopo(Topo):
    """Implements a Fat-Tree topology of degree k.

    k-ary fat tree: three-layer topology (edge, aggregation and core)
        - each pod consists of (k/2)^2 servers and 2 layers of k/2 k-port
          switches
        - each edge switch connects to k/2 servers and k/2 aggr. switches
        - each aggr. switch connects to k/2 edge and k/2 core switches
        - (k/2)^2 core switches: each connects to k pods

    see page 12 of
    https://www.cs.cornell.edu/courses/cs5413/2014fa/lectures/08-fattree.pdf
    for details
    """
    # == Helper functions ====================================================
    def coreName(self, seq):
        return "Cs%d" % (seq)

    def aggrName(self, pod, seq):
        return "Ap%ds%d" % (pod, seq)

    def edgeName(self, pod, seq):
        return "Ep%ds%d" % (pod, seq)

    def hostName(self, pod, edge, seq):
        name = "Hp%de%ds%d" % (pod, edge, seq)
        assert len(name) <= 8   # stupid distem bug...
        return name

    def build(self, k = 2, **_opts):
        # only even numbers are allowed for k
        if k % 2 is not 0:
            raise Exception("k must be a multiple of 2")

        self.k = k
        k2 = int( k/2 )     # k/2

        # build cores
        for seq in irange(1, int((k/2)**2)):
            corename = self.coreName(seq)
            self.addSwitch(corename)

        # Create Pods
        for pod in irange(1, k):
            
            # Create aggregation switches
            for aggr in irange (1, k2):
                aggrname = self.aggrName(pod, aggr)
                self.addSwitch(aggrname)
               
                # Connect it to the core switches
                for meta_pod in irange(1, k2):
                    coreid = (meta_pod - 1) * k2 + aggr 
                    corename = self.coreName(coreid)
                    self.addLink(aggrname, corename)

            # Create edge switches
            for edge in irange(1, k2):
                edgename = self.edgeName(pod, edge)
                self.addSwitch(edgename)

                # Connect it to the aggregation switches
                for aggr in irange(1, k2):
                    self.addLink(edgename, self.aggrName(pod, aggr))

                # Create hosts
                for host in irange(1, k2):
                    hostname = self.hostName(pod, edge, host)

                    self.addNode(hostname)
                    # Connect it to the edge switch
                    self.addLink(hostname, edgename)

        # Verify the number of hosts, should be k * ((k/2)**2)
        assert (len(self.hosts()) == ((k/2)**2)*k)
        # Verify the number of switches, should be
        #               (k/2)**2 cores + (k*k/2) aggr. + (k*k/2) edge.
        assert (len(self.switches()) == (k/2)**2 + k * (k/2 + k/2))

class HadoopFatTreeTopo2(FatTreeTopo):
    master=None
    def masterName(self):
        return self.master
    def build(self, k = 2, slave_image=None, master_image=None, **_opts):
        """
        Make a Fat-Tree topology and configure the hosts to be in a Hadoop
        cluster
        The first (alphabetical order) host is the master, all others are the
        slaves.
        """
        # Build the Fat-Tree topology
        FatTreeTopo.build(self, k, **_opts)

        # configure each host
        i = 0
        for host in self.hosts(sort=True):
            image = slave_image
            role = "slave"
            if i == 0:
                image = master_image
                role = "master"
                self.master = host
            self.setNodeInfo(host, {"image":image, "role":role})
            i = i + 1


# ============================================================================
###
from distem_api import distem_api
from utils_distem import distem as Distem
###

class Distrinet(object):
    inited = False

    def __init__(self, login, password, location, walltime="2:00", topo=None,  switch=None, host=None, controller=None,
            link=None, ipBase=u"10.0.0.0/24", build=True, cleanup=False) :
        """ Create a Distribet object.
                login: G5K login
                password: G5K password
                location: G5K location
                walltime: job duration in G5K
                switch: default Switch class
                host: default Host class/constructor
                controller: default Controller class/constructor
                link: default Link class/constructor
                ipBase: IP prefix for the nodes
                cleanup: whether or not we clean before building/deploying
           """
        self.cleanup = cleanup

        # G5K infos
        self.login = login
        self.password = password
        self.location = location
        self.walltime = walltime

        # Topology
        self.topo = topo
        self.ipBase = ipBase
        self.built = False              # topology is not built yet

        # component classes
        self.switch = switch
        self.host = host
        self.controller = controller
        self.link = link

        # Object to interact with G5k
        self.o = None

        # Object to interact with Distem
        self.distem_api = None

        # Define if resources have been reserved in G5K
        self.reserved = False
       
        # components
        self.hosts = []                 # host names
        self.hosts_by_name = {}         # host objects {name:object}
        self.switches = []              # switch names
        self.switches_by_name = {}      # switch objects {name:object}
        self.controllers = []           # controller names
        self.links = []                 # controller objects {name:object}

        # Initialize everything
        Distrinet.init()

        # Prepare for distem
        self.distem()

        # Automatically build the topology is asked for
        if topo and build:
            self.build()

    def getDistemApi(self):
        """Retrieve object to interact with Distem
        If the object to interact with G5K is not initialized, it will be
        initialized first.
        If the object to interact with Distem is not initialized, it will be
        initialized first.
        """
        # We need to interact with G5K
        if not self.o:
            self.distem()

        # instantiate the interaction with Distem if not done yet
        if not self.distem_api:
            self.distem_api = distem_api(coordinator=self.o.get_coordinator(), user=self.login)

        return self.distem_api

    def distem(self):
        """Initialize and return an object to interact with G5K
        """
        self.o = Distem(user=self.login, password=self.password, ip=self.ipBase)
        return self.o

    def pingAll(self, intervall=1, number=1):
        result, packet_lost = self.o.pingAll(intervall=intervall, number=number)
        return result, packet_lost

    def parallel_pingAll(self, intervall=1, number=1):
        result = self.o.parallel_pingAll(intervall=intervall, number=number)
        return result

    def clean(self):
        print "should implement properly clean()..."
        self.reserved = False

    def xterm(self, vnode_id=None, ip=None):
        try:
            self.o.xterm(vnode_id=vnode_id, ip=ip)
        except Exception:
            pass

    def addHost(self, name, cls=None, **params):
        """Add host.
           name: name of host to add
           cls: custom host class/constructor (optional)
           params: parameters for host
           returns: added host"""
        defaults = {}
        defaults.update(params)
        self.o.add_node(name, image=defaults["image"])

        if not cls:
            raise Exception("You must provide a host class")
        h = cls(name, self)

        self.hosts.append(name)
        self.hosts_by_name.update({name:h})

    def getHostByName( self, *args ):
        "Return node(s) with given name(s)"
        if len( args ) == 1:
            return self.hosts_by_name[ args[ 0 ] ]
        return [ self.hosts_by_name[ n ] for n in args ]

    # DSA - TODO - a class to support default switches
    def addSwitch(self, name, cls=None, **params):
        defaults = {}
        defaults.update(params)
        self.o.add_switch(name, image=defaults["image"])

        if not cls:
            raise Exception("You must provide a switch class")
        s = cls(name, self)

        # DSA - TODO
        self.switches.append(name)
        self.switches_by_name.update({name:s})

    def getSwitchByName( self, *args ):
        "Return node(s) with given name(s)"
        if len( args ) == 1:
            return self.switches_by_name[ args[ 0 ] ]
        return [ self.switches_by_name[ n ] for n in args ]


    def addLink(self, node1, node2, cls=None, **params):
        defaults = {}
        defaults.update(params)
        self.o.add_link(node1, node2)

        # DSA - TODO
        self.links.append( str((node1,node2)))


    def buildFromTopo(self, topo = None):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""

        if self.cleanup:
            self.clean()

        ### DSA - add controller
        if not self.controllers and self.controller:
            print "TBD"

        # Add all the hosts
        for host in topo.hosts():
            self.addHost(host, cls=Host, **topo.nodeInfo(host))

        # Add all the switches
        for switch in topo.switches():
            params = topo.nodeInfo(switch)
            self.addSwitch(switch, cls=Switch, **params)

        # Add all links
        for a, b, params in topo.links(sort=True, withInfo=True):
            self.addLink(**params)


    def build(self):
        """Build Distrinet"""
        if self.topo:
            self.buildFromTopo(self.topo)
        ###
        ###
        self.built = True

    def start(self, reservation_id=None, location=None):
        """ Start the experiment"""
        # build the topology if not done yet
        if reservation_id:
            self.reserved = True

        if not self.built:
            self.build()
        
        # reserve resources in G5K is not done yet
        if not self.reserved:
            self.reserve()

        # we can deploy the topology in G5K now
        self.deploy(reservation_id=reservation_id, location=location)


    def getIp(self, name):
        return self.o.nodes[name]["ip"]

    # == helpers =============================================================
    def deploy(self, reservation_id=None, location=None):
        if not location:
            location = self.location
        if reservation_id:
            self.o.build(reservation_id=reservation_id, location=location)
        else:
            self.o.build()
        
    def reserve(self, location=None, walltime=None):
        """Reserve resources in G5K
        """
        # The topology must be built to know the number of resources to
        # reserve
        if not self.built:
            self.build()

        if not location:
            location = self.location
        if not walltime:
            walltime = self.walltime

        self.o.reserve(location, walltime=walltime)
        self.reserved = True

    @classmethod
    def init(cls):
        """Initialize Distrinet, we need G5K VPN activated
        """
        if cls.inited:
            return
        ensureVpn()
        cls.inited = True

# == Node ====================================================================
class Node(object):
    def __init__(self, name, net=None):
        self.name = name
        self.distem_command = None
        self.net = net

    #### DSA - Only one command at a time supported for now
    def sendBlockingCmd(self, *args, **kwargs):
        """Send a command to the node and waits for its termination
        Return the result of the execution of the command
        """
         # construct the command from args
        command = " ".join([str(v) for v in args])

        return self.net.getDistemApi().execute_command_rest([self.name], command=command)
##NOO        return self.net.getDistemApi().execute_command_rest([self.name], command=command)
   

    #### DSA - Only one command at a time supported for now
    def cmd( self, *args, **kwargs ):
        """Send a command, wait for output, and return its (stdout, stderr)
        asyn: do not wait for the command to execute, return its PID
        """
        # Send the command
        results = self.sendBlockingCmd(*args, **kwargs)
        print "CMD", self.name, results

        # set execution parameters from kwargs
        asyn = kwargs.get('asyn', False)

        if asyn:
            raise Exception ("Not implemented")
        return results

class Switch(Node):
    pass

class Host(Node):
    pass

# == Utils ===================================================================
def getHadoopMaster(topo):
    """ Return one Hadoop master of the topology
    """
    for host in topo.hosts(sort=True):
        if topo.nodeInfo(host)["role"] == "master":
            return host
    raise Exception("No Hadoop master found, is it a Hadoop cluster?")

def toHadoop(topo, slave_image=None, master_image=None, **_opts):
        """
        Configure the hosts of a topology to be in a Hadoop cluster
        The first (alphabetical order) host is the master, all others are the
        slaves.
        returns the name of the host selected for being the master
        """
        master = None
        # configure each host
        for host in topo.hosts(sort=True):
            image = slave_image
            role = "slave"
            if not master:
                image = master_image
                role = "master"
                master = host
            topo.setNodeInfo(host, {"image":image, "role":role})
        return master

#### DSA - VPN to be implemented properly
VPN = True
def ensureVpn():
    """Ensure that the G5K VPN is running
    """
    if not VPN:
        raise Exception("VPN to G5K must be activated.\n")
    return

def makeFile(net, host, lines, filename, overwrite=True):
    ln = 1
    for line in lines:
        command = 'echo "%s"' % (line)
        if overwrite and ln == 1:
            command = "%s \> %s" % (command, filename)
        else:
            command = "%s \>\> %s"% (command, filename)

        net.getHostByName(host).cmd(command)
        ln = ln + 1

def makeEtcHosts(topo, net):
    """Prepare a correct /etc/hosts for the hosts in the network and put it
    in each host.

    XXX we assume that each host is connected to the network with only one
    interface.
    """
    # build the entries for /etc/hosts
    entries = list()
    
    # Add localhost
    entries.append("127.0.0.1   localhost localhost.localdomain")
    
    # Add each host
    for h in net.hosts:
        entries.append("%s   %s" %(net.getIp(h), h))

        if "role" in topo.nodeInfo(h).keys() and topo.nodeInfo(h)["role"] == "master":
            entries.append("%s   master" %(net.getIp(h)))

    # Execute the command to build /etc/hosts on each host
    for host in net.hosts:
        makeFile(net, host, entries, "/etc/hosts", overwrite=True)

def makeSlaves(topo, net):
    """ Generate the etc/hadoop/slaves file on all hosts
    """
    cluster = list()
    slaves = list()

    for host in topo.hosts():
        if "role" in topo.nodeInfo(host).keys():
            if topo.nodeInfo(host)["role"] == "slave":
                slaves.append(host)
                cluster.append(host)
            elif topo.nodeInfo(host)["role"] == "master":
                cluster.append(host)

    # Execute the command to build etc/hadoop/slaves on each host
    for host in cluster:
        makeFile(net, host, slaves, "/root/hadoop-2.7.6/etc/hadoop/slaves", overwrite=True)

def makeMasters(topo, net):
    """Generate the etc/hadoop/masters file on all the masters
    """
    masters = list()

    for host in topo.hosts():
        if "role" in topo.nodeInfo(host).keys() and topo.nodeInfo(host)["role"] == "master":
            masters.append(host)

    # Execute the command to build etc/hadoop/masters on each master
    for master in masters:
        makeFile(net, master, masters, "/root/hadoop-2.7.6/etc/hadoop/masters", overwrite=True)


def getCredentials(filename):
    import json
    s = str()
    with open(filename) as f:
        for line in f:
            s = s + line

    return json.loads(s)


if __name__ == '__main__':
    VPN = True

    credentials = getCredentials("credentials.json")

    print 
    print "# Create a Fat-Tree-4 topology"
    topo_dc = FatTreeTopo(k=6, sopts={"image":"file:///home/dsaucez/distem-fs-jessie-ovs.tar.gz"})

##    print "# Create a Spine&Leaf-4 topology"
##    topo_dc = SpineAndLeafTopo(k=4, sopts={"image":"file:///home/dsaucez/distem-fs-jessie-ovs.tar.gz"})

    master = toHadoop(topo_dc, slave_image="file:///home/dsaucez/slave.tar.gz", master_image="file:///home/dsaucez/master.tar.gz")

    print
    print "# prepare the network"
    net = Distrinet(login=credentials["login"], password=credentials["password"], location="nancy", topo=topo_dc, cleanup=True, ipBase=u"10.0.0.0/16")

    net.o.add_controller(image="file:///home/dsaucez/distem-fs-jessie-ovs.tar.gz", controller_id="c0")

    print
    print "# reserve resources in G5K"
    #net.reserve()

    print
    print "# commission nodes"
    net.start()

#    raw_input("Press enter to populate /etc/hosts")
    print
    print "# populate /etc/hosts"
    makeEtcHosts(topo=topo_dc, net=net)

#    raw_input("Press enter to configure Hadoop")
    print
    print "# populate etc/hadoop/masters"
    makeMasters(topo=topo_dc, net=net)

    print
    print "# populate etc/hadoop/slaves"
    makeSlaves(topo=topo_dc, net=net)

#    raw_input("Press enter to start the Hadoop cluster")
    print
    print "# Start Hadoop in the cluster"
    print "# Format HDFS"
    net.getHostByName(master).cmd("/root/hadoop-2.7.6/bin/hdfs namenode -format -force")

    print
    print "# Launch HDFS"
    net.getHostByName(master).cmd("/root/hadoop-2.7.6/sbin/start-dfs.sh")
    
    print 
    print "# Launch YARN"
    net.getHostByName(master).cmd("/root/hadoop-2.7.6/sbin/start-yarn.sh")

#    raw_input("Press enter to test Hadoop")
    print
    print "# Time for benchmarks!"
    print "# Create a directory for the user"
    net.getHostByName(master).cmd("/root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root")

    print
    print "# Compute PI"
    net.getHostByName(master).cmd("/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 20 100")


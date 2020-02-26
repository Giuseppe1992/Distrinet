# Copyright 2018 - 2019 Inria Damien.Saucez@inria.fr                                                                               
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
from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo, SingleSwitchTopo)


# == Utils ================================================================

def toDemo(topo):
        """
        Configure the hosts of a topology to be in a Hadoop cluster
        The first (alphabetical order) host is the master, all others are the
        slaves.
        returns the name of the host selected for being the master
        """
        master = None
        # configure each host
        if len(topo.hosts()) < 9:
            raise Exception("Not enough hosts")
        user_1, user_2, downloader_1, f1, f2, fbackup, streaming, http, nagios = topo.hosts(sort=True)[:9]
        topo.setNodeInfo(user_1, {"image":"ubuntu", "role":"user"})
        topo.setNodeInfo(user_2, {"image": "ubuntu", "role": "user"})
        topo.setNodeInfo(downloader_1, {"image": "ubuntu", "role": "downloader"})
        topo.setNodeInfo(f1, {"image": "ubuntu", "role": "firewall_1"})
        topo.setNodeInfo(f2, {"image": "ubuntu", "role": "firewall_2"})
        topo.setNodeInfo(fbackup, {"image": "ubuntu", "role": "firewall_backup"})
        topo.setNodeInfo(streaming, {"image": "streaming", "role": "streaming"})
        topo.setNodeInfo(http, {"image": "server", "role": "http"})
        topo.setNodeInfo(nagios, {"image": "nagios", "role": "nagios"})


"""class DemoTopo( Topo ):
    "Demo"

    def build( self, **_opts ):
        #toDemo(self, slave_image="ubuntu-hadoop-slave", master_image="ubuntu-hadoop-master")

    # highest node is a web node
        h1 = self.addHost( 'h1' ) #u1
        h2 = self.addHost( 'h2' ) #u2
        h3 = self.addHost( 'h3' ) #d1
        h4 = self.addHost( 'h4' ) #f1
        h5 = self.addHost( 'h5' ) #f2
        h6 = self.addHost( 'h6' ) #fbackup
        h7 = self.addHost( 'h7' ) #streaming
        h8 = self.addHost( 'h8' ) #http
        h9 = self.addHost( 'h9' ) #nagios


        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )
        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        s5 = self.addSwitch( 's5' )


        self.addLink( h1, s1 )
        self.addLink( h2, s1 )
        self.addLink( h3, s1 )
        self.addLink( s2, s1 )
        self.addLink( s2, s3 )
        self.addLink( s4, s3 )
        self.addLink( s2, s4 )
        self.addLink( s2, s5 )
        self.addLink( s4, s5 )
        self.addLink( s3, h4 )
        self.addLink( s3, h8 )
        self.addLink( s4, h5 )
        self.addLink( s4, h7 )
        self.addLink( h6, s5 )"""


from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo, SingleSwitchTopo)


# == Utils ===================================================================
def getHadoopMaster(topo):
    """ Return one Hadoop master of the topology
    """
    for host in topo.hosts(sort=True):
        if "role" in topo.nodeInfo(host) and topo.nodeInfo(host)["role"] == "master":
            return host
    raise Exception("No Hadoop master found, is it a Hadoop cluster?")


def toHadoop(topo, slave_image='ubuntu-hadoop-slave', master_image='ubuntu-hadoop-master', **_opts):
    """
    Configure the hosts of a topology to be in a Hadoop cluster
    The first (alphabetical order) host is the master, all others are the
    slaves.
    returns the name of the host selected for being the master
    """
    """    master = None
    # configure each host
    for host in topo.hosts(sort=True):
        image = slave_image
        role = "slave"
        if not master:
            image = master_image
            role = "master"
            master = host
        infos = {}
        infos.update(topo.nodeInfo(host))
        infos.update({"image": image, "role": role})
        topo.setNodeInfo(host, infos)
    return master"""

    if len(topo.hosts()) < 9:
        raise Exception("Not enough hosts")
    user_1, user_2, downloader_1, f1, f2, fbackup, streaming, http, nagios = topo.hosts(sort=True)[:9]
    topo.setNodeInfo(user_1, {"image": "ubuntu", "role": "user"})
    topo.setNodeInfo(user_2, {"image": "ubuntu", "role": "user"})
    topo.setNodeInfo(downloader_1, {"image": "ubuntu", "role": "downloader"})
    topo.setNodeInfo(f1, {"image": "ubuntu", "role": "firewall_1"})
    topo.setNodeInfo(f2, {"image": "ubuntu", "role": "firewall_2"})
    topo.setNodeInfo(fbackup, {"image": "ubuntu", "role": "firewall_backup"})
    topo.setNodeInfo(streaming, {"image": "streaming", "role": "streaming"})
    topo.setNodeInfo(http, {"image": "server", "role": "http"})
    topo.setNodeInfo(nagios, {"image": "nagios", "role": "nagios"})
    return "h1"


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

        assert len(name) <= 8  # stupid distem bug
        return name

    def build(self, k=2, **_opts):
        if k % 2 is not 0:
            raise Exception("k must be a multiple of 2")

        self.k = k
        k2 = int(k / 2)  # k/2

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
        assert len(name) <= 8  # stupid distem bug...
        return name

    def build(self, k=2, **_opts):
        # only even numbers are allowed for k
        if k % 2 is not 0:
            raise Exception("k must be a multiple of 2")

        self.k = k
        k2 = int(k / 2)  # k/2

        # build cores
        for seq in irange(1, int((k / 2) ** 2)):
            corename = self.coreName(seq)
            self.addSwitch(corename)

        # Create Pods
        for pod in irange(1, k):

            # Create aggregation switches
            for aggr in irange(1, k2):
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
                    self.setNodeInfo(hostname, self.hopts)
                    # Connect it to the edge switch
                    self.addLink(hostname, edgename)

        # Verify the number of hosts, should be k * ((k/2)**2)
        assert (len(self.hosts()) == ((k / 2) ** 2) * k)
        # Verify the number of switches, should be
        #               (k/2)**2 cores + (k*k/2) aggr. + (k*k/2) edge.
        assert (len(self.switches()) == (k / 2) ** 2 + k * (k / 2 + k / 2))


class HadoopFatTreeTopo(FatTreeTopo):
    def build(self, k=2, slave_image=None, master_image=None, **_opts):
        FatTreeTopo.build(self, k, **_opts)
        toHadoop(self, slave_image=slave_image, master_image=master_image)


class DirectHostsTopo(Topo):
    "Two hosts directly connected"

    def build(self, **_opts):
        h1 = self.addHost('master')
        h2 = self.addHost('slave1')

        self.addLink(h1, h2)


class HadoopDirectHostsTopo(Topo):
    def build(self, master_image="ubuntu-hadoop-master", slave_image="ubuntu-hadoop-slave", **_opts):
        DirectHostsTopo.build(self, **_opts)
        toHadoop(self, slave_image=slave_image, master_image=master_image)


class DumbbellTopo(Topo):
    "Dumbbell topology"

    def build(self, n=4, **_opts):
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        self.addLink(s1, s2)

        hosts = list()
        for i in range(n):
            h = self.addHost("h{}".format(i + 1))
            if i < int(n / 2):
                sw = s1
            else:
                sw = s2
            self.addLink(h, sw)
            hosts.append(h)


class LxcSingleSwitchTopo(SingleSwitchTopo):
    def __init__(self, *args, **params):
        """
        pub_id: the public key to use to connect to the nodes
        """
        self.pub_id = params.get("pub_id", None)
        super(LxcSingleSwitchTopo, self).__init__(*args, **params)

    def addHost(self, name, **opts):
        return super(LxcSingleSwitchTopo, self).addHost(name=name, image="ubuntu", pub_id=self.pub_id, cpu=1,
                                                        memory="512MB", **opts)

    def addSwitch(self, name, **opts):
        return super(LxcSingleSwitchTopo, self).addSwitch(name=name, image="switch", pub_id=self.pub_id, **opts)


class HadoopDumbbellTopo(DumbbellTopo):
    def build(self, master_image="ubuntu-hadoop-master", slave_image="ubuntu-hadoop-slave", **_opts):
        DumbbellTopo.build(self, **_opts)
        toHadoop(self, slave_image=slave_image, master_image=master_image)


class MicroBenchTopo(Topo):
    "Microbenchmark topology"

    def build(self, **_opts):
        send1 = self.addHost('snd1')
        send2 = self.addHost('snd2')

        recv1 = self.addHost('rcv1')
        recv2 = self.addHost('rcv2')

        sin = self.addSwitch('sin')
        sout = self.addSwitch('sout')
        stest = self.addSwitch('stest')

        self.addLink(send1, sin)
        self.addLink(send2, sin)

        self.addLink(sin, stest)
        self.addLink(stest, sout)
        self.addLink(recv1, sout)
        self.addLink(recv2, sout)




from mininet.topodc import (toDemo)
from time import sleep
from mininet.dutil import makeFile, makeHosts, default_images
from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo)
from mininet.cli import CLI

def demo_test(mn):
    topo = mn.topo
    for h in mn.hosts:
        cmd = "nohup iperf -s &"
        h.cmd(cmd)
    sleep(5)

    for host in mn.topos:
        if "t1" in host.name:
            rec = mn.nameToNode["t2-"+host.name.split("-")[1]]
            ip = rec.IP()
            cmd = "bash -c 'iperf -t {} -c {} > {}_to_{}.iperf &'".format(60, ip, host.name, rec)
            host.cmd(cmd)
        if "t3" in host.name:
            rec = mn.nameToNode["t4-"+host.name.split("-")[1]]
            ip = rec.IP()
            cmd = "bash -c 'iperf -t {} -c {} > {}_to_{}.iperf &'".format(60, ip, host.name, rec)
            host.cmd(cmd)
    CLI(mn)


class Tree4Topo( Topo ):
    "Demo"

    def add_tree(self,name, deep=3, root=1):
        switches = ["s{}".format(x) for x in range(root, root+(2**deep)-1)]
        hosts = ["t{}-h{}".format(name, x) for x in range(root, root+(2**deep))]
        arr_tree = [node for node in switches+hosts]
        for n in switches:
            self.addSwitch(n)
        for n in hosts:
            self.addHost(n)

        #right child = 2(n+1)
        #left child = 2n + 1
        for c,node in enumerate(switches):
            self.addLink(arr_tree[(2*c)+1],arr_tree[2*(c+1)])
        #return the root of the tree
        return switches[0]

    def build( self):

        r1 = self.add_tree("t1", 3, root=1)
        r2 = self.add_tree("t2", 3, root=21)
        r3 = self.add_tree("t3", 3, root=41)
        r4 = self.add_tree("t4", 3, root=61)

        root="s1000"
        self.addSwitch(root)
        self.addLink(root, r1)
        self.addLink(root, r2)
        self.addLink(root, r3)
        self.addLink(root, r4)


class Tree2Topo(Tree4Topo):
    def build(self):
        r1 = self.add_tree("t1", 3)
        r2 = self.add_tree("t2", 20)

        self.addLink(r1, r2)

# we need the right images to run hadoop
PREBUILD = [default_images, toDemo]
#TOPOS={}
topos = { 'demo_topo': ( lambda: Tree4Topo() ) }

# adding the test in the suite
TESTS = {'demo_test':demo_test}
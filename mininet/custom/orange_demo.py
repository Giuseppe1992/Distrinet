from mininet.topodc import (toDemo)
import time
from mininet.dutil import makeFile, makeHosts, default_images
from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo)
from mininet.cli import CLI


"""

def demo(mn):
    topo = mn.topo

    hadoopMasterNode = mn.nameToNode[hm]

    output ("# Start Hadoop in the cluster\n")
    output ("# Format HDFS\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs namenode -format -force"'))

# we need the right images to run hadoop
PREBUILD = [default_images, toDemo]

# adding the test in the suite
TESTS = {'hadoop':demo}
"""

def demo_test(mn):
    topo = mn.topo
    user_1, user_2, downloader_1, f1, f2, fbackup, streaming, http, nagios = [ mn.nameToNode[host] for host in topo.hosts(sort=True)[:9]]
    streaming_ip = streaming.IP()
    http_ip = http.IP()

    cmd=f"iptables -t nat -A PREROUTING -p tcp -m tcp --dport 8080 -j DNAT --to-destination {streaming_ip}:8080"
    output("f1", f1.cmd(cmd))
    cmd=f"iptables -t nat -A POSTROUTING -p tcp -m tcp --dport 8080 -j MASQUERADE"
    output("f1", f1.cmd(cmd))

    cmd=f"iptables -t nat -A PREROUTING -p tcp -m tcp --dport 80 -j DNAT --to-destination {http_ip}:80"
    output("f2", f2.cmd(cmd))
    cmd=f"iptables -t nat -A POSTROUTING -p tcp -m tcp --dport 80 -j MASQUERADE"
    output("f2", f2.cmd(cmd))

    cmd=f"iptables -t nat -A PREROUTING -p tcp -m tcp --dport 8080 -j DNAT --to-destination {streaming_ip}:8080"
    output("fbackup",fbackup.cmd(cmd))
    cmd=f"iptables -t nat -A POSTROUTING -p tcp -m tcp --dport 8080 -j MASQUERADE"
    output("fbackup", fbackup.cmd(cmd))

    CLI(mn)


class DemoTopo( Topo ):
    "Demo"

    def build( self):

    # highest node is a web node
        h1 = self.addHost( 'user1' ) #u1
        h2 = self.addHost( 'user2' ) #u2
        h3 = self.addHost( 'user3' ) #d1
        h4 = self.addHost( 'fw-1' ) #f1
        h5 = self.addHost( 'fw-2' ) #f2
        h6 = self.addHost( 'fw-b' ) #fbackup
        h7 = self.addHost( 'stream' ) #streaming
        h8 = self.addHost( 'http' ) #http
        h9 = self.addHost( 'nagios' ) #nagios


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
        self.addLink( h6, s5 )
        self.addLink(h9, s2)
        #default_images(topo=self)
        #toDemo(self)

# we need the right images to run hadoop
PREBUILD = [default_images, toDemo]
#TOPOS={}
topos = { 'demo_topo': ( lambda: DemoTopo() ) }

# adding the test in the suite
TESTS = {'demo_test':demo_test}
from mininet.topodc import (toDemo)
import time
from mininet.dutil import makeFile, makeHosts, default_images
from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo)


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

class DemoTopo( Topo ):
    "Demo"

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

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
        self.addLink( h6, s5 )

PREBUILD = [default_images, toDemo]

topos={"demo":( lambda: DemoTopo() )}
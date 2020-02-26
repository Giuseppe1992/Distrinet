from mininet.topodc import (toDemo)
import time
from mininet.dutil import makeFile, makeHosts, default_images
from mininet.log import info, debug, warn, error, output





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

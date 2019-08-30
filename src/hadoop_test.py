from distrinet.topodc import (toHadoop, getHadoopMaster)
import time
from util import makeFile, makeHosts

import default_image

def aliasMaster(topo, net):
    master = getHadoopMaster(topo)
    print ("The master is {} ".format(master))

    lines = []
    line = "{} {}".format(net.nameToNode[master].IP(), "master")
    lines.append(line)
    for host in topo.hosts():
        lines.append("{} {}".format(net.nameToNode[host].IP(), host))
    print (" >>> {}".format(lines))
    for host in topo.hosts():
        print ("\t Adding to host {}".format(lines))
        makeFile(net=net, host=host, lines=lines, filename="/etc/hosts", overwrite=False)

def makeMasters(topo, net):
    """Generate the etc/hadoop/masters file on all the masters
    """
    masters = list()

    for host in topo.hosts():
        if "role" in topo.nodeInfo(host).keys() and topo.nodeInfo(host)["role"] == "master":
            masters.append(host)

    # Execute the command to build etc/hadoop/masters on each master
    for master in masters:
        makeFile(net, master, masters, "/root/hadoop-2.7.6/etc/hadoop/masters", overwrite=False)

def makeSlaves(topo, net):
    """ Generate the etc/hadoop/slaves file on all hosts
    """
    cluster = list()
    slaves = list()

    hosts = topo.hosts()
    for host in hosts:
        if "role" in topo.nodeInfo(host).keys():
            if topo.nodeInfo(host)["role"] == "slave":
                slaves.append(host)
                cluster.append(host)
            elif topo.nodeInfo(host)["role"] == "master":
                cluster.append(host)

    # Execute the command to build etc/hadoop/slaves on each host
    for host in cluster:
        makeFile(net, host, slaves, "/root/hadoop-2.7.6/etc/hadoop/slaves", overwrite=False)

def hadoop_test(mn):
    print (dir(mn))
    topo = mn.topo
    aliasMaster(topo=topo, net=mn)
    print ("# populate etc/hadoop/masters")
    makeMasters(topo=topo, net=mn)

    print
    print ("# populate etc/hadoop/slaves")
    makeSlaves(topo=topo, net=mn)

    hm = getHadoopMaster(topo)
    hadoopMasterNode = mn.nameToNode[hm]

    print ("# Start Hadoop in the cluster")
    print ("# Format HDFS")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs namenode -format -force"'))

    print ("# Launch HDFS")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-dfs.sh"'))

    print ("# Launch YARN")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-yarn.sh"'))

    print ("# Time for benchmarks!")
    print ("# Create a directory for the user")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root"'))
    time.sleep(2)

    print ("")
    print ("# Compute PI")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 20 100"'))

    print ("")
    print ("# Teragen")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar teragen 1000000 bench.tera"'))
    print ("# Terasort")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar terasort bench.tera bench.tera.out"'))
    print ("# Teravalidate")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar teravalidate bench.tera.out bench.tera.validate"'))


    print ("")
    print ("# Wordcount")
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop dfs -mkdir bench.wordcount"'))
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop dfs -copyFromLocal /etc/hosts bench.wordcount/hosts"'))
    print (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar wordcount bench.wordcount/hosts bench.wordcount bench.wordcount.out"'))


# we need the right images to run hadoop
PREBUILD = [default_image.default_images, toHadoop]

# adding the test in the suite
TESTS = {'hadoop':hadoop_test}

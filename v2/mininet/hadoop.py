from distrinet.topodc import ( getHadoopMaster )

#===============================================================================================
def makeFile(net, host, lines, filename, overwrite=True):
    ln = 1
    for line in lines:
        command = 'echo "%s"' % (line)
        if overwrite and ln == 1:
            command = "%s > %s" % (command, filename)
        else:
            command = "%s >> %s"% (command, filename)

        net.nameToNode[host].cmd("{}".format(command))
        ln = ln + 1

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

def aliasMaster(topo, net):
    master = getHadoopMaster(topo)
    print ("The master is {} ".format(master))
    
    line = "{} master".format(net.nameToNode[master].IP())
    print (" >>> {}".format(line))
    for host in topo.hosts():
        print ("\t Adding to host {}".format(line))
        makeFile(net=net, host=host, lines=[line], filename="/etc/hosts", overwrite=False)

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



def hadoopPrepare(net, topo):
    aliasMaster(topo=topo, net=net)
    print ("# populate etc/hadoop/masters")
    makeMasters(topo=topo, net=net)

    print ("# populate etc/hadoop/slaves")
    makeSlaves(topo=topo, net=net)

    hm = getHadoopMaster(topo)
    master = net.nameToNode[hm] 
    print ("# Start Hadoop in the cluster")
    print ("# Format HDFS")
    print (master.cmd("/root/hadoop-2.7.6/bin/hdfs namenode -format -force"))

    print ("# Launch HDFS")
    print (master.cmd("/root/hadoop-2.7.6/sbin/start-dfs.sh"))
    
    print ("# Launch YARN")
    print (master.cmd("/root/hadoop-2.7.6/sbin/start-yarn.sh"))

def hadoopPi(net, topo):
    hm = getHadoopMaster(topo)
    master = net.nameToNode[hm]

    print ("# Time for benchmarks!")
    print ("# Create an empty directory for the user")
    print (master.cmd("/root/hadoop-2.7.6/bin/hdfs dfs -rmr /user/root"))
    print (master.cmd("/root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root"))

    print ("# Compute PI")
    print (master.cmd("/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 20 100"))

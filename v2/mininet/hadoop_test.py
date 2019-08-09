#!/usr/bin/env python
#import os
#import sys
import time
from time import sleep

# Fix setuptools' evil madness, and open up (more?) security holes
#if 'PYTHONPATH' in os.environ:
#    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

from distrinet.topodc import (HadoopDumbbellTopo, getHadoopMaster)

from distrinet.cloud.cloudcontroller import (LxcRemoteController)

from distrinet.cloud.lxc_container import (LxcNode)
from distrinet.cloud.cloudswitch import (LxcOVSSwitch)
from distrinet.cloud.cloudlink import (CloudLink)
from distrinet.distrinet import (Distrinet)


def makeFile(net, host, lines, filename, overwrite=True):
    ln = 1
    for line in lines:
        command = 'echo %s' % (line)
        if overwrite and ln == 1:
            command = "%s > %s" % (command, filename)
        else:
            command = "%s >> %s"% (command, filename)

        net.nameToNode[host].cmd('bash -c "{}"'.format(command))
        ln = ln + 1

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
        makeFile(net, host, slaves, "/root/hadoop-2.7.6/etc/hadoop/slaves", overwrite=True)

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
        makeFile(net, master, masters, "/root/hadoop-2.7.6/etc/hadoop/masters", overwrite=True)
def ip2name(ip):
    return "ip-" + ip.replace(".", "-")




if __name__ == "__main__":
    host, switch, link = LxcNode, LxcOVSSwitch, CloudLink

    pub_id = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDgEnskmrOMpOht9KZV2rIYYLKkw4BSd8jw4t9cJKclE9BEFyPFr4H4O0KR85BP64dXQgAYumHv9ufnNe1jntLhilFql2uXmLcaJv5nDFdn7YEd01GUN2QUkNy6yguTO8QGmqnpKYxYiKz3b8mWDWY2vXaPvtHksaGJu2BFranA3dEuCFsVEP4U295z6LfG3K0vr+M0xawhJ8GRUnX+EyjK5rCOn0Nc04CmSVjIpNazyXyni4cW4q8FUADtxoi99w9fVIlFcdMAgoS65FxAxOF11bM6EzbJczdN4d9IjS4NPBqcWjwCH14ZWUAXvv3t090tUQOLGdDOih+hhPjHTAZt root@7349f78b2047"
    topo = HadoopDumbbellTopo(pub_id=pub_id, sopts={"image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":8, "memory":"2GB"}, hopts={"image":"ubuntu", 'pub_id':pub_id, "cpu":4, "memory":"8GB"}, lopts={"rate":1000})

    hosts = topo.hosts()
    n = len(hosts)
    for i in range(int(n/2)):
        print ("iperf {} <> {}".format(hosts[i], hosts[-i-1]))

#DSA#    from distrinet.cloud.awsprovisiondsaucez import distrinetAWS
#DSA#
#DSA#    vpcname = "demo_{}".format(int(time.time()))
#DSA#    o = distrinetAWS(VPCName=vpcname, addressPoolVPC="10.0.0.0/16", publicSubnetNetwork='10.0.0.0/24',
#DSA#                     privateSubnetNetwork='10.0.1.0/24',
#DSA#                     bastionHostDescription={"numberOfInstances": 1, 'instanceType': 't2.2xlarge', 'KeyName': 'pub_dsaucez',
#DSA#                                             'ImageId': 'ami-03bca18cb3dc173c9',
#DSA#                                             "BlockDeviceMappings":[{"DeviceName": "/dev/sda1","Ebs" : { "VolumeSize" : 50 }}]},
#DSA#                     workersHostsDescription=[{"numberOfInstances": 1, 'instanceType': 't2.2xlarge',
#DSA#                                               'ImageId': 'ami-03bca18cb3dc173c9',
#DSA#                                               "BlockDeviceMappings":[{"DeviceName": "/dev/sda1","Ebs" : { "VolumeSize" : 50 }}]}
#DSA#                                              ])
#DSA#    print(o.ec2Client)
#DSA###    start = time()
#DSA#    jump, master, workerHostsPrivateIp = o.deploy()
#DSA#    cluster = [master] + workerHostsPrivateIp
#DSA##    print (jump, master, workerHostsPrivateIp)
#DSA##    print (cluster)
#DSA##    print(o.deploy())
#DSA##    print("Environment ready in {} seconds".format(time() - start))
#DSA#
#DSA#    master = ip2name(master)
#DSA#    cname = []
#DSA#    for n in cluster:
#DSA#        cname.append(ip2name(n))
#DSA#    cluster = cname
    jump= "35.181.125.65"
    master="ip-10-0-0-49"
    cluster= ['ip-10-0-0-49', 'ip-10-0-1-253']
    print ("jump:", jump, "mastername:", master, "clustername:", cluster)
    

#    jump="35.181.129.103"
#    master="ip-10-0-0-239"
#    cluster = ['ip-10-0-0-239', 'ip-10-0-1-13']

    print ("# sleep 60s to wait for LXD to do its magic")
##    sleep(60)

    ipBase='10.0.0.0/8'
    inNamespace=False
    xterms=False
    autoSetMacs=True
    waitConnected=False
    autoSetMacs=False
    autoStaticArp=False
    autoPinCpus=False
    listenPort=6654
    user="root"
    build=False

    # mapper
    from distrinet.dummymapper import RoundRobbinMapper
    mapper = RoundRobbinMapper(physical=cluster)
    print ("targets:", mapper.physical)
    print ("\t\t", mapper.place(1))

    # DSA - TODO - not really nice, need to clean that
    from distrinet.cloud.sshutil import name2IP
    name2IP.eyeball=master
    name2IP.user=user

    print ("JUMP!",jump)
    mn = Distrinet(
            topo=topo,
            switch=switch, host=host, #controller=controller,
            link=link,
            ipBase=ipBase, inNamespace=inNamespace,
            xterms=xterms, autoSetMacs=autoSetMacs,
            autoStaticArp=autoSetMacs, autoPinCpus=autoPinCpus,
            listenPort=listenPort, build=build, jump=jump, master=master, mapper=mapper, user=user, waitConnected=waitConnected)

    mn.addController(name='c0', controller=LxcRemoteController, ip="192.168.42.1", port=6633 )

    mn.build()
    print (dir (mn))
    print (mn.hosts)
    mn.start()

    print ("Wait 60s for LLDP and STP to do their magic")
    sleep(60)
    
    aliasMaster(topo=topo, net=mn)
    print ("# populate etc/hadoop/masters")
    makeMasters(topo=topo, net=mn)

    print
    print ("# populate etc/hadoop/slaves")
    makeSlaves(topo=topo, net=mn)

    hm = getHadoopMaster(topo)
    master = mn.nameToNode[hm]

    print ("# Start Hadoop in the cluster")
    print ("# Format HDFS")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs namenode -format -force"'))

    print ("# Launch HDFS")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-dfs.sh"'))

    print ("# Launch YARN")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-yarn.sh"'))

    print ("# Time for benchmarks!")
    print ("# Create a directory for the user")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root"'))
    sleep(2)

    print ("")
    print ("# Compute PI")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 20 100"')) 

    print ("")
    print ("# Teragen")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar teragen 1000000 bench.tera"'))
    print ("# Terasort")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar terasort bench.tera bench.tera.out"'))
    print ("# Teravalidate")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar teravalidate bench.tera.out bench.tera.validate"'))


    print ("")
    print ("# Wordcount")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop dfs -mkdir bench.wordcount"'))
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop dfs -copyFromLocal /etc/hosts bench.wordcount/hosts"'))
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar wordcount bench.wordcount/hosts bench.wordcount bench.wordcount.out"'))
    
    input("press a key to clean stop")
    mn.stop()

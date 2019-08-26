#!/usr/bin/env python
#import os
#import sys
import time
from time import sleep

# Fix setuptools' evil madness, and open up (more?) security holes
#if 'PYTHONPATH' in os.environ:
#    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

from distrinet.topodc import (HadoopDumbbellTopo, getHadoopMaster, DumbbellTopo)

from distrinet.cloud.cloudcontroller import (LxcRemoteController, RyuNativeController, OnosNativeController)

from distrinet.cloud.lxc_container import (LxcNode)
from distrinet.cloud.cloudswitch import (LxcOVSSwitch)
from distrinet.cloud.cloudlink import (CloudLink)
from distrinet.distrinet import (Distrinet)

from util import makeFile, makeHosts

from optparse import OptionParser


def iperf_test(topo, mn):
    # iperf servers
    print ("# start iperf -s")
    for h in mn.hosts:
        print ("#   on {}".format(h))
        h.cmd("nohup iperf -s &")

    # iperf clients
    l = len(mn.hosts)
    half = int(l/2)
    print ("# measure bandwidth")
    for i in range(half-1):
        print ("#   between {} and {}".format(mn.hosts[i], mn.hosts[-i-1]))
        t = 120
        mn.hosts[i].sendCmd("iperf -t {} -c {}".format(t, mn.hosts[-i-1]) )


    def _parseIperf( iperfOutput ):
        import re
        """Parse iperf output and return bandwidth.
           iperfOutput: string
           returns: result string"""
        r = r'([\d\.]+ \w+/sec)'
        m = re.findall( r, iperfOutput )
        if m:
            return m[-1]
        else:
            # was: raise Exception(...)
            error( 'could not parse iperf output: ' + iperfOutput )
            return ''

    print ("# real test between {} and {}".format(mn.hosts[half-1], mn.hosts[-(half-1)-1]))
    time.sleep(10)
    iperfOutput = mn.hosts[half-1].cmd("iperf -t {} -c {}".format(60, mn.hosts[-(half-1)-1]) )
    print (_parseIperf(iperfOutput))

    for i in range(half-1):
        print ("# waiting for background traffic to stop (may take up to {}s)".format(t))
        mn.hosts[i].waitOutput()



def hadoop_test(topo,mn):
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

    from distrinet.topodc import (HadoopDumbbellTopo, getHadoopMaster)

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
    sleep(2)

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


"""
Example:
    python3 tests.py -n 10  --bastion "52.47.186.84" --cluster="ip-10-0-0-39,ip-10-0-1-247"
"""
if __name__ == "__main__":
    import time
    start = time.time()

    host, switch, link = LxcNode, LxcOVSSwitch, CloudLink

    parser = OptionParser()
    parser.add_option("-n", dest="n", default=4,
                      help="number of hosts to emulate", metavar="n")
    parser.add_option("-s", "--single", dest="single", default=False,
                      action="store_true", help="Should we run the experiment on one machine only", metavar="single")
    parser.add_option("--hadoop", dest="hadoop", default=False,
                      action="store_true", help="Should we run the Hadoop experiment", metavar="hadoop")
    parser.add_option("--iperf", dest="iperf", default=False,
                      action="store_true", help="Should we run the iperf experiment", metavar="iperf")
    parser.add_option("-b","--bastion", dest="bastion",
                      help="bsation node", metavar="bastion")
    parser.add_option("-c","--cluster", dest="cluster",
                      help="clusters nodes (their LXC name)", metavar="cluster")
    (options, args) = parser.parse_args()

    from provision import Provision
    conf = Provision.get_configurations()
    ssh_conf = conf["ssh"]
    pub_id = ssh_conf["pub_id"]
    client_keys = ssh_conf["client_keys"]
    user = ssh_conf["user"]
    jump = ssh_conf.get("bastion", None)

    # number of hosts in the dumbbell
    n = int(options.n)

    if options.hadoop:
        topo = HadoopDumbbellTopo(n=n, pub_id=pub_id, sopts={"image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":8, "memory":"2GB"}, hopts={"image":"ubuntu", 'pub_id':pub_id, "cpu":4, "memory":"8GB"}, lopts={"rate":1000})
        test = hadoop_test
    else:
        topo = DumbbellTopo(n=n, pub_id=pub_id, sopts={"image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":1, "memory":"2GB"}, hopts={"image":"ubuntu", 'pub_id':pub_id, "cpu":1, "memory":"2GB"}, lopts={"rate":1000,"bw":1000})
        test = iperf_test


    # should we deploy to Amazon first?
    #    nope
    if options.bastion:
        jump = options.bastion

    if options.cluster:
        cluster = options.cluster.split(",")
        master = cluster[0]
    
    # we have to deploy first
    if jump is None:
        print ("# Deploy on Amazon")
        from distrinet.cloud.awsprovision import distrinetAWS

        vpcname = "demo_{}".format(int(time.time()))
        o = distrinetAWS(VPCName=vpcname, addressPoolVPC="10.0.0.0/16", publicSubnetNetwork='10.0.0.0/24',
                         privateSubnetNetwork='10.0.1.0/24',
                         bastionHostDescription={'instanceType': 't3.2xlarge',
                                                 "BlockDeviceMappings":[{"DeviceName": "/dev/sda1",
                                                                         "Ebs" : { "VolumeSize" : 50 }}]},
                         workersHostsDescription=[{"numberOfInstances": 2, 'instanceType': 't3.2xlarge',
                                                   "BlockDeviceMappings":[{"DeviceName": "/dev/sda1",
                                                                           "Ebs" : { "VolumeSize" : 50 }}]}
                                                  ])
        print(o.ec2Client)
        jump, master, workerHostsPrivateIp = o.deploy()
        cluster = [master] + workerHostsPrivateIp
    else:
        print ("# Already deployed")

    assert cluster, "must provide a cluster "

    print ("jump:", jump, "mastername:", master, "clustername:", cluster)

    adminIpBase='192.168.0.1/8'
    ipBase='10.0.0.0/8'
    inNamespace=False
    xterms=False
    autoSetMacs=True
    waitConnected=False
    autoSetMacs=False
    autoStaticArp=False
    autoPinCpus=False
    listenPort=6654

    build=False

    def _singleMachine(topo, cluster):
        places = {}
        hosts = topo.hosts()
        for i in range(len(hosts)):
            places[hosts[i]] = cluster[0]
        places["s1"] = cluster[0]
        places["s2"] = cluster[0]
        return places

    def _twoMachines(topo, cluster):
        places = {}
        hosts = topo.hosts()
        for i in range(len(hosts)):
            target = cluster[0]
            if i >= int(len(hosts)/2):
                target = cluster[1]
            places[hosts[i]] = target
        places["s1"] = cluster[0]
        places["s2"] = cluster[1]
        return places

    def _rounRobin(topo, cluster):
        i = 0
        places = {}
        nodes = topo.hosts() + topo.switches()
        for node in nodes:
            places[node] = cluster[i%len(cluster)]
            i = i + 1
        return places

    print ("# compute mapping")
    from distrinet.dummymapper import DummyMapper
    if options.single:
        places = _singleMachine(topo, cluster)
    else:
        places = _rounRobin(topo, cluster)

    mapper = DummyMapper(places=places)

    print ("mapping:", mapper.places)

    print ("JUMP!",jump)
    mn = Distrinet(
            topo=topo,
            switch=switch, host=host, #controller=controller,
            link=link,
            ipBase=ipBase,
            adminIpBase=adminIpBase,
            inNamespace=inNamespace,
            xterms=xterms, autoSetMacs=autoSetMacs,
            autoStaticArp=autoSetMacs, autoPinCpus=autoPinCpus,
            listenPort=listenPort, build=build, jump=jump, master=master, mapper=mapper,
            user=user,
            client_keys=client_keys,
            waitConnected=waitConnected)

    from distrinet.cloud.assh import ASsh
    masterSsh = ASsh(loop=mn.loop, host=master, username=user, bastion=jump, client_keys=client_keys)
    masterSsh.connect()
    masterSsh.waitConnected()
    mn.addController(name='c0', controller=OnosNativeController, ip="192.168.0.1", port=6633 , masterSsh=masterSsh)

    mn.build()
    print (dir (mn))
    print (mn.hosts)
    mn.start()

    elapsed = float( time.time() - start )
    print ( 'completed in %0.3f seconds\n' % elapsed )

    print ("Wait 10s for LLDP and STP to do their magic")
    sleep(10)
    
    print ("# populate /etc/hosts")
    makeHosts(topo=topo, net=mn, wait=False)
    for host in mn.hosts:
        host.waitOutput()


    print ("# configure bottleneck link to 1Gbps")
    s1=mn.get('s1')
    s2=mn.get('s2')

    links = s1.connectionsTo(s2)

    srcLink = links[0][0]
    dstLink = links[0][1]

    srcLink.config(**{ 'bw' : 1000})
    dstLink.config(**{ 'bw' : 1000})

    from mininet.cli import CLI
    CLI(mn)

    test(topo, mn)
    
    print ("# stopping the experiment")
    mn.stop()
    mn.loop.stop()

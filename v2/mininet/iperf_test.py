#!/usr/bin/env python
#import os
#import sys
import time
from time import sleep

# Fix setuptools' evil madness, and open up (more?) security holes
#if 'PYTHONPATH' in os.environ:
#    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

from distrinet.topodc import (HadoopDumbbellTopo, getHadoopMaster, DumbbellTopo)

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

def makeHosts(topo, net):
    lines = []
    for host in topo.hosts():
        lines.append("{} {}".format(net.nameToNode[host].IP(), host))
    print (" >>> {}".format(lines))
    for host in topo.hosts():
        print ("\t Adding to host {}".format(lines))
        makeFile(net=net, host=host, lines=lines, filename="/etc/hosts", overwrite=False)

def ip2name(ip):
    return "ip-" + ip.replace(".", "-")


from optparse import OptionParser
"""
Example:
    python3 iperf_test.py --pub-id="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDgEnskmrOMpOht9KZV2rIYYLKkw4BSd8jw4t9cJKclE9BEFyPFr4H4O0KR85BP64dXQgAYumHv9ufnNe1jntLhilFql2uXmLcaJv5nDFdn7YEd01GUN2QUkNy6yguTO8QGmqnpKYxYiKz3b8mWDWY2vXaPvtHksaGJu2BFranA3dEuCFsVEP4U295z6LfG3K0vr+M0xawhJ8GRUnX+EyjK5rCOn0Nc04CmSVjIpNazyXyni4cW4q8FUADtxoi99w9fVIlFcdMAgoS65FxAxOF11bM6EzbJczdN4d9IjS4NPBqcWjwCH14ZWUAXvv3t090tUQOLGdDOih+hhPjHTAZt root@7349f78b2047" -n 10  --jump "52.47.186.84" --master="ip-10-0-0-39" --cluster="ip-10-0-0-39,ip-10-0-1-247"
"""
if __name__ == "__main__":
    import time
    start = time.time()

    host, switch, link = LxcNode, LxcOVSSwitch, CloudLink

    parser = OptionParser()
    parser.add_option("--pub-id", dest="pub_id",
                      help="public key to access the cloud", metavar="pub_id")
    parser.add_option("-n", dest="n", default=4,
                      help="number of hosts to emulate", metavar="n")
    parser.add_option("-s", "--single", dest="single", default=False,
                      action="store_true", help="Should we run the experiment on one machine only", metavar="single")
    parser.add_option("-j","--jump", dest="jump",
                      help="jump node (bastion)", metavar="jump")
    parser.add_option("-m","--master", dest="master",
                      help="master node name", metavar="master")
    parser.add_option("-c","--cluster", dest="cluster",
                      help="clusters nodes (their LXC name)", metavar="cluster")
    (options, args) = parser.parse_args()

    # The public key to use
    pub_id = options.pub_id

    # number of hosts in the dumbbell
    n = int(options.n)

    topo = DumbbellTopo(n=n, pub_id=pub_id, sopts={"image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":1, "memory":"2GB"}, hopts={"image":"ubuntu", 'pub_id':pub_id, "cpu":1, "memory":"2GB"}, lopts={"rate":1000,"bw":1000})

    # should we deploy to Amazon first?
    #    nope
    if options.jump:
        print ("# Already deployed")
        assert options.master, "must provide a master when a jump is provided"
        assert options.cluster, "must provide a cluster when a jump is provided"
        deploy = False
        jump = options.jump
        master= options.master
        cluster = options.cluster.split(",")
    #    yep
    else:
        print ("# Deploy on Amazon")
        from distrinet.cloud.awsprovisiondsaucez import distrinetAWS

        vpcname = "demo_{}".format(int(time.time()))
        o = distrinetAWS(VPCName=vpcname, addressPoolVPC="10.0.0.0/16", publicSubnetNetwork='10.0.0.0/24',
                         privateSubnetNetwork='10.0.1.0/24',
                         bastionHostDescription={"numberOfInstances": 1, 'instanceType': 't3.2xlarge', 'KeyName': 'pub_dsaucez',
                                                 'ImageId': 'ami-03bca18cb3dc173c9',
                                                 "BlockDeviceMappings":[{"DeviceName": "/dev/sda1","Ebs" : { "VolumeSize" : 50 }}]},
                         workersHostsDescription=[{"numberOfInstances": 1, 'instanceType': 't3.2xlarge',
                                                   'ImageId': 'ami-03bca18cb3dc173c9',
                                                   "BlockDeviceMappings":[{"DeviceName": "/dev/sda1","Ebs" : { "VolumeSize" : 50 }}]}
                                                  ])
        print(o.ec2Client)
        jump, master, workerHostsPrivateIp = o.deploy()
        cluster = [master] + workerHostsPrivateIp

        master = ip2name(master)
        cname = []
        for n in cluster:
            cname.append(ip2name(n))
        cluster = cname

        print ("# sleep 60s to wait for LXD to do its magic")
        sleep(60)
    print ("jump:", jump, "mastername:", master, "clustername:", cluster)

#    jump="35.181.129.103"
#    master="ip-10-0-0-239"
#    cluster = ['ip-10-0-0-239', 'ip-10-0-1-13']

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
#    from distrinet.dummymapper import RoundRobbinMapper
#    mapper = RoundRobbinMapper(physical=cluster)
#    print ("targets:", mapper.physical)
#    print ("\t\t", mapper.place(1))
    
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
        
    
    print ("# compute mapping")
    from distrinet.dummymapper import DummyMapper
    if options.single:
        places = _singleMachine(topo, cluster)
    else:
        places = _twoMachines(topo, cluster)
    mapper = DummyMapper(places=places)

    print ("mapping:", mapper.places)

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

    elapsed = float( time.time() - start )
    print ( 'completed in %0.3f seconds\n' % elapsed )

    print ("Wait 60s for LLDP and STP to do their magic")
    sleep(60)
    
    print ("# populate /etc/hosts")
    makeHosts(topo=topo, net=mn)
   

    print ("# configure bottleneck link to 1Gbps")
    s1=mn.get('s1')
    s2=mn.get('s2')

    links = s1.connectionsTo(s2)

    srcLink = links[0][0]
    dstLink = links[0][1]

    srcLink.config(**{ 'bw' : 100})
    dstLink.config(**{ 'bw' : 100})
    from mininet.cli import CLI
    CLI(mn)

    print ("# start iperf -s")
    for h in mn.hosts:
        print ("#   on {}".format(h))
        h.cmd("nohup iperf -s &")

    l = len(mn.hosts)
    half = int(l/2)
    print ("# measure bandwidth")
    for i in range(half):
        print ("#   between {} and {}".format(mn.hosts[i], mn.hosts[-i-1]))
        t = 300
        if i == half - 1:
            time.sleep(10)
            t = 60
        mn.hosts[i].sendCmd("iperf -t {} -c {}".format(t, mn.hosts[-i-1]) )

    print ("# wait for results on {}".format(mn.hosts[half - 1]))
    print (mn.hosts[half -1].waitOutput())
    for i in range(half):
        mn.hosts[i].waitOutput()




    input("press a key to clean stop")
    mn.stop()

from distrinet.distrinet import (Distrinet)
from distrinet.cloud.cloud import (Cloud)
from distrinet.topodc import (FatTreeTopo, HadoopFatTreeTopo, HadoopDirectHostsTopo, HadoopDumbbellTopo, getHadoopMaster, MicroBenchTopo, DumbbellTopo)
from distrinet.mapper import (Mapper)


#===============================================================================================
def makeFile(net, host, lines, filename, overwrite=True):
    ln = 1
    for line in lines:
        command = 'echo "%s"' % (line)
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
    
    line = "{} {}".format(net.nameToNode[master].IP(), master)
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



### unitests

def testAddController1():
    c = Cloud(master="master1", slaves=["slave1"])
    m = Distrinet(cloud=c,build=False, controller=CloudController)
    name = "controller0"
    ctrl = m.addController(name)
    assert(m.controllers == [ctrl])
    assert(isinstance(ctrl, CloudController))
    assert(m.nameToNode[name] == ctrl)

def testAddHost1():
    c = Cloud(master="master1", slaves=["slave1"])
    m = Distrinet(cloud=c, build=False, host=CloudHost)
    name = "host0"
    hst = m.addHost(name)
    assert(m.hosts == [hst])
    assert(isinstance(hst, CloudHost))
    assert(m.nameToNode[name] == hst)

def testAddHost2():
    c = Cloud(master="master1", slaves=["slave1"])
    m = Distrinet(cloud=c, build=False, autoSetMacs=True, ipBase="192.0.2.0/24")
    name = "host0"
    hst = m.addHost(name)
    assert(isinstance(hst, CloudHost))
    assert(m.nameToNode[name] == hst)
    assert(m.nameToNode[name])
    
    # check MACs and IPs are correctly computed
    assert(hst.params['mac'] == '00:00:00:00:00:01')
    assert(m.nameToNode[name].params['ip'] == '192.0.2.1/24')

    name = "host1"
    hst = m.addHost(name)
    assert(m.nameToNode[name].params['mac'] == '00:00:00:00:00:02')
    assert(m.nameToNode[name].params['ip'] == '192.0.2.2/24')

def testAddSwitch1():
    c = Cloud(master="master1", slaves=["slave1"])
    m = Distrinet(cloud=c, build=False, switch=CloudSwitch)
    name = "s0"
    sw = m.addSwitch(name)
    assert(m.switches == [sw])
    assert(isinstance(sw, CloudSwitch))
    assert(m.nameToNode[name] == sw)

   
def testAddLink1():
    c = Cloud(master="master1", slaves=["slave1"])
    m = Distrinet(cloud=c, build=False, link=CloudLink, intf=CloudTCIntf, host=CloudHost)
    n1="n1"
    n2="n2"
    m.addHost(n1)
    m.addHost(n2)
    l = m.addLink(n1, n2, port1=1, port2=2, cls=CloudLink, l=1 )
    assert (m.links == [l])
    assert (isinstance(l, CloudLink))

def testHadoopPi():
    cloud = Cloud(master="grisou-8.nancy.grid5000.fr", slaves=["grisou-9.nancy.grid5000.fr"])

    topo_dc = HadoopDumbbellTopo(sopts={"image":"switch","controller":"c0", "cores":1, "memory":2000}, hopts={"image":"ubuntu", "cores":1, "memory":2000}, lopts={"rate":1000})
    print (" >>>>>>>", topo_dc.nodeInfo("master"))
    print ("      the Hadoop master is {}".format(getHadoopMaster(topo_dc)))

    from mapping_distrinet.mapping.embedding.physical import PhysicalNetwork
    from mapping_distrinet.mapping.virtual import VirtualNetwork
    from mininet.topo import Topo
    phy_topo = Topo()

    # Add nodes
    n1 = phy_topo.addHost('N1', cores=0, memory=80000)
    n2 = phy_topo.addHost('N2', cores=0, memory=80000)
    sw1 = phy_topo.addSwitch('SW')

    # Add links
    phy_topo.addLink(n1, sw1, port1="eth0", port2="eth0", rate=10000)
    phy_topo.addLink(n1, sw1, port1="eth1", port2="eth1", rate=10000)
    phy_topo.addLink(n2, sw1, port1="eth0", port2="eth1", rate=10000)
    physical_topo = PhysicalNetwork.from_mininet(phy_topo)

    virtual_topo = VirtualNetwork.from_mininet(topo_dc)

#    m = Mapper(virtual_topo=virtual_topo, physical_topo=physical_topo)
#    for n in topo_dc.nodes():
#        print (">>> {} := {}".format(n, m.place(n)))
#
#    print (m)

#    mn = Distrinet(cloud=cloud, topo = topo_dc, mapper=m, autoSetMacs=True, build=False, waitConnected=False)
    mn = Distrinet(cloud=cloud, topo = topo_dc, autoSetMacs=True, build=False, waitConnected=False)

    mn.addController("c0", image="pox-controller")

    mn.build()

    mn.start()

    mn.nameToNode["master"].setIP("192.0.2.100/24")
    mn.nameToNode["slave1"].setIP("192.0.2.101/24")
    mn.nameToNode["slave2"].setIP("192.0.2.102/24")
    mn.nameToNode["slave3"].setIP("192.0.2.103/24")

    for switch_name in topo_dc.switches():
        switch = mn.nameToNode[switch_name]
        for intf_name in switch.intfNames():
            switch.cmd("ovs-vsctl add-port {} {}".format(switch_name, intf_name))

    #    print
    aliasMaster(topo=topo_dc, net=mn)
    print ("# populate etc/hadoop/masters")
    makeMasters(topo=topo_dc, net=mn)

    print
    print ("# populate etc/hadoop/slaves")
    makeSlaves(topo=topo_dc, net=mn)

    hm = getHadoopMaster(topo_dc)
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

    print ("# Compute PI")
    print (master.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 20 100"'))


def testMapping():
    topo_dc = DumbbellTopo(sopts={"image":"switch","controller":"c0", "cores":1, "memory":1000}, hopts={"image":"ubuntu", "cores":1, "memory":1000}, lopts={"rate":1000})

    from mapping_distrinet.mapping.embedding.physical import PhysicalNetwork
    from mapping_distrinet.mapping.virtual import VirtualNetwork
    from mininet.topo import Topo
    phy_topo = Topo()

    # Add nodes
    master1 = phy_topo.addHost('master1', cores=4, memory=8000)
    slave1 = phy_topo.addHost('slave1', cores=4, memory=8000)
    sw1 = phy_topo.addSwitch('SW')

    # Add links
    phy_topo.addLink(master1, sw1, port1="enp0s8", port2="eth0", rate=10000)
    phy_topo.addLink(slave1, sw1, port1="enp0s8", port2="eth1", rate=10000)
    physical_topo = PhysicalNetwork.from_mininet(phy_topo)

    virtual_topo = VirtualNetwork.from_mininet(topo_dc)
    m = Mapper(virtual_topo=virtual_topo, physical_topo=physical_topo)
    m.solve()
    for n in topo_dc.nodes():
        print (">>> {} := {}".format(n, m.place(n)))

    print("topo_dc.links():",topo_dc.links())
    print("topo_dc.g.edges():",topo_dc.g.edges())
    print("virtual_topo._g.edges:",virtual_topo._g.edges)

    print (" ")
    print ("\tsol.node_mapping:",m.prob.solution.node_mapping)
    print ("\tsol.link_mapping:",m.prob.solution.link_mapping)
    print ("\tsol.paths:",m.prob.solution.paths)


    print ("********************************")
    for link in topo_dc.links():
#        if link in m.prob.solution.link_mapping:
        print ("{}".format(link))
        try:
            for p in m.placeLink(link):
                print ("\t{}:{} , {}:{}".format( p.s_node, p.s_device, p.d_node, p.d_device))
        except Exception as e:
            print (e)
            pass
    cloud = Cloud(master="master1", slaves=["slave1"])
    mn = Distrinet(cloud=cloud, topo = topo_dc, mapper=m, autoSetMacs=True, build=False, waitConnected=False)
    mn.build()
    print ("ICI")

def testMicroBench():
    cloud = Cloud(master="master1", slaves=["slave1"])

    topo_dc = MicroBenchTopo(sopts={"image":"switch","controller":"c0"}, hopts={"image":"ubuntu"}, lopts={})

    mn = Distrinet(cloud=cloud, topo = topo_dc, autoSetMacs=True, build=False, waitConnected=False)
    mn.addController("c0", image="pox-controller")

    mn.build()
    mn.start()
    
    
    for host in mn.hosts:
        host.setARP(ip="192.168.254",mac="00:16:3e:e9:4b:11")
        host.setHostRoute(ip="192.168.254", intf="eth0")

    # add all ports to switches
    for switch_name in topo_dc.switches():
        switch = mn.nameToNode[switch_name]
        for intf_name in switch.intfNames():
            switch.cmd("ovs-vsctl add-port {} {}".format(switch_name, intf_name))

    from time import sleep
    print ("Setup benchmark...")
    sleep(60)
    i = 0
    for host in mn.hosts:
        i = i + 1
        print ("{}. Install on host {}".format(i, host))
        print (host.cmd("apt install -y iperf3"))
        print (host.cmd("iperf3 -s -D"))


if __name__ == '__main__':
#    testMicroBench()
    testMapping()

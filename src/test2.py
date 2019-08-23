from distrinet.distrinet import (Distrinet)
from distrinet.cloud.cloud import (Cloud)
from distrinet.topodc import (FatTreeTopo)

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
    m = Distrinet(cloud=c, build=False, link=CloudLink, intf=CloudIntf, host=CloudHost)
    n1="n1"
    n2="n2"
    m.addHost(n1)
    m.addHost(n2)
    l = m.addLink(n1, n2, port1=1, port2=2, cls=CloudLink, l=1 )
    assert (m.links == [l])
    assert (isinstance(l, CloudLink))

###########################################################
if __name__ == '__main__':
#    testAddController1()
#
#    testAddHost1()
#    testAddHost2()
#
#    testAddSwitch1()
#
#    testAddLink1()

    cloud = Cloud(master="ma", slaves=["sl"])

#    topo_dc = FatTreeTopo(k=2, sopts={"image":"switch","controller":"c0"}, hopts={"image":"ubuntu"}, lopts={'l':1})

    from mininet.topo import Topo
    topo_dc = Topo()

    topo_dc.addSwitch("s1",image="switch")
    topo_dc.addSwitch("s2",image="switch")
    topo_dc.addSwitch("s3",image="switch")

    topo_dc.addHost("h1")
    topo_dc.addHost("h2")

    topo_dc.addLink("s1","s3")
    topo_dc.addLink("s2", "s3")
    topo_dc.addLink("h1", "s1")
    topo_dc.addLink("h2", "s2")


    mn = Distrinet(cloud=cloud, topo = topo_dc, autoSetMacs=True, build=False, waitConnected=False)

    mn.addController("c1", image="pox-controller", target="ma", ip_address="192.168.100.2/24")

    mn.build()

    mn.start()

#    print (">>> run a command")
#    mn.getNodeByName("Hp2e1s1").cmd("touch COUCOU666")
    exit()

    verbose = False
    if verbose:
        print ("Switches:")
        for s in mn.switches:
            print ("\t",s)
        print ("------------------------")

        print ("Hosts:")
        for h in mn.hosts:
            print ("\t", h)
        print ("------------------------")

        print ("Controllers:")
        for c in mn.controllers:
            print("\t", c)
        print ("------------------------")

        print ("Links:")
        for l in mn.links:
            print("\t", l)
        print ("------------------------")

    mn.start()

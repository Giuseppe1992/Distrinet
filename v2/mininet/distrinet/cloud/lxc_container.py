from distrinet.cloud.container import (Container)
from distrinet.cloud.cloudlink import (CloudLink)
from distrinet.cloud.sshutil import (name2IP, RemotePopen)

intfnum=0
def genIntfName():
    global intfnum
    intfnum = intfnum + 1
    return "intf{}".format(intfnum)

class LxcNode(Container):
    connectedToAdmin = {}
    def __init__(self, name, master, target=None, admin_ip=None, user="rootXXX", jump=None, **params):
        """
        name: name of the node
        target: host where to run the node
        admin_ip: address used to connect to the node
        ssh: ssh client to connect to the target
        """
        super(LxcNode, self).__init__(name=name, admin_ip=admin_ip, user=user, target=target, jump=jump, master=master, **params)

        self.containerInitialized = False
        self.containerInterfaces = {}
        self.containerLinks = {}

    def addContainerInterface(self, intfName, devicename=None, brname=None, **params):
        """
        Add the interface with name intfName to the container that is
        associated to the bridge named name-intfName-br on the host
        """
        if devicename is None:
            devicename = "{}-{}".format(self.name, intfName)
            devicename = genIntfName()
        if brname is None:
            brname = "{}-br".format(devicename)
            brname = genIntfName()
        cmds = []
        cmds.append("brctl addbr {}".format(brname))
        cmds.append("lxc network attach {} {} {} {}".format(brname, self.name, devicename, intfName))
        cmds.append("ip link set up {}".format(brname))

        cmd = ";".join(cmds)
        self.sendCommand(cmd)

        self.containerInterfaces[intfName] = brname

        return brname

    def deleteContainerInterface(self, intf, **kwargs):
        if intf.name in self.containerInterfaces:
            self.sendCommand("ip link delete {}".format(self.containerInterfaces[intf.name]))
            self.waitPendingContainerActions()

    @staticmethod
    def allowInternetConnection(network, bridge):
        """"allow internet connection via the bridge"""

        cmds = []
        cmds.append('ip -4 route add dev {} {} proto static'.format(bridge, network))
        cmds.append(
            'iptables -A FORWARD -o {} -t filter -m comment --comment "generated for Distrinet Admin Network" -j ACCEPT'.format(
                bridge))
        cmds.append(
            'iptables -A FORWARD -i {} -t filter -m comment --comment "generated for Distrinet Admin Network" -j ACCEPT'.format(
                bridge))
        cmds.append(
            'iptables -A POSTROUTING -t nat -m comment --comment "generated for Distrinet Admin Network" -s {} ! -d {} -j MASQUERADE'.format(
                network, network))
        cmds.append('sysctl -w net.ipv4.ip_forward=1')
        return cmds

    @classmethod
    def createContainerLinkCommandList(cls, target1, target2, vxlan_id, vxlan_name, bridge1, bridge2, iface1=None,
                                       vxlan_dst_port=4789, **params):
        cmds = []
        if target1 != target2:
            ip1 = name2IP(target1)
            ip2 = name2IP(target2)
            if ip1 == ip2:
                return cmds
            comm = "ip link add {} type vxlan id {} remote {} local {} dstport {}".format(vxlan_name, vxlan_id, ip2,
                                                                                          ip1, vxlan_dst_port)
            if iface1:
                comm += " dev {}".format(iface1)

            cmds.append(comm)
            cmds.append("ip link set up {}".format(vxlan_name))
            cmds.append('brctl addif {} {}'.format(bridge1, vxlan_name))
            cmds.append('ip link set up {}'.format(bridge1))

        else:
            if bridge1 != bridge2:
                'the containers are in different bridge, we need to create 2 virtual interface to attach the two bridges'
                v_if1 = "v{}".format(bridge1)
                v_if2 = "v{}".format(bridge2)
                cmds.append('ip link add {} type veth peer name {}'.format(v_if1, v_if2))
                cmds.append('brctl addif {} {}'.format(bridge1, v_if1))
                cmds.append('brctl addif {} {}'.format(bridge2, v_if2))
                cmds.append('ip link set up {}'.format(v_if1))
                cmds.append('ip link set up {}'.format(v_if2))
        return cmds

    def addContainerLink(self, target1, target2, link_id, bridge1, bridge2, iface1=None,
                         vxlan_dst_port=4789, **params):
        """Add the link between 2 containers"""

        vxlan_name = "vx_{}".format(link_id)
        cmds = LxcNode.createContainerLinkCommandList(target1, target2, link_id, vxlan_name, bridge1, bridge2,
                                                           iface1=iface1, vxlan_dst_port=vxlan_dst_port, **params)

        cmd = ';'.join(cmds)
        self.sendCommand(cmd)
        link = params["link"]
        self.containerLinks[link] = vxlan_name


    def deleteContainerLink(self, link, **kwargs):
        self.sendCommand("ip link delete {}".format(self.containerLinks[link]))
        self.waitPendingContainerActions()

    def startContainer(self, **params):
        cmd = "lxc start {}".format(self.name)
        self.sendCommand(cmd)

    def stopContainer(self, **kwargs):
        self.sendCommand("lxc stop {} --force".format(self.name))
        self.waitPendingContainerActions()

    def createContainer(self, image="ubuntu", cpu=None, memory=None, **params):
        cmds = []

        # initialise the container
        cmd = "lxc init {} {}".format(image, self.name)
        # specify a target
        if self.target is not None:
            # cmd += " --target {}".format(self.target)
            cmd += " ".format(self.target)
#        cmds.append("lxc init {} {} --target {}".format(image, self.name, self.target))
        cmds.append(cmd)

        # limit resources
        if cpu:
            cmds.append("lxc config set {} limits.cpu {}".format(self.name, cpu))
        if memory:
            cmds.append("lxc config set {} limits.memory {}".format(self.name, memory))

        cmd = ";".join(cmds)
        self.sendCommand(cmd)

        if self.params.get("blocking", False):
            self.waitPendingContainerActions()
            self.containerInitialized = True
    
    def deleteContainer(self, **kwargs):
        self.sendCommand("lxc delete {}".format(self.name))
        self.waitPendingContainerActions()


    # DSA OK
    def _startContainer(self, **params):
        """
        Initialized the container and start it
        """
        # initialize the container if not yet initialized
        if not self.containerInitialized:
            # initialize the container
            self.createContainer(**params)
            self.waitPendingContainerActions()
            self.containerInitialized = True
            

        # get the location where the container is installed
        if self.target is None:
            # get the name of the target that has actually been used
            cmd = "lxc info %s | grep 'Location' | awk '{print $2}'" % (self.name)
            session = self.sendCommand(cmd)
            self.waitPendingContainerActions()
            self.target = (session.recv(1024).decode('utf-8')).rstrip()

            # establish a SSH connection with the target for future commands
            self.sshConnect(server=self.target, user=self.user, jump=self.jump)
       

        # make an admin network
        adminbr = "admin-br"
        self.addContainerInterface(intfName="admin", brname=adminbr)
        self.waitPendingContainerActions()

        # connect the admin network to the jump if not done already
        if not self.target in LxcNode.connectedToAdmin:
            assert self.jump    # DSA: what do we do if no jump is specified? where to put the admin network star?
            link_id = CloudLink.nextLinkId
            CloudLink.nextLinkId += 1
            self.connectToAdminNetwork(master=self.master, target=self.target, link_id=link_id, admin_br=adminbr, user=self.user, **params)
            self.waitPendingContainerActions()
            LxcNode.connectedToAdmin[self.target] = True

        # start the container
        self.startContainer()
        self.waitPendingContainerActions()

        # configure the container to have
        #       an admin IP address
        cmd = "lxc exec {} -- ifconfig admin {}".format(self.name, self.admin_ip)
        self.sendCommand(cmd)
        #       a public key
        if "pub_id" in params:
            cmd = "lxc exec {} -- bash -c 'echo \"{}\" >> /root/.ssh/authorized_keys'".format(self.name, params.get("pub_id"))
            self.sendCommand(cmd)
        #       a ssh server
        cmd = "lxc exec {} -- service ssh start".format(self.name)
        self.sendCommand(cmd)
        self.waitPendingContainerActions()

        # start a shell
        self._startShell()

        # the container is starting...

    def waitPendingContainerActions(self):
        """
        Wait for all pending actions related to the container to be finished
        """
        self.wait()

    @classmethod
    def createMasterAdminNetwork(cls, master, brname="admin-br", ip="192.168.42.1/24", user="root", **params):
        cmds = []
        cmds.append("brctl addbr {}".format(brname))
        cmds.append("ifconfig {} {}".format(brname, ip))
        cmd = ";".join(cmds)
        popen = RemotePopen(cmd, server=master, user=user)
        popen.wait()

    def connectToAdminNetwork(self, master, target, link_id, admin_br, user="root", **params):
        # no need to connect admin on the same machine or if it is already connected
        vxlan_name = "vx_{}".format(link_id)

        # locally
        # DSA - TODO - XXX beurk bridge2 = None
        cmds = LxcNode.createContainerLinkCommandList(target, master, link_id, vxlan_name, bridge1=admin_br, bridge2=None)
        cmd = ';'.join(cmds)
        self.sendCommand(cmd)

        # on master
        # DSA - TODO - XXX beurk bridge2 = None
        cmds = LxcNode.createContainerLinkCommandList(master, target, link_id, vxlan_name, bridge1=admin_br, bridge2=None)
        cmd = ';'.join(cmds)
        popen = RemotePopen(cmd, server=master, user=user)

        self.waitPendingContainerActions()
        popen.wait()

    # DSA - OK
    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        super(LxcNode, self).terminate()

        self.stopContainer()
        self.waitPendingContainerActions()
        self.deleteContainer()
        self.waitPendingContainerActions()

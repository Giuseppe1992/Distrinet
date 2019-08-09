import utils_g5k
from time import sleep
import ipaddress
import distem_api
from os import system

import logging

logging.basicConfig(filename='distrinet.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

class distem(object):
    def __init__(self, user, password, ip="10.149.128.0/24"):
        self.ids = set()
        self.nodes = dict()
        self.links = dict()
        self.switches = dict()
        self.controller = None
        self.user = user
        self.password = password
        self.reservation = None
        self.ip_pool = self.generate_pool(ip)
        self.coordinator = None
        self.reservation_id = None
        self.host_ips = None
        self.ip = ip
        self.controller_adm_ip = None
        logging.info("Distem Object Created")
        logging.debug("Distem Object Created USER: {}, IP_RANGE:{}".format(user,ip))

    #TODO: implement pingall to make sure that the controller is working properly
    def pingAll(self, intervall =1, number=1, **opts):
        results=[]
        packet_lost=[]
        for node in self.nodes:
            nodes_to_ping = self.nodes.keys()
            nodes_to_ping.remove(node)
            for destination in nodes_to_ping:
                result = self.ping(vnode1=node, vnode2=destination, intervall=intervall, number=number)
                results.append((node, destination, result))
                print
                print (node, destination, result)
                print

                dict_result= eval(result[1])[node]
                if dict_result["success"]=="ko":
                    packet_lost.append((node, destination, result))

        return results, packet_lost


    def ping(self, vnode1, vnode2, intervall=1, number=1):
        vnode2_ip = self.nodes[vnode2]["ip"]
        result = self.distem_api.execute_command_rest(vnodes=[vnode1], command="ping {} -i {} -c {}".format(vnode2_ip, intervall, number))
        return result

    def parallel_ping(self, source_vnodes, destination_vnode, intervall=1, number=1):
        destinantion_node_ip = self.nodes[destination_vnode]["ip"]
        result = self.distem_api.execute_command_rest(vnodes=source_vnodes,
                                                      command="ping {} -i {} -c {}".format(destinantion_node_ip, intervall,
                                                                                           number))
        return result

    def parallel_pingAll(self, intervall =1, number=1, **opts):
        results =[]
        for node in self.nodes:
            results.append((node, self.parallel_ping(source_vnodes=self.nodes.keys(), destination_vnode=node, intervall=intervall, number=number)))
        return results

    def xterm(self, vnode_id=None, ip=None):
        if vnode_id is None and ip is None:
            raise Exception("You should provide the node id or the ip")

        if vnode_id and ip:
            raise Exception("You should provide the node id or the ip, not both")

        if vnode_id:
            if vnode_id not in self.ids:
                raise Exception("Wrong id, please check the name")

            ip = self.distem_api.get_iface_ip(vnode=vnode_id, iface="ifadm").split("/")[0]

        system('xterm -e "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ProxyJump=root@{} root@{}" &'.format(self.coordinator, ip))



    def get_coordinator(self):
        if self.coordinator:
            return self.coordinator
        ######Send the request to all the hosts
        self.coordinator = self.reservation.get_coordinator(self.reservation.get_reservation_nodes())
        return self.coordinator

    def pre_build(self):
        self.assign_ports()  # OK
        self.assign_ips()  # OK
        self.assign_interfaces()  # OK
        self.assing_links()  # OK

    def get_switch_ifaces(self, switch_id):
        ifaces=[]
        for l1,l2 in self.links:
            if switch_id == l1:
                ifaces.append(self.links[(l1, l2)]["iface"][0])
            if switch_id == l2:
                ifaces.append(self.links[(l1, l2)]["iface"][1])
        return ifaces

    def reserve(self, location="nancy", walltime="2:00"):
        #self.pre_build()

        #######
        #make reservation and install distem
        #########################################################
        number_of_node = self.get_number_of_node_to_reserve() + 1
        self.reservation = utils_g5k.g5k(user=self.user, passw=self.password)
        self.reservation.make_reservation(walltime=walltime, nodes=number_of_node, location=location,
                                          command="rm -rf /home/"+self.user+"/public/test;"             
                                                  "mkdir /home/"+self.user+"/public/test;"
                                                  "kadeploy3 -f $OAR_NODE_FILE -k -a"
                                                  " http://public.nancy.grid5000.fr/~amerlin/kadeploy/jessie-x64-nfs-ovs.env;"
                                                  "touch /home/"+self.user+"/public/test/reservation_kadeploy.log;"
                                                  "/grid5000/code/bin/distem-bootstrap --enable-admin-network --vxlan-id 7;"
                                                  "touch /home/"+self.user+"/public/test/reservation_distem.log; sleep 7200;")
        self.reservation.wait_running_state_of_the_job()
        sleep(5)
        print self.reservation.get_reservation_nodes()
        self.wait_distem()
        print "Distem Ready!"

        ###########################################################
        self.reservation_id = self.reservation.reservation_id
        return self.reservation.reservation_id

    def build(self, reservation_id=None, location="nancy"):
        if reservation_id:
            self.reservation = utils_g5k.g5k(user=self.user, passw=self.password)
            self.reservation.reservation_id = reservation_id
            self.reservation.location = location
            self.reservation.reservation = self.reservation.get_reservation()
            logging.debug("Reservation info. USER: {}, RESERVATION_ID: {}, LOCATION: {} ".format(self.user,reservation_id,location))

        else:
            if self.reservation_id is None:
                raise Exception("you need to reserve before")

        self.pre_build()

        self.get_coordinator()
        print "Coordinator -->", self.coordinator
        logging.info("coordinator address: {}".format(self.coordinator))

        self.set_controller_host()
        self.host_ips = self.get_host_ips()
        self.host_ips.remove(self.coordinator)

        print "Hosts ip -->", self.host_ips

        ##### map switch with physical nodes
        self.simple_mapping()

        print
        print "SWITCHES"
        print self.switches
        print
        print "NODES"
        print self.nodes
        print
        print "LINKS"
        print self.links

        self.distem_api = distem_api.distem_api(coordinator=self.coordinator, user="gidilena")


        if self.controller:
            self.distem_api.add_vnode_rest(name=self.controller["id"], image=self.controller["image"],
                                           host=self.controller["host"], shared="true")
            self.controller_adm_ip = self.distem_api.get_iface_ip(vnode=self.controller["id"], iface="ifadm").split("/")[0]

        self.__create_vnetworks()
        self.__add_switches()
        self.__add_nodes()

        print
        print "STARTING VNODES..."
        print

        sleep(30)
        self.start_containers()
        ##configure switches
        self.switches_configuration()
        sleep(10)
        print "PLATFORM READY!"

    def __create_vnetworks(self):
        for link in self.links:
            print "\t\tDSA Link:::", link
            vnet = self.links[link]["vnet"]
            print self.distem_api.create_vnet_rest(vnet=vnet, address=self.ip, network_type="vxlan")

    def __add_switches(self):
        for switch in self.switches:
            name = switch
            image = self.switches[switch]["image"]
            host = self.switches[switch]["host"]
            print self.distem_api.add_vnode_rest(name=name, image=image, host=host, shared="false")
            print "\t\tADDITION OF  SWITCH", self.switches[switch]
            for link in self.switches[switch]["links"]:
                iface =self.links[link]["iface"][0] if link[0] == switch else self.links[link]["iface"][1]
                vnetwork = self.links[link]["vnet"]
                address = self.links[link]["ip"][0] if link[0] == switch else self.links[link]["ip"][1]
                print self.distem_api.set_vnetwork_rest(vnode=name, iface=iface, vnetwork=vnetwork, address=address)

    def __add_nodes(self):
        for node in self.nodes:
            name = node
            image = self.nodes[node]["image"]
            host = self.nodes[node]["host"]
            print self.distem_api.add_vnode_rest(name=name, image=image, host=host, shared="false")
            print "\t\tADDITION OF  HOST", self.nodes[node]
            iface = self.nodes[node]["iface"]
            vnetwork = self.nodes[node]["vnet"]
            address = self.nodes[node]["ip"]
            print self.distem_api.set_vnetwork_rest(vnode=name, iface=iface, vnetwork=vnetwork, address=address)

    def switches_configuration(self):
        if not self.controller:
            for switch in self.switches:
                print "\tDSA CONFIGURING SWITCH", switch
                ifaces= self.get_switch_ifaces(switch_id=switch)
                print self.distem_api.execute_command_rest([switch], command="ovs-vsctl add-br {}".format(switch))
                for iface in ifaces:
                    print "\t\t\tDSA: modify interface", iface, "of",switch
                    print self.distem_api.execute_command_rest([switch], command="ifconfig {} 0".format(iface))
                    print self.distem_api.execute_command_rest([switch], command="ovs-vsctl add-port {} {}".format(switch,iface))
                    print self.distem_api.execute_command_rest([switch], command="ifconfig {} promisc up".format(iface))
        else:

            for switch in self.switches:
                ifaces= self.get_switch_ifaces(switch_id=switch)
                print self.distem_api.execute_command_rest([switch], command="ovs-vsctl add-br {}".format(switch))
                for iface in ifaces:
                    print self.distem_api.execute_command_rest([switch], command="ifconfig {} 0".format(iface))
                    print self.distem_api.execute_command_rest([switch], command="ovs-vsctl add-port {} {}".format(switch,iface))
                    print self.distem_api.execute_command_rest([switch], command="ifconfig {} promisc up".format(iface))

                print self.distem_api.execute_command_rest([switch], command="ovs-vsctl set-fail-mode {} secure".format(switch))
                print self.distem_api.execute_command_rest([switch], command="ovs-vsctl set-controller {} tcp:{}:6633".format(switch, self.controller_adm_ip))

            sleep(2)
            # start controller command
            self.start_controller_commands(self.controller["id"], self.controller["type"])

            ### wait configuration and LLDP protocol
            sleep(10)

    def simple_mapping(self):
        support_list = self.host_ips[:]
        for switch in self.switches:
            self.switches[switch]["host"] = support_list.pop()

        for switch in self.switches:
            nodes = self.get_connected_nodes(switch)
            for node in nodes:
                self.nodes[node]["host"] = self.switches[switch]["host"]

    def start_controller_commands(self, controller_id, controller_type="pox"):
        if controller_type=="pox":
            print self.distem_api.execute_command_rest([controller_id], "echo '\#!/bin/bash' \> /root/start_controller.sh")
            print self.distem_api.execute_command_rest([controller_id],
                                         "echo '/root/pox/pox.py  forwarding.l2_learning   openflow.spanning_tree --no-flood --hold-down   log.level --DEBUG samples.pretty_log   openflow.discovery  info.packet_dump \> /root/pox/log.out \%26' \>\> /root/start_controller.sh ")
            print self.distem_api.execute_command_rest([controller_id], "chmod 777 /root/start_controller.sh")
            print self.distem_api.execute_command_rest([controller_id], 'coproc /root/start_controller.sh ')
        if controller_type=="opendaylight":
            print self.distem_api.execute_command_rest([controller_id], "/home/ubuntu/karaf/karaf-0.7.3/bin/start")
            print self.__proxy_odl_conf()
            sleep(20)


    def get_connected_switches(self, id_):
        if id_ in self.switches:
            d = self.switches
        else:
            d = self.nodes

        connected = []
        links = d[id_]["links"]
        for id1, id2 in links:
            if id1 == id_ and id2 != id_:
                connected.append(id2)
            elif id2 == id_ and id1 != id_:
                connected.append(id1)
            else:
                raise Exception("id not in links")
        return list(filter(lambda x: self.is_switch(x), connected))

    def start_containers(self):
        if self.controller:
            print "Starting the controller"
            print self.distem_api.start_vnodes_rest([self.controller["id"]])
        sleep(2)
        print "Starting the switches"
        print self.distem_api.start_vnodes_rest(self.switches.keys())
        sleep(2)
        print "Starting the nodes"
        print self.distem_api.start_vnodes_rest(self.nodes.keys())
        sleep(10)

    def set_controller_host(self, host=None):
        if self.controller and not host:
            self.controller["host"] = self.coordinator
            return
        if self.controller and host:
            self.controller["host"] = host
            return
        return


    def get_connected_nodes(self, id_):
        if id_ in self.switches:
            d = self.switches
        else:
            d = self.nodes

        connected = []
        links = d[id_]["links"]
        for id1, id2 in links:
            if id1 == id_ and id2 != id_:
                connected.append(id2)
            elif id2 == id_ and id1 != id_:
                connected.append(id1)
            else:
                raise Exception("id not in links")
        return list(filter(lambda x: self.is_node(x), connected))


    @staticmethod
    def generate_pool(network):
        return list([str(x) for x in ipaddress.ip_network(network)])[1:-1]

    def assing_links(self):
        for link in self.links:
            for id_ in link:
                if self.is_switch(id_):
                    self.switches[id_]["links"].append(link)
                if self.is_node(id_):
                    self.nodes[id_]["links"].append(link)

    def get_number_of_node_to_reserve(self):
        if len(self.ids) < 1:
            raise Exception("You need to create at least one Node, one Switch or one Controller")
        return len(self.switches)

    def wait_distem(self):
        test_dir = self.reservation.get_test_dir()
        while not ("reservation_distem.log" in test_dir):
            test_dir = self.reservation.get_test_dir()
            sleep(5)

    def get_assigned_ports(self, switch_id):
        ports = []
        for link in self.links:
            if link[0] == switch_id:
                ports.append(self.links[link]["port"][0])
            if link[1] == switch_id:
                ports.append(self.links[link]["port"][1])
        return list(filter(lambda x:x!=None, ports))

    def get_next_free_port(self, switch_id):
        assigned_ports = self.get_assigned_ports(switch_id)
        if assigned_ports == []:
            return 1
        disponible_ports = set(range(1, max(assigned_ports) + 2)) - set(assigned_ports)
        return min(disponible_ports)

    def assign_ports(self):
        for link in self.links:
            port = self.links[link]["port"]
            p1 = port[0] if port[0] != None else self.get_next_free_port(link[0])
            p2 = port[1] if port[1] != None else self.get_next_free_port(link[1])
            self.links[link]["port"] = (p1, p2)

            if self.is_node(link[0]):
                self.nodes[link[0]]["port"] = p1
                self.nodes[link[0]]["iface"] = "if{}".format(p1)

            if self.is_node(link[1]):
                self.nodes[link[1]]["port"] = p2
                self.nodes[link[1]]["iface"] = "if{}".format(p2)

        self.check_port_assignments()

    def check_port_assignments(self):
        for switch in self.switches:
            self.check_switch_ports(switch)

    def check_switch_ports(self, switch_id):
        ports=[]
        for id_1, id_2 in self.links:
            if id_1 == switch_id:
                ports.append(self.links[(id_1, id_2)]["port"][0])
            if id_2 == switch_id:
                ports.append(self.links[(id_1, id_2)]["port"][1])

        errors_port = set([x for x in ports if ports.count(x)>1])

        if errors_port:
            raise Exception("Switch {} port repetition {}".format(switch_id, errors_port))

    def add_controller(self, image, controller_id="c0", controller_type="pox"):
        if self.check_id(controller_id):
            raise Exception("this ID {} is already assigned".format(controller_id))
        self.controller = {"id":controller_id, "image":image, "type":controller_type}
        self.ids.add(controller_id)

    def del_controller(self):
        self.ids.remove(self.controller["id"])
        self.controller = None


    def add_switch(self, switch_id, image=None):
        if self.check_id(switch_id):
            raise Exception("this ID {} is already assigned".format(switch_id))
        self.switches[switch_id] = {"image": image, "links":[]}
        self.ids.add(switch_id)

    def add_node(self, node_id, image):
        if self.check_id(node_id):
            raise Exception("this ID {} is already assigned".format(node_id))
        self.ids.add(node_id)
        self.nodes[node_id] = {"image": image, "links":[]}

    def add_link(self, id_1, id_2, port1=None, port2=None):
        if id_1 == id_2:
            raise Exception("id_1 == id_2, id={}".format(id_1))

        if self.is_node(id_1) and self.is_node(id_2):
            raise Exception("you can not connect to node directly, connect them with a switch")

        if not (self.check_id(id_1) and self.check_id(id_2)):
            raise Exception("id {} or id {} missing".format(id_1, id_2))

        if self.check_link(id_1, id_2):
            raise Exception("link ({}, {}) already exist".format(id_1, id_2))

        self.links[(id_1, id_2)] = {"port": (port1, port2)}

    def check_link(self, id_1, id_2):
        return (id_1, id_2) in self.links or (id_2, id_1) in self.links

    def del_link(self, id_1, id_2):
        if not self.check_link(id_1, id_2):
            raise Exception("link ({}, {}) missing".format(id_1, id_2))

        if (id_1, id_2) in self.links:
            del self.links[(id_1, id_2)]
        else:
            del self.links[(id_2, id_1)]

    def del_node(self, node_id):
        if not (node_id in self.nodes):
            raise Exception("Node with id {} missing".format(node_id))

        del self.nodes[node_id]
        self.clean_links(node_id)
        self.ids.remove(node_id)

    def clean_links(self, id_):
        links = self.links.keys()
        for link in links:
            if link[0] == id_ or link[1] == id_:
                del self.links[link]

    def del_switch(self, switch_id):
        if not (switch_id in self.switches):
            raise Exception("Switch with id {} missing".format(switch_id))

        del self.switches[switch_id]
        self.clean_links(switch_id)
        self.ids.remove(switch_id)

    def check_id(self, id_):
        return id_ in self.ids

    def get_reservation_info(self):
        return self.reservation.reservation

    def __str__(self):
        return str(self.ids) + str(self.links)

    def assign_interfaces(self):
        for link in self.links:
            p1, p2 = self.links[link]["port"]
            self.links[link]["iface"] = ("if{}".format(p1), "if{}".format(p2))

    def assign_ips(self):
        vnet = 1
        for link in self.links:
            if len(self.ip_pool) < 2:
                raise Exception("You need more IPs address")
            ip1 = self.pop_ip()
            ip2 = self.pop_ip()
            self.links[link]["ip"] = (ip1, ip2)
            self.links[link]["vnet"] = "vnet"+str(vnet)

            if self.is_node(link[0]):
                self.nodes[link[0]]["ip"] = ip1
                self.nodes[link[0]]["vnet"] = "vnet"+str(vnet)

            if self.is_node(link[1]):
                self.nodes[link[1]]["ip"] = ip2
                self.nodes[link[1]]["vnet"] = "vnet"+str(vnet)
            vnet += 1

    def is_node(self, id_):
        return id_ in self.nodes

    def is_switch(self, id_):
        return id_ in self.switches

    def pop_ip(self):
        return self.ip_pool.pop(0)

    def get_host_ips(self):
        print self.reservation.get_reservation_nodes()
        return self.reservation.get_reservation_nodes()

    def __proxy_odl_conf(self):
        system('ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{} '
               '"sysctl -w net.ipv4.ip_forward=1;'
               'iptables --table nat --append PREROUTING --protocol tcp --dport 8181 --jump DNAT --to-destination 220.0.0.1:8181;'
               'iptables --table nat --append PREROUTING --protocol tcp --dport 8888 --jump DNAT --to-destination 220.0.0.1:8080;'
               'iptables -t nat -A POSTROUTING -j MASQUERADE;"'.format(self.coordinator))


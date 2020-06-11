from distriopt import VirtualNetwork
from distriopt.embedding.physical import PhysicalNetwork
from distriopt.embedding.algorithms import (
    EmbedBalanced,
    EmbedILP,
    EmbedPartition,
    EmbedGreedy,
)
from distriopt.packing.algorithms import ( BestFitDopProduct,
                                           FirstFitDecreasingPriority,
                                           FirstFitOrderedDeviation )

from distriopt.packing import CloudInstance
from distriopt.packing.algorithms import BestFitDopProduct,FirstFitDecreasingPriority,FirstFitOrderedDeviation
from random import randint
import subprocess
from pathlib import Path

class DummyMapper(object):
    def __init__(self, places={}):
        self.places = places

    def place(self, node):
        return self.places[node]

    def placeLink(self, link):
        return ({}, {})

class RoundRobinMapper(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[]):
        self.physical = physical_topo
        self.vNodes = virtual_topo.hosts()+virtual_topo.switches()
        self.places = self.__places(self.vNodes, physical_topo)

    def __places(self, vNodes, physical_topo):
        places={}
        i=0
        for node in vNodes:
            places[node] = physical_topo[i % len(physical_topo)]
            i += 1
        return places

    def place(self, node):
        return self.places[node]

class RandomMapper(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[]):
        self.physical = physical_topo
        self.vNodes = virtual_topo.hosts()+virtual_topo.switches()
        self.places = self.__places(self.vNodes, physical_topo)

    def __places(self, vNodes, physical_topo):
        places={}
        for node in vNodes:
            places[node] = physical_topo[randint(0,len(physical_topo)-1)]
        return places

    def place(self, node):
        return self.places[node]


class MaxinetMapper(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[], share_path="/Users/giuseppe/Desktop/algo_experiments/algo_experiments/distrinet/mininet/mininet/mapper/shares/equal10.txt"):
        self.physical = physical_topo
        self.virtual_network = virtual_topo
        self.vNodes = virtual_topo.hosts()+virtual_topo.switches()
        self.vHosts = virtual_topo.hosts()
        self.vSwitches = virtual_topo.switches()
        self.vlinks = virtual_topo.links()
        self.metis_node_mapping = None
        self.node_metis_mapping = None
        self.metis_dict = None
        maxinet_dict = self.convert_in_maxinet_dict()
        # OK
        metis_dict = self.convert_in_metis_dict(maxinet_dict=maxinet_dict)
        print(metis_dict) # OK
        self.create_metis_file(metis_dict=metis_dict, path="/tmp/metis_file") #OK
        print("USING {}".format(share_path))
        self.run_metis(graph_path="/tmp/metis_file", share_path=share_path) # OK
        mapping = self.get_mapping(graph_path="/tmp/metis_file", share_path=share_path) # OK
        print(mapping)
        mapping_converted = self.convert_mapping(mapping) # OK
        print("MAPPING CONVERTED")
        print(mapping_converted)

        complete_mapping = self.get_mapping_for_all_nodes(mapping_converted) # OK
        print("COMPLETE MAPPING")
        print(complete_mapping)
        print(self.metis_node_mapping)
        compute_nodes = sorted(self.physical)
        mapping = complete_mapping
        sorted_keys = sorted(mapping.keys(), key=lambda x: int(x), reverse=True)

        physical_names_mapping = {phy_name: metis_name for phy_name, metis_name in
                                  zip(compute_nodes, sorted_keys)}

        metis_name_mapping = {physical_names_mapping[x]: x for x in physical_names_mapping.keys()}

        mapping_with_pyhisical_names = {metis_name_mapping[node]: mapping[node] for node in mapping.keys()}

        print(mapping_with_pyhisical_names)
        self.places = self.__places(mapping_with_pyhisical_names)
        print("FINAL")
        print(self.places)

    def __places(self, mapping):
        final = dict()
        for physical, list_vnodes in mapping.items():
            for v in list_vnodes:
                final[v]=physical

        return final


    def get_mapping(self, graph_path, share_path):
        gr_path = Path(graph_path)
        if gr_path.is_file():
            file_name = gr_path.name
        else:
            raise RuntimeError()

        if Path(share_path).is_file():
            physical_hosts = self.get_physical_hosts(share_path)
        else:
            raise RuntimeError()

        mapping_file_name = file_name +".part."+ str(len(physical_hosts))
        mapping_file_path = gr_path.parent / mapping_file_name
        mapping = {host: [] for host in physical_hosts}
        with open(mapping_file_path,"r") as file:
            lines = list(map(lambda x:x.strip(), file.readlines()))

        for c, m in enumerate(lines):
            switch = c + 1
            mapping[m].append(switch)

        return mapping

    def run_metis(self, graph_path, share_path):
        n_physical_hosts = len(self.get_physical_hosts(share_path))
        cmd=f"gpmetis -ptype=rb -tpwgts={str(share_path)} {str(graph_path)} {n_physical_hosts}"
        output = subprocess.check_output(cmd, shell=True)
        out = output.decode("utf-8")
        return out

    def get_mapping_for_all_nodes(self, mapping_node_names):
        total_mapping={host: mapping_node_names[host] for host in mapping_node_names.keys()}
        for host in total_mapping.keys():
            for node in total_mapping[host]:
                total_mapping[host] += self.get_connected_hosts(node)

        return total_mapping

    def get_connected_hosts(self, node_name):
        nodes = []
        for node in self.getNeighbors(node_name):
            if node in self.vHosts:
                nodes.append(node)
        return nodes

    def convert_mapping(self, mapping):
        mapping_node_names = {host: [] for host in mapping.keys()}
        for host in mapping.keys():
            mapping_node_names[host] = [self.metis_node_mapping[node] for node in mapping[host]]
        return mapping_node_names

    def create_metis_file(self, metis_dict, path):
        nodes, edges = len(self.get_metis_nodes()), len(self.get_metis_edges())

        sorted_keys = sorted(list(metis_dict.keys()))
        metis_lines = [[nodes, edges, "011", "0"]]

        for k in sorted_keys:
            weight = metis_dict[k]["weight"]
            edges = metis_dict[k]["edges"]
            line = [weight] + edges
            metis_lines.append(line)

        with open(Path(path), "w") as file:
            for line in metis_lines:
                file.write(" ".join([str(x) for x in line]) + "\n")

        return metis_lines

    def get_physical_hosts(self, share_path):
        with open(share_path, "r") as file:
            lines = file.readlines()
            lines = list(map(lambda x: x.strip(), lines))
            while [] in lines:
                lines.remove([])
        hosts = [x.split('=')[0].strip() for x in lines]
        return hosts


    def get_metis_nodes(self):
        return self.vSwitches

    def get_metis_edges(self):
        edges = []
        for u, v in self.vlinks:
            if u in self.vSwitches and v in self.vSwitches:
                edges.append((u, v))

        return edges

    def getNeighbors(self, n):
        links = self.vlinks
        links = list(filter(lambda x: x[0] == n or x[1] == n, links))
        neighbors = set([x[0] for x in links]+[x[1] for x in links] )
        neighbors.remove(n)
        return list(neighbors)

    def convert_in_maxinet_dict(self):
        maxinet_nodes = dict()
        for n in self.vSwitches:
            maxinet_nodes[n] = {"weight": 1, "connected_switches": []}

        for n in maxinet_nodes.keys():
            connected_nodes = self.getNeighbors(n)
            for connected_node in connected_nodes:
                if connected_node in self.vHosts:
                    maxinet_nodes[n]["weight"] += 1
                else:
                    maxinet_nodes[n]["connected_switches"].append(connected_node)
        return maxinet_nodes

    def req_rate(self, n1, n2):
        links = self.virtual_network.links(withInfo=True)
        for u, v, d in links:
            if (u, v) == (n1,n2) or (v,u) == (n1,n2):
                return d["bw"]
        raise ValueError("Link {}-{} does not exist")

    def convert_in_metis_dict(self, maxinet_dict):
        metis_node_mapping = {num+1: node for num, node in enumerate(maxinet_dict.keys())}
        node_metis_mapping = {metis_node_mapping[num]: num for num in metis_node_mapping.keys()}
        metis_dict = {num: {"weight": None, "edges": []} for num in metis_node_mapping.keys()}
        for node in maxinet_dict.keys():
            num = node_metis_mapping[node]
            metis_dict[num]["weight"] = maxinet_dict[node]["weight"]
            for neighboor in maxinet_dict[node]["connected_switches"]:
                neighboor_mapped = node_metis_mapping[neighboor]
                required_edge_rate = self.req_rate(node, neighboor)
                metis_dict[num]["edges"] += [neighboor_mapped, required_edge_rate]

        self.metis_node_mapping = metis_node_mapping
        self.node_metis_mapping = node_metis_mapping
        self.metis_dict = metis_dict
        return metis_dict






class BlockMapper(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[],block=10):
        self.physical = physical_topo
        try:
            self.vNodes = zip(sorted(virtual_topo.hosts(), key= lambda x:int(x[1:])),sorted(virtual_topo.switches(), key= lambda x:int(x[1:])))
        except:
            print("Not a valid Mapper for this instance")
            exit(1)
        self.places = self.__places(self.vNodes, physical_topo,block)

    def __places(self, vNodes, physical_topo,block):
        places={}
        vNodes= list(vNodes)
        if len(physical_topo) < len(vNodes) / block:
            raise Exception("Not a valid Mapper for this instance")
        for i, (v, s) in enumerate(vNodes):

            places[v] = physical_topo[i//block]
            places[s] = physical_topo[i//block]

        return places

    def place(self, node):
        return self.places[node]


class Mapper(object):
    def __init__(self, virtual_topo, physical_topo, solver=EmbedGreedy):
        """ virtual_topo: virtual topology to map
            physical_topo: physical topology to map on
            solver: solver class to use to solve the mapping"""
        self.virtual_topo =  VirtualNetwork.from_mininet(virtual_topo)
        self.mininet_virtual=virtual_topo
        self.physical_topo = PhysicalNetwork.from_files(physical_topo)
        self.prob = None
        self.solver = solver
        self.solve()

        self.places= self.__places()

    def solve(self, solver=None):
        """ Solve the mapping problem of the virtual topology on the physical
            one using the specified solver
            solver: solver class to use to solve the mapping
        """

        if solver is not None:
            self.solver = solver


        self.prob = self.solver(virtual=self.virtual_topo, physical=self.physical_topo)

        time_solution, status = self.prob.solve()
        if status == "0" or status == 0:
            raise Exception("Failed to solve")
        elif status == "-1" or status == - 1:
            raise Exception("Unfeasible Problem")

    def __places(self):
        places={}
        vNodes=self.mininet_virtual.hosts()+self.mininet_virtual.switches()
        for node in vNodes:
            places[node]=self.place(node)

        return places


    def place(self, node):
        """ Returns physical placement of the node
            node: node in the virtual topology
            return: name of the physical host to use
        """
        if self.prob == None:
            self.solve()

        place = self.prob.solution.node_info(node)

        return place

    def placeLink(self, link):
        """ Returns physical placement of the link
            link: link in the virtual topology
            returns: list of placements for the link
        """
        if self.prob == None:
            self.solve()
        n1,n2=link
        #p1,p2 = self.prob.solution.node_info(n1),self.prob.solution.node_info(n2)

        return {},{}


class Packing(object):
    def __init__(self, virtual_topo, cloud_prices,solver=BestFitDopProduct):
        """ virtual_topo: virtual topology to map
            physical_topo: physical topology to map on
            solver: solver class to use to solve the mapping"""
        self.virtual_topo =  VirtualNetwork.from_mininet(virtual_topo)
        self.cloud = CloudInstance.read_ec2_instances(vm_type=cloud_prices)
        self.mininet_virtual=virtual_topo
        self.prob = None

        self.solver = solver

        self.places=self.__places()


    def solve(self, solver=None):
        """ Solve the mapping problem of the virtual topology on the physical
            one using the specified solver
            solver: solver class to use to solve the mapping
        """

        if solver is not None:
            self.solver = solver
        #virtual_network= VirtualNetwork.from_mininet(self.virtual_topo)
        self.prob = self.solver(virtual=self.virtual_topo, physical=self.cloud)


        time_solution, status = self.prob.solve()
        if status == "0":
            raise Exception("Failed to solve")
        elif status == "-1":
            raise Exception("Unfeasible Problem")

    def __places(self):
        places=dict()

        vNodes=self.mininet_virtual.hosts()+self.mininet_virtual.switches()
        for node in vNodes:
            places[node]=self.place(node)

        return places


    def place(self, node):
        """ Returns physical placement of the node
            node: node in the virtual topology
            return: name of the physical host to use
        """
        if self.prob == None:
            self.solve()
        place = self.prob.solution.node_info(node)

        return place

    def placeLink(self, link):
        """ Returns physical placement of the link
            link: link in the virtual topology
            returns: list of placements for the link
        """
        if self.prob == None:
            self.solve()

        place =  self.prob.solution.link_mapping[link]

        return place

if __name__ == '__main__':
    #physical = PhysicalNetwork.from_files("/Users/giuseppe/.distrinet/gros_partial")
    virtual_topo = VirtualNetwork.create_fat_tree(k=2, density=2, req_cores=2, req_memory=100,
                                                  req_rate=100)
    from distriopt.packing import CloudInstance

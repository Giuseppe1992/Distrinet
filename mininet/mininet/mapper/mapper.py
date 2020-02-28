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



class BlockMapper(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[],block=10):
        self.physical = physical_topo
        try:
            self.vNodes = zip(sorted(virtual_topo.hosts(), key= lambda x: int(x[1:])),sorted(virtual_topo.switches(), key= lambda x:int(x[1:])))
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


class OverMapper1(DummyMapper):
    def __init__(self, virtual_topo, physical_topo=[],over=1):
        self.physical = physical_topo
        try:
            self.vNodes = zip(sorted(virtual_topo.hosts(), key= lambda x: int(x[1:])),sorted(virtual_topo.switches(), key= lambda x:int(x[1:])))
        except:
            print("Not a valid Mapper for this instance")
            exit(1)
        self.places = self.__places(self.vNodes, physical_topo,over)

    def __places(self, vNodes, physical_topo, over):
        places={}
        vNodes= list(vNodes)
        jump = (len(vNodes) // len(physical_topo))-over
        if len(vNodes) % len(physical_topo) !=0:
            raise Exception("OverMapper, wrong topology")
        overloaded_machine = len(physical_topo)//2
        counter=0
        id_mapping=[]
        for i in range(len(physical_topo)):
            if i == overloaded_machine:
                over_jump = (len(vNodes) //len(physical_topo)) + (len(physical_topo)-1)*over
                id_mapping.append(list(range(counter, counter + over_jump)))
                counter += over_jump
            else:
                id_mapping.append(list(range(counter,counter+jump)))
                counter += jump

        for i, (v, s) in enumerate(vNodes):
            for c, j in enumerate(id_mapping):
                if i in j:
                    places[v] = physical_topo[c]
                    places[s] = physical_topo[c]

        return places

    def place(self, node):
        return self.places[node]


class OverMapper2(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=2):
        super(OverMapper2, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper3(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=3):
        super(OverMapper3, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper4(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=4):
        super(OverMapper4, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper5(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=5):
        super(OverMapper5, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper6(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=6):
        super(OverMapper6, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper7(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=7):
        super(OverMapper7, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

class OverMapper8(OverMapper1):
    def __init__(self, virtual_topo, physical_topo=[], over=8):
        super(OverMapper8, self).__init__(virtual_topo, physical_topo=physical_topo, over=over)

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
        if status == "0":
            raise Exception("Failed to solve")
        elif status == "-1":
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

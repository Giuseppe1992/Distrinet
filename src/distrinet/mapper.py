from mapping.embedding.algorithms import EmbedBalanced, EmbedPartition, EmbedTwoPhases, EmbedILP
from mapping_distrinet.mapping.embedding.algorithms.ilp import EmbedILP
from mapping_distrinet.mapping.embedding.physical import PhysicalNetwork
from mapping_distrinet.mapping.virtual import VirtualNetwork
import mapping_distrinet.mapping as mp
from mininet.topo import Topo

class DummyMapper(object):
    def __init__(self, places={}):
        self.places = places

    def place(self, node):
        return self.places[node]

class Mapper(object):
    def __init__(self, virtual_topo, physical_topo, solver=EmbedTwoPhases):
        """ virtual_topo: virtual topology to map
            physical_topo: physical topology to map on
            solver: solver class to use to solve the mapping"""
        self.virtual_topo = virtual_topo
        self.physical_topo = physical_topo
        self.prob = None
        self.solver = solver

    def solve(self, solver=None):
        """ Solve the mapping problem of the virtual topology on the physical
            one using the specified solver
            solver: solver class to use to solve the mapping
        """

        if solver is not None:
            self.solver = solver

        self.prob = self.solver(virtual=self.virtual_topo, physical=self.physical_topo)
        time_solution, status = self.prob.solve()

        if mp.SolutionStatus[status] == "Not Solved":
            raise Exception("Failed to solve")
        elif mp.SolutionStatus[status] == "Infeasible":
            raise Exception("Unfeasible Problem")


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

from distriopt import VirtualNetwork
from distriopt.embedding.physical import PhysicalNetwork
from distriopt.embedding.algorithms import (
    EmbedBalanced,
    EmbedILP,
    EmbedPartition,
    EmbedGreedy,
)
class DummyMapper(object):
    def __init__(self, places={}):
        self.places = places

    def place(self, node):
        return self.places[node]

class Mapper(object):
    def __init__(self, virtual_topo, physical_topo, solver=EmbedGreedy):
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


if __name__ == '__main__':
    physical = PhysicalNetwork.from_files("/Users/giuseppe/.distrinet/gros_partial")
    virtual_topo = VirtualNetwork.create_fat_tree(k=2, density=2, req_cores=2, req_memory=100,
                                                  req_rate=100)

    prob = EmbedGreedy(virtual_topo, physical)
    time_solution, status = prob.solve()
    print(time_solution, status)
    print(prob.solution.node_mapping)
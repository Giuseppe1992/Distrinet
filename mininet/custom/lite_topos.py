from mininet.topo import Topo

class LiteLinear( Topo ):
    "Simple topology example."


    def build( self , n):
        "Create custom topo."
        # Add hosts and switches

        if n <= 0:
            raise ValueError(" you need at least one switch")

        for i in range(1, n + 1):
            s = "s{}".format(i)
            self.addSwitch(s)

        for i in range(1, n):
            s1, s2 = "s{}".format(i), "s{}".format(i + 1)
            self.addLink(s1, s2)

class LiteTree( Topo ):
    def build( self , depth):
        "Create custom topo."
        # Add hosts and switches

        if depth <= 0:
            raise ValueError(" you need at least one switch")
        switches = ["s{}".format(i) for i in range (1, 2**depth)]

        for s in switches:
            self.addSwitch(s)

        for i in range(0,2**(depth -1)-1):
            self.addLink(switches[i],switches[(i+1)*2-1])
            self.addLink(switches[i], switches[(i + 1) * 2])

topos = { 'litelinear': ( lambda n: LiteLinear(n) ), 'litetree':(lambda n: LiteTree(n) ) }
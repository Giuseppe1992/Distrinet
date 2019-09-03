from mininet.cli import CLI
from mininet.log import info, output, error


class DCLI( CLI ):
    def do_xterm( self, line, term='xterm' ):
        """Spawn xterm(s) for the given node(s).
           Usage: xterm node1 node2 ..."""
        error ("not supported")

    def do_x( self, line ):
        """Create an X11 tunnel to the given node,
           optionally starting a client.
           Usage: x node [cmd args]"""
        error ("not supported")

    def do_gterm( self, line ):
        """Spawn gnome-terminal(s) for the given node(s).
           Usage: gterm node1 node2 ..."""
        error ("not supported")

    def waitForNode( self, node ):
        "Wait for a node to finish, and print its output."
        while node.waiting:
            v = node.monitor(timeoutms=1)
            output( v )

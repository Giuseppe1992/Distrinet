"""
author: Damien Saucez (damien.saucez@gmail.com) 
"""
from mininet.cli import CLI
from mininet.log import info, output, error
import sys

class DCLI( CLI ):
    """
    A simple command-line interface for Distrinet.

    Notes
    -----
    Extends `mininet.cli.CLI` to take into account the peculiarities of
    Distrinet.

    The prompt is changed to 'distrinet> ' by default.
    
    See also
    --------
    `mininet.cli`
    """

    def __init__( self, mininet, stdin=sys.stdin, script=None, prompt='distrinet> '):
        """
        Start and run interactive or batch mode CLI
        mininet : mininet.distrinet.Distrinet
            Distrinet network object.
        stdin : file object
            Standard input for CLI.
        script : str
            Script to run in batch mode.
        prompt : str (optional, default='distrinet> ')
            CLI prompt.
        """ 
        self.setPrompt(prompt)
        super(DCLI, self).__init__(mininet=mininet, stdin=stdin, script=script)

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

    def setPrompt( self, prompt):
        """
        Set the CLI prompt.

        Parameters
        ----------
        prompt : str
            The prompt to use in the CLI.
        """
        self.prompt = prompt

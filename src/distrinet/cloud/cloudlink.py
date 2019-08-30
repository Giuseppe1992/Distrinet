"""
link.py: interface and link abstractions for mininet

It seems useful to bundle functionality for interfaces into a single
class.

Also it seems useful to enable the possibility of multiple flavors of
links, including:

- simple veth pairs
- tunneled links
- patchable links (which can be disconnected and reconnected via a patchbay)
- link simulators (e.g. wireless)

Basic division of labor:

  Nodes: know how to execute commands
  Intfs: know how to configure themselves
  Links: know how to connect nodes together

Intf: basic interface object that can configure itself
TCIntf: interface with bandwidth limiting and delay via tc

Link: basic link class for creating veth pairs
"""

from mininet.log import info, error, debug
import re

from mininet.link import(Intf, TCIntf, Link, TCLink)

class CloudLink( Link ):
    nextLinkId = 20 

    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    # pylint: disable=too-many-branches
    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None, addr1=None, addr2=None,
                  intf=TCIntf, cls1=None, cls2=None, params1=None,
                  params2=None, fast=True, **params ):
        """Create veth link to another node, making two new interfaces.
           node1: first node
           node2: second node
           port1: node1 port number (optional)
           port2: node2 port number (optional)
           intf: default interface class/constructor
           cls1, cls2: optional interface-specific constructors
           intfName1: node1 interface name (optional)
           intfName2: node2  interface name (optional)
           addr1: MAC address for interface 1
           addr2: MAC address for interface 2
           params1: parameters for interface 1
           params2: parameters for interface 2
           params: parameters for the link"""
        # This is a bit awkward; it seems that having everything in
        # params is more orthogonal, but being able to specify
        # in-line arguments is more convenient! So we support both.
        if params1 is None:
            params1 = {}
        if params2 is None:
            params2 = {}
        # Allow passing in params1=params2
        if params2 is params1:
            params2 = dict( params1 )
        if port1 is not None:
            params1[ 'port' ] = port1
        if port2 is not None:
            params2[ 'port' ] = port2
        if 'port' not in params1:
            params1[ 'port' ] = node1.newPort()
        if 'port' not in params2:
            params2[ 'port' ] = node2.newPort()
        if not intfName1:
            intfName1 = self.intfName( node1, params1[ 'port' ] )
        if not intfName2:
            intfName2 = self.intfName( node2, params2[ 'port' ] )

        self.params1 = {}
        self.params1.update(params)
        self.params1.update(params1)


        self.params2 = {}
        self.params2.update(params)
        self.params2.update(params2)

        # Make interfaces
        interfaces = self.makeIntfPair( intfName1, intfName2, addr1, addr2,
                           node1, node2, deleteIntfs=False )

        if not cls1:
            cls1 = intf
        if not cls2:
            cls2 = intf
        
        intf1 = cls1( name=intfName1, node=node1,
                      link=self, mac=addr1, **self.params1  )
        intf2 = cls2( name=intfName2, node=node2,
                      link=self, mac=addr2, **self.params2 )
        
        # All we are is dust in the wind, and our two interfaces
        self.intf1, self.intf2 = intf1, intf2

        # Effectively create the links
##        host_iface1 = self.params1.get("host_iface", None)
##        host_iface2 = self.params2.get("host_iface", None)
        link_id = self.newLinkId()

        node1.addContainerLink(target1=node1.target, target2=node2.target, link_id=link_id, bridge1=interfaces[0], bridge2=interfaces[1], link=self)
        node2.addContainerLink(target1=node2.target, target2=node1.target, link_id=link_id, bridge1=interfaces[1], bridge2=interfaces[0], link=self)
        
    @classmethod
    def newLinkId(cls):
        link_id = CloudLink.nextLinkId
        cls.nextLinkId += 1
        return link_id


    # pylint: enable=too-many-branches

    @staticmethod
    def _ignore( *args, **kwargs ):
        "Ignore any arguments"
        pass

    def intfName( self, node, n ):
        "Construct a canonical interface name node-ethN for interface n."
        # Leave this as an instance method for now
        assert self
        return node.name + '-eth' + repr( n )

    @classmethod
    def makeIntfPair( cls, intfname1, intfname2, addr1=None, addr2=None,
                      node1=None, node2=None, deleteIntfs=True ):
        """Create pair of interfaces
           intfname1: name for interface 1
           intfname2: name for interface 2
           addr1: MAC address for interface 1 (optional)
           addr2: MAC address for interface 2 (optional)
           node1: home node for interface 1 (optional)
           node2: home node for interface 2 (optional)
           (override this method [and possibly delete()]
           to change link type)"""
        # Leave this as a class method for now
        assert cls
        
        if deleteIntfs:
            # Delete any old interfaces with the same names
            raise Exception("Must implement delete interface")

        # Add the interface on both ends:
        br1 = node1.addContainerInterface(intfName=intfname1)
        br2 = node2.addContainerInterface(intfName=intfname2)
        
        return (br1, br2)

    # DSA - TODO implement delete interface on the host
    def delete( self ):
        # DSA - TODO implement delete container in container not here.
        # delete the interfaces of the link
        self.intf1.node.deleteContainerInterface(self.intf1)
        self.intf2.node.deleteContainerInterface(self.intf2)

        # delete the link
        self.intf1.node.deleteContainerLink(self)
        self.intf2.node.deleteContainerLink(self)

##        self.intf1.node.deleteIntersendCommand("brctl delbr {}".format(self.intf1.bridge))
##        self.intf2.node.sendCommand("brctl delbr {}".format(self.intf2.bridge))
        
        super().delete()


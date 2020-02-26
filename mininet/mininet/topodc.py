# Copyright 2018 - 2019 Inria Damien.Saucez@inria.fr                                                                               
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
from mininet.log import info, debug, warn, error, output
from mininet.topo import (irange, Topo, SingleSwitchTopo)


# == Utils ================================================================

def toDemo(topo):
        """
        Configure the hosts of a topology to be in a Hadoop cluster
        The first (alphabetical order) host is the master, all others are the
        slaves.
        returns the name of the host selected for being the master
        """
        master = None
        # configure each host
        if len(topo.hosts()) < 9:
            raise Exception("Not enough hosts")
        user_1, user_2, downloader_1, f1, f2, fbackup, streaming, http, nagios = topo.hosts(sort=True)[:9]
        topo.setNodeInfo(user_1, {"image":"ubuntu", "role":"user"})
        topo.setNodeInfo(user_2, {"image": "ubuntu", "role": "user"})
        topo.setNodeInfo(downloader_1, {"image": "ubuntu", "role": "downloader"})
        topo.setNodeInfo(f1, {"image": "ubuntu", "role": "firewall_1"})
        topo.setNodeInfo(f2, {"image": "ubuntu", "role": "firewall_2"})
        topo.setlinkInfo(fbackup, {"image": "ubuntu", "role": "firewall_backup"})
        topo.setlinkInfo(streaming, {"image": "streaming", "role": "streaming"})
        topo.setlinkInfo(http, {"image": "server", "role": "http"})
        topo.setlinkInfo(nagios, {"image": "nagios", "role": "nagios"})


class DemoTopo( Topo ):
    "Demo"

    def build( self, **_opts ):
        #toDemo(self, slave_image="ubuntu-hadoop-slave", master_image="ubuntu-hadoop-master")

    # highest node is a web node
        h1 = self.addHost( 'h1' ) #u1
        h2 = self.addHost( 'h2' ) #u2
        h3 = self.addHost( 'h3' ) #d1
        h4 = self.addHost( 'h4' ) #f1
        h5 = self.addHost( 'h5' ) #f2
        h6 = self.addHost( 'h6' ) #fbackup
        h7 = self.addHost( 'h7' ) #streaming
        h8 = self.addHost( 'h8' ) #http
        h9 = self.addHost( 'h9' ) #nagios


        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )
        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        s5 = self.addSwitch( 's5' )


        self.addLink( h1, s1 )
        self.addLink( h2, s1 )
        self.addLink( h3, s1 )
        self.addLink( s2, s1 )
        self.addLink( s2, s3 )
        self.addLink( s4, s3 )
        self.addLink( s2, s4 )
        self.addLink( s2, s5 )
        self.addLink( s4, s5 )
        self.addLink( s3, h4 )
        self.addLink( s3, h8 )
        self.addLink( s4, h5 )
        self.addLink( s4, h7 )
        self.addLink( h6, s5 )

from mininet.provision.provision import Provision
from mininet.log import info, error, debug, output, warn

def _info(*args, **kwargs):
    pass

def default_images(*args, **kwargs):
    conf = Provision.get_configurations()
    ssh_conf = conf["ssh"]
    pub_id = ssh_conf["pub_id"]

    topo = kwargs['topo']

    sopts={ "image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":4, "memory":"2GB" }
    hopts={ "image":"ubuntu", 'pub_id':pub_id, "cpu":2, "memory":"4GB" }
    lopts={ "bw":1000 } #, "delay":"10ms"}

    topo.hopts.update(hopts)
    topo.sopts.update(sopts)
    topo.lopts.update(lopts)
    for n in topo.hosts():
        infos = {}
        infos.update(hopts)
        infos.update(topo.nodeInfo(n))
        topo.setNodeInfo(n, infos)

    for n in topo.switches():
        infos = {}
        infos.update(sopts)
        infos.update(topo.nodeInfo(n))

        topo.setNodeInfo(n, infos)
    
    for l in topo.links():
        src, dst = l[0],l[1]
        infos = {}
        infos.update(lopts)
        infos.update(topo.linkInfo(src=src, dst=dst))
        topo.setlinkInfo(src=src, dst=dst, info=infos)

def makeFile(net, host, lines, filename, overwrite=True, wait=True):
    ln = 1
    cmds = []
    for line in lines:
        command = 'echo %s' % (line)
        if overwrite and ln == 1:
            command = "%s > %s" % (command, filename)
        else:
            command = "%s >> %s"% (command, filename)
        cmds.append(command)

    cmd = ";".join(cmds)

    if wait:
        net.nameToNode[host].cmd(cmd)
    else:
        net.nameToNode[host].sendCmd(cmd)

def makeHosts(topo, net, wait=True):
    lines = []
    for host in topo.hosts():
        lines.append("{} {}".format(net.nameToNode[host].IP(), host))
    info (" >>> {} \n".format(lines))
    for host in topo.hosts():
        info (" Adding to host {}".format(lines))
        makeFile(net=net, host=host, lines=lines, filename="/etc/hosts", overwrite=False, wait=wait)
    info ("\n")

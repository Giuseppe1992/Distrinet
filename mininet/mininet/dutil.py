from mininet.provision.provision import Provision
from mininet.log import info, error, debug, output, warn

def _info(*args, **kwargs):
    pass

def default_images(*args, **kwargs):
    conf = Provision.get_configurations()
    ssh_conf = conf["ssh"]
    pub_id = ssh_conf["pub_id"]

    topo = kwargs['topo']
    # TODO: you need to specify cpu for LXD and cores for mininet API
    sopts={ "image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":1, "memory":"3500MB"}
    hopts={ "image":"ubuntu", 'pub_id':pub_id, "cpu":2, "memory":"6GB"}
    lopts={ "bw":100 } #, "delay":"10ms"}

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
            ln = 2
        else:
            command = "%s >> %s"% (command, filename)
        cmds.append(command)

    if wait:
        if len(cmds) <= 20:
            cmd = ";".join(cmds)
            net.nameToNode[host].cmd(cmd)
        else:
            list_cmds=[]
            i = 0
            cmds_ = []
            for c in cmds:
                if i < 20:
                    cmds_.append(c)
                    i += 1
                else:
                    i = 0
                    list_cmds.append(cmds_)
                    cmds_= [c]

            if cmds_ != []:
                list_cmds.append(cmds_)

            for list_c in list_cmds:
                cmd = ";".join(list_c)
                net.nameToNode[host].cmd(cmd)
    else:
        cmd = ";".join(cmds)
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

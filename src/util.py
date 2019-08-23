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
    print (" >>> {}".format(lines))
    for host in topo.hosts():
        print ("\t Adding to host {}".format(lines))
        makeFile(net=net, host=host, lines=lines, filename="/etc/hosts", overwrite=False, wait=wait)

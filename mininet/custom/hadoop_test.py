from mininet.topodc import (toHadoop, getHadoopMaster)
import time
from mininet.dutil import makeFile, makeHosts, default_images
from mininet.log import info, debug, warn, error, output

def aliasMaster(topo, net):
    master = getHadoopMaster(topo)
    output ("The Hadoop master is {}\n".format(master))

    lines = []
    line = "{} {}".format(net.nameToNode[master].IP(), "master")
    lines.append(line)
    for host in topo.hosts():
        lines.append("{} {}".format(net.nameToNode[host].IP(), host))
#    output (" >>> {}\n".format(lines))
    for host in topo.hosts():
#        output ("\t Adding to host {}".format(lines))
        makeFile(net=net, host=host, lines=lines, filename="/etc/hosts", overwrite=False)

def makeMasters(topo, net):
    """Generate the etc/hadoop/masters file on all the masters
    """
    masters = list()

    for host in topo.hosts():
        if "role" in topo.nodeInfo(host).keys() and topo.nodeInfo(host)["role"] == "master":
            masters.append(host)

    # Execute the command to build etc/hadoop/masters on each master
    for master in masters:
        makeFile(net, master, masters, "/root/hadoop-2.7.6/etc/hadoop/masters", overwrite=False)

def makeSlaves(topo, net):
    """ Generate the etc/hadoop/slaves file on all hosts
    """
    cluster = list()
    slaves = list()

    hosts = topo.hosts()
    for host in hosts:
        if "role" in topo.nodeInfo(host).keys():
            if topo.nodeInfo(host)["role"] == "slave":
                slaves.append(host)
                cluster.append(host)
            elif topo.nodeInfo(host)["role"] == "master":
                cluster.append(host)

    # Execute the command to build etc/hadoop/slaves on each host
    for host in cluster:
        makeFile(net, host, slaves, "/root/hadoop-2.7.6/etc/hadoop/slaves", overwrite=False)



def makePermanentSwitchRules(topo, net):
    for vswitch in sorted(topo.switches()):
        makeFile(net,vswitch,makeRules(vswitch, len(topo.switches())),"/root/rules",overwrite=False)
        net.nameToNode[vswitch].cmd(f"ovs-ofctl add-flows {vswitch} /root/rules")

def makeRules(switch,number_of_switches):
    switch_n = int(switch[1:])
    destip_out_port = []
    if switch_n == 1 or switch_n == number_of_switches:
        for i in range(1, number_of_switches + 1):
            if switch_n == i:
                destip_out_port.append((f"10.0.0.{i}", f"{switch}-eth1"))
            else:
                destip_out_port.append((f"10.0.0.{i}", f"{switch}-eth2"))

    else:

        for i in range(1,number_of_switches+1):
            if switch_n < i:
                destip_out_port.append((f"10.0.0.{i}", f"{switch}-eth3"))
            elif switch_n == i:
                destip_out_port.append((f"10.0.0.{i}", f"{switch}-eth1"))
            else:
                destip_out_port.append((f"10.0.0.{i}", f"{switch}-eth2"))

    ovs_rules=[]
    for ip_, o_port in destip_out_port:
        rule=f'priority=9999,eth_type=0x0800,ip,ip_dst={ip_},actions=output:"{o_port}"'
        ovs_rules.append(rule)

    return ovs_rules



def hadoop_test(mn):
    topo = mn.topo
    aliasMaster(topo=topo, net=mn)
    output ("# populate etc/hadoop/masters\n")
    makeMasters(topo=topo, net=mn)

    output ("# populate etc/hadoop/slaves\n")
    makeSlaves(topo=topo, net=mn)

    makePermanentSwitchRules(topo,mn)

    for h in topo.hosts():
        output(f"{h}")
        output(mn.nameToNode["h1"].cmd(f"ping {h} -c 1"))

    hm = getHadoopMaster(topo)
    hadoopMasterNode = mn.nameToNode[hm]

    output ("# Start Hadoop in the cluster\n")
    output ("# Format HDFS\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs namenode -format -force"'))

    output ("# Launch HDFS\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-dfs.sh"'))

    output ("# Launch YARN\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/sbin/start-yarn.sh"'))

    output ("# Create a directory for the user\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root"'))
    time.sleep(2)

    output ("\n")
    output ("# Compute PI\n")
    output (hadoopMasterNode.cmd('bash -c "/root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 400 400"'))


# we need the right images to run hadoop
PREBUILD = [default_images, toHadoop]

# adding the test in the suite
TESTS = {'hadoop':hadoop_test}

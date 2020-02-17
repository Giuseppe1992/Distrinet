from os import system
import  sys
from time import sleep
import uuid

topologies=['litetree','litelinear']

def get_info(topo, size):
    if topo == 'litelinear':
        hosts = ["h{}".format(h) for h in range(1, size + 1)]
        links = [("s{}".format(i), "h{}".format(i)) for i in range(1, size + 1)]
        return hosts, links

    if topo == 'litetree':
        hosts = ["h{}".format(h) for h in range(2**(size-1), 2**size)]
        links = [("s{}".format(i), "h{}".format(i)) for i in range(2**(size-1), 2**size)]
        return hosts, links
    raise ValueError(topo)

def test(topo, size):
    master_image = "ubuntu-hadoop-master"
    worker_image = "ubuntu-hadoop-slave"
    #topo = sys.argv[1]
    #size = int(sys.argv[2])

    hosts, links = get_info(topo, size)
    hosts_addr = [("127.0.0.1", "localhost"), ("192.168.0.1", "master")]
    master = hosts[0]
    workers = hosts[1:]
    system("screen -d -m mn --custom=lite_topos.py --topo={},{} --controller=remote".format(topo,size))
    bridge = "br_{}".format(master)
    system("ip link add name {} type bridge".format(bridge))
    system("ip link set {} up".format(bridge))
    system("lxc init {} {}".format(master_image, master))
    system("lxc config set {} limits.cpu 4".format(master))
    system("lxc config set {} limits.memory 8GB".format(master))
    system("lxc network attach {} {} eth0 eth0".format(bridge, master))
    system("lxc start {}".format(master))

    for worker in workers:
        bridge = "br_{}".format(worker)
        system("ip link add name {} type bridge".format(bridge))
        system("ip link set {} up".format(bridge))
        system("lxc init {} {}".format(worker_image, worker))
        system("lxc config set {} limits.cpu 4".format(worker))
        system("lxc config set {} limits.memory 8GB".format(worker))
        system("lxc network attach {} {} eth0 eth0".format(bridge, worker))
        system("lxc start {}".format(worker))

    for c, host in enumerate(hosts):
        bridge = "br_{}".format(host)
        system("ovs-vsctl  add-port s{} {}".format(host[1:],bridge))
        system("lxc exec {} -- ifconfig eth0 192.168.0.{} netmask 255.255.255.0".format(host,c+1))
        hosts_addr.append(("192.168.0.{}".format(c+1),host))
        system("lxc exec {} -- ifconfig eth0 up".format(host))
    sleep(60)
    for host in hosts:
        system("lxc exec {} -- service sshd start".format(host))

    with open("/tmp/hosts", "w") as f:
        f.writelines(["{}   {}\n".format(x,y) for x,y in hosts_addr])


    with open("/tmp/slaves", "w") as f:
        f.writelines(["{}\n".format(x) for x in workers])

    for host in hosts:
        system("lxc file push /tmp/hosts {}/etc/".format(host))
        system("lxc file push /tmp/slaves {}/root/hadoop-2.7.6/etc/hadoop/".format(host))

    with open("/tmp/masters", "w") as f:
        f.writelines(["master\n"])

    system("lxc file push /tmp/masters {}/root/hadoop-2.7.6/etc/hadoop/".format(master))

    sleep(100)
    r_id= uuid.uuid4()
    id_= r_id.hex[:8]

    for w in workers:
        system("lxc exec {} -- ping -c 3 {} >> tests/{}_{}_{}_ping.log 2>&1".format(master, w, topo, size, id_))

    for w in workers:
        system("lxc exec {} -- service sshd start".format(w))
    sleep(40)
    system("sleep 3")
    system("lxc exec {} -- /root/hadoop-2.7.6/bin/hdfs namenode -format -force > tests/{}_{}_{}_format.log 2>&1".format(master, topo, size, id_))
    system("sleep 3")
    system("lxc exec {} -- /root/hadoop-2.7.6/sbin/start-dfs.sh > tests/{}_{}_{}_dfs.log 2>&1".format(master, topo, size, id_))
    system("sleep 3")
    system("lxc exec {} -- /root/hadoop-2.7.6/sbin/start-yarn.sh > tests/{}_{}_{}_yarn.log 2>&1".format(master, topo, size, id_))
    system("sleep 3")
    system("lxc exec {} -- /root/hadoop-2.7.6/bin/hdfs dfs -mkdir -p /user/root > tests/{}_{}_{}_hdfs.log 2>&1".format(master, topo, size, id_))
    system("sleep 3")
    system("lxc exec {} -- /root/hadoop-2.7.6/bin/hadoop jar  /root/hadoop-2.7.6/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.7.6.jar pi 400 400 > tests/{}_{}_{}_test.log 2>&1".format(master, topo, size, id_))
    system("sleep 3")
    system("lxc exec {} -- echo FINISHED >> tests/{}_{}_{}_test.log".format(master, topo, size, id_))
    for host in hosts:
        bridge = "br_{}".format(host)
        system("lxc delete {} --force".format(host))
        system("ip link delete {}".format(bridge))

    system("killall screen")
    system("mn -c")

if __name__ == '__main__':
    topo = "litelinear"
    sizes = [10]
    system("mkdir -p tests")
    for s in sizes:
        for _ in range(1):
            test(topo, s)


import time
from mininet.log import info, debug, warn, error, output
from mininet.dutil import (default_images)

def iperf_test(mn):
    topo = mn.topo
    # iperf servers
    for h in mn.hosts:
        cmd = "nohup iperf -s &"
        h.cmd(cmd)

    # iperf clients
    l = len(mn.hosts)
    half = int(l/2)
    info ("*** Generate background traffic:")
    for i in range(half-1):
        info (" {}->{}".format(mn.hosts[i], mn.hosts[-i-1]))
        t = 120
        cmd = "nohup iperf -t {} -c {} &".format(t, mn.hosts[-i-1].IP())
        mn.hosts[i].cmd(cmd)
    info ("\n")

    info ("*** Measure throughput: {}->{}\n".format(mn.hosts[half-1], mn.hosts[-(half-1)-1]))
    time.sleep(20)
    cmd = "iperf -t {} -c {}".format(60, mn.hosts[-(half-1)-1].IP())
    iperfOutput = mn.hosts[half-1].cmd(cmd)
    output (mn._parseIperf(iperfOutput))

    for h in mn.hosts:
        h.cmd("killall -9 iperf")

# we need the right images to run iperf
PREBUILD = [default_images]

# adding the test in the suite
TESTS = {'iperfall':iperf_test}

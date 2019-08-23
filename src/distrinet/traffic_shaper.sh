# from https://wiki.archlinux.org/index.php/advanced_traffic_control
INTERFACE=enp0s8
tc qdisc del root dev $INTERFACE
tc qdisc add dev $INTERFACE root handle 1: htb default 30
tc class add dev $INTERFACE parent 1: classid 1:1 htb rate 100mbit burst 15k

# The previous class has this branches:

# Class 1:10, which has a rate of 5mbit
tc class add dev $INTERFACE parent 1:1 classid 1:10 htb rate 5mbit burst 15k

# Class 1:20, which has a rate of 3mbit but can go up to 100mbit if free space
tc class add dev $INTERFACE parent 1:1 classid 1:20 htb rate 3mbit ceil 100mbit burst 15k

# Class 1:30, which has a rate of 1kbit that can go up to 6mbit. This one is the default class.
tc class add dev $INTERFACE parent 1:1 classid 1:30 htb rate 1kbit ceil 6mbit burst 15k

# Martin Devera, author of HTB, then recommends SFQ for beneath these classes:
tc qdisc add dev $INTERFACE parent 1:10 handle 10: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:20 handle 20: sfq perturb 10
tc qdisc add dev $INTERFACE parent 1:30 handle 30: sfq perturb 10


# This command adds a filter to the qdisc 1: of dev ${INTERFACE}, set the
# priority of the filter to 1, matches packets with a
# destination port 5001, and make the class 1:10 process the
# packets that match.
tc filter add dev $INTERFACE protocol ip parent 1: prio 1 u32 match ip dport 5001 0xffff flowid 1:10

# This command adds a filter to the qdisc 1: of dev ${INTERFACE}, set the
# priority of the filter to 2, matches packets with a
# destination port 5002, and make the class 1:20 process the
# packets that match.
tc filter add dev $INTERFACE protocol ip parent 1: prio 2 u32 match ip dport 5002 0xffff flowid 1:20



# This filter is attached to the qdisc 1: of dev ${INTERFACE}, has a
# priority of 2, and matches the ip address 4.3.2.1 exactly, and
# matches packets with a source port of 80, then makes class
# 1:11 process the packets that match
#tc filter add dev ${INTERFACE} parent 1: protocol ip prio 2 u32 match ip src 4.3.2.1/32 match ip sport 80 0xffff flowid 1:11
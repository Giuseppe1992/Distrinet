# DMN

## Deployment in Amazon

```
python3 bin/dmn --provision=aws --controller=lxcremote,ip=192.168.0.1
```

With the possibility to overwrite default parameters:

```
python3 bin/dmn --provision=aws,3,instanceType=t3.2xlarge,volumeSize=10 --controller=lxcremote,ip=192.168.0.1
```

would instantiate a total of 3 t3.2xlarge instances, each one with a volume
size of 10 GiB.

## Using running cluster

Specify the bastion address in the `ssh` section of the `~/.distrinet/conf.yml`
file or using the `--bastion` option:

```
python3 bin/dmn [--bastion <bastion_ip>] --workers="<ip1>,<ip2>,...,<ipn>" --custom=default_image.py
```

## Note

To connect to an already started controller:

```
--controller=lxcremote,ip=<ip>
```

where

* `<ip>` is an address reachable on the admin network where an OpenFlow controller listens

```
--controller=onoslxc,ip=<ip>,[admin_ip=<admin_ip>,target=<target_ip>]
```

where


* `<ip>` is an address reachable on the admin network where an OpenFlow
  controller listens,
* `<admin_ip>` is the admin IP address for the container,
* `<target_ip>` is the IP of the node where to deploy the container.

When `<admin_ip>` is not specified the `<ip>` address is used as admin IP.

When `<target>` is not specified, the master node is used to host the
controller.

# Port forwarding

To forward ports from bastion to a reachable machine, add an entry as follows
in the `port_forwarding` section of the `~/.distrinet/conf.yml` file.

```
port_forwarding:
  - local: <port number on which to listen>
    proto: '<protocol>'
    ip: '<ip address of the listening machine>'
    remote: <port number on the listening>
```

To forward ports from bastion to a container, add an entry as follows in the
`port_forwarding` section of the `~/.distrinet/conf.yml` file.

```
port_forwarding:
  - local: <port number on which to listen>
    proto: '<protocol>'
    container: '<container name>'
    ip: '<ip address of the listening machine>'
    remote: <port number on the listening>
```



# Runing Hadoop tests

```
--controller=lxcremote,ip=192.168.0.1 --custom hadoop_test.py --test hadoop
```

## Examples

```
python3 bin/dmn --workers="10.0.0.200,10.0.1.31,10.0.1.76" --topo=tree,2 --controller=lxcremote,ip=192.168.0.1 --custom=default_image.py
```

```
python3 bin/dmn --workers="10.0.0.200,10.0.1.31,10.0.1.76" --topo=tree,2 --controller=onoslxc,ip=192.168.0.250,admin_ip=192.168.0.250,target=10.0.0.200 --custom=default_image.py
```

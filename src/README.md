# DMN

## Deployment in Amazon

```
python3 dmn --provision=aws
```

## Using running cluster

Specify the bastion address in the `ssh` section of the `~/.distrinet/conf.yml`
file or using the `--bastion` option:

```
python3 dmn [--bastion <bastion_ip>] --workers="<ip1>,<ip2>,...,<ipn>"
```

## Note

To connect to an already started controller:

```
--controller=lxcremote,ip=<ip>
```

where

* `<ip>` is an address reachable on the admin network where an OpenFlow controller listens

```
--controller=onoslxc,ip=<ip>,admin_ip=<admin_ip>,target=<target_ip>
```

where

* `<ip>` is an address reachable on the admin network where an OpenFlow controller listens
* `<admin_ip>` is the admin IP address for the container
* `<target_ip>` is the IP of the node where to deploy the container


# Port forwarding

To forward ports from bastion to an emulated machine, add an entry in the
`port_forwarding` section of the `~/.distrinet/conf.yml` file.

```
port_forwarding:
  - local: 8181
    proto: 'tcp'
    ip: '192.168.0.250'
    remote: 8181
```

## Examples

```
python3 dmn --workers="10.0.0.200,10.0.1.31,10.0.1.76" --topo=tree,2 --controller=lxcremote,ip=192.168.0.1
```

```
python3 dmn --workers="10.0.0.200,10.0.1.31,10.0.1.76" --topo=tree,2 --controller=onoslxc,ip=192.168.0.250,admin_ip=192.168.0.250,target=10.0.0.200
```

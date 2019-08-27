# DMN

## Deployment in Amazon

```
python3 dmn --provision=aws
```

## Using running cluster

Specify the bastion address in the `ssh` section of the `~/.distrinet/conf.yml` file

```
python3 dmn --workers="<ip1>,<ip2>,...,<ipn>"
```

## Note

To connect to an already started controller:

```
--controller=lxcremote,ip=<ip>
```

where `<ip>` is an address reachable on the admin network where an OpenFlow controller listens

## Example

```
python3 dmn --workers="10.0.0.28,10.0.1.219,10.0.1.23" --topo=linear,4 --controller=lxcremote,ip=192.168.0.1
```

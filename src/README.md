# DMN

## Deployment in Amazon

```
python3 dmn --provision=aws
```

## Using running cluster

Specify the bastion address in the `ssh` section of the `~/.distrinet/conf.yml` file

```
python3 dmn --workers="ip1,ip2,...,ipn"
```

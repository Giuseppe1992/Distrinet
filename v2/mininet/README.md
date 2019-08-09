# How to run distrinet:
  
Make sure your PYTHONPATH contains the path to Mininet module and to the distrinet.cloud module

## Example
```
# export PYTHONPATH=$PYTHONPATH:/tmp/mininet:distrinet/cloud
```

# How to run iperf_test:

```
# python3 iperf_test.py --help
Usage: iperf_test.py [options]

Options:
  -h, --help            show this help message and exit
  --pub-id=pub_id       public key to access the cloud
  -n n                  number of hosts to emulate
  -s, --single          Should we run the experiment on one machine only
  -j jump, --jump=jump  jump node (bastion)
  -m master, --master=master
                        master node name
  -c cluster, --cluster=cluster
                        clusters nodes (their LXC name)
```

```
python3 iperf_test.py --pub-id="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDgEnskmrOMpOht9KZV2rIYYLKkw4BSd8jw4t9cJKclE9BEFyPFr4H4O0KR85BP64dXQgAYumHv9ufnNe1jntLhilFql2uXmLcaJv5nDFdn7YEd01GUN2QUkNy6yguTO8QGmqnpKYxYiKz3b8mWDWY2vXaPvtHksaGJu2BFranA3dEuCFsVEP4U295z6LfG3K0vr+M0xawhJ8GRUnX+EyjK5rCOn0Nc04CmSVjIpNazyXyni4cW4q8FUADtxoi99w9fVIlFcdMAgoS65FxAxOF11bM6EzbJczdN4d9IjS4NPBqcWjwCH14ZWUAXvv3t090tUQOLGdDOih+hhPjHTAZt root@7349f78b2047" -n 10  --jump "52.47.186.84" --master="ip-10-0-0-39" --cluster="ip-10-0-0-39,ip-10-0-1-247"
```

This example will deploy the test for a topology of 10 nodes (i.e., `n=10`) connecting to the cloud via IP address `52.47.186.84` to connect to the LXC cluster composed of the machines `ip-10-0-0-39` and `ip-10-0-1-247` where `ip-10-0-0-39` is the master node.

By default the experiment is split between the two first hosts of the cluster. If the `-s` flag is used, the experiment is run entirely on the first node.

It assumes that the cluster is already deployed and images 'ubuntu' and 'switch' are exported in LXC.

It also assumes that a controller runs on the master node (e.g., ryu).
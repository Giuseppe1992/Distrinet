from distrinet.cloud.provision import Provision

def default_images(*args, **kwargs):
    conf = Provision.get_configurations()
    ssh_conf = conf["ssh"]
    pub_id = ssh_conf["pub_id"]
#    client_keys = ssh_conf["client_keys"]
#    if isinstance(client_keys, str):
#        client_keys = [client_keys]
#    user = ssh_conf["user"]
#    jump = ssh_conf.get("bastion", None)

    topo = kwargs['topo']

    sopts={"image":"switch","controller":"c0", 'pub_id':pub_id, "cpu":4, "memory":"2GB"}
    hopts={"image":"ubuntu", 'pub_id':pub_id, "cpu":2, "memory":"4GB"}
    lopts={"rate":1000,"bw":1000}

    topo.hopts.update(hopts)
    topo.sopts.update(sopts)
    topo.lopts.update(lopts)
    for n in topo.hosts():
        infos = {}
        infos.update(topo.nodeInfo(n))
        infos.update(hopts)
        topo.setNodeInfo(n, infos)
    for n in topo.switches():
        infos = {}
        infos.update(topo.nodeInfo(n))
        infos.update(sopts)
        topo.setNodeInfo(n, infos)

PREBUILD = [default_images]

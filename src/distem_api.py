import requests
import json

DISTEM_PORT = 4567

class distem_api(object):
    def __init__(self, coordinator, user):
        self.coordinator = coordinator
        self.distem_port = DISTEM_PORT
        self.user = user
        self.header = {"Accept": "*/*","Accept-Encoding": "gzip", "Content-Type": "application/x-www-form-urlencoded"}

    def execute_command_rest(self, vnodes, command):
        data='names='+str(vnodes).replace(" ", "").replace("'",'"')+'&command="{}"'.format(command)
        response = requests.post("http://{}:{}/commands/".format(self.coordinator, self.distem_port), data=data, headers=self.header)
        return response.status_code, response.content



    def start_vnodes_rest(self, list_of_nodes):
        data='names='+str(list_of_nodes).replace(" ", "").replace("'",'"')+'&async=false&type=update&desc={"status":"RUNNING"}'
        response = requests.put("http://{}:{}/vnodes".format(self.coordinator, self.distem_port), data=data, headers=self.header)
        return response.status_code, response.content

    def add_vnode_rest(self, name, image, host,  shared="true"):
        desc='{"host":"'+host+'","vfilesystem":{"image":"'+image+'","shared":'+shared+'}}'
        data = 'name={}&desc={}'.format(name,desc)

        response=requests.post("http://{}:{}/vnodes/{}".format(self.coordinator, self.distem_port, name), data=data, headers=self.header)
        return response, response.content

    def create_vnet_rest(self,vnet,address, network_type="vxlan"):
        addr, sub = address.split("/")
        desc = '{"network_type":"'+network_type+'"}'
        data = 'name={}&address={}/{}&opts={}'.format(vnet,addr,sub,desc)#

        response = requests.post("http://{}:{}/vnetworks".format(self.coordinator, self.distem_port),
                                data=data, headers=self.header)
        return response, response.content

    def get_iface_ip(self, vnode, iface="ifadm"):
        response = requests.get("http://{}:{}/vnodes/{}/ifaces/{}/".format(self.coordinator, self.distem_port, vnode, iface),headers=self.header)
        return dict(json.loads(response.text))["address"]

    def set_vnetwork_rest(self, vnode, iface, vnetwork, address):
        desc = '{"address":"' + address + '/24","vnetwork":"' + vnetwork + '"}'
        data = 'name={}&desc={}'.format(iface, desc)
        response = requests.post("http://{}:{}/vnodes/{}/ifaces/".format(self.coordinator, self.distem_port, vnode),
                                 data=data,
                                 headers=self.header)
        return response, response.content
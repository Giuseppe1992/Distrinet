from mininet.provision.provision import Provision
import requests
import base64
import json
from time import sleep
import paramiko
import os

conf = Provision.get_configurations()
ssh_conf = conf["ssh"]
g5k_conf = conf["g5k"]
G5K_USER = g5k_conf["g5k_user"]
G5K_PASS = g5k_conf["g5k_password"]
KEY = ssh_conf["pub_id"]
IMAGE = g5k_conf["image_name"]
USERNAME = ssh_conf["user"]
LOCATION = g5k_conf["location"]
CLUSTER = g5k_conf["cluster"]
SRC_PLAYBOOKS_DIR = "distrinet/cloud/playbooks"
DST_PLAYBOOKS_DIR = "/root/playbooks"


class g5k(Provision):
    def __init__(self, user, password, Image, Key, walltime="2:00", nodes="1", Location="nancy", cluster='grisou',
                 command="sleep 7d", **kwargs):
        super(g5k, self).__init__(user, password, Image=IMAGE, Key=KEY, walltime="2:00", nodes="1", Location="nancy",
                                  cluster=cluster, command="sleep 7d", **kwargs)

        self.user = user
        self.password = password
        user_password = ":".join([user, password])
        self.authorization = str(base64.b64encode(user_password.encode('ascii')), "utf-8")
        self.header = {"Accept": "*/*", "Content-Type": "application/json",
                       "Authorization": "Basic " + self.authorization}

        self.image = Image
        self.key = Key
        self.walltime = walltime
        self.nodes = nodes
        self.location = Location
        self.cluster = cluster
        self.command = command


    @staticmethod
    def makeReservation(header, walltime="2:00", nodes="1", location="nancy", cluster="grisou", command="sleep 1d"):
        js = {
            "command": command,
            "resources": "nodes=" + str(nodes) + ",walltime=" + walltime,
            "properties": "cluster='{}'".format(cluster),
            "types": [
                "deploy"
            ]
        }

        response = requests.post("https://api.grid5000.fr/3.0/sites/{}/jobs".format(location), json.dumps(js),
                                 headers=header)
        return response.text

    @staticmethod
    def getReservationNodes(header, location, reservation_id):
        link = "https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(location, reservation_id)
        response = requests.get(link, headers=header)
        return eval(response.text)['assigned_nodes']

    @staticmethod
    def getReservation(header, location, reservation_id):
        link = "https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(location, reservation_id)
        response = requests.get(link, headers=header)
        return eval(response.text)

    @staticmethod
    def extractReservationId(makeReservationResponse):
        dict_response = eval(makeReservationResponse)
        if "uid" not in dict_response:
            raise Exception("Wrong Reservation response")
        return dict_response["uid"]

    @staticmethod
    def checkJobState(Header, Location, Reservation_id):
        """check the state of a job, it can be running, waiting or error"""
        link = "https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(Location, Reservation_id)
        response = requests.get(link, headers=Header)
        return eval(response.text)["state"]

    @staticmethod
    def checkDeploymentState(Header, Location, Deployment_id):
        null = None
        """check the state of a job, it can be running, waiting or error"""
        link = "https://api.grid5000.fr/3.0/sites/{}/deployments/{}".format(Location, Deployment_id)
        response = requests.get(link, headers=Header)
        return eval(response.text)['status']

    @staticmethod
    def waitJobInRunningState(Header, Location, ReservationId):
        while g5k.checkJobState(Header=Header, Location=Location, Reservation_id=ReservationId) != "running":
            if g5k.checkJobState(Header=Header, Location=Location, Reservation_id=ReservationId) == "error":
                raise Exception("Reservation in error state")
            sleep(4)

    @staticmethod
    def waitDeploymentInReadyState(Header, Location, DeploymentID):
        while g5k.checkDeploymentState(Header=Header, Location=Location, Deployment_id=DeploymentID) != "terminated":
            state = g5k.checkDeploymentState(Header=Header, Location=Location, Deployment_id=DeploymentID)
            print(state)
            if state == "error":
                raise Exception("Deployment in error state")
            sleep(4)

    def reserveNodes(self, walltime="2:00", nodes="1", location="nancy", cluster="grisou", command="sleep 1d",
                     reservation_id=None):
        print(self.user, self.password, self.header)
        reservation = self.makeReservation(header=self.header, walltime=walltime, nodes=nodes, location=location,
                                           cluster=cluster, command=command)
        print(reservation)
        sleep(2)
        reservation_id = self.extractReservationId(reservation)

        self.waitJobInRunningState(Header=self.header, Location=location, ReservationId=reservation_id)
        print(reservation_id)

        nodes = self.getReservationNodes(self.header, location=location, reservation_id=reservation_id)
        print(nodes)
        return nodes

    @staticmethod
    def installImage(Header, Location, Nodes, Image, Key):
        js = {
            "nodes": Nodes,
            "environment": Image,
            "key": Key,
        }
        print(js)
        response = requests.post("https://api.grid5000.fr/3.0/sites/{}/deployments".format(Location),
                                 json.dumps(js), headers=Header)
        return response.text

    @staticmethod
    def extractDeploymentId(installImageResponse):
        dict_response = eval(installImageResponse)
        if "uid" not in dict_response:
            raise Exception("Wrong Deployment response")
        return dict_response["uid"]

    @staticmethod
    def createKeyPair(hostname, username="root"):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=hostname, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            "echo -e 'y\n' | ssh-keygen -f $HOME/.ssh/id_rsa -t rsa -N ''")
        sleep(1)

        print(ssh_stdout.read())

        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command("cat $HOME/.ssh/id_rsa.pub")
        sleep(1)

        id_rsa_pub = ssh_stdout.read()

        ssh_connection.close()
        return str(id_rsa_pub, 'utf-8').strip()

    @staticmethod
    def setupMasterAutorizedKeysOnWorkers(pub_id, WorkerHostsIp):
        """
        Append the Master authorized_keys on the Slaves Authorized Keys
        :param pub_id: public_id to authorize
        :param WorkerHostsIp: list of the worker host private Ip
        :return: None
        """

        for workerIp in WorkerHostsIp:
            print(pub_id)
            command = "echo '' >> $HOME/.ssh/authorized_keys; echo  '{}' >> $HOME/.ssh/authorized_keys".format(pub_id)
            print(WorkerHostsIp)
            session = g5k.createSshSession(host=workerIp, username=USERNAME)
            g5k.executeCommand(SshSession=session, command=command)
            g5k.closeSshSession(SshSession=session)

    def InstallImageInTheNodes(self, Image, Location, Nodes, Key):
        Master = Nodes[0]
        Workers = Nodes[1:]
        deploymentNodes = self.installImage(Header=self.header, Location=Location, Nodes=Nodes, Image=Image,
                                             Key=Key)
        deploymentNodesId = self.extractDeploymentId(deploymentNodes)
        print(deploymentNodesId)
        self.waitDeploymentInReadyState(Header=self.header, Location=Location, DeploymentID=deploymentNodesId)

        publicKey = self.createKeyPair(hostname=Master, username=USERNAME)

        self.setupMasterAutorizedKeysOnWorkers(pub_id=publicKey, WorkerHostsIp=Workers)

        sshMasterSession = self.createSshSession(host=Master, username=USERNAME)

        self.setupMasterHost(SshSession=sshMasterSession)
        sleep(2)
        self.setAnsibleHosts(SshSession=sshMasterSession, MasterHostIp=Master, WorkersList=Workers)
        self.copyFilesInHost(SshSession=sshMasterSession, SrcDir=SRC_PLAYBOOKS_DIR, DstDir=DST_PLAYBOOKS_DIR)
        sleep(2)
        self.installEnvironment(SshSession=sshMasterSession, PlaybookPath=DST_PLAYBOOKS_DIR + "/install-g5k-lxd.yml")
        sleep(2)
        self.configureLxd(SshSession=sshMasterSession, MasterPrivateIp=Master, PlaybookPath=DST_PLAYBOOKS_DIR)
        return Master, Workers

    def deploy(self):
        reservedNodes = self.reserveNodes(walltime=self.walltime, nodes=self.nodes, location=self.location,
                                          cluster=self.cluster, command=self.command)
        Master, Workers = self.InstallImageInTheNodes(Image=self.image, Location=self.location, Nodes=reservedNodes,
                                                      Key=self.key)
        return Master, Workers


if __name__ == '__main__':
    obj = g5k(user=G5K_USER, password=G5K_PASS, Image=IMAGE, Key=KEY, Location=LOCATION, nodes="3", walltime="2:00",

              cluster=CLUSTER)
    r = obj.deploy()
    print(r)
    #obj.setupMasterAutorizedKeysOnWorkers(pub_id="HELLO",WorkerHostsIp=['grisou-9.nancy.grid5000.fr'])
    #print(obj.createKeyPair(hostname='grisou-31.nancy.grid5000.fr'))
    #print(1)

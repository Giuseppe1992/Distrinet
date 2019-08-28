from provision import Provision
import requests
import base64
import json
from time import sleep
import paramiko
import os

KEY = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDN+7brU3dYYrMLrjO3+MAO7xGQATwA47FfzIxxjOkbpuP7zCOGSuJK1g9fRkPK5psygt' \
      'lbGsklTgGqfRntTNU0rK9u7KSFy4+WwCAQ1gKHDRjKjNrvpgqt9994SnqIBd8B8nTAP6YriOdrsLCLOfZZR17iL63KQlmeEl5/Rpitj6Rc' \
      'SaY4Xkmozg8eH7hBVaVoA6tCGelUHe+xYPJ+YJN/v13Qprb49ngPSweX/BhCQ1QiXtNlsVI1YI0Y5QoZbeSlUgj/e8gVYnBSXN788xEs/W' \
      '3n3EM+PcWAUoayg0NZlfbmBG65/jgNlQruD/zEiXyO9JclCAcsQttplTQXQ1a/ giuseppe@eduroam-249a.sophia.inria.fr'

IMAGE = 'ubuntu1804-x64-python3'
USERNAME = "root"
SRC_PLAYBOOKS_DIR = "playbooks"
DST_PLAYBOOKS_DIR = "/tmp/playbooks"


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
        return str(id_rsa_pub, 'utf-8')

    def InstallImageInTheNodes(self, Image, Location, Nodes, Key):
        Master = Nodes[0]
        Workers = Nodes[1:]
        deploymentMaster = self.installImage(Header=self.header, Location=Location, Nodes=[Master], Image=Image,
                                             Key=Key)
        deploymentMasterId = self.extractDeploymentId(deploymentMaster)
        print(deploymentMasterId)
        self.waitDeploymentInReadyState(Header=self.header, Location=Location, DeploymentID=deploymentMasterId)
        publicKey = self.createKeyPair(hostname=Master, username=USERNAME)

        deploymentWorkers = self.installImage(Header=self.header, Location=Location, Nodes=Workers, Image=Image,
                                              Key=publicKey)
        deploymentWorkersId = self.extractDeploymentId(deploymentWorkers)
        sshMasterSession = self.createSshSession(host=Master, username=USERNAME)

        self.setupMasterHost(SshSession=sshMasterSession)
        sleep(2)
        self.setAnsibleHosts(SshSession=sshMasterSession, MasterHostIp=Master, WorkersList=Workers)
        self.copyFilesInHost(SshSession=sshMasterSession, SrcDir=SRC_PLAYBOOKS_DIR, DstDir=DST_PLAYBOOKS_DIR)
        sleep(2)
        self.waitDeploymentInReadyState(Header=self.header, Location=Location, DeploymentID=deploymentWorkersId)
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
    with open("g5k_credentials.json", "r") as credentials_file:
        credentals_json = eval(credentials_file.read())
        username, password = credentals_json["username"], credentals_json["password"]
    obj = g5k(user=username, password=password, Image=IMAGE, Key=KEY, Location='nancy', nodes="2", walltime="5:00",
              cluster="grisou")
    r = obj.deploy()
    print(r)

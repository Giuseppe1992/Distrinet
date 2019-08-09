import boto3
import paramiko
from time import sleep
import os

"""
1 Create VPC
2 Create public and private subnet
3 Create Internet-Gateway and Nat-gateway
4 Create public and private route
5 Keys 
6 NACL for security 
7 Create Hosts
"""


class distrinetAWS(object):
    def __init__(self):
        self.ec2 = boto3.resource('ec2')
        self.ec2Client = boto3.client('ec2')
        self.vpc = None
        self.IGW = None
        self.NGW = None
        self.publicRouteTable = None
        self.privateRouteTable = None
        self.publicSubnet = None
        self.privateSubnet = None
        self.bastionHost = None
        self.workerNodes = None
        self.bastionPublicIp = None
        self.hosts_id = []

    def createVPC(self, VPCName="Distrinet_VPC", addressPoolVPC="10.0.0.0/16", **kwargs):
        self.vpc = self.ec2.create_vpc(CidrBlock=addressPoolVPC)
        self.vpc.create_tags(Tags=[{"Key": "Name", "Value": VPCName}])
        self.vpc.wait_until_available()
        return self.vpc.id

    def createSubnet(self, subnetName, subnetNetwork, routeTable):
        subnet = self.ec2.create_subnet(CidrBlock=subnetNetwork, VpcId=self.vpc.id)
        subnet.create_tags(Tags=[{"Key": "Name", "Value": subnetName}])
        routeTable.associate_with_subnet(SubnetId=subnet.id)
        print(subnet)
        return subnet.id

    def createIGW(self):
        self.IGW = self.ec2.create_internet_gateway()
        self.vpc.attach_internet_gateway(InternetGatewayId=self.IGW.id)


    def createNGW(self, subnetID):
        eip = self.ec2Client.allocate_address(Domain='vpc')
        print(eip)
        self.NGW = self.ec2Client.create_nat_gateway(SubnetId=subnetID, AllocationId=eip['AllocationId'])

        print(self.NGW)


    def createRouteTables(self):
        self.publicRouteTable = self.vpc.create_route_table()
        self.publicRouteTable.create_tags(Tags=[{"Key": "Name", "Value": "PublicRouteTableScript"}])
        self.privateRouteTable = self.vpc.create_route_table()
        self.privateRouteTable.create_tags(Tags=[{"Key": "Name", "Value": "PrivateRouteTableScript"}])

    def addRoute(self, routeTable, GatewayId, DestinationCidrBlock='0.0.0.0/0', **kwargs):
        routeTable.create_route(GatewayId=GatewayId, DestinationCidrBlock=DestinationCidrBlock)

    def createBastionHost(self, SubnetId, instanceType="t2.micro", KeyName="id_rsa", imageId="ami-090f10efc254eaf55"):
        bastionId = self.createWorkerHosts(SubnetId=SubnetId, numberOfInstances=1, instanceType=instanceType,
                                           KeyName=KeyName, imageId=imageId)
        self.bastionHost = bastionId[0]
        self.bastionPrivateIp = self.hosts[0]['PrivateIpAddress']
        return bastionId[0]

    def assign_eip(self, instanceId):
        eip = self.ec2Client.allocate_address(Domain='vpc')
        self.ec2Client.associate_address(AllocationId=eip['AllocationId'], InstanceId=instanceId)
        return eip

    def waitInstancesRunning(self, instancesList):
        print(instancesList)
        self.ec2Client.get_waiter('instance_running').wait(Filters=[{'Name': "instance-id", "Values": instancesList}])

    def createWorkerHosts(self, SubnetId, numberOfInstances, instanceType="t2.micro", KeyName="id_rsa",
                          imageId="ami-090f10efc254eaf55"):
        hosts = self.ec2Client.run_instances(SubnetId=SubnetId, ImageId=imageId, InstanceType=instanceType,
                                             KeyName=KeyName, MaxCount=numberOfInstances, MinCount=numberOfInstances)

        hosts_id = []
        for host in hosts['Instances']:
            print(host)
            hosts_id.append(host['InstanceId'])

        self.hosts_id = hosts_id
        self.hosts = hosts["Instances"]

        return hosts_id

    def create_security_group(self, vpc_id):
        response = self.ec2Client.create_security_group(GroupName='Distrinet',
                                                        Description='Distrinet',
                                                        VpcId=vpc_id)
        print(response)
        security_group_id = response['GroupId']
        print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))
        data = self.ec2Client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 0,
                 'ToPort': 65353,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ])
        print('Ingress Successfully Set %s' % data)
        return security_group_id

    def setupBastionHost(self, master_host, privateKey, username='ubuntu'):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=master_host, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            'sudo echo -e "{}" > $HOME/.ssh/id_rsa'.format(privateKey))
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('sudo chmod 0400 $HOME/.ssh/id_rsa')
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('sudo cp $HOME/.ssh/id_rsa /root/.ssh/id_rsa')
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('sudo apt update -y')
        print (ssh_stdout.read(), ssh_stderr.read())
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('sudo apt install -y ansible')
        print (ssh_stdout.read(), ssh_stderr.read())
        return

    def grantRootAccess(self, host, username='ubuntu'):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=host, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            'sudo rm /root/.ssh/authorized_keys; sudo cp $HOME/.ssh/authorized_keys /root/.ssh/authorized_keys')

        print (host, "STD_OUT", ssh_stdout.read(), "STD_ERR", ssh_stderr.read())
        return

    def modifyGroupId(self, instanceId, Groups):
        r = []
        for id_ in instanceId:
            r.append(self.ec2Client.modify_instance_attribute(InstanceId=id_, Groups=Groups))
        print(r)

    def createKeyPair(self, KeyName="distrinetPair"):
        self.ec2Client.delete_key_pair(KeyName=KeyName)
        response = self.ec2Client.create_key_pair(KeyName=KeyName)
        return response["KeyMaterial"]

    def setAnsibleHosts(self, master, workers, username="root"):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=master, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('echo "[master]" >> /etc/ansible/hosts')
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            'echo "{} ansible_connection=local ansible_python_interpreter=/usr/bin/python3" >> /etc/ansible/hosts'.format(
                master))
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command('echo "[workers]" >> /etc/ansible/hosts')

        for worker in workers:
            ssh_connection.exec_command(
                'echo "{} ansible_ssh_extra_args=\'-o StrictHostKeyChecking=no\' ansible_python_interpreter=/usr/bin/python3" >> /etc/ansible/hosts'.format(
                    worker))

    def copy_files_in_host(self, host, source_dir, dest_dir, username="ubuntu"):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=host, username=username)
        ssh_connection.exec_command("mkdir $HOME/{}".format(dest_dir))
        ftp_client = ssh_connection.open_sftp()
        for file_ in os.listdir(source_dir):
            ftp_client.put("{}/{}".format(source_dir, file_), "{}/{}".format(dest_dir, file_))
        ssh_connection.close()

    def installEnvironment(self, master, username='ubuntu'):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=master, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            'ansible-playbook $HOME/playbooks/install-aws-lxd.yml')
        print (master, "STD_OUT", ssh_stdout.read(), "STD_ERR", ssh_stderr.read())

    def configureLXD(self, masterPublic, masterPrivate, username='root'):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=masterPublic, username=username)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh_connection.exec_command(
            'ansible-playbook /home/ubuntu/playbooks/configure-lxd.yml -e "master_ip={}"'.format(masterPrivate))
        print (masterPublic, "STD_OUT", ssh_stdout.read(), "STD_ERR", ssh_stderr.read())

    def build(self, VPCName="Distrinet_VPC_1", addressPoolVPC="10.0.0.0/16", publicSubnetNetwork="10.0.0.0/24",
              privateSubnetNetwork="10.0.1.0/24", bastionInstanceType='t2.micro', hostsInstanceType='t2.micro',
              numberOfInstances=2):
        self.createVPC(VPCName=VPCName, addressPoolVPC=addressPoolVPC)
        self.createIGW()
        self.createRouteTables()
        security_group_id = self.create_security_group(self.vpc.id)
        print("iDDDD", security_group_id)
        self.addRoute(self.publicRouteTable, self.IGW.id, DestinationCidrBlock='0.0.0.0/0')
        self.publicSubnet = self.createSubnet(subnetName="publicSubnetScript", subnetNetwork=publicSubnetNetwork,
                                              routeTable=self.publicRouteTable)

        self.createNGW(subnetID=self.publicSubnet)

        print(self.NGW["NatGateway"].keys())

        self.privateSubnet = self.createSubnet(subnetName="privateSubnetScript", subnetNetwork=privateSubnetNetwork,
                                               routeTable=self.privateRouteTable)

        self.createBastionHost(SubnetId=self.publicSubnet, instanceType=bastionInstanceType)
        self.modifyGroupId([self.bastionHost], [security_group_id])

        privateKey = self.createKeyPair(KeyName="distrinetPair")

        self.createWorkerHosts(SubnetId=self.privateSubnet, instanceType=hostsInstanceType,
                               numberOfInstances=numberOfInstances, KeyName="distrinetPair")
        self.modifyGroupId(self.hosts_id, [security_group_id])

        self.waitInstancesRunning([self.bastionHost])
        self.bastionPublicIp = self.assign_eip(self.bastionHost)['PublicIp']

        print(self.ec2Client.get_waiter('nat_gateway_available').wait(
            NatGatewayIds=[self.NGW["NatGateway"]["NatGatewayId"]]))
        self.addRoute(self.privateRouteTable, self.NGW["NatGateway"]["NatGatewayId"], DestinationCidrBlock='0.0.0.0/0')

        self.waitInstancesRunning(self.hosts_id)
        sleep(2)

        print(self.grantRootAccess(self.bastionPublicIp, username='ubuntu'))
        print(self.setupBastionHost(self.bastionPublicIp, privateKey=privateKey, username='ubuntu'))
        print(self.hosts)
        workers_ip = [x['PrivateIpAddress'] for x in self.hosts]
        self.setAnsibleHosts(self.bastionPublicIp, workers_ip)
        self.copy_files_in_host(self.bastionPublicIp, source_dir="./playbooks", dest_dir='playbooks/')
        sleep(1)
        self.installEnvironment(self.bastionPublicIp, username='ubuntu')
        self.configureLXD(self.bastionPublicIp, self.bastionPrivateIp, username='root')
        return self.bastionPublicIp

if __name__ == '__main__':
    o = distrinetAWS()
    print(o.build(bastionInstanceType='t2.large', hostsInstanceType='t2.large'))

from mininet.provision.provision import Provision
from time import sleep, time
import boto3
import os
import paramiko
import uuid
from botocore.exceptions import ClientError
import progressbar

conf = Provision.get_configurations()
azure_conf = conf["azure"]
AZURE_REGION = azure_conf["region"]
SRC_PLAYBOOKS_DIR = "mininet/provision/playbooks"
DST_PLAYBOOKS_DIR = "/root/playbooks"
VOLUME_SIZE= int(azure_conf["volumeSize"])
MAIN_USER = azure_conf["user"]
KEY_PAIR_NAME_WORKERS = 'DistrinetKey-' + str(uuid.uuid4().hex)
IP_PERMISSION = azure_conf["network_acl"]
IMAGE_NAME_AZURE = azure_conf["image_name"]
KEY_PAIR_NAME_BASTION = azure_conf["key_name_azure"]


class distrinetAzure(Provision):
    ec2Resource = boto3.resource('ec2', region_name=AZURE_REGION)
    ec2Client = boto3.client('ec2', region_name=AZURE_REGION)

    def __init__(self, VPCName, addressPoolVPC, publicSubnetNetwork, privateSubnetNetwork, bastionHostDescription,
                 workersHostsDescription, **kwargs):
        super(distrinetAzure, self).__init__(VPCName, addressPoolVPC, publicSubnetNetwork, privateSubnetNetwork,
                                           bastionHostDescription, workersHostsDescription, **kwargs)

        self.VPCName = VPCName
        self.addressPoolVPC = addressPoolVPC
        self.publicSubnetNetwork = publicSubnetNetwork
        self.privateSubnetNetwork = privateSubnetNetwork
        self.bastionHostDescription = bastionHostDescription
        self.workersHostsDescription = workersHostsDescription
        self.param = kwargs


    @staticmethod
    def CreateVPC(VpcName, addressPoolVPC, **kwargs):
        """
        Create a vpc Object using boto3.resource('ec2')
        :param VpcName: Name of the new vpc
        :param addressPoolVPC: Ipv4 Address pool assigned to the vpc, be careful to assign a valid address pool: you can
         check if your pool is valid at: https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html
        :param kwargs: Optional parameters that you can assign to the Vpc
        :return: Vpc object from boto3.resource('ec2')
        """


    @staticmethod
    def CheckResources(VpcNeeded=1, ElasticIpNeeded=2, instancesNeeded=(("t3.2xlarge", 2),)):
        pass

    @staticmethod
    def getAllInstancesInVPC(VpcId):
        """
        get all the instances type, with the private ip in the vpc
        :param vpcId: Id of the Vpc
        :return: list containing tuples of (instance_type, private_ip)
        """
        pass

    @staticmethod
    def removeVPC(VpcId):
        """
        Remove the vpc using boto3.resource('ec2')
        :param vpcId: Id of the Vpc
        :return: client response
        Script adapted from https://gist.github.com/vernhart/c6a0fc94c0aeaebe84e5cd6f3dede4ce
        TODO: Make it cleaner and more modular, seems to work now, but the code is terrible

        """
        pass

    @staticmethod
    def getImageAMIFromRegion(Region, ImageName):
        """
        Return the imageId (ami-xxxxxxxx) for a given ImageName and a given region. Note that an imageId is different
        for the same image in a different region.
        :param Region: regione name ex. eu-central-1 or us-west-1 etc.
        :param ImageName: image Name provided by in the amazon description,
                ex. ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-20190722.1 for Ubuntu bionic
        :return:  string containing the ImageId
        """
        pass

    @staticmethod
    def modifyEnableDnsSupport(VpcId, Value=True):
        """
        Modify the parameter EnableDnsSupport in a given VPC with the new Value
        :param VpcId: VpcId where to modify EnableDnsSupport
        :param Value: new value of EnableDnsSupport
        :return: None
        """
        pass
    @staticmethod
    def modifyEnableDnsHostnames(VpcId, Value=True):
        """
        Modify the parameter EnableDnsHostnames in a given VPC with the new Value
        :param VpcId: VpcId where to modify EnableDnsHostnames
        :param Value: new value of EnableDnsHostnames
        :return: None
        """
        pass

    @staticmethod
    def createSubnet(VpcId, subnetName, subnetNetwork, routeTable, **kwargs):
        """
        Create a subnet inside a Vpc
        :param VpcId: id of a Vpc already created; be careful, the Vpc should be ready, before creating a subnet
        :param subnetName: Subnet Name tag associated to the subnet
        :param subnetNetwork: Network pool to be assigned, be sure that the subnet is contained in the vpc pool, and
         that the subnet pool is valid. You can chec if it is a valid subnet at:
         https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html
        :param routeTable: Route table object associated to the subnet
        :param kwargs: Optional parameters that you can assign to the Subnet
        :return: subnet object from boto3.resource('ec2')
        """
        pass

    @staticmethod
    def createInternetGateWay(**kwargs):
        """
        Create an Internet Gateway
        :param kwargs: Optional parameters that you can assign to the gateway
        :return: Internet Gateway object from boto3.resource('ec2'), you can access the Id by: InternetGatewayObject.id
        """
        pass

    @staticmethod
    def attachInternetGateWayToVpc(Vpc, InternetGatewayId, **kwargs):
        """
        Attach an Internet gateway already created to a vpc
        :param Vpc: vpc object
        :param InternetGatewayId: internet gateway id
        :param kwargs: Optional parameters that you can assign
        :return: None
        """
        pass

    @staticmethod
    def createElasticIp(Domain='vpc', **kwargs):
        """
        Create a new Elastic Ip.Be careful, you can have at most 5 Elastic Ip per Region
        :param Domain: Domain of the Elastic Ip
        :param kwargs: Optional parameters that you can assign to the ElasticIp
        :return: ElasticIp Client response, you can access the Id by: ElasticIpObject["AllocationId"]
        """
        pass

    @staticmethod
    def assignElasticIp(ElasticIpId, InstanceId):
        """
        Assign an Elastic Ip to an instance
        :param ElasticIpId: Elastic Ip Id
        :param InstanceId: Instance Id, The instance has to be in a valid state
        :return: None
        """
        pass

    @staticmethod
    def createNatGateWay(SubnetId, AllocationId, **kwargs):
        """
        Create a new Nat Gateway
        :param SubnetId: Subnet where to assigne the Nat Gateway
        :param AllocationId: ElasticIp Id assigned to the Nat Gateway
        :return: NatGateway Client response, you can access the Id by: NatGatewayObject["NatGateway"]["NatGatewayId"]
        """
        pass

    @staticmethod
    def waitNatGateWaysAvailable(NatGatewaysId):
        """
        Wait until the NatGateway is in Available state
        :param NatGatewaysId: Nat Gateway Id
        :return: None
        """
        pass

    @staticmethod
    def createRouteTable(Vpc, TableName, **kwargs):
        """
        Create a new route table inside a Vpc
        :param Vpc: Vpc Object where to create the table
        :param TableName: Tag Name added to the new table
        :param kwargs: Optional parameters that you can assign to the RouteTable
        :return: Route Table Object
        """
        pass

    @staticmethod
    def addRoute(routeTable, GatewayId, DestinationCidrBlock, **kwargs):
        """
        Add new route in the route table
        :param routeTable: RouteTable Object
        :param GatewayId: Gateway Id to add in the route
        :param DestinationCidrBlock: Ip subnet to route. "0.0.0.0/0" for all the traffic
        :param kwargs: Optional parameters that you can assign to the route
        :return: Route Object
        """
        pass

    @staticmethod
    def runInstances(SubnetId, numberOfInstances, instanceType, KeyName, ImageId, **kwargs):
        """
        Run multiple instances in the specified SubnetId, using the specified KeyName pair and The specified Id
        :param SubnetId: SubnetId where to run the instance
        :param numberOfInstances: Number of instances that you want to run; be careful to not exceed the limits imposed
        by Amazon AWS
        :param instanceType: Type of instance that you want to run
        :param KeyName: KeyName present in your account
        :param ImageId: Image AMI id provided by Amazon AWS
        :param kwargs: Optional parameters to personalize your image, the correct documentation can be found at:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.run_instances
        :return: RunInstances Client response, boto3.client('ec2').run_instances()
        """
        pass

    @staticmethod
    def waitInstancesRunning(instancesIdList):
        """
        Wait until all the instance in input are in 'running state'
        :param instancesIdList: List of instances Ids
        :return: None
        """
        pass

    @staticmethod
    def extractInstancesId(runInstancesResponse):
        """
        Take in input the entire response from runInstance method and extract the Ids of all the instances created by
        the call
        :param runInstancesResponse: runInstance Response
        :return: List of Instance Ids
        """
        pass

    @staticmethod
    def createSecurityGroup(VpcId, GroupName="Distrinet", Description="Distrinet", **kwargs):
        """
        Create a new Security in the Vpc
        :param VpcId: Vpc Id where to create the new Security Group
        :param GroupName: Name of the Security Group, 'Distrinet by default'
        :param Description: description of the new Security Group
        :param kwargs: Optional parameters that you can assign to the Security Group
        :return: SecurityGroup Client response, you can access the Id by SecurityGroupResponse["GroupId"]
        """
        pass

    @staticmethod
    def extractSecurityGroupId(createSecurityGroupResponse):
        """
        Take in input the entire response from createSecurityGroup method and extract the Id of the Security Group
        :param createSecurityGroupResponse: createSecurityGroup response
        :return: Security Group Id
        """
        pass

    @staticmethod
    def AuthorizeSecurityGroupTraffic(GroupId, IpPermissions, Directions=[]):
        """
        Add a Security Group Rule in the Security Group
        :param GroupId: Security Group Id
        :param IpPermissions: Description of the rule, Tuo can find the documentation at:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.authorize_security_group_egress
        or:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.authorize_security_group_ingress
        :param Directions: list of the Direction of the rule, it can be :
        ['ingress','egress'] or ['egress'] or ['ingress']
        :return: tuple containing (ingressData, egressData), in case you dont specify one of the two,
        that part will be None.

        Example:
        >>> i, e = distrinetAzure.AuthorizeSecurityGroupTraffic("id-xxxx", {"RULES..."},Directions=["egress"])
        >>> i
            None
        >>> e
            SOMEDATA....

        """
        pass

    @staticmethod
    def modifyGroupId(instancesId, Groups, **kwargs):
        """
        Change the Security Groups Assigned to an instance
        :param instancesId: Instance where to modify the Security Groups
        :param Groups: List of Security groups Ids to set in the instance
        :param kwargs: Optional parameters that you can assign to the boto3.client("ec2").modify_instance_attribute
        method, you can find the correct documentation at:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.modify_instance_attribute
        :return: boto3.client("ec2").modify_instance_attribute response
        """
        pass

    @staticmethod
    def createKeyPair(KeyName, **kwargs):
        """
        Create a new Key pair in Your Account; if the KeyName already exist, it will override it
        :param KeyName: Name assigns to the new Kaypair
        :param kwargs: Optional parameters that you can assign to boto3.client("ec2").create_key_pair method,
        you can find the correct documentation at:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_key_pair
        :return:
        """
        pass

    @staticmethod
    def grantRootAccess(SshSession):
        """ Takes in input an SshSession object, from a User with root privileges, and allows to
        connect the root user by ssh
        :param SshSession: SshSession from a User with root privileges
        :return: the execution results of the commands
        """
        commands = []
        commands.append('sudo rm /root/.ssh/authorized_keys')
        commands.append('sudo cp $HOME/.ssh/authorized_keys /root/.ssh/authorized_keys')

        command = ";".join(commands)
        return distrinetAzure.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def setupBastionHost(SshSession, PrivateKey):
        """
        Takes in input an SshSession object, from a User with root privileges and copies the PrivateKey in the
        $HOME/.ssh/id_rsa and /root/.ssh/id_rsa; after that it update the system and install ansible
        :param SshSession: SshSession from a User with root privileges
        :param PrivateKey: Private key to install in the host from the SshSession
        :return:  the execution results of the commands
        """
        commands = []
        commands.append('sudo echo -e "{}" > $HOME/.ssh/id_rsa'.format(PrivateKey))
        commands.append('sudo chmod 0400 $HOME/.ssh/id_rsa')
        commands.append('sudo cp $HOME/.ssh/id_rsa /root/.ssh/id_rsa')
        commands.append('sudo apt update ')
        commands.append('sleep 5')
        commands.append('sudo DEBIAN_FRONTEND=noninteractive apt install -y -q software-properties-common')
        commands.append('sudo apt-add-repository --yes --update ppa:ansible/ansible')
        commands.append('sudo DEBIAN_FRONTEND=noninteractive apt install -y -q ansible')

        command = ";".join(commands)
        return distrinetAzure.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def setupMasterAutorizedKeysOnWorkers(SshSession, WorkerHostsIp):
        """
        Append the Master authorized_keys on the Slaves Authorized Keys
        :param SshSession: SshSession from a User with root privileges
        :param WorkerHostsIp: list of the worker host private Ip
        :return: None
        """
        command = "cat $HOME/.ssh/authorized_keys"
        i, sessionAuthorizedKeys, e = distrinetAzure.executeCommand(SshSession=SshSession, command=command)

        for workerIp in WorkerHostsIp:
            command = " ssh root@{} echo '{} >> $HOME/.ssh/authorized_keys'".format(workerIp, str(sessionAuthorizedKeys,
                                                                                                  "utf-8")[:-1])
            distrinetAzure.executeCommand(SshSession=SshSession, command=command)


    @staticmethod
    def releaseElasticIP(ElasticIpID):
        """
        release An elastic IP
        :param ElasticIpID: IP id
        :return: client responce
        """


    def __aws_resource_check(self):
        pass

    def __aws_vpc__configuration(self):
        pass

    def __aws_deploy(self):
        pass

    def deploy(self):
        pass

def awsProvisionHelper(*args, instanceType='t3.2xlarge', volumeSize=10, **kwargs):
    pass

def optimizationAzureHelper(node_assigement):
    pass

if __name__ == '__main__':
    a={'host_2': ('t3.xlarge', 0), 'host_1': ('t3.xlarge', 0), 'host_3': ('t3.xlarge', 1), 'host_4': ('t3.xlarge', 1),
       'aggr_1': ('t3.xlarge', 2), 'core_1': ('t3.xlarge', 2), 'aggr_2': ('t3.xlarge', 3), 'edge_1': ('t3.xlarge', 3),
       'edge_2': ('t3.xlarge', 4)}
    optimizationAzureHelper(a)



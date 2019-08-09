from provision import Provision
from time import sleep, time
import boto3
import os
import paramiko

AWS_REGION = 'eu-central-1'
SRC_PLAYBOOKS_DIR = "../../../../src/playbooks"
DST_PLAYBOOKS_DIR = "/tmp/playbooks"
MAIN_USER = "ubuntu"
KEY_PAIR_NAME = 'DistrinetKeyGiuseppe'
IP_PERMISSION = [{'IpProtocol': "-1", 'FromPort': 1, 'ToPort': 65353, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}]

class distrinetAWS(Provision):
    ec2Resource = boto3.resource('ec2', region_name=AWS_REGION)
    ec2Client = boto3.client('ec2', region_name=AWS_REGION)

    def __init__(self, VPCName, addressPoolVPC, publicSubnetNetwork, privateSubnetNetwork, bastionHostDescription,
                 workersHostsDescription, **kwargs):
        super(distrinetAWS, self).__init__(VPCName, addressPoolVPC, publicSubnetNetwork, privateSubnetNetwork,
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
        vpc = distrinetAWS.ec2Resource.create_vpc(CidrBlock=addressPoolVPC, **kwargs)
        vpc.create_tags(Tags=[{"Key": "Name", "Value": VpcName}])
        vpc.wait_until_available()
        return vpc

    @staticmethod
    def modifyEnableDnsSupport(VpcId, Value=True):
        """
        Modify the parameter EnableDnsSupport in a given VPC with the new Value
        :param VpcId: VpcId where to modify EnableDnsSupport
        :param Value: new value of EnableDnsSupport
        :return: None
        """
        distrinetAWS.ec2Client.modify_vpc_attribute(VpcId=VpcId, EnableDnsSupport={"Value": Value})

    @staticmethod
    def modifyEnableDnsHostnames(VpcId, Value=True):
        """
        Modify the parameter EnableDnsHostnames in a given VPC with the new Value
        :param VpcId: VpcId where to modify EnableDnsHostnames
        :param Value: new value of EnableDnsHostnames
        :return: None
        """
        distrinetAWS.ec2Client.modify_vpc_attribute(VpcId=VpcId, EnableDnsHostnames={"Value": Value})


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
        subnet = distrinetAWS.ec2Resource.create_subnet(CidrBlock=subnetNetwork, VpcId=VpcId, **kwargs)
        subnet.create_tags(Tags=[{"Key": "Name", "Value": subnetName}])
        routeTable.associate_with_subnet(SubnetId=subnet.id)
        return subnet

    @staticmethod
    def createInternetGateWay(**kwargs):
        """
        Create an Internet Gateway
        :param kwargs: Optional parameters that you can assign to the gateway
        :return: Internet Gateway object from boto3.resource('ec2'), you can access the Id by: InternetGatewayObject.id
        """
        IGW = distrinetAWS.ec2Resource.create_internet_gateway(**kwargs)
        return IGW

    @staticmethod
    def attachInternetGateWayToVpc(Vpc, InternetGatewayId, **kwargs):
        """
        Attach an Internet gateway already created to a vpc
        :param Vpc: vpc object
        :param InternetGatewayId: internet gateway id
        :param kwargs: Optional parameters that you can assign
        :return: None
        """
        Vpc.attach_internet_gateway(InternetGatewayId=InternetGatewayId, **kwargs)

    @staticmethod
    def createElasticIp(Domain='vpc', **kwargs):
        """
        Create a new Elastic Ip.Be careful, you can have at most 5 Elastic Ip per Region
        :param Domain: Domain of the Elastic Ip
        :param kwargs: Optional parameters that you can assign to the ElasticIp
        :return: ElasticIp Client response, you can access the Id by: ElasticIpObject["AllocationId"]
        """
        eip = distrinetAWS.ec2Client.allocate_address(Domain=Domain, **kwargs)
        return eip

    @staticmethod
    def assignElasticIp(ElasticIpId, InstanceId):
        """
        Assign an Elastic Ip to an instance
        :param ElasticIpId: Elastic Ip Id
        :param InstanceId: Instance Id, The instance has to be in a valid state
        :return: None
        """
        distrinetAWS.ec2Client.associate_address(AllocationId=ElasticIpId, InstanceId=InstanceId)

    @staticmethod
    def createNatGateWay(SubnetId, AllocationId, **kwargs):
        """
        Create a new Nat Gateway
        :param SubnetId: Subnet where to assigne the Nat Gateway
        :param AllocationId: ElasticIp Id assigned to the Nat Gateway
        :return: NatGateway Client response, you can access the Id by: NatGatewayObject["NatGateway"]["NatGatewayId"]
        """
        NGW = distrinetAWS.ec2Client.create_nat_gateway(SubnetId=SubnetId, AllocationId=AllocationId, **kwargs)
        return NGW

    @staticmethod
    def waitNatGateWaysAvailable(NatGatewaysId):
        """
        Wait until the NatGateway is in Available state
        :param NatGatewaysId: Nat Gateway Id
        :return: None
        """
        distrinetAWS.ec2Client.get_waiter('nat_gateway_available').wait(NatGatewayIds=NatGatewaysId)

    @staticmethod
    def createRouteTable(Vpc, TableName, **kwargs):
        """
        Create a new route table inside a Vpc
        :param Vpc: Vpc Object where to create the table
        :param TableName: Tag Name added to the new table
        :param kwargs: Optional parameters that you can assign to the RouteTable
        :return: Route Table Object
        """
        RouteTable = Vpc.create_route_table(**kwargs)
        RouteTable.create_tags(Tags=[{"Key": "Name", "Value": TableName}])
        return RouteTable

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
        route = routeTable.create_route(GatewayId=GatewayId, DestinationCidrBlock=DestinationCidrBlock, **kwargs)
        return route

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
        :param kwargs: Oprional parameters to personalize your image, the correct documentation can be found at:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.run_instances
        :return: RunInstances Client response, boto3.client('ec2').run_instances()
        """
        response = distrinetAWS.ec2Client.run_instances(SubnetId=SubnetId, ImageId=ImageId, InstanceType=instanceType,
                                                        KeyName=KeyName, MaxCount=numberOfInstances,
                                                        MinCount=numberOfInstances, **kwargs)
        return response

    @staticmethod
    def waitInstancesRunning(instancesIdList):
        """
        Wait until all the instance in input are in 'running state'
        :param instancesIdList: List of instances Ids
        :return: None
        """
        distrinetAWS.ec2Client.get_waiter('instance_running').wait(
            Filters=[{'Name': "instance-id", "Values": instancesIdList}])

    @staticmethod
    def extractInstancesId(runInstancesResponse):
        """
        Take in input the entire response from runInstance method and extract the Ids of all the instances created by
        the call
        :param runInstancesResponse: runInstance Response
        :return: List of Instance Ids
        """
        hosts_id = []
        for host in runInstancesResponse['Instances']:
            hosts_id.append(host['InstanceId'])

        return hosts_id

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
        sg = distrinetAWS.ec2Client.create_security_group(VpcId=VpcId, GroupName=GroupName, Description=Description,
                                                          **kwargs)
        return sg

    @staticmethod
    def extractSecurityGroupId(createSecurityGroupResponse):
        """
        Take in input the entire response from createSecurityGroup method and extract the Id of the Security Group
        :param createSecurityGroupResponse: createSecurityGroup response
        :return: Security Group Id
        """
        return createSecurityGroupResponse["GroupId"]

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
        >>> i, e = distrinetAWS.AuthorizeSecurityGroupTraffic("id-xxxx", {"RULES..."},Directions=["egress"])
        >>> i
            None
        >>> e
            SOMEDATA....

        """
        if ("ingress" not in Directions) and ("egress" not in Directions):
            raise ValueError("Directions not correct")

        ingressData, egressData = None, None

        if "ingress" in Directions:
            ingressData = distrinetAWS.ec2Client.authorize_security_group_ingress(GroupId=GroupId,
                                                                                  IpPermissions=IpPermissions)

        if "egress" in Directions:
            egressData = distrinetAWS.ec2Client.authorize_security_group_ingress(GroupId=GroupId,
                                                                                 IpPermissions=IpPermissions)

        return ingressData, egressData

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
        responses = []
        for id_ in instancesId:
            responses.append(distrinetAWS.ec2Client.modify_instance_attribute(InstanceId=id_, Groups=Groups, **kwargs))
        return responses

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
        distrinetAWS.ec2Client.delete_key_pair(KeyName=KeyName)
        response = distrinetAWS.ec2Client.create_key_pair(KeyName=KeyName, **kwargs)
        return response

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
        return distrinetAWS.executeCommand(SshSession=SshSession, command=command)

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
        commands.append('sudo DEBIAN_FRONTEND=noninteractive apt install -y -q ansible')

        command = ";".join(commands)
        return distrinetAWS.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def setupMasterAutorizedKeysOnWorkers(SshSession, WorkerHostsIp):
        """
        Append the Master authorized_keys on the Slaves Authorized Keys
        :param SshSession: SshSession from a User with root privileges
        :param WorkerHostsIp: list of the worker host private Ip
        :return: None
        """
        command = "cat $HOME/.ssh/authorized_keys"
        i, sessionAuthorizedKeys, e = distrinetAWS.executeCommand(SshSession=SshSession, command=command)

        for workerIp in WorkerHostsIp:
            command = " ssh root@{} echo '{} >> $HOME/.ssh/authorized_keys'".format(workerIp, str(sessionAuthorizedKeys,
                                                                                                  "utf-8")[:-1])
            distrinetAWS.executeCommand(SshSession=SshSession, command=command)



    def deploy(self):
        """
        Deploy Amazon environment
        :return: BastionHost Ip, masterHostPrivateIp, PrivateHosts Ip
        """
        self.vpc = self.CreateVPC(VpcName=self.VPCName, addressPoolVPC=self.addressPoolVPC)
        vpcId = self.vpc.id
        self.modifyEnableDnsSupport(VpcId=vpcId, Value=True)
        self.modifyEnableDnsHostnames(VpcId=vpcId, Value=True)
        self.internetGateway = self.createInternetGateWay()
        internetGatewayId = self.internetGateway.id
        self.attachInternetGateWayToVpc(Vpc=self.vpc, InternetGatewayId=internetGatewayId)

        self.publicRouteTable = self.createRouteTable(Vpc=self.vpc, TableName='publicRouteTable')
        self.privateRouteTable = self.createRouteTable(Vpc=self.vpc, TableName='privateRouteTable')

        self.securityGroup = self.createSecurityGroup(VpcId=vpcId, GroupName="Distrinet", Description="Distrinet")
        securityGroupId = self.securityGroup["GroupId"]
        self.AuthorizeSecurityGroupTraffic(GroupId=securityGroupId, IpPermissions=IP_PERMISSION, Directions=["ingress"])

        self.addRoute(self.publicRouteTable, GatewayId=internetGatewayId, DestinationCidrBlock='0.0.0.0/0')

        self.publicSubnet = self.createSubnet(VpcId=vpcId, subnetName='PublicSubnetDistrinet',
                                              subnetNetwork=self.publicSubnetNetwork, routeTable=self.publicRouteTable)

        self.privateSubnet = self.createSubnet(VpcId=vpcId, subnetName="PrivateSubnetDistrinet",
                                               subnetNetwork=self.privateSubnetNetwork,
                                               routeTable=self.privateRouteTable)

        self.privateKey = self.createKeyPair(KeyName=KEY_PAIR_NAME)
        privateKey = self.privateKey["KeyMaterial"]

        publicSubnetId = self.publicSubnet.id
        privateSubnetId = self.privateSubnet.id

        self.bastionHostPublicIp = self.createElasticIp(Domain='vpc')
        self.natGateWayPublicIp = self.createElasticIp(Domain='vpc')

        bastionHostPublicIpId = self.bastionHostPublicIp['AllocationId']
        natGateWayPublicIpId = self.natGateWayPublicIp["AllocationId"]
        bastionHostPublicIp = self.bastionHostPublicIp["PublicIp"]

        self.natGateWay = self.createNatGateWay(SubnetId=publicSubnetId, AllocationId=natGateWayPublicIpId)
        natGateWayId = self.natGateWay["NatGateway"]["NatGatewayId"]

        self.bastionHost = self.runInstances(SubnetId=publicSubnetId, **self.bastionHostDescription)
        print(self.bastionHost)
        bastionHostId = self.bastionHost['Instances'][0]['InstanceId']

        self.workerHosts = []
        workerHostsId = []
        for workerDescription in self.workersHostsDescription:
            response = self.runInstances(SubnetId=privateSubnetId, KeyName=KEY_PAIR_NAME, **workerDescription)
            self.workerHosts.append(response)
            for instance in response['Instances']:
                workerHostsId.append(instance['InstanceId'])

        self.modifyGroupId(instancesId=[bastionHostId], Groups=[securityGroupId])
        self.modifyGroupId(instancesId=workerHostsId, Groups=[securityGroupId])

        self.waitInstancesRunning(instancesIdList=[bastionHostId])
        self.assignElasticIp(ElasticIpId=bastionHostPublicIpId, InstanceId=bastionHostId)
        sleep(30)
        sshUserSession = self.createSshSession(host=bastionHostPublicIp, username=MAIN_USER)
        self.grantRootAccess(SshSession=sshUserSession)
        self.setupBastionHost(SshSession=sshUserSession, PrivateKey=privateKey)
        self.waitInstancesRunning(instancesIdList=workerHostsId)
        sleep(30)

        self.waitNatGateWaysAvailable(NatGatewaysId=[natGateWayId])
        self.addRoute(routeTable=self.privateRouteTable, GatewayId=natGateWayId, DestinationCidrBlock="0.0.0.0/0")
        sleep(5)

        sshRootSession = self.createSshSession(host=bastionHostPublicIp, username="root")

        masterHostPrivateIp = self.bastionHost['Instances'][0]['PrivateIpAddress']
        workerHostsPrivateIp = []
        for response in self.workerHosts:
            for instance in response['Instances']:
                workerHostsPrivateIp.append(instance['PrivateIpAddress'])

        self.setAnsibleHosts(SshSession=sshRootSession, MasterHostIp=masterHostPrivateIp,
                             WorkersList=workerHostsPrivateIp)
        self.copyFilesInHost(SshSession=sshRootSession, SrcDir=SRC_PLAYBOOKS_DIR, DstDir=DST_PLAYBOOKS_DIR)
        sleep(5)
        self.installEnvironment(SshSession=sshRootSession, PlaybookPath=DST_PLAYBOOKS_DIR + "/install-aws-lxd.yml")
        sleep(5)
        self.configureLxd(SshSession=sshRootSession, MasterPrivateIp=masterHostPrivateIp,
                          PlaybookPath=DST_PLAYBOOKS_DIR)

        self.setupMasterAutorizedKeysOnWorkers(SshSession=sshRootSession, WorkerHostsIp=workerHostsPrivateIp)

        return bastionHostPublicIp, masterHostPrivateIp, workerHostsPrivateIp


if __name__ == '__main__':
    o = distrinetAWS(VPCName="DEMO", addressPoolVPC="10.0.0.0/16", publicSubnetNetwork='10.0.0.0/24',
                     privateSubnetNetwork='10.0.1.0/24',
                     bastionHostDescription={"numberOfInstances": 1, 'instanceType': 't3.2xlarge',
                                             'KeyName': 'id_rsa',
                                             'ImageId': 'ami-090f10efc254eaf55', "BlockDeviceMappings": [
                             {"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 8}}]},
                     workersHostsDescription=[{"numberOfInstances": 1, 'instanceType': 't3.2xlarge',
                                               'ImageId': 'ami-090f10efc254eaf55', "BlockDeviceMappings": [
                             {"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 8}}]}
                                              ])
    print(o.ec2Client)
    start = time()
    print(o.deploy())
    print("Environment ready in {} seconds".format(time() - start))

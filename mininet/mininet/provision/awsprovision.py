from mininet.provision.provision import Provision
from time import sleep, time
import boto3
import os
import paramiko
import uuid
from botocore.exceptions import ClientError
import progressbar

conf = Provision.get_configurations()
if "aws" in conf:
    aws_conf = conf["aws"]
    AWS_REGION = aws_conf["region"]
    SRC_PLAYBOOKS_DIR = "mininet/provision/playbooks"
    DST_PLAYBOOKS_DIR = "/root/playbooks"
    VOLUME_SIZE= int(aws_conf["volumeSize"])
    MAIN_USER = aws_conf["user"]
    KEY_PAIR_NAME_WORKERS = 'DistrinetKey-' + str(uuid.uuid4().hex)
    IP_PERMISSION = aws_conf["network_acl"]
    IMAGE_NAME_AWS = aws_conf["image_name"]
    KEY_PAIR_NAME_BASTION = aws_conf["key_name_aws"]
else:
    AWS_REGION = "eu-central-1"


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
    def CheckResources(VpcNeeded=1, ElasticIpNeeded=2, instancesNeeded=(("t3.2xlarge", 2),)):

        # TODO: find the best way to get this data directly from AWS
        default_max_vpcs = 5
        default_max_elastic_ip = 5
        default_max_instances_per_type = 10
        default_total_max_instances = 20
        ############################################################

        usedVpc = len(distrinetAWS.ec2Client.describe_vpcs()["Vpcs"])
        if usedVpc + VpcNeeded > default_max_vpcs:
            raise PermissionError(f"You dont have enough free Vpcs: Required={VpcNeeded},"
                                  f" used={usedVpc}, limit={default_max_vpcs}")

        usedElasticIps = len(distrinetAWS.ec2Client.describe_addresses()["Addresses"])
        if usedElasticIps + ElasticIpNeeded > default_max_elastic_ip:
            raise PermissionError(f"You dont have enough free ElasticIp: Required={ElasticIpNeeded},"
                                  f" used={usedElasticIps}, limit={default_max_elastic_ip}")

        usedInstances = {}
        for reservation in distrinetAWS.ec2Client.describe_instances()["Reservations"]:
            instances = reservation["Instances"]
            for instance in instances:
                instance_type = instance['InstanceType']
                if instance["State"]["Name"] == "running":
                    if instance_type in usedInstances.keys():
                        usedInstances[instance_type] += 1
                    else:
                        usedInstances[instance_type] = 1

        total_requested = sum([n for _, n in instancesNeeded])
        if sum(usedInstances.values()) + total_requested > default_total_max_instances:
            raise PermissionError(f"You dont have enough free instances: Required={total_requested},"
                                  f" used={sum(usedInstances.values())}, limit={default_total_max_instances}")

        for instance, _ in instancesNeeded:
            if instance not in usedInstances.keys():
                usedInstances[instance] = 0

        for instance_type, number_requested in instancesNeeded:
            if usedInstances[instance_type] + number_requested > default_max_instances_per_type:
                raise PermissionError(f"You dont have enough free {instance_type} instances: "
                                      f"Required={number_requested},  used={usedInstances[instance_type]}, "
                                      f"limit={default_max_instances_per_type}")

    @staticmethod
    def getAllInstancesInVPC(VpcId):
        """
        get all the instances type, with the private ip in the vpc
        :param vpcId: Id of the Vpc
        :return: list containing tuples of (instance_type, private_ip)
        """
        vpcid = VpcId
        ec2 = distrinetAWS.ec2Resource
        vpc = ec2.Vpc(vpcid)

        # get all instances
        instances_types = []
        for subnet in vpc.subnets.all():
            for instance in subnet.instances.all():
                ip = instance.private_ip_address
                t = instance.instance_type
                instances_types.append((t,ip))

        return instances_types

    @staticmethod
    def removeVPC(VpcId):
        """
        Remove the vpc using boto3.resource('ec2')
        :param vpcId: Id of the Vpc
        :return: client response
        Script adapted from https://gist.github.com/vernhart/c6a0fc94c0aeaebe84e5cd6f3dede4ce
        TODO: Make it cleaner and more modular, seems to work now, but the code is terrible

        """
        vpcid = VpcId
        ec2 = distrinetAWS.ec2Resource
        vpc = ec2.Vpc(vpcid)
        ec2client = ec2.meta.client

        # detach default dhcp_options if associated with the vpc
        dhcp_options_default = ec2.DhcpOptions('default')
        if dhcp_options_default:
            dhcp_options_default.associate_with_vpc(
                VpcId=vpc.id
            )

        # delete any instances
        key_name = None
        public_ips = []
        for subnet in vpc.subnets.all():
            for instance in subnet.instances.all():
                if instance.public_ip_address:
                    public_ips.append(instance.public_ip_address)
                if instance.key_name and instance.key_name.startswith("DistrinetKey-") and len(instance.key_name) > 30:
                    key_name = instance.key_name
                instance.terminate()

        if key_name:
            ec2client.delete_key_pair(KeyName=key_name)

        # delete nat_gateways
        nat_gateways = ec2client.describe_nat_gateways(Filters=[{"Name":"vpc-id", "Values": [vpc.id]}])["NatGateways"]
        nat_ids = [nat['NatGatewayId']for nat in nat_gateways]

        for nat in nat_gateways:
            for address in nat["NatGatewayAddresses"]:
                if "PublicIp" in address.keys():
                    public_ips.append(address["PublicIp"])

        for nat in nat_ids:
            ec2client.delete_nat_gateway(NatGatewayId=nat)

        # wait that all the nat gateways are in deleted state
        with progressbar.ProgressBar(max_value=len(nat_ids), prefix="Deleting the nat gateway") as bar:
            bar.update(0)
            while True:
                nat_gateways = ec2client.describe_nat_gateways(Filters=[{"Name": "vpc-id", "Values": [vpc.id]}])[
                    "NatGateways"]
                if nat_gateways == []:
                    break
                status = tuple(set([nat["State"] for nat in nat_gateways]))
                if status == ("deleted",):
                    bar.update(len(nat_ids))
                    break

                sleep(2)

        # wait that all the instances are deleted

        subnets = vpc.subnets.all()
        i = 0
        for subnet in subnets:
            i += len(list(subnet.instances.all()))

        with progressbar.ProgressBar(max_value=i, prefix="Deleting the instances", suffix="It needs some minutes") as bar:
            bar.update(0)
            completed_hosts = 0
            while True:
                subnets = vpc.subnets.all()
                instances = []
                for subnet in subnets:
                    instances += subnet.instances.all()
                    if i-len(instances) != completed_hosts:
                        completed_hosts = i-len(instances)
                if not instances:
                    bar.update(i)
                    break
                bar.update(completed_hosts)
                sleep(1)

        # make sure that the elastic ip addresses are not linked to the vpc
        sleep(5)
        # delete elasticIp
        address_description = ec2client.describe_addresses(PublicIps=public_ips)["Addresses"]
        allocation_id_ips = [ip["AllocationId"]for ip in address_description]
        for id_ in allocation_id_ips:
            ec2client.release_address(AllocationId=id_)

        # detach and delete all gateways associated with the vpc
        for gw in vpc.internet_gateways.all():
            # We need to remove the public address before removing the Internet GW
            vpc.detach_internet_gateway(InternetGatewayId=gw.id)
            gw.delete()
        # delete all route table associations
        route_tables = ec2client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc.id]}])["RouteTables"]
        for rt in route_tables:
            associations = rt['Associations']
            if associations == []:
                ec2client.delete_route_table(RouteTableId=rt['RouteTableId'])
                continue

            for association in associations:
                if not association["Main"]:
                    association_id = association['RouteTableAssociationId']
                    ec2client.disassociate_route_table(AssociationId=association_id)
            sleep(1)
            if (False,) == tuple(set([association["Main"] for association in associations])):
                ec2client.delete_route_table(RouteTableId=rt["RouteTableId"])

        # delete our endpoints
        for ep in ec2client.describe_vpc_endpoints(
                Filters=[{
                    'Name': 'vpc-id',
                    'Values': [vpc.id]
                }])['VpcEndpoints']:
            ec2client.delete_vpc_endpoints(VpcEndpointIds=[ep['VpcEndpointId']])
        # delete our security groups
        for sg in vpc.security_groups.all():
            if sg.group_name != 'default':
                sg.delete()
        # delete any vpc peering connections
        for vpcpeer in ec2client.describe_vpc_peering_connections(
                Filters=[{
                    'Name': 'requester-vpc-info.vpc-id',
                    'Values': [vpc.id]
                }])['VpcPeeringConnections']:
            ec2.VpcPeeringConnection(vpcpeer['VpcPeeringConnectionId']).delete()
        # delete non-default network acls
        for netacl in vpc.network_acls.all():
            if not netacl.is_default:
                netacl.delete()
        # delete network interfaces
        for subnet in vpc.subnets.all():
            for interface in subnet.network_interfaces.all():
                interface.delete()
            subnet.delete()
        # finally, delete the vpc
        sleep(1)
        return ec2client.delete_vpc(VpcId=vpc.id)

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
        images_response_with_filter = distrinetAWS.ec2Client.describe_images(ExecutableUsers=["all"],
                                                                             Filters=[{"Name": "name",
                                                                                       "Values": [ImageName]}])

        Images = images_response_with_filter["Images"]
        if len(Images) == 0:
            raise RuntimeError(f"Image with Name: {ImageName} not found in region:{Region}")
        image_description = Images[0]
        imageId = image_description["ImageId"]
        return imageId

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
        sleep(1)
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
        :param kwargs: Optional parameters to personalize your image, the correct documentation can be found at:
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
        commands.append('sudo DEBIAN_FRONTEND=noninteractive apt install -y -q software-properties-common')
        commands.append('sudo apt-add-repository --yes --update ppa:ansible/ansible')
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


    @staticmethod
    def isKeyNameExistingInRegion(KeyName, region):
        return True

    @staticmethod
    def releaseElasticIP(ElasticIpID):
        """
        release An elastic IP
        :param ElasticIpID: IP id
        :return: client responce
        """
        responce = distrinetAWS.ec2Client.release_address(AllocationId=ElasticIpID)
        return responce

    def __aws_resource_check(self):
        if not self.isKeyNameExistingInRegion(KeyName=KEY_PAIR_NAME_BASTION, region=AWS_REGION):
            raise Exception(f"Key: {KEY_PAIR_NAME_BASTION} not found in region: {AWS_REGION}")



        instance_needed = {self.bastionHostDescription["instanceType"]: 1}
        for instance in self.workersHostsDescription:
            instanceType = instance["instanceType"]
            numberOfInstances = instance["numberOfInstances"]
            if instanceType in instance_needed.keys():
                instance_needed[instanceType] += numberOfInstances
            else:
                instance_needed[instanceType] = numberOfInstances

        instance_needed = [(instanceType, instance_needed[instanceType]) for instanceType in instance_needed]

        # raise an error if the resources in the region are not enough without starting to deploy
        self.CheckResources(VpcNeeded=1, ElasticIpNeeded=2, instancesNeeded=instance_needed)

    def __aws_vpc__configuration(self):
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
        self.AuthorizeSecurityGroupTraffic(GroupId=securityGroupId,
                                           IpPermissions=IP_PERMISSION,
                                           Directions=["ingress"])

        self.addRoute(self.publicRouteTable, GatewayId=internetGatewayId, DestinationCidrBlock='0.0.0.0/0')

        self.publicSubnet = self.createSubnet(VpcId=vpcId, subnetName='PublicSubnetDistrinet',
                                              subnetNetwork=self.publicSubnetNetwork, routeTable=self.publicRouteTable)

        self.privateSubnet = self.createSubnet(VpcId=vpcId, subnetName="PrivateSubnetDistrinet",
                                               subnetNetwork=self.privateSubnetNetwork,
                                               routeTable=self.privateRouteTable)

        self.privateKey = self.createKeyPair(KeyName=KEY_PAIR_NAME_WORKERS)

    def __aws_deploy(self):
        with progressbar.ProgressBar(max_value=10, prefix="AWS Configuration") as bar:
            bar.update(0)
            image_ami = self.getImageAMIFromRegion(Region=AWS_REGION, ImageName=IMAGE_NAME_AWS)
            bar.update(1)
            self.__aws_resource_check()
            bar.update(2)
            self.__aws_vpc__configuration()
            bar.update(3)

            privateKey = self.privateKey["KeyMaterial"]
            publicSubnetId = self.publicSubnet.id
            privateSubnetId = self.privateSubnet.id

            self.bastionHostPublicIp = self.createElasticIp(Domain='vpc')
            bastionHostPublicIpId = self.bastionHostPublicIp['AllocationId']
            bastionHostPublicIp = self.bastionHostPublicIp["PublicIp"]


            self.natGateWayPublicIp = self.createElasticIp(Domain='vpc')
            natGateWayPublicIpId = self.natGateWayPublicIp["AllocationId"]

            self.natGateWay = self.createNatGateWay(SubnetId=publicSubnetId, AllocationId=natGateWayPublicIpId)
            natGateWayId = self.natGateWay["NatGateway"]["NatGatewayId"]
            bar.update(4)
            "Run the bastion host"
            self.bastionHostDescription["ImageId"] = image_ami
            self.bastionHostDescription["numberOfInstances"] = 1
            self.bastionHost = self.runInstances(SubnetId=publicSubnetId,
                                                 KeyName=KEY_PAIR_NAME_BASTION,
                                                 **self.bastionHostDescription)
            #print(self.bastionHost)
            bastionHostId = self.bastionHost['Instances'][0]['InstanceId']
            bar.update(5)
            self.workerHosts = []
            workerHostsId = []
            for workerDescription in self.workersHostsDescription:
                workerDescription["ImageId"] = image_ami
                response = self.runInstances(SubnetId=privateSubnetId, KeyName=KEY_PAIR_NAME_WORKERS, **workerDescription)
                self.workerHosts.append(response)
                for instance in response['Instances']:
                    workerHostsId.append(instance['InstanceId'])

            securityGroupId = self.securityGroup["GroupId"]
            self.modifyGroupId(instancesId=[bastionHostId], Groups=[securityGroupId])
            self.modifyGroupId(instancesId=workerHostsId, Groups=[securityGroupId])
            bar.update(6)
            self.waitInstancesRunning(instancesIdList=[bastionHostId])
            self.assignElasticIp(ElasticIpId=bastionHostPublicIpId, InstanceId=bastionHostId)
            bar.update(7)
            sleep(30)
            sshUserSession = self.createSshSession(host=bastionHostPublicIp, username=MAIN_USER)
            self.grantRootAccess(SshSession=sshUserSession)
            self.setupBastionHost(SshSession=sshUserSession, PrivateKey=privateKey)
            if workerHostsId:
                self.waitInstancesRunning(instancesIdList=workerHostsId)
            bar.update(8)
            sleep(30)

            self.waitNatGateWaysAvailable(NatGatewaysId=[natGateWayId])
            self.addRoute(routeTable=self.privateRouteTable, GatewayId=natGateWayId, DestinationCidrBlock="0.0.0.0/0")
            bar.update(9)
            sleep(5)
            bar.update(10)
            return bastionHostPublicIp

    def deploy(self):
        """
        Deploy Amazon environment
        :return: BastionHost Ip, masterHostPrivateIp, PrivateHosts Ip
        """

        bastionHostPublicIp = self.__aws_deploy()
        with progressbar.ProgressBar(max_value=6, prefix="Nodes Configuration") as bar:
            sshRootSession = self.createSshSession(host=bastionHostPublicIp, username="root")

            masterHostPrivateIp = self.bastionHost['Instances'][0]['PrivateIpAddress']
            workerHostsPrivateIp = []
            for response in self.workerHosts:
                for instance in response['Instances']:
                    workerHostsPrivateIp.append(instance['PrivateIpAddress'])
            bar.update(1)

            self.setAnsibleHosts(SshSession=sshRootSession, MasterHostIp=masterHostPrivateIp,
                                 WorkersList=workerHostsPrivateIp)
            bar.update(2)
            self.copyFilesInHost(SshSession=sshRootSession, SrcDir=SRC_PLAYBOOKS_DIR, DstDir=DST_PLAYBOOKS_DIR)
            sleep(5)
            bar.update(3)
            self.installEnvironment(SshSession=sshRootSession, PlaybookPath=DST_PLAYBOOKS_DIR + "/install-aws-lxd.yml")
            sleep(5)
            bar.update(4)
            sshRootSession = self.createSshSession(host=bastionHostPublicIp, username="root")

            self.configureLxd(SshSession=sshRootSession, MasterPrivateIp=masterHostPrivateIp,
                              PlaybookPath=DST_PLAYBOOKS_DIR)
            bar.update(5)
            self.setupMasterAutorizedKeysOnWorkers(SshSession=sshRootSession, WorkerHostsIp=workerHostsPrivateIp)
            bar.update(6)
            return bastionHostPublicIp, masterHostPrivateIp, workerHostsPrivateIp, self.vpc.id

def awsProvisionHelper(*args, instanceType='t3.2xlarge', volumeSize=10, **kwargs):
    numberOfInstances = (args[0]-1) if len(args) > 0 else 2
    if isinstance(volumeSize, str):
        volumeSize = int(volumeSize)

    vpcname = "demo_{}".format(int(time()))
    params = {'VPCName':vpcname,
            'addressPoolVPC': '10.0.0.0/16',
            'publicSubnetNetwork': '10.0.0.0/24',
            'privateSubnetNetwork': '10.0.1.0/24',
            'bastionHostDescription': {'instanceType': instanceType,
                'BlockDeviceMappings':[{'DeviceName': "/dev/sda1",
                    'Ebs' : { 'VolumeSize' : volumeSize }}]},
                'workersHostsDescription':[{'numberOfInstances': numberOfInstances, 'instanceType': instanceType,
                    'BlockDeviceMappings':[{'DeviceName': '/dev/sda1',
                        'Ebs' : { 'VolumeSize' : volumeSize }}]}
                    ]
            }
    return distrinetAWS(**params)


def optimizationAWSHelper(node_assigement):
    if not node_assigement:
        raise Exception("AWS provider cannot create 0 nodes")

    cloud_instances_list = list(set(node_assigement.values()))
    cloud_instances_to_create = {x[0]: 0 for x in cloud_instances_list}

    for instance in cloud_instances_list:
        cloud_instances_to_create[instance[0]] += 1
    instance_type = instance[0]
    cloud_instances_to_create[instance_type] -= 1
    if cloud_instances_to_create[instance_type] == 0:
        cloud_instances_to_create.pop(instance_type)

    bastionHostDescription = {'instanceType': instance_type,
                                         'BlockDeviceMappings': [{'DeviceName': "/dev/sda1",
                                                                  'Ebs': {'VolumeSize': VOLUME_SIZE}}]}

    workersHostsDescription=[]
    for instanceType in cloud_instances_to_create:
        numberOfInstances= cloud_instances_to_create[instanceType]
        workersHostsDescription.append({'numberOfInstances': numberOfInstances, 'instanceType': instanceType,
                                           'BlockDeviceMappings': [{'DeviceName': '/dev/sda1',
                                                                    'Ebs': {'VolumeSize': VOLUME_SIZE}}]})

    vpcname = "demo_{}".format(int(time()))

    params = {'VPCName': vpcname,
              'addressPoolVPC': '10.0.0.0/16',
              'publicSubnetNetwork': '10.0.0.0/24',
              'privateSubnetNetwork': '10.0.1.0/24',
              'bastionHostDescription': bastionHostDescription,
              'workersHostsDescription': workersHostsDescription
              }
    print(params)
    return distrinetAWS(**params)

if __name__ == '__main__':
    a={'host_2': ('t3.xlarge', 0), 'host_1': ('t3.xlarge', 0), 'host_3': ('t3.xlarge', 1), 'host_4': ('t3.xlarge', 1),
       'aggr_1': ('t3.xlarge', 2), 'core_1': ('t3.xlarge', 2), 'aggr_2': ('t3.xlarge', 3), 'edge_1': ('t3.xlarge', 3),
       'edge_2': ('t3.xlarge', 4)}
    optimizationAWSHelper(a)

    #input()
    #distrinetAWS.removeVPC("vpc-0e603975c640e7778")


from abc import abstractmethod
from time import sleep, time
import boto3
import os
import paramiko
from pathlib import Path
import yaml
import logging

logging.basicConfig(filename='provision.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')

CONF_FILE = ".distrinet/conf.yml"

class Provision (object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.conf = self.get_configurations()

    @abstractmethod
    def deploy(self):
        """
        Deploy the instances and blocks until it is fully deployed.

        returns the bastion and the workers
        """
        pass

    @staticmethod
    def configureLxd(SshSession, MasterPrivateIp, PlaybookPath):
        """
        Uses ansible to Configure lxd cluster in all the hosts
        :param SshSession: SshSession from the root user
        :param MasterPrivateIp: Privaate ip of the Master Host
        :param PlaybookPath: Path where is present the file configure-lxd.yml
        TODO: change this function to be more generic
        :return: execute.command result, see executeCommand() Documentation
        """
        command = 'ansible-playbook {}/configure-lxd-no-clustering.yml'.format(PlaybookPath)

        return Provision.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def installEnvironment(SshSession, PlaybookPath, Forks=40):
        """
        Uses ansible to install the environment in the hosts
        :param SshSession: SshSession from a User
        :param PlaybookPath: Path where is present the file install-aws-lxd.yml
        TODO: change this function to me more generic
        :return: execute.command result, see executeCommand() Documentation
        """
        command = 'ansible-playbook {} --forks {}'.format(PlaybookPath, Forks)
        return Provision.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def get_configurations():
        home_path = Path.home()
        conf_file = home_path / CONF_FILE
        if not conf_file.exists():
            raise RuntimeError(f"configuration file: {conf_file} not found")

        with open(str(conf_file), "r") as stream:
            conf_dict = yaml.safe_load(stream)
        return conf_dict



    @staticmethod
    def createSshSession(host, username):
        """
        Connect to the host with the username and the default private key in your client
        :param host: Host ip where to connect
        :param username: host Username to use in order to connect
        :return: ssh connection Object
        """
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_connection.connect(hostname=host, username=username)
        return ssh_connection

    @staticmethod
    def executeCommand(SshSession, command):
        """
        Execute a command using the SshSession
        :param SshSession: SshSession
        :param command: Command to be execute
        :return: return tuple with 3 object, std_in, std_out, std_err; to read the value on this objects you can use the
        .read() method, for example std_out.read()
        """
        ssh_stdin, ssh_stdout, ssh_stderr = SshSession.exec_command(command)
        in_, out, err = ssh_stdin, ssh_stdout.read(), ssh_stderr.read()

        logging.info(command)
        logging.info(f"OUT: {out}")
        logging.info(f"ERR: {err}")

        return in_, out, err

    @staticmethod
    def setupMasterHost(SshSession):
        commands = []
        commands.append('sudo apt update ')
        commands.append('sleep 5')
        commands.append('sudo DEBIAN_FRONTEND=noninteractive apt install -q -y ansible')
        command = ";".join(commands)
        return Provision.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def setAnsibleHosts(SshSession, MasterHostIp, WorkersList):
        """
        Takes in input an SshSession object, and append in /etc/ansible/hosts the bastion host ip with the ansible
        connection parameters and the worker hosts
        :param SshSession: SshSession from a User with root privileges
        :param BastionHostIp: Host ip of the host reacheble from the outside Network
        :param WorkersList: list of the private Ips assigned to the worker hosts
        :return: None
        """
        commands = []
        commands.append('echo "[master]" >> /etc/ansible/hosts')
        commands.append(
            'echo "{} ansible_connection=local ansible_python_interpreter=/usr/bin/python3" >> /etc/ansible/hosts'.format(
                MasterHostIp))
        commands.append('echo "[workers]" >> /etc/ansible/hosts')
        command = ";".join(commands)
        Provision.executeCommand(SshSession=SshSession, command=command)
        for worker in WorkersList:
            command = 'echo "{} ansible_ssh_extra_args=\'-o StrictHostKeyChecking=no\' ansible_python_interpreter=/usr/bin/python3" >> /etc/ansible/hosts'.format(
                worker)
            Provision.executeCommand(SshSession=SshSession, command=command)

    @staticmethod
    def copyFilesInHost(SshSession, SrcDir, DstDir):
        """
        Copy the file from the Source directory to the remote Destination directory using the SshSession
        Be careful Not really robust with the path
        :param SshSession: SshSession from a User
        :param SrcDir: Local source Directory
        :param DstDir: remote Destination Directory
        :return: None
        """
        command = 'mkdir -p {}'.format(DstDir)
        Provision.executeCommand(SshSession=SshSession, command=command)
        ftpClient = SshSession.open_sftp()
        for file_ in os.listdir(SrcDir):
            ftpClient.put("{}/{}".format(SrcDir, file_), "{}/{}".format(DstDir, file_))

    @staticmethod
    def closeSshSession(SshSession):
        """
        Close the ssh session
        :param SshSession: Ssh Session object
        :return: None
        """
        SshSession.close()


# dummy
from time import sleep
class DummyProvision (Provision):
    def __init__(self, n, **kwargs):
        self.n = n
        self.user = kwargs.pop("user", "root")
        self.params = kwargs
        _info ("DummyProvision {} {}\n".format(self.n, self.params))

    def deploy(self):
        _info ("deploying...\n")
        sleep(2)
        return "master1"

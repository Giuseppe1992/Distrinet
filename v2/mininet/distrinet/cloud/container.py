from abc import ABCMeta, abstractmethod
import paramiko
from time import sleep

from distrinet.cloud.sshutil import (sshConnect, sshSendCommand)
from distrinet.cloud.sshnode import (SshNode)


class Container(SshNode):
    def __init__(self, name, target, admin_ip, ssh=None, user="root", jump=None, master=None, **params):
        """
        name: name of the node
        target: host where to run the node
        admin_ip: address used to connect to the node
        ssh: ssh client to connect to the target,
        """
        super(Container, self).__init__(name=name, server=target, admin_ip=admin_ip, user=user, jump=jump, **params)

        self.pending_commands = []

        self.target = target
        self.master = master
        assert self.admin_ip and self.name

        # Initialized the Node part 
        if ssh is None:
            # DSA - TODO - make it clean, not really nice...
            # connect to the target if we know it
            if target is not None:
                self.sshConnect(server=target, user=user, jump=jump)
            # otherwise just use the jump
            else:
                self.sshConnect(server=jump, user=user)
        assert (self.ssh)
        
        print ("\tPARAMS",params)

    def _start(self):
            self._startContainer(**self.params)

    def sendCommand(self, cmd):
        session = sshSendCommand(self.ssh, cmd)
        self.pending_commands.append(session)
        return session

    def wait(self):
        """
        Wait for all pending commands to finish, blocking call
        """
        while len(self.pending_commands) > 0:
            self.pending_commands = [ c for c in self.pending_commands  if not c.closed ]
            sleep(.1)

    def sshConnect(self, server, user="root", jump=None):
        """
        Establish the SSH connection to interact with the node
        """
        self.ssh = sshConnect(server=server, user=user, jump=jump)

    @abstractmethod
    def _startContainer(self, **kwargs):
        """
        Create and start container
        """
        pass

    @abstractmethod
    def startContainer(self, **kwargs):
        """
        Start the container if already created
        """
        pass
    
    @abstractmethod
    def stopContainer(self, **kwargs):
        """
        Stop the container
        """
        pass

    @abstractmethod
    def createContainer(self, **kwargs):
        """
        Create the container on the target host
        """
        pass

    @abstractmethod
    def deleteContainer(self, **kwargs):
        """
        Delete the container if stopped:
        """
        pass


    @abstractmethod
    def addContainerInterface(self, intfName, **kwargs):
        """
        Add the interface
        """
        pass

    @abstractmethod
    def deleteContainerInterface(self, intf, **kwargs):
        """
        Delete the interface
        """
        pass

    @abstractmethod
    def addContainerLink(self, intfName, **kwargs):
        pass

    @abstractmethod
    def deleteContainerLink(self, link, **kwargs):
        """
        Delete the link on the node
        """
        pass







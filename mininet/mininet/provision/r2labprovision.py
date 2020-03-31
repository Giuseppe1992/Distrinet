from mininet.provision.provision import Provision
from abc import abstractmethod
from time import sleep, time
import os
import paramiko
from pathlib import Path
import yaml
import logging
import requests
import base64
import json

logging.basicConfig(filename='provision.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')

CONF_FILE = ".distrinet/conf.yml"

class r2lab(Provision):
    #TODO: you can add all the functions that you consider necessary to implement the deploy in R2Lab,
    # you can use the g5kprovision.py as a tutorial.
    # r2lab inherit the Provision class, so it will be worth to check it before starting the implementation.
    # You can overload the inherited methods if you think is necessary.
    # If R2Labs request Username and Password, you can't hard code them, you need to use the get_configurations() method
    # to get the informations from the configuration file (see the user/password example for g5kprovision.py)
    # For any other info that R2Lab need, make an r2lab entry in the configuration file (conf/conf.yml)
    # if you need any help to implement, open an issue in the main repository page.
    # Distrinet need that Ansible and LXD are configured in the host that you are using (basically you need to authomatize the
    # general environment tutorial in the documentation).
    # IMPORTANT: you should be able to implement it just using this file, if you think that it is not enough and you need
    # to modify something in the core to make it work, open an issue and we can discuss how to do it.


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
        #TODO: implement the deploy such that it returns the master host ip and the worker host ips in a list;
        # the first element shoud be the master host ip.
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





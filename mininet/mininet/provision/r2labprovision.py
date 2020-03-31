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
    # r2lab class inherit the Provision class, so it will be worth to check it before starting the implementation.
    # You can overload the inherited methods if you think is necessary.
    # If R2Labs request Username and Password, you can't hard code them, you need to use the get_configurations() method
    # to get the infos from the configuration file (see the user/password example for g5kprovision.py)
    # For any other info that R2Lab need, make an r2lab entry in the configuration file (conf/conf.yml)
    # If you need any help to implement, open an issue in the main repository page.
    # Distrinet need that Ansible and LXD are configured in the host that you are using (basically you need to authomatize the
    # reservations of the hosts and the general environment tutorial in the documentation, for r2Lab).
    # IMPORTANT: you should be able to implement it just using this file, if you think that it is not enough and you need
    # to modify something in the core to make it work, open an issue and we can discuss how to do it.

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.conf = self.get_configurations()

    def deploy(self):
        """
        Deploy the instances and blocks until it is fully deployed.

        returns the bastion and the workers
        """
        #TODO: implement the deploy such that it returns the master host ip and the worker host ips in a list;
        # the first element shoud be the master host ip.
        pass






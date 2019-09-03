from mininet.provision.provision import Provision

import requests
import base64
import json
from time import sleep
import paramiko
import os

SRC_PLAYBOOKS_DIR = "../../../../src/playbooks"
DST_PLAYBOOKS_DIR = "/tmp/playbooks"


class basicprovision(Provision):
    def __init__(self, username, master_ip, workers_ip, **kwargs):
        super(Provision, self).__init__(username, master_ip, workers_ip, **kwargs)
        self.username = username
        self.master = master_ip
        self.workers = workers_ip

    def deploy(self):
        sshMasterSession = self.createSshSession(host=self.master, username=self.username)
        self.setupMasterHost(SshSession=sshMasterSession)
        sleep(2)
        self.setAnsibleHosts(SshSession=sshMasterSession, MasterHostIp=self.master, WorkersList=self.workers)
        self.copyFilesInHost(SshSession=sshMasterSession, SrcDir=SRC_PLAYBOOKS_DIR, DstDir=DST_PLAYBOOKS_DIR)
        sleep(2)
        self.installEnvironment(SshSession=sshMasterSession, PlaybookPath=DST_PLAYBOOKS_DIR + "/install-lxd.yml")
        sleep(2)
        self.configureLxd(SshSession=sshMasterSession, MasterPrivateIp=self.master, PlaybookPath=DST_PLAYBOOKS_DIR)
        return self.master, self.workers

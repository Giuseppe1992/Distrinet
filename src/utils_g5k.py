import requests
import base64
import json
from time import sleep


class g5k(object):
    def __init__(self, user, passw):
        self.header = {"Accept": "*/*", "Authorization": "Basic " + base64.b64encode(":".join([user,passw])), "Content-Type": "application/json"}
        self.reservation_id = None
        self.reservation = None
        self.location = None
        self.cluster = None
        self.user = user

    def make_reservation(self, walltime="2:00",nodes="1", location="nancy", cluster=None, command="sleep 7200"):
        """make a reservetion and return the job_id"""
        if self.reservation_id:
            raise Exception("you have already reserved te resources for this istance, remember to release the resources.--> delete_reservtion()")
        js = {
            "command": command,
            "resources": "nodes="+str(nodes)+",walltime="+walltime,
            "types": [
                "deploy"
            ]
        }

        response = requests.post("https://api.grid5000.fr/3.0/sites/{}/jobs".format(location), json.dumps(js), headers=self.header)
        self.reservation_id = eval(response.text)["uid"]
        self.cluster = cluster
        self.location = location
        self.reservation = eval(response.text)
        return self.reservation_id

    def get_reservation_nodes(self):
        response = requests.get("https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(self.location, self.reservation_id),headers=self.header)
        return eval(response.text)['assigned_nodes']

    def get_reservation(self):
        response = requests.get(
            "https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(self.location, self.reservation_id),
            headers=self.header)
        return eval(response.text)

    def check_state(self):
        """check the state of a job, it can be running, waiting or error"""
        response = requests.get("https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(self.location,self.reservation_id), headers=self.header)
        return eval(response.text)["state"]

    def delete_reservation(self):
        header= {"Accept": "*/*", "Authorization":self.header["Authorization"]}
        response = requests.delete("https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(self.location,self.reservation_id), headers=header)
        return response.status_code

    def get_nodes(self):
        if self.check_state() != "running":
            return None
        response = requests.get("https://api.grid5000.fr/3.0/sites/{}/jobs/{}".format(self.location, self.reservation_id), headers=self.header)
        return eval(response.text)["assigned_nodes"]

    def wait_running_state_of_the_job(self):
        while self.check_state() != "running":
            sleep(2)

    def get_test_dir(self):
        response = requests.get("https://api.grid5000.fr/sid/sites/{}/public/{}/test/".format(self.location,self.user), headers=self.header)
        return str(response.text)

    def __str__(self):
        return str(self.reservation_id) + str(self.reservation)
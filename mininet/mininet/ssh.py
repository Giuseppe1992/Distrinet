from subprocess import PIPE
from mininet.log import info, error, debug, output, warn
import asyncio, asyncssh
from functools import partial
import time

from mininet.dutil import _info

class SSH(object):
    """
    Class to interact with a remote node using SSH.

    The class support direct connection to the host or connection via a
    bastion. When a bastion is used, an SSH connection is established to the
    bastion and is used as a tunnel to connect ot the host.
    The tunnel is setup as follows:
        <random_port>:`host`:`host_port` `bastion_username`@`bastion`:`bastion_port`
    
    Attributes
    ----------
    loop : asyncio.AbstractEventLoop 
        The async event loop to which associate the connection.
    host : str
        Hostname or IP address of the host to connect to.
    port : int
        The SSH port number to use to connect to the host.
    username : str
        Username to use to connect to the host. 
    bastion : str 
        Hostname or IP address of the bastion to use to connect to the host.
    bastion_port : int 
        The SSH port number to use to connect to the bastion.
    bastion_username: str 
        Username to use to connect to the bastion.
    client_keys : list
        List with the path to the authentications keys to use. Each entry
        consists of a path to the authentication key, e.g.,
        ['/home/example/.ssh/id_rsa_a', '/home/example/keys/key1'].
    task : _asyncio.Task
        Current task in execution.
    tasks : list
        Current tasks in execution (when multiple tasks have been ordered)
    tunnel : asyncssh.listener.SSHForwardListener
        Actual tunnel through the bastion
    conn : asyncssh.connection.SSHClientConnection
        Actual SSH connection with the host
        hostname to connect to
    connection_host : str
        Hostname to actually use to connect to the host.
    connection_port : int
        Port number to actually use to connect to the host.

    """
    def __init__(self, loop, host, port=22, username=None, bastion=None,
                       bastion_port=22, bastion_username=None,
                       client_keys=None, **params):
        """
        Initialize an SSH connection object to connect to a host using SSHv2.

        Parameters
        ----------
        loop : asyncio.AbstractEventLoop 
            The async event loop to which associate the connection.
        host : str
            Hostname or IP address of the host to connect to.
        port : int (optional, default=22)
            The SSH port number to use to connect to the host.
        username : str (optional, default=None)
            Username to use to connect to the host. If None is provided, the
            username of the process is used.
        bastion : str (optional, default=None)
            Hostname or IP address of the bastion to use to connect to the
            host. If None is provided, no bastion is used to connect to the
            host.
        bastion_port : int (optional, default=22)
            The SSH port number to use to connect to the bastion.
        bastion_username: str (optional, default=None)
            Username to use to connect to the bastion. If None is provided, the
            username of the process is used.
        client_keys : list (optional, default=None)
            List with the path to the authentications keys to use. Each entry
            consists of a path to the authentication key, e.g.,
            ['/home/example/.ssh/id_rsa_a', '/home/example/keys/key1'].

        Notes
        -----
        No SSH operation is performed at this stage, it is only used to preset
        the object attributes.
        """
        # the node runs
        self.run = True

        # asyncio loop
        self.loop = loop

        # host information
        self.host = host
        self.port = port
        self.username = username
        self.client_keys = client_keys

        # ssh bastion information
        self.bastion = bastion
        self.bastion_port = bastion_port
        self.bastion_username = bastion_username

        # current task in execution
        self.task = None
        self.tasks = []

        # SSH tunnel through the bastion
        self.tunnel = None

        # SSH connection with the host
        self.conn = None

        # hostname to connect to
        self.connection_host = self.host
        # port number to use
        self.connection_port = self.port


    def createTunnel(self):
        """
        Creates a tunnel with the bastion if needed (i.e., a bastion is
        specified).
        """
        if self.bastion is not None:
            self.loop.create_task(self._tunnel(bastion=self.bastion,
                                               bastion_port=self.bastion_port,
                                               bastion_username=self.bastion_username,
                                               host=self.host, port=self.port))
   
    async def _tunnel(self, bastion, host, bastion_port=22, port=22, bastion_username=None):
        """
        Establishes SSH local port forwarding to `host:port` via the bastion
        node (`bastion`:`bastion_port`).

        The tunnel is stored in `self.tunnel`.
        The local port number is obtained by calling `get_port()` on the
        `tunnel` attribute.

        Parameters 
        ----------
        bastion : str
            name of the bastion (i.e., SSH relay) to use to connect to
            `host`:`port`. 
        host : str
            name of the host to connect to.
        bastion_port : int (optional, default=22)
            SSH port number to use to connect to the bastion.
        port : int (optional, default=22)
            SSH port number to use to connect to the host.
        """
        connect = partial(asyncssh.connect, known_hosts=None, client_keys=self.client_keys)
        if bastion_username is not None:
            connect = partial(connect, username=bastion_username)

        async with connect(host=bastion, port=bastion_port) as conn:
            self.tunnel = await conn.forward_local_port('', 0, host, port)
            _info ("tunnel {}:{}:{} {}@{}:{} \n".format(self.tunnel.get_port(), host, port, bastion_username, bastion, bastion_port))
            while self.run:
                await asyncio.sleep(1)

    def waitTunneled(self):
        """
        Waits that the tunnel with the bastion is established (if needed) and
        updates `connection_host` and `connection_port` attributes to use it
        instead of having a direct connection to the host
        """
        if self.bastion is not None:
            while self.tunnel is None:
                time.sleep(0.001)

            # get the local port number
            self.connection_port = self.tunnel.get_port()
            # when a tunnel is used, connect locally
            self.connection_host = 'localhost'

    def connect(self):
        """
        Establishes an SSH connection to the host
        """
        if self.bastion:
            # create a tunnel via the bastion to connect to the hostA
            self.createTunnel()
            # wait fot th tunnel to be created
            self.waitTunneled()
  
        task = self.loop.create_task(self._connect(host=self.connection_host, port=self.connection_port))

    async def _connect(self, host, port):
        """
        Establishes an SSH connection to `host`:`port`.

        Parameters
        ----------
        host : str
            hostname
        port : int
            port number
        """
        connect = partial(asyncssh.connect, known_hosts=None, client_keys=self.client_keys)
        if self.username is not None:
            connect = partial(connect, username=self.username)

        while True:
            try:
                async with connect(host=host, port=port) as conn:
                    self.conn = conn
                    while self.run:
                        await asyncio.sleep(1)
            except Exception as e:
                error ("Error for {}@{} via {}:{}: {} \n".format(self.username, self.host, self.bastion, port, e))

    def waitConnected(self):
        """
        Blocking until the node is actually started
        """

        while not self.connected():
            time.sleep(0.001)

    def connected(self):
        return self.conn is not None

    def sendCmd(self, cmd, multi=False):
        task = self.loop.create_task(self._run(cmd))

        if multi:
            self.tasks.append(task)
        else:
            self.task = task

    def cmd(self, cmd):
        self.sendCmd(cmd)
        return self.waitOutput()
    
    def waitAllOutput(self):
        while len(self.tasks) > 0:
            if self.tasks[0].done():
                self.tasks.pop(0)
            else:
                time.sleep(0.001)

    def waitOutput(self):
        while not self.task.done():
            time.sleep(0.001)
        return self.task.result()

    async def _run(self, cmd):
        result = await self.conn.run(cmd)
        return result.stdout

    def close(self):
        self.conn.close()

        if self.tunnel:
            self.tunnel.close()

    async def createProcess(self, cmd, stdin=None, stdout=None, stderr=None):
        process = await self.conn.create_process(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        return process

    # XXX - SAME
    def __str__( self ):
        "Abbreviated string representation"
        return self.host


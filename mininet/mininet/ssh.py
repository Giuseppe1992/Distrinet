"""
author: Damien Saucez (damien.saucez@gmail.com) 
"""

from subprocess import PIPE
from mininet.log import info, error, debug, output, warn
import asyncio, asyncssh
from functools import partial
import time

from mininet.dutil import _info

class SSH(object):
    """
    Class to interact with a remote node using SSH.

    The class supports direct connection to the host or connection via a
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
    tasks : list of _asyncio.Task
        Current tasks in execution 
    tunnel : asyncssh.listener.SSHForwardListener
        Actual tunnel through the bastion
    conn : asyncssh.connection.SSHClientConnection
        Actual SSH connection with the host
        hostname to connect to
    connection_host : str
        Hostname to actually use to connect to the host.
    connection_port : int
        Port number to actually use to connect to the host.
    run : bool
        Specifies wether or not the connection is active (True for active,
        False for inactive)
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
        # the connection is active
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

        # current tasks in execution
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
        Create a tunnel with the bastion if needed (i.e., a bastion is
        specified).
        """
        if self.bastion is not None:
            self.loop.create_task(self._tunnel(bastion=self.bastion,
                                               bastion_port=self.bastion_port,
                                               bastion_username=self.bastion_username,
                                               host=self.host, port=self.port))
   
    async def _tunnel(self, bastion, host, bastion_port=22, port=22, bastion_username=None):
        """
        Establish SSH local port forwarding to `host:port` via the bastion node
        (`bastion`:`bastion_port`).

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
        Wait that the tunnel with the bastion is established (if needed) and
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
        Establish an SSH connection to the host. Make a tunnel with the bastion
        first when a bastion is provided.

        Notes
        -----
        This method is blocking for the establishment of the tunnel with the
        bastion but is non-blocking for the establishment of the connection
        with the host.
        """
        if self.bastion:
            # create a tunnel via the bastion to connect to the host
            self.createTunnel()
            # wait for the tunnel to be created
            self.waitTunneled()
  
        task = self.loop.create_task(self._connect(host=self.connection_host, port=self.connection_port))

    async def _connect(self, host, port):
        """
        Establish an SSH connection to `host`:`port`.

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
        Blocking until the SSH connection is established with the host.
        """

        while not self.connected():
            time.sleep(0.001)

    def connected(self):
        """
        Determine whether or not the SSH connection to the host is established.

        Returns
        -------
        bool
            True if the connection is established. Otherwise, a False is
            returned.
        """
        return self.conn is not None

    def sendCmd(self, cmd):
        """
        Launch a command on the host and don't wait for its termination. The
        task associated to the command is added at the end of the tasks list.

        Parameters
        ----------
        cmd : str
            The command to launch on the host.
        
        Returns
        -------
        _asyncio.Task
            The task corresponding to the command call. The result of the task
            will be the standard output of the command.

        Notes
        -----
        This method does not block. To retrieve the result of the command, use
        `SSH.waitOutput`, `SSH.waitAll`, or operate directly on the task.

        See also
        --------
        `SSH.waitOutput`
        `SSH.waitAll`
        """
        task = self.loop.create_task(self._run(cmd))

        self.tasks.append(task)

        return task

    def cmd(self, cmd):
        """
        Execute a command on the host and returns its standard output result.

        Parameters
        ----------
        cmd : str
            The command to run on the host.

        Returns
        -------
        str
            The standard output of the command once finished.

        Notes
        -----
        This method is blocking.
        """
        self.sendCmd(cmd)
        return self.waitOutput()
    
    def waitAll(self):
        """
        Wait for all tasks in the tasks list to be done.

        Post
        ----
        Tasks list is empty.
        """
        while len(self.tasks) > 0:
            if self.tasks[0].done():
                self.tasks.pop(0)
            else:
                time.sleep(0.001)

    def waitOutput(self):
        """
        Wait for the first task in the tasks lists to be done and returns the
        task result.

        Pre
        ---
        There is at least one task in the tasks list.

        Post
        ----
        The first task of the list has been removed from the list.
       
        Returns
        -------
        str
            The result of the task.
        """
        task = self.tasks.pop()
        while not task.done():
            time.sleep(0.001)
        return task.result()

    async def _run(self, cmd):
        """
        Run a command on a host and returns its standard output.

        Parameters
        ----------
        cmd : str
            The command to run on the host.

        Returns
        -------
        str
            The standard output of the command once finished.
        """
        result = await self.conn.run(cmd)
        return result.stdout

    def stop(self):
        """
        Gracefully stop the SSH connection.
        
        See also
        --------
        `SSH.run`
        `SSH.close`

        Notes
        -----
        The SSH connection is not closed.
        """
        self.run = False

    def close(self):
        """
        Close the SSH connection to the host.  Close the tunnel with the
        bastion when a bastion is used.
        """
        self.conn.close()

        if self.tunnel:
            self.tunnel.close()

    async def createProcess(self, cmd, stdin=None, stdout=None, stderr=None):
        """
        Create a process executing `cmd` on the host.

        Parameters
        ----------
        cmd : str
            Command to be run by the process.
        stdin : int (optional, default=None)
            File descriptor to which attach the standard input of the created
            process. None being DEVNULL.
        stdout : int (optional, default=None)
            File descriptor to which attach the standard input of the created
            process. None being DEVNULL.
        stderr : int (optional, default=None)
            File descriptor to which attach the standard input of the created
            process. None being DEVNULL.

        Returns
        -------
        asyncssh.SSHClientProcess
            The process handler of the created process.
        """
        process = await self.conn.create_process(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        return process

    def __str__( self ):
        """
        Abbreviated string representation

        Returns
        -------
        str
            String representation of the object.
        """
        return self.host


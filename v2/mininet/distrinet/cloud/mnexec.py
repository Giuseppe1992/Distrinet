#!/usr/bin/python3
from os import getpid, execvp
from sys import argv
import time
import shlex
print ('\001{}\012'.format(getpid()), end='')
#time.sleep(10)
args = argv[1]
args = ["/bin/bash", "-c", args]
execvp(args[0], args)

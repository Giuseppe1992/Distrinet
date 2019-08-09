import socket
import sys
from os import system
UDP_IP = ""
UDP_PORT = 8765
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
fi = open("server_log.txt".format(sys.argv[1]), "w")

while True:
    data, addr = sock.recvfrom(1024)
    if data=="exit_daemon":
        fi.write(str(data))
        break
    system(str(data))
    fi.write(str(data))

fi.close()
exit(0)

# docker build -t distrinet:1.1 .
FROM ubuntu:18.04
MAINTAINER Giuseppe Di Lena (giuseppedilena92@gmail.com)
RUN apt-get update
RUN apt-get install -y software-properties-common vim
RUN add-apt-repository ppa:jonathonf/python-3.6
RUN apt-get update
RUN apt-get install -y build-essential python3.6 python3.6-dev python3-pip python3.6-venv
RUN apt-get install -y git
# update pip
RUN python3.6 -m pip install pip --upgrade
WORKDIR /
RUN git clone https://github.com/mininet/mininet.git
RUN git clone https://github.com/Giuseppe1992/Distrinet
WORKDIR /Distrinet
ENV PYTHONPATH "${PYTHONPATH}:/mininet:/Distrinet/src/distrinet/cloud"
RUN pip install -r requirements.txt
RUN python3.6 setup.py install
RUN mkdir -p ~/.aws

RUN echo "[default]" > ~/.aws/credentials
RUN echo "aws_access_key_id=XXXXXXXXXXXXXXXX\naws_secret_access_key=YYYYYYYYYYYYYYYYYYYY">> ~/.aws/credentials
CMD /bin/bash

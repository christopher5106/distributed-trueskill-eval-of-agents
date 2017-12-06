FROM ubuntu:17.04
RUN apt-get update
RUN apt-get install -y openssh-server vim man
RUN apt-get install -y python3-pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt
ENV HOME=/root
WORKDIR /root/
COPY docker.py docker.py
RUN python3 -c "from docker import setup_ssh; setup_ssh()"
RUN echo "export LC_ALL=C.UTF-8 && export LANG=C.UTF-8" >> ~/.bashrc
COPY . /root/

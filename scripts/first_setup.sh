#!/bin/bash


set -e

#This is a script for setting up the developing environment for the first time on your machine
#first run 'sudo chmod 744 scripts/first_setup.sh' in your terminal
#then './scripts/first_setup.sh'

cd ~

#install docker
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo service docker start
docker --version

#for making .env, input your own api keys here
echo OPENAI_API_KEY=1234x > .env
echo ANTHROPIC_API_KEY=1234x >> .env

#temp fix for the perms when running docker
mkdir -p logs
sudo chmod 777 logs/

docker compose up --build

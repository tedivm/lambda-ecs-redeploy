#!/usr/bin/env bash
set -e

REPOSITORY="lambda-ecs-redeploy"
REGION="eu-central-1"
REGISTRY="986656860062"

# Will error out if not called from the root of this repository.

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "${REGISTRY}.dkr.ecr.${REGION}.amazonaws.com"

docker build -t "${REGISTRY}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY}:latest" .
docker image push "${REGISTRY}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY}:latest"

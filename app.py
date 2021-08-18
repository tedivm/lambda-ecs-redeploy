import json
import os
import sys
import boto3

CONFIG_TAG_NAME = os.environ.get("CONFIG_TAG_NAME", "AutoDeploy")

ecs_client = boto3.client('ecs')
lambda_client = boto3.client('lambda')


def handler(event, context):
  print(f"Received event: {json.dumps(event, indent=4, sort_keys=True)}")

  if event['detail-type'] != "ECR Image Action":
    print(f"Expected detail-type 'ECR Image Action', got '{event['detail-type']}'")
    return False

  if event['detail']['result'] != "Success":
    print(f"Expected detail result 'Success', got '{event['detail']['result']}'")
    return False

  detail = event['detail']
  image = f"{detail['repository-name']}:{detail['image-tag']}"


  # Redeploy Lambdas
  print(f"Attempting to deploy lambdas using image '{image}'")
  redeploy_lambdas_with_image(image)

  # Redeploy Services
  print(f"Attempting to deploy services using image '{image}'")
  redeploy_services_with_image(image)

  return


#
# ECS
#


def redeploy_services_with_image(image):
  for cluster in get_cluster_arns():
    for service in get_service_details(cluster):
      images = get_task_images(service['taskDefinition'])
      if image in images:
        redeploy_service(cluster, service['serviceName'])


def get_cluster_arns():
  paginator = ecs_client.get_paginator('list_clusters')
  cluster_iterator = paginator.paginate()
  for page in cluster_iterator:
    for cluster_arn in page['clusterArns']:
      yield cluster_arn


def get_service_details(cluster):
  paginator = ecs_client.get_paginator('list_services')
  list_service_iterator = paginator.paginate(
    cluster=cluster,
    maxResults=10
  )
  for list_page in list_service_iterator:
    service_descriptions = ecs_client.describe_services(
      cluster=cluster,
      services=list_page['serviceArns'],
      include=[
        'TAGS',
      ]
    )

    for service in service_descriptions['services']:
      if validate_reload_tag(service):
        yield service


def get_task_images(task_definition_arn):
  task_definition = ecs_client.describe_task_definition(
    taskDefinition=task_definition_arn
  )["taskDefinition"]
  images = []
  for definition in task_definition['containerDefinitions']:
    images.append(definition['image'])
  return images


def redeploy_service(cluster, service):
  print(f"Redeploying {service} on {cluster}")
  ecs_client.update_service(
   cluster=cluster,
   service=service,
   forceNewDeployment=True
  )


def validate_reload_tag(service_description):
  for tagset in service_description['tags']:
    if tagset['key'] == CONFIG_TAG_NAME:
      return tagset['value'].lower() == "true"
  return False


#
# Lambda
#

def redeploy_lambdas_with_image(image):
  for lambda_details in get_container_lambdas():
    tag_response = lambda_client.list_tags(
      Resources=lambda_details['FunctionArn']
    )
    if tag_response['Tags'].get('AutoDeploy', False).lower() != "true":
      continue

    if tag_response['Tags'].get('Image', False).lower() != image:
      continue

    print(f"Redeploying {lambda_details['FunctionName']}")
    lambda_client.update_function_code(
      FunctionName=lambda_details['FunctionArn'],
      ImageUri=image,
      Publish=True
    )


def get_container_lambdas():
  paginator = lambda_client.get_paginator('list_functions')
  function_iterator = paginator.paginate(
    MaxItems=50
  )
  for function_page in function_iterator:
    for function_details in function_page['Functions']:
      if function_details['PackageType'] != "Image":
        continue
      yield function_details



# Calling script directly
if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Image name required")
  print(f"Redeploying services using image {sys.argv[1]}")
  redeploy_services_with_image(sys.argv[1])

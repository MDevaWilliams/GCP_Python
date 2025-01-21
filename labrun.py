
import os
import time
from google.cloud import storage, pubsub_v1, iam, resource_manager
from googleapiclient.discovery import build

# Function to enable GCP services
def enable_services(project_id, services):
    service_usage = build('serviceusage', 'v1')
    for service in services:
        print(f"Enabling service: {service}")
        service_usage.services().enable(
            name=f'projects/{project_id}/services/{service}'
        ).execute()

# Function to set IAM policy bindings
def add_iam_policy_binding(project_id, member, role):
    crm_service = resource_manager.ProjectsClient()
    policy = crm_service.get_iam_policy(request={"resource": project_id})
    binding = {"role": role, "members": [member]}
    policy.bindings.append(binding)
    crm_service.set_iam_policy(request={"resource": project_id, "policy": policy})
    print(f"Added IAM policy binding: {member} -> {role}")

# Function to create a Cloud Storage bucket
def create_bucket(bucket_name, region):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    bucket.location = region
    bucket = storage_client.create_bucket(bucket)
    print(f"Bucket {bucket_name} created in region {region}.")

# Function to create a Pub/Sub topic
def create_topic(project_id, topic_name):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)
    publisher.create_topic(request={"name": topic_path})
    print(f"Pub/Sub topic {topic_name} created.")

# Function to deploy a Cloud Function
def deploy_function(function_name, bucket_name, region, topic_name, source_dir):
    os.system(f"""
    gcloud functions deploy {function_name} \
    --runtime python310 \
    --trigger-resource {bucket_name} \
    --trigger-event google.storage.object.finalize \
    --entry-point main \
    --region={region} \
    --source {source_dir} \
    --quiet
    """)
    print(f"Cloud Function {function_name} deployed.")

# Main script
if __name__ == "__main__":
    # User inputs
    username2 = input("Enter USERNAME2: ")
    zone = input("Enter ZONE (e.g., us-central1-a): ")
    topic_name = input("Enter TOPIC_NAME: ")
    function_name = input("Enter FUNCTION_NAME: ")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    # Extract region from zone
    region = "-".join(zone.split("-")[:-1])
    
    # Enable required GCP services
    services = [
        "artifactregistry.googleapis.com",
        "cloudfunctions.googleapis.com",
        "cloudbuild.googleapis.com",
        "eventarc.googleapis.com",
        "run.googleapis.com",
        "logging.googleapis.com",
        "pubsub.googleapis.com"
    ]
    enable_services(project_id, services)
    
    # Add IAM policy bindings
    project_number = os.popen(f"gcloud projects describe {project_id} --format='value(projectNumber)'").read().strip()
    service_account = f"service-{project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
    add_iam_policy_binding(project_id, f"serviceAccount:{service_account}", "roles/pubsub.publisher")
    
    # Create Cloud Storage bucket
    bucket_name = f"{project_id}-bucket"
    create_bucket(bucket_name, region)
    
    # Create Pub/Sub topic
    create_topic(project_id, topic_name)
    
    # Prepare source directory for Cloud Function
    source_dir = "./function_source"
    os.makedirs(source_dir, exist_ok=True)
    with open(os.path.join(source_dir, "main.py"), "w") as f:
        f.write("""
from google.cloud import pubsub_v1
from google.cloud import storage
import os

def main(event, context):
    bucket_name = event['bucket']
    file_name = event['name']
    print(f"Processing file {file_name} in bucket {bucket_name}")

    # Publish a message to the Pub/Sub topic
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.getenv('GOOGLE_CLOUD_PROJECT'), '"""+topic_name+"""')
    publisher.publish(topic_path, data=f"Processed {file_name}".encode())
    print(f"Message published for file {file_name}")
        """)
    
    # Deploy Cloud Function
    deploy_function(function_name, bucket_name, region, topic_name, source_dir)
    
    # Test setup
    print("Uploading a test file to the bucket...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("test-image.jpg")
    blob.upload_from_filename("path/to/local/test-image.jpg")
    print(f"Test file uploaded to {bucket_name}.")

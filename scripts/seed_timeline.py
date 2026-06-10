import boto3
import uuid

def seed_data():
    dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
    table = dynamodb.Table('project-sam-timeline')
    
    items = [
        # Experiences
        {
            "id": str(uuid.uuid4()),
            "type": "experience",
            "role": "Lead Platform & DevOps Engineer",
            "company": "SecOps Cloud Solutions",
            "duration": "2024 - Present",
            "location": "Hanoi, Vietnam (Hybrid)",
            "description": "Lead engineering for containerized deployments on AWS. Configured multi-region VPC peering routing, designed automated DevSecOps pipelines with SonarQube/Trivy gating, and standardized Helm chart templates.",
            "order": 1
        },
        {
            "id": str(uuid.uuid4()),
            "type": "experience",
            "role": "Cloud Security & DevOps Engineer",
            "company": "Aegis Systems Corp",
            "duration": "2022 - 2024",
            "location": "Singapore (Remote)",
            "description": "Architected EKS infrastructure blueprints with Terraform. Implemented declarative GitOps continuous delivery via Argo CD and optimized application telemetry collections with Prometheus and Grafana.",
            "order": 2
        },
        {
            "id": str(uuid.uuid4()),
            "type": "experience",
            "role": "Systems Administrator & Automation Engineer",
            "company": "TechBase Global",
            "duration": "2020 - 2022",
            "location": "Hanoi, Vietnam",
            "description": "Managed virtualization clusters, automated configurations with Ansible playbooks, built CI pipelines in GitLab CI, and monitored network routing paths.",
            "order": 3
        },
        # Certifications
        {
            "id": str(uuid.uuid4()),
            "type": "certification",
            "title": "AWS Certified Solutions Architect",
            "issuer": "Associate \u2022 Verified Credly Badge",
            "badge_url": "https://www.credly.com/badges/fb64362a-24b4-4006-bc6d-d7fd1428a9e1/public_url",
            "icon": "fa-brands fa-aws text-orange-400",
            "order": 4
        },
        {
            "id": str(uuid.uuid4()),
            "type": "certification",
            "title": "AWS Certified Cloud Practitioner",
            "issuer": "Foundational \u2022 Verified Credly Badge",
            "badge_url": "https://www.credly.com/badges/d38c4a62-2af2-4593-9e90-5b0bd42517e2/public_url",
            "icon": "fa-brands fa-aws text-orange-400",
            "order": 5
        }
    ]
    
    print("Clearing existing items from table...")
    # Scan and delete existing items
    response = table.scan()
    for item in response.get('Items', []):
        table.delete_item(Key={'id': item['id']})
        
    print(f"Seeding {len(items)} items into 'project-sam-timeline' DynamoDB Table...")
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            
    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed_data()

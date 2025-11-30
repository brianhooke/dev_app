"""
Helper to retrieve secrets from AWS Secrets Manager
"""
import json
import boto3
from botocore.exceptions import ClientError


def get_secret(secret_name, region_name="us-east-1"):
    """
    Retrieve a secret from AWS Secrets Manager
    
    Usage:
        from dev_app.aws_secrets import get_secret
        email_password = get_secret('dev-app/email-password')
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    # Secrets can be string or binary
    if 'SecretString' in get_secret_value_response:
        return get_secret_value_response['SecretString']
    else:
        return get_secret_value_response['SecretBinary']

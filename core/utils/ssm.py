"""
AWS SSM Parameter Store utility for storing Xero credentials.

This module provides functions to read/write Xero credentials to AWS SSM
Parameter Store instead of the database. This ensures credentials persist
across database wipes and deployments.

Parameter naming convention:
  /dev-app/xero/{instance_pk}/{param_name}

Parameters stored:
  - client_id
  - client_secret
  - access_token
  - refresh_token
  - tenant_id
  - token_expires_at
"""

import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings

logger = logging.getLogger(__name__)

# Prefix for all Xero-related SSM parameters
SSM_PREFIX = '/dev-app/xero'

# Flag to enable/disable SSM (for local development without AWS)
_ssm_client = None
_ssm_available = None


def _get_ssm_client():
    """Get or create SSM client. Returns None if AWS credentials not available."""
    global _ssm_client, _ssm_available
    
    if _ssm_available is False:
        return None
    
    if _ssm_client is not None:
        return _ssm_client
    
    try:
        _ssm_client = boto3.client(
            'ssm',
            region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
        )
        # Test connection
        _ssm_client.describe_parameters(MaxResults=1)
        _ssm_available = True
        logger.info("SSM Parameter Store connection established")
        return _ssm_client
    except NoCredentialsError:
        logger.warning("AWS credentials not found - SSM storage disabled, using DB fallback")
        _ssm_available = False
        return None
    except ClientError as e:
        logger.warning(f"SSM connection failed: {e} - using DB fallback")
        _ssm_available = False
        return None
    except Exception as e:
        logger.warning(f"SSM unavailable: {e} - using DB fallback")
        _ssm_available = False
        return None


def is_ssm_available():
    """Check if SSM Parameter Store is available."""
    return _get_ssm_client() is not None


def _get_param_name(instance_pk, param_name):
    """Build full parameter path."""
    return f"{SSM_PREFIX}/{instance_pk}/{param_name}"


def get_xero_param(instance_pk, param_name, default=None):
    """
    Get a Xero parameter from SSM.
    
    Args:
        instance_pk: Xero instance primary key
        param_name: Parameter name (client_secret, access_token, etc.)
        default: Default value if parameter doesn't exist
        
    Returns:
        Parameter value or default
    """
    client = _get_ssm_client()
    if not client:
        return default
    
    try:
        full_name = _get_param_name(instance_pk, param_name)
        response = client.get_parameter(
            Name=full_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            return default
        logger.error(f"Error getting SSM param {param_name} for instance {instance_pk}: {e}")
        return default
    except Exception as e:
        logger.error(f"Unexpected error getting SSM param: {e}")
        return default


def set_xero_param(instance_pk, param_name, value):
    """
    Set a Xero parameter in SSM.
    
    Args:
        instance_pk: Xero instance primary key
        param_name: Parameter name
        value: Value to store (will be stored as SecureString)
        
    Returns:
        True if successful, False otherwise
    """
    client = _get_ssm_client()
    if not client:
        logger.warning(f"SSM not available - cannot store {param_name} for instance {instance_pk}")
        return False
    
    if value is None:
        # Delete parameter if value is None
        return delete_xero_param(instance_pk, param_name)
    
    try:
        full_name = _get_param_name(instance_pk, param_name)
        client.put_parameter(
            Name=full_name,
            Value=str(value),
            Type='SecureString',
            Overwrite=True
        )
        logger.info(f"Stored SSM param {param_name} for instance {instance_pk}")
        return True
    except ClientError as e:
        logger.error(f"Error setting SSM param {param_name} for instance {instance_pk}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error setting SSM param: {e}")
        return False


def delete_xero_param(instance_pk, param_name):
    """
    Delete a Xero parameter from SSM.
    
    Args:
        instance_pk: Xero instance primary key
        param_name: Parameter name
        
    Returns:
        True if successful or param doesn't exist, False on error
    """
    client = _get_ssm_client()
    if not client:
        return False
    
    try:
        full_name = _get_param_name(instance_pk, param_name)
        client.delete_parameter(Name=full_name)
        logger.info(f"Deleted SSM param {param_name} for instance {instance_pk}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            return True  # Already deleted
        logger.error(f"Error deleting SSM param {param_name} for instance {instance_pk}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting SSM param: {e}")
        return False


def delete_all_xero_params(instance_pk):
    """
    Delete all SSM parameters for a Xero instance.
    Called when deleting a Xero instance.
    
    Args:
        instance_pk: Xero instance primary key
        
    Returns:
        True if successful, False on error
    """
    client = _get_ssm_client()
    if not client:
        return False
    
    param_names = ['client_id', 'client_secret', 'access_token', 'refresh_token', 'tenant_id', 'token_expires_at']
    
    for param_name in param_names:
        delete_xero_param(instance_pk, param_name)
    
    logger.info(f"Deleted all SSM params for instance {instance_pk}")
    return True


def get_all_xero_params(instance_pk):
    """
    Get all Xero parameters for an instance.
    
    Args:
        instance_pk: Xero instance primary key
        
    Returns:
        Dict of parameter values
    """
    return {
        'client_id': get_xero_param(instance_pk, 'client_id'),
        'client_secret': get_xero_param(instance_pk, 'client_secret'),
        'access_token': get_xero_param(instance_pk, 'access_token'),
        'refresh_token': get_xero_param(instance_pk, 'refresh_token'),
        'tenant_id': get_xero_param(instance_pk, 'tenant_id'),
        'token_expires_at': get_xero_param(instance_pk, 'token_expires_at'),
    }


def set_xero_oauth_tokens(instance_pk, access_token, refresh_token, expires_at, tenant_id=None):
    """
    Set all OAuth tokens for a Xero instance at once.
    
    Args:
        instance_pk: Xero instance primary key
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_at: Token expiry datetime (ISO format string or datetime)
        tenant_id: Optional tenant ID
        
    Returns:
        True if all succeeded, False if any failed
    """
    success = True
    
    success = set_xero_param(instance_pk, 'access_token', access_token) and success
    success = set_xero_param(instance_pk, 'refresh_token', refresh_token) and success
    
    # Convert datetime to ISO string if needed
    if expires_at and hasattr(expires_at, 'isoformat'):
        expires_at = expires_at.isoformat()
    success = set_xero_param(instance_pk, 'token_expires_at', expires_at) and success
    
    if tenant_id:
        success = set_xero_param(instance_pk, 'tenant_id', tenant_id) and success
    
    return success


def clear_xero_oauth_tokens(instance_pk):
    """
    Clear OAuth tokens for a Xero instance (e.g., when credentials change).
    
    Args:
        instance_pk: Xero instance primary key
        
    Returns:
        True if successful
    """
    delete_xero_param(instance_pk, 'access_token')
    delete_xero_param(instance_pk, 'refresh_token')
    delete_xero_param(instance_pk, 'token_expires_at')
    delete_xero_param(instance_pk, 'tenant_id')
    return True

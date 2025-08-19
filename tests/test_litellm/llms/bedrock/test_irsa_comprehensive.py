"""
Comprehensive tests for IRSA (IAM Roles for Service Accounts) functionality
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from litellm.llms.bedrock.base_aws_llm import BaseAWSLLM


class TestIRSAComprehensive:
    """Comprehensive tests for IRSA role assumption logic"""

    def test_irsa_same_role_with_env_credentials(self):
        """Test IRSA same-role optimization when AWS credentials are in environment"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_env_vars method to return test credentials
        mock_creds = MagicMock()
        mock_creds.access_key = 'irsa-access-key'
        mock_creds.secret_key = 'irsa-secret-key'
        mock_creds.token = 'irsa-session-token'
        
        with patch.dict(os.environ, {
            'AWS_ROLE_ARN': 'arn:aws:iam::111111111111:role/LitellmRole',
            # Note: Current implementation doesn't require AWS_WEB_IDENTITY_TOKEN_FILE
            # It only checks AWS_ROLE_ARN and that no explicit credentials are provided
        }):
            with patch.object(base_llm, '_auth_with_env_vars', return_value=(mock_creds, None)) as mock_env_auth:
                with patch.object(base_llm, '_auth_with_aws_role', side_effect=Exception("Should not be called")) as mock_role_auth:
                    # Clear cache to ensure fresh evaluation
                    base_llm.iam_cache.flush_cache()
                    
                    # Test with same role as current IRSA role
                    creds = base_llm.get_credentials(
                        aws_access_key_id=None,
                        aws_secret_access_key=None,
                        aws_role_name='arn:aws:iam::111111111111:role/LitellmRole',  # Same as AWS_ROLE_ARN
                        aws_session_name='test-session',
                        aws_region_name='us-east-1'
                    )
                    
                    # Should use IRSA optimization
                    assert mock_env_auth.called, "Should use _auth_with_env_vars for IRSA same-role optimization"
                    assert not mock_role_auth.called, "Should not call _auth_with_aws_role when using IRSA optimization"
                    assert creds.access_key == 'irsa-access-key'

    def test_irsa_different_role_forces_assumption(self):
        """Test that different role forces role assumption even in IRSA environment"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_aws_role method
        mock_creds = MagicMock()
        mock_creds.access_key = 'assumed-role-access-key'
        mock_creds.secret_key = 'assumed-role-secret-key'
        mock_creds.token = 'assumed-role-session-token'
        
        with patch.dict(os.environ, {
            'AWS_ROLE_ARN': 'arn:aws:iam::111111111111:role/CurrentRole',
            'AWS_WEB_IDENTITY_TOKEN_FILE': '/var/run/secrets/eks.amazonaws.com/serviceaccount/token'
        }):
            with patch.object(base_llm, '_auth_with_aws_role', return_value=(mock_creds, None)) as mock_role_auth:
                with patch.object(base_llm, '_auth_with_env_vars', side_effect=Exception("Should not be called")) as mock_env_auth:
                    # Clear cache
                    base_llm.iam_cache.flush_cache()
                    
                    # Test with different role than current IRSA role
                    creds = base_llm.get_credentials(
                        aws_access_key_id=None,
                        aws_secret_access_key=None,
                        aws_role_name='arn:aws:iam::111111111111:role/DifferentRole',  # Different from AWS_ROLE_ARN
                        aws_session_name='test-session',
                        aws_region_name='us-east-1'
                    )
                    
                    # Should use role assumption
                    assert mock_role_auth.called, "Should use _auth_with_aws_role for different role"
                    assert not mock_env_auth.called, "Should not call _auth_with_env_vars for different role"
                    assert creds.access_key == 'assumed-role-access-key'

    def test_non_irsa_environment_uses_role_assumption(self):
        """Test that non-IRSA environment uses normal role assumption"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_aws_role method
        mock_creds = MagicMock()
        mock_creds.access_key = 'assumed-role-access-key'
        
        with patch.dict(os.environ, {
            # No IRSA environment variables
        }, clear=True):
            with patch.object(base_llm, '_auth_with_aws_role', return_value=(mock_creds, None)) as mock_role_auth:
                with patch.object(base_llm, '_auth_with_env_vars', side_effect=Exception("Should not be called")) as mock_env_auth:
                    # Clear cache
                    base_llm.iam_cache.flush_cache()
                    
                    creds = base_llm.get_credentials(
                        aws_access_key_id=None,
                        aws_secret_access_key=None,
                        aws_role_name='arn:aws:iam::111111111111:role/SomeRole',
                        aws_session_name='test-session',
                        aws_region_name='us-east-1'
                    )
                    
                    # Should use role assumption
                    assert mock_role_auth.called, "Should use _auth_with_aws_role in non-IRSA environment"
                    assert not mock_env_auth.called, "Should not call _auth_with_env_vars in non-IRSA environment"

    def test_irsa_without_web_identity_token_file(self):
        """Test that AWS_ROLE_ARN alone still triggers IRSA optimization in current implementation"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_env_vars method (current implementation uses this for IRSA)
        mock_creds = MagicMock()
        mock_creds.access_key = 'irsa-access-key'
        
        with patch.dict(os.environ, {
            'AWS_ROLE_ARN': 'arn:aws:iam::111111111111:role/LitellmRole',
            # Current implementation doesn't require AWS_WEB_IDENTITY_TOKEN_FILE
        }):
            with patch.object(base_llm, '_auth_with_env_vars', return_value=(mock_creds, None)) as mock_env_auth:
                with patch.object(base_llm, '_auth_with_aws_role', side_effect=Exception("Should not be called")) as mock_role_auth:
                    # Clear cache
                    base_llm.iam_cache.flush_cache()
                    
                    creds = base_llm.get_credentials(
                        aws_access_key_id=None,
                        aws_secret_access_key=None,
                        aws_role_name='arn:aws:iam::111111111111:role/LitellmRole',  # Same as AWS_ROLE_ARN
                        aws_session_name='test-session',
                        aws_region_name='us-east-1'
                    )
                    
                    # Should use IRSA optimization (current implementation behavior)
                    assert mock_env_auth.called, "Should use _auth_with_env_vars with AWS_ROLE_ARN present"
                    assert not mock_role_auth.called, "Should not call _auth_with_aws_role when using IRSA optimization"

    def test_explicit_credentials_override_irsa(self):
        """Test that explicit credentials override IRSA optimization"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_aws_role method
        mock_creds = MagicMock()
        mock_creds.access_key = 'explicit-access-key'
        
        with patch.dict(os.environ, {
            'AWS_ROLE_ARN': 'arn:aws:iam::111111111111:role/LitellmRole',
            'AWS_WEB_IDENTITY_TOKEN_FILE': '/var/run/secrets/eks.amazonaws.com/serviceaccount/token'
        }):
            with patch.object(base_llm, '_auth_with_aws_role', return_value=(mock_creds, None)) as mock_role_auth:
                with patch.object(base_llm, '_auth_with_env_vars', side_effect=Exception("Should not be called")) as mock_env_auth:
                    # Clear cache
                    base_llm.iam_cache.flush_cache()
                    
                    # Provide explicit credentials
                    creds = base_llm.get_credentials(
                        aws_access_key_id='EXPLICIT_ACCESS_KEY',
                        aws_secret_access_key='EXPLICIT_SECRET_KEY',
                        aws_role_name='arn:aws:iam::111111111111:role/LitellmRole',  # Same as AWS_ROLE_ARN
                        aws_session_name='test-session',
                        aws_region_name='us-east-1'
                    )
                    
                    # Should use role assumption with explicit credentials
                    assert mock_role_auth.called, "Should use _auth_with_aws_role with explicit credentials"
                    assert not mock_env_auth.called, "Should not call _auth_with_env_vars with explicit credentials"

    def test_irsa_condition_components(self):
        """Test individual components of the IRSA condition (current implementation)"""
        base_llm = BaseAWSLLM()
        
        test_cases = [
            # (AWS_ROLE_ARN, requested_role, should_use_irsa)
            # Current implementation only checks AWS_ROLE_ARN and role match
            ('arn:aws:iam::111111111111:role/Role1', 'arn:aws:iam::111111111111:role/Role1', True),
            ('arn:aws:iam::111111111111:role/Role1', 'arn:aws:iam::111111111111:role/Role2', False),
            (None, 'arn:aws:iam::111111111111:role/Role1', False),
        ]
        
        for current_role, requested_role, should_use_irsa in test_cases:
            with patch.dict(os.environ, {
                'AWS_ROLE_ARN': current_role or '',
            }, clear=True):
                # Remove empty values
                if not current_role:
                    os.environ.pop('AWS_ROLE_ARN', None)
                
                mock_env_creds = MagicMock()
                mock_env_creds.access_key = 'irsa-key'
                
                mock_role_creds = MagicMock()
                mock_role_creds.access_key = 'role-key'
                
                with patch.object(base_llm, '_auth_with_env_vars', return_value=(mock_env_creds, None)) as mock_env_auth:
                    with patch.object(base_llm, '_auth_with_aws_role', return_value=(mock_role_creds, None)) as mock_role_auth:
                        # Clear cache
                        base_llm.iam_cache.flush_cache()
                        
                        creds = base_llm.get_credentials(
                            aws_access_key_id=None,
                            aws_secret_access_key=None,
                            aws_role_name=requested_role,
                            aws_session_name='test-session',
                            aws_region_name='us-east-1'
                        )
                        
                        if should_use_irsa:
                            assert mock_env_auth.called, f"Should use IRSA for case: {current_role}, {requested_role}"
                            assert not mock_role_auth.called, f"Should not use role assumption for IRSA case: {current_role}, {requested_role}"
                            assert creds.access_key == 'irsa-key'
                        else:
                            assert not mock_env_auth.called, f"Should not use IRSA for case: {current_role}, {requested_role}"
                            assert mock_role_auth.called, f"Should use role assumption for case: {current_role}, {requested_role}"
                            assert creds.access_key == 'role-key'

    def test_irsa_with_web_identity_token_direct(self):
        """Test that direct web identity token flow takes precedence over IRSA optimization"""
        base_llm = BaseAWSLLM()
        
        # Mock the _auth_with_web_identity_token method
        mock_creds = MagicMock()
        mock_creds.access_key = 'web-identity-access-key'
        
        with patch.dict(os.environ, {
            'AWS_ROLE_ARN': 'arn:aws:iam::111111111111:role/LitellmRole',
            'AWS_WEB_IDENTITY_TOKEN_FILE': '/var/run/secrets/eks.amazonaws.com/serviceaccount/token',
            'AWS_WEB_IDENTITY_TOKEN': 'direct-token-value'  # This should trigger web identity flow
        }):
            with patch.object(base_llm, '_auth_with_web_identity_token', return_value=(mock_creds, None)) as mock_web_auth:
                with patch.object(base_llm, '_auth_with_env_vars', side_effect=Exception("Should not be called")) as mock_env_auth:
                    with patch.object(base_llm, '_auth_with_aws_role', side_effect=Exception("Should not be called")) as mock_role_auth:
                        # Clear cache
                        base_llm.iam_cache.flush_cache()
                        
                        creds = base_llm.get_credentials(
                            aws_access_key_id=None,
                            aws_secret_access_key=None,
                            aws_role_name='arn:aws:iam::111111111111:role/LitellmRole',
                            aws_session_name='test-session',
                            aws_region_name='us-east-1',
                            aws_web_identity_token='direct-token-value'
                        )
                        
                        # Should use web identity token flow
                        assert mock_web_auth.called, "Should use _auth_with_web_identity_token when token is provided"
                        assert not mock_env_auth.called, "Should not call _auth_with_env_vars when using web identity token"
                        assert not mock_role_auth.called, "Should not call _auth_with_aws_role when using web identity token"
                        assert creds.access_key == 'web-identity-access-key'
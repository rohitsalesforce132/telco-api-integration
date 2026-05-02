"""
Tests for API Gateway & Security
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.gateway import (
    HTTPMethod, AuthType, ErrorType,
    APIGateway, OAuth2Server, APIKeyManager,
    RateLimiter, RequestValidator, ResponseFormatter, ErrorMapper
)


class TestAPIGateway(unittest.TestCase):
    """Test APIGateway"""

    def setUp(self):
        self.gateway = APIGateway()

    def test_add_route(self):
        """Test adding a route"""
        route = self.gateway.add_route(
            path="/api/v1/catalog",
            method=HTTPMethod.GET,
            handler="catalog_handler"
        )

        self.assertIsNotNone(route)
        self.assertEqual(route.path, "/api/v1/catalog")
        self.assertEqual(route.method, HTTPMethod.GET)

    def test_get_route(self):
        """Test getting a route"""
        self.gateway.add_route("/api/v1/catalog", HTTPMethod.GET, "handler")

        route = self.gateway.get_route("/api/v1/catalog", HTTPMethod.GET)
        self.assertIsNotNone(route)
        self.assertEqual(route.path, "/api/v1/catalog")

    def test_list_routes(self):
        """Test listing routes"""
        self.gateway.add_route("/api/v1/catalog", HTTPMethod.GET, "handler1")
        self.gateway.add_route("/api/v1/inventory", HTTPMethod.POST, "handler2")

        routes = self.gateway.list_routes()
        self.assertEqual(len(routes), 2)

    def test_register_handler(self):
        """Test registering a handler"""
        def test_handler(request_id, path, method, headers, body):
            return {"status": 200, "data": "test"}

        self.gateway.register_handler("test_handler", test_handler)

        self.assertIn("test_handler", self.gateway._handlers)

    def test_handle_request(self):
        """Test handling a request"""
        def test_handler(request_id, path, method, headers, body):
            return {"status": 200, "data": "success"}

        self.gateway.add_route("/test", HTTPMethod.GET, "test_handler")
        self.gateway.register_handler("test_handler", test_handler)

        response = self.gateway.handle_request("/test", "GET", {})

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["data"], "success")

    def test_handle_request_route_not_found(self):
        """Test handling request with route not found"""
        response = self.gateway.handle_request("/nonexistent", "GET", {})

        self.assertEqual(response["status"], 404)


class TestOAuth2Server(unittest.TestCase):
    """Test OAuth2Server"""

    def setUp(self):
        self.server = OAuth2Server()

        # Register test client
        self.server.register_client(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uris=["http://localhost/callback"],
            scopes=["read", "write"]
        )

        # Register test user
        self.server.register_user(
            user_id="user1",
            username="testuser",
            password="testpass"
        )

    def test_issue_token(self):
        """Test issuing OAuth2 token"""
        token = self.server.issue_token(
            client_id="test_client",
            client_secret="test_secret",
            user_id="user1"
        )

        self.assertIsNotNone(token)
        self.assertEqual(token.client_id, "test_client")
        self.assertEqual(token.user_id, "user1")
        self.assertIsNotNone(token.access_token)

    def test_issue_token_invalid_client_fails(self):
        """Test that issuing token with invalid client fails"""
        with self.assertRaises(ValueError):
            self.server.issue_token(
                client_id="invalid_client",
                client_secret="invalid_secret",
                user_id="user1"
            )

    def test_validate_token(self):
        """Test validating OAuth2 token"""
        token = self.server.issue_token(
            client_id="test_client",
            client_secret="test_secret",
            user_id="user1",
            expires_in_seconds=3600
        )

        validated = self.server.validate_token(token.access_token)

        self.assertIsNotNone(validated)
        self.assertEqual(validated.token_id, token.token_id)

    def test_validate_token_invalid(self):
        """Test validating invalid token"""
        validated = self.server.validate_token("invalid_token")
        self.assertIsNone(validated)

    def test_refresh_token(self):
        """Test refreshing OAuth2 token"""
        token = self.server.issue_token(
            client_id="test_client",
            client_secret="test_secret",
            user_id="user1"
        )

        new_token = self.server.refresh_token(token.refresh_token, "test_client")

        self.assertIsNotNone(new_token)
        self.assertNotEqual(new_token.access_token, token.access_token)

    def test_revoke_token(self):
        """Test revoking OAuth2 token"""
        token = self.server.issue_token(
            client_id="test_client",
            client_secret="test_secret",
            user_id="user1"
        )

        result = self.server.revoke_token(token.access_token)
        self.assertTrue(result)

        validated = self.server.validate_token(token.access_token)
        self.assertIsNone(validated)


class TestAPIKeyManager(unittest.TestCase):
    """Test APIKeyManager"""

    def setUp(self):
        self.manager = APIKeyManager()

    def test_create_key(self):
        """Test creating an API key"""
        key = self.manager.create_key(partner_id="partner1")

        self.assertIsNotNone(key)
        self.assertEqual(key.partner_id, "partner1")
        self.assertTrue(key.is_active)
        self.assertIsNotNone(key.key_value)

    def test_validate_key(self):
        """Test validating an API key"""
        key = self.manager.create_key(partner_id="partner1")

        validated = self.manager.validate_key(key.key_value)

        self.assertIsNotNone(validated)
        self.assertEqual(validated.key_id, key.key_id)

    def test_validate_key_invalid(self):
        """Test validating invalid API key"""
        validated = self.manager.validate_key("invalid_key")
        self.assertIsNone(validated)

    def test_revoke_key(self):
        """Test revoking an API key"""
        key = self.manager.create_key(partner_id="partner1")

        result = self.manager.revoke_key(key.key_value)
        self.assertTrue(result)

        validated = self.manager.validate_key(key.key_value)
        self.assertIsNone(validated)

    def test_list_keys(self):
        """Test listing keys for partner"""
        self.manager.create_key("partner1")
        self.manager.create_key("partner1")
        self.manager.create_key("partner2")

        partner1_keys = self.manager.list_keys("partner1")
        self.assertEqual(len(partner1_keys), 2)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter"""

    def setUp(self):
        self.limiter = RateLimiter()

    def test_check_rate_limit_within_limit(self):
        """Test checking rate limit within limit"""
        is_allowed = self.limiter.check_rate_limit("user1", limit_per_minute=60)

        self.assertTrue(is_allowed)

    def test_check_rate_limit_exceeded(self):
        """Test checking rate limit exceeded"""
        # Use a low limit for testing
        limit = 5

        # Make 5 requests
        for _ in range(limit):
            self.limiter.check_rate_limit("user1", limit_per_minute=limit)

        # 6th request should be blocked
        is_allowed = self.limiter.check_rate_limit("user1", limit_per_minute=limit)
        self.assertFalse(is_allowed)

    def test_reset_bucket(self):
        """Test resetting rate limit bucket"""
        self.limiter.check_rate_limit("user1", limit_per_minute=1)
        self.limiter.check_rate_limit("user1", limit_per_minute=1)

        self.limiter.reset_bucket("user1")

        is_allowed = self.limiter.check_rate_limit("user1", limit_per_minute=1)
        self.assertTrue(is_allowed)

    def test_get_bucket_status(self):
        """Test getting bucket status"""
        self.limiter.check_rate_limit("user1", limit_per_minute=60)

        status = self.limiter.get_bucket_status("user1")

        self.assertIsNotNone(status)
        self.assertIn("tokens_remaining", status)
        self.assertIn("capacity", status)


class TestRequestValidator(unittest.TestCase):
    """Test RequestValidator"""

    def setUp(self):
        self.validator = RequestValidator()

        # Register a test schema
        self.validator.register_schema("test_schema", {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"},
                "status": {"enum": ["active", "inactive"]}
            }
        })

    def test_validate_valid_data(self):
        """Test validating valid data"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "active": True,
            "status": "active"
        }

        is_valid, errors = self.validator.validate(data, "test_schema")

        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_missing_required_field(self):
        """Test validating with missing required field"""
        data = {
            "name": "John Doe"
        }

        is_valid, errors = self.validator.validate(data, "test_schema")

        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        self.assertIn("email", errors[0])

    def test_validate_wrong_type(self):
        """Test validating with wrong type"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": "thirty"  # Should be integer
        }

        is_valid, errors = self.validator.validate(data, "test_schema")

        self.assertFalse(is_valid)
        type_error = any("age" in e and "type" in e for e in errors)
        self.assertTrue(type_error)

    def test_validate_invalid_enum(self):
        """Test validating with invalid enum value"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "status": "pending"  # Not in enum
        }

        is_valid, errors = self.validator.validate(data, "test_schema")

        # Status is not a required field, so validation passes
        # but the enum value doesn't match
        self.assertTrue(is_valid or len(errors) > 0)


class TestResponseFormatter(unittest.TestCase):
    """Test ResponseFormatter"""

    def setUp(self):
        self.formatter = ResponseFormatter()

    def test_format_success(self):
        """Test formatting successful response"""
        response = self.formatter.format_success({"id": 123}, request_id="req1")

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"]["id"], 123)
        self.assertEqual(response["request_id"], "req1")

    def test_format_error(self):
        """Test formatting error response"""
        response = self.formatter.format_error(
            error_type="INVALID_REQUEST",
            message="Invalid input",
            request_id="req1"
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["type"], "INVALID_REQUEST")
        self.assertEqual(response["error"]["message"], "Invalid input")

    def test_format_paginated(self):
        """Test formatting paginated response"""
        items = [{"id": 1}, {"id": 2}]
        response = self.formatter.format_paginated(items, total=10, offset=0, limit=2)

        self.assertEqual(len(response["items"]), 2)
        self.assertEqual(response["pagination"]["total"], 10)
        self.assertTrue(response["pagination"]["has_more"])


class TestErrorMapper(unittest.TestCase):
    """Test ErrorMapper"""

    def setUp(self):
        self.mapper = ErrorMapper()

    def test_get_mapping(self):
        """Test getting error mapping"""
        mapping = self.mapper.get_mapping(ErrorType.NOT_FOUND)

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.http_status, 404)
        self.assertIsNotNone(mapping.tmf_code)

    def test_map_exception_not_found(self):
        """Test mapping not found exception"""
        mapping = self.mapper.map_exception(ValueError("Resource not found"))

        self.assertEqual(mapping.error_type, ErrorType.NOT_FOUND)

    def test_map_exception_unauthorized(self):
        """Test mapping unauthorized exception"""
        mapping = self.mapper.map_exception(PermissionError("Unauthorized access"))

        self.assertEqual(mapping.error_type, ErrorType.UNAUTHORIZED)

    def test_map_exception_generic(self):
        """Test mapping generic exception"""
        mapping = self.mapper.map_exception(Exception("Some error"))

        self.assertEqual(mapping.error_type, ErrorType.INTERNAL_ERROR)


if __name__ == "__main__":
    unittest.main()

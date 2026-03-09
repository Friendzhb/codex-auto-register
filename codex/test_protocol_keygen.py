import unittest
from unittest import mock

import protocol_keygen


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, get_responses=None, post_response=None):
        self.get_responses = list(get_responses or [])
        self.post_response = post_response
        self.last_post_kwargs = {}

    def get(self, *args, **kwargs):
        return self.get_responses.pop(0)

    def post(self, *args, **kwargs):
        self.last_post_kwargs = kwargs
        return self.post_response

    def delete(self, *args, **kwargs):
        return FakeResponse(status_code=200)


class ProtocolKeygenMailTests(unittest.TestCase):
    def test_use_moemail_ignores_placeholder_api_key(self):
        with mock.patch.object(protocol_keygen, "MOEMAIL_API_KEY", "YOUR_API_KEY"):
            self.assertFalse(protocol_keygen.use_moemail())

    def test_extract_verification_code_supports_moemail_patterns(self):
        self.assertEqual(
            protocol_keygen.extract_verification_code("Verification code: 123456"),
            "123456",
        )
        self.assertEqual(
            protocol_keygen.extract_verification_code("验证码：654321"),
            "654321",
        )
        self.assertIsNone(protocol_keygen.extract_verification_code("Subject: 177010"))
        self.assertIsNone(
            protocol_keygen.extract_verification_code("<p>验证码：177010</p>")
        )
        self.assertIsNone(
            protocol_keygen.extract_verification_code("https://example.com?a=177010&b=1")
        )
        self.assertEqual(
            protocol_keygen.extract_verification_code("Use code 555444 to continue"),
            "555444",
        )

    def test_create_temp_email_uses_moemail_response_shape(self):
        session = FakeSession(
            post_response=FakeResponse(
                payload={"email": "demo@moemail.app", "id": "email-id-1"}
            )
        )
        with mock.patch.object(protocol_keygen, "MOEMAIL_API_KEY", "key"), \
             mock.patch.object(protocol_keygen, "MOEMAIL_API_URL", "https://mail.example.com"), \
             mock.patch.object(protocol_keygen, "MOEMAIL_DOMAIN", "moemail.app"), \
             mock.patch.object(protocol_keygen, "MOEMAIL_EXPIRY_TIME", 3600000):
            email, mailbox_token = protocol_keygen.create_temp_email(session)

        self.assertEqual(email, "demo@moemail.app")
        self.assertEqual(mailbox_token, "email-id-1")

    def test_test_moemail_uses_valid_expiry_time(self):
        """_test_moemail must send an expiryTime accepted by the MoeMail API."""
        VALID_EXPIRY_TIMES = {0, 3600000, 86400000, 259200000}
        captured = {}

        class CapturingSession:
            def post(self, url, json=None, **kwargs):
                captured["json"] = json
                return FakeResponse(
                    status_code=200,
                    payload={"email": "t@moemail.app", "id": "eid-1"},
                )

            def delete(self, *args, **kwargs):
                return FakeResponse(status_code=200)

        with mock.patch("protocol_keygen.create_session", return_value=CapturingSession()):
            ok, err = protocol_keygen._test_moemail(
                "https://mail.example.com", "testkey", "moemail.app"
            )

        self.assertTrue(ok, err)
        self.assertIn(
            captured["json"]["expiryTime"],
            VALID_EXPIRY_TIMES,
            f"expiryTime {captured['json']['expiryTime']} is not a valid MoeMail value",
        )

    def test_fetch_emails_normalizes_moemail_message_details(self):
        session = FakeSession(
            get_responses=[
                FakeResponse(payload={"messages": [{"id": "msg-1"}]}),
                FakeResponse(payload={
                    "html": "<p>Verification code: 246810</p>",
                    "subject": "OpenAI",
                    "from": "noreply@openai.com",
                }),
            ]
        )
        with mock.patch.object(protocol_keygen, "MOEMAIL_API_KEY", "key"), \
             mock.patch.object(protocol_keygen, "MOEMAIL_API_URL", "https://mail.example.com"):
            messages = protocol_keygen.fetch_emails(session, "demo@moemail.app", "email-id-1")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], "msg-1")
        self.assertIn("246810", messages[0]["raw"])
        self.assertEqual(messages[0]["subject"], "OpenAI")


if __name__ == "__main__":
    unittest.main()

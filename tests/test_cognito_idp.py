"""Tests for scripts/cognito_idp.py.

The probe classifier needs to correctly interpret Cognito's different
wordings for "this flow is disabled on the app client":

* USER_PASSWORD_AUTH → ``"USER_PASSWORD_AUTH flow not enabled for this client"``
* USER_SRP_AUTH      → ``"USER_SRP_AUTH is not enabled for the client."``
"""
from __future__ import annotations

import responses

from scripts.cognito_idp import COGNITO_IDP_URL, CognitoIdentityProvider


def _cognito_error(msg: str, err_type: str = "InvalidParameterException") -> dict:
    return {"__type": err_type, "message": msg}


@responses.activate
def test_probe_user_password_auth_recognises_flow_disabled() -> None:
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("USER_PASSWORD_AUTH flow not enabled for this client"),
        status=400,
    )
    result = CognitoIdentityProvider().probe_user_password_auth()
    assert result["status"] == "flow_disabled"
    assert result["flow"] == "USER_PASSWORD_AUTH"


@responses.activate
def test_probe_user_srp_auth_recognises_flow_disabled_alt_wording() -> None:
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("USER_SRP_AUTH is not enabled for the client."),
        status=400,
    )
    result = CognitoIdentityProvider().probe_user_srp_auth()
    assert result["status"] == "flow_disabled"
    assert result["flow"] == "USER_SRP_AUTH"


@responses.activate
def test_probe_reports_flow_enabled_on_not_authorized() -> None:
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("Incorrect username or password.", "NotAuthorizedException"),
        status=400,
    )
    result = CognitoIdentityProvider().probe_user_password_auth()
    assert result["status"] == "flow_enabled"


@responses.activate
def test_probe_reports_flow_enabled_on_user_not_found() -> None:
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("User does not exist.", "UserNotFoundException"),
        status=400,
    )
    result = CognitoIdentityProvider().probe_user_password_auth()
    assert result["status"] == "flow_enabled"


@responses.activate
def test_probe_reports_unknown_on_waf_block() -> None:
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("Request not allowed due to WAF block.", "ForbiddenException"),
        status=403,
    )
    result = CognitoIdentityProvider().probe_user_password_auth()
    assert result["status"] == "unknown"
    assert result["http_status"] == 403


@responses.activate
def test_call_sends_waf_bypass_headers() -> None:
    """The probe must send SDK-impersonating headers or it's WAF-blocked."""
    responses.post(
        COGNITO_IDP_URL,
        json=_cognito_error("Incorrect username or password.", "NotAuthorizedException"),
        status=400,
    )
    CognitoIdentityProvider().probe_user_password_auth()
    req = responses.calls[0].request
    assert req.headers["X-Amz-Target"] == "AWSCognitoIdentityProviderService.InitiateAuth"
    assert req.headers["Content-Type"] == "application/x-amz-json-1.1"
    assert "aws-amplify" in req.headers["X-Amz-User-Agent"]
    assert req.headers["Origin"] == "https://www.olx.pl"

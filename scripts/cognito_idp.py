"""Direct AWS Cognito Identity Provider client for OLX's user pool.

Talks to ``cognito-idp.eu-west-1.amazonaws.com`` without going through the
Hosted UI / PKCE / browser path. This is the route to **fully headless**
auth when the user has a native Cognito password and the app client has
the relevant auth flow enabled on its ``ExplicitAuthFlows`` allowlist.

Pool:       eu-west-1_dUjFuvTf4
Client:     6j7elk01p32o648o1io8lvhhab (public, no client_secret)
Region:     eu-west-1

See :mod:`scripts.auth_cognito` for the interactive PKCE flow used when
the password path is not available.
"""
from __future__ import annotations

from typing import Optional

import requests

from .auth_cognito import CLIENT_ID

COGNITO_IDP_URL = "https://cognito-idp.eu-west-1.amazonaws.com/"


class CognitoIdentityProvider:
    """AWS Cognito Identity Provider API, scoped to OLX's user pool.

    Each public method maps 1:1 to a Cognito ``X-Amz-Target`` action.
    """

    def __init__(
        self,
        client_id: str = CLIENT_ID,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._client_id = client_id
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _call(self, target: str, body: dict) -> requests.Response:
        # OLX fronts cognito-idp with AWS WAF; direct calls without the
        # headers the amazon-cognito-identity-js SDK sends from the OLX
        # web app are blocked with "Request not allowed due to WAF block".
        # We mimic those so the WAF rule treats us as the legitimate SDK.
        return self._session.post(
            COGNITO_IDP_URL,
            json=body,
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": f"AWSCognitoIdentityProviderService.{target}",
                "X-Amz-User-Agent": "aws-amplify/5.0.4 js",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Origin": "https://www.olx.pl",
                "Referer": "https://www.olx.pl/",
                "Accept": "*/*",
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            },
            timeout=15,
        )

    # ------------------------------------------------------------------
    # InitiateAuth
    # ------------------------------------------------------------------

    def initiate_auth_user_password(self, username: str, password: str) -> dict:
        """USER_PASSWORD_AUTH flow — returns the raw Cognito JSON."""
        r = self._call("InitiateAuth", {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": self._client_id,
            "AuthParameters": {"USERNAME": username, "PASSWORD": password},
        })
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Probes — no valid credentials required
    # ------------------------------------------------------------------

    def probe_user_password_auth(
        self,
        username: str = "probe-does-not-exist@example.invalid",
        password: str = "not-a-real-password-just-probing",
    ) -> dict:
        """Classify the server's response to a dummy USER_PASSWORD_AUTH call.

        This tells us whether the flow is in the app client's
        ``ExplicitAuthFlows`` list *without* needing valid credentials:

        * ``flow_disabled`` — server refuses the flow itself.
        * ``flow_enabled`` — server accepted the flow, rejected the
          (dummy) credentials. Headless password auth is viable once
          the user has real credentials.
        * ``unknown`` — unexpected response; inspect ``raw``.
        """
        return _classify_initiate_auth(
            self._call("InitiateAuth", {
                "AuthFlow": "USER_PASSWORD_AUTH",
                "ClientId": self._client_id,
                "AuthParameters": {"USERNAME": username, "PASSWORD": password},
            }),
            flow_name="USER_PASSWORD_AUTH",
        )

    def probe_user_srp_auth(
        self,
        username: str = "probe-does-not-exist@example.invalid",
    ) -> dict:
        """Classify the server's response to a dummy USER_SRP_AUTH call.

        SRP_A is a placeholder — an unused big number. The server checks
        the flow allowlist before touching SRP_A, so a malformed value
        is fine for probing purposes.
        """
        # Any valid-looking hex big integer — server won't get far enough
        # to actually validate it if the flow is disabled.
        srp_a_placeholder = "2" * 64
        return _classify_initiate_auth(
            self._call("InitiateAuth", {
                "AuthFlow": "USER_SRP_AUTH",
                "ClientId": self._client_id,
                "AuthParameters": {
                    "USERNAME": username,
                    "SRP_A": srp_a_placeholder,
                },
            }),
            flow_name="USER_SRP_AUTH",
        )


# ----------------------------------------------------------------------
# Response classification
# ----------------------------------------------------------------------


def _says_flow_disabled(err_msg: str, flow_name: str) -> bool:
    """Cognito uses two different wordings depending on the flow:

    * ``"USER_PASSWORD_AUTH flow not enabled for this client"``
    * ``"USER_SRP_AUTH is not enabled for the client."``
    """
    msg = err_msg.lower()
    name = flow_name.lower()
    if name not in msg:
        return False
    return "not enabled" in msg or "flow not enabled" in msg


def _classify_initiate_auth(r: requests.Response, flow_name: str) -> dict:
    """Turn a raw InitiateAuth response into a ``{status, error_type, …}`` dict."""
    try:
        payload = r.json()
    except ValueError:
        payload = {"__text__": r.text}

    err_type = (payload.get("__type") or "").split("#")[-1]
    err_msg = payload.get("message") or payload.get("Message") or ""

    result = {
        "flow": flow_name,
        "http_status": r.status_code,
        "error_type": err_type,
        "error_message": err_msg,
        "raw": payload,
    }

    if r.ok and "AuthenticationResult" in payload:
        result["status"] = "flow_enabled"
        result["note"] = "Credentials actually worked — unexpected for a probe."
    elif _says_flow_disabled(err_msg, flow_name):
        result["status"] = "flow_disabled"
    elif err_type in ("NotAuthorizedException", "UserNotFoundException"):
        result["status"] = "flow_enabled"
    else:
        result["status"] = "unknown"
    return result


# ----------------------------------------------------------------------
# CLI entry point — `python -m scripts.cognito_idp`
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import json

    idp = CognitoIdentityProvider()
    print("Probing USER_PASSWORD_AUTH …")
    pw = idp.probe_user_password_auth()
    print(json.dumps(pw, indent=2, ensure_ascii=False))

    print("\nProbing USER_SRP_AUTH …")
    srp = idp.probe_user_srp_auth()
    print(json.dumps(srp, indent=2, ensure_ascii=False))

    print("\n--- Summary ---")
    print(f"USER_PASSWORD_AUTH: {pw['status']}")
    print(f"USER_SRP_AUTH:      {srp['status']}")

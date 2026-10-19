# Bounded PR18 repair candidate — unpublished authority

Protocol authority is owner-relayed DevOps clarification dated 2026-10-19, not a published public contract. Public documentation refresh remains pending. No live authentication was performed.

`GenericClient(..., secret=...)` appends an optional Base32 secret without shifting existing positional parameters. Configuration `secret` is optional. Session login generates one SHA1/six-digit/30-second code and sends it in the OTP header; username/password alone remain JSON. No pyotp dependency is added. Enrollment URIs are not consumed (explicit rejection), hence URI parameters are never silently ignored.

Existing generic GET/get_raw/POST/PUT/DELETE methods accept an optional trailing `otp=` code for one caller-selected request. Ordinary session operations do not generate or retain OTP headers, including after elapsed time. The server decides verification expiry (default one hour, not a guarantee) and sensitive-operation challenges. Empty 401 OTP challenges remain AuthError without cause discrimination. Cookies alone are not MFA success.

There is no automatic login, OTP retry, mutation replay or auth downgrade after a challenge. Single-attempt behavior is SDK policy, not a server mandate. The caller must not resubmit an accepted code; this client does not implement a global replay cache across clients/processes. Explicit repeated caller invocations remain caller responsibility. High-level resource methods are unchanged; advanced explicit OTP requests use GenericClient, not an invented generic resource-option framework. No PATCH/HEAD/OPTIONS API exists in this SDK and none is introduced.

Existing session borrowing, timeout/proxy/trust_env, CSRF, origin/redirect refusal and redacted built-in request logging remain intact. Caller response hooks/transport exceptions retain their existing behavior. This is a source candidate requiring independent review and exact-composition hosted installed-wheel CI before publication or merge. No release/readiness or public documentation acceptance is granted.

## R1: explicit OTP with Digest is unsupported

Explicit `otp=` with `login_method='digest'` raises a fixed ApiClientError before dispatch, for every existing generic entry point. This intentional restriction prevents Requests' Digest 401 response hook from resending the same OTP and mutation body. Authentication is not stripped or changed to Basic/none. Ordinary Digest calls without OTP retain existing challenge negotiation (including its legacy second send); the single-attempt OTP policy does not claim all legacy Digest operations are single-dispatch.

Requests HTTPDigestAuth can send a preemptive Digest header when that auth object has a cached nonce and registers response hooks capable of resending on challenge. The SDK creates fresh Digest auth objects per ordinary operation; a previous successful operation is not grounds to reuse state or accept OTP+Digest. R1 rejects the combination before creating a Digest auth object or preparing any request, rather than relying on nonce state or suppressing hooks. Arbitrary caller-provided Session auth/hooks/adapters remain caller customizations, not a universal no-replay certification; no hidden SDK Digest challenge replay is permitted for the new explicit OTP argument.

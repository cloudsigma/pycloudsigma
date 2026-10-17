# Native policy changes (SDK proposal, not API contract)
GenericClient accepts timeout=15 (positive finite scalar orconnect/readtuple),trust_env=False,proxies=None,session=None. Explicitlogin_method wins;omittedNone inheritsconfig orbasic. Legacyconfigselection retainedwhenomitted. Existingcustomapi_endpoint remainsallowed;absolute cross-origin/userinfo request URLs refusedbeforeauth dispatch. Redirectfollow alwaysdisabled and3xxdecoder raisesApiClientError instead ofNone;noautomaticredirectoptin inthiscandidate. Usersmustexplicitlyconstructclientforneworigin. This changesdefaults intentionally inproposedmajor3.0.0rc1.
Client-ownedrequestsSession noenvproxy/netrc bydefault;trust_env=True explicitcompatibilityoptin;explicitproxies dictpassedthrough. Borrowedsession trust_env is deliberatelyset (documentedmutation);sessionmusthonorrequests keywordsemantics,not arbitrarypluginsecurityboundary. Directprivate_session reassignment remainsinternal/trusted,notpolicyproof. Timeoutisrequestsconnect/readtimeout,NOTwholeoperationdeadline norretrybudget/bodycap. Existingtransportexceptions propagate;SDKdoesnotwraptheir potentiallysensitive messages. Applications shouldredacterrors asbefore.
Built-in log hook emitsHTTPstatusONLY: noURL/path/query/headers/body/response content. Customresponse_hook remainscaller-controlled;no guaranteeagainstmaliciouscustomlogging. Explicitrequest_log_level=config selection remainsbutcannotenableoldrawbuiltinlogging. 403/4xx/5xx SDKexceptionmessages stillcontainservicebody bylegacycontract;notchanged/errorredactionbacklog. No wrapperNEXT/accountfence transferredtonativegenericclient.

## Runtime and qualification
Proposal version3.0.0rc1 selects Python>=3.10,<3.13; removes Python2 and older3.x. No publication of this prerelease has occurred. Build backend is pinned setuptools.build_meta. Installed final artifacts were tested on3.10/3.11/3.12:19 native/representative SDK methods plus13 companion inventory methods per target. Not full SDK API or live acceptance coverage. Live provisioning acceptance tests are excluded from offline runs.
Run portable SDK tests against an installed candidate wheel with `python -m unittest discover -s tests_offline -v`. No provider credentials required. Synthetic canaries only. Custom hooks/session.auth/cookies may still expose credentials; legacy error text includes service bodies. URL guard compares final resolved and Requests-normalized origin; custom endpoints allowed, ambiguous slash/backslash forms refused. No whole-operation deadline is implied by request timeout.

## HTTP 401 response details (additive)

AuthError raised by the common HTTP response decoder now exposes
`response_body` (the exact Requests `response.text`, without JSON parsing) and
`response_request_id` (X-REQUEST-ID, or None when absent). Empty, malformed,
plain-text and JSON bodies are preserved without interpretation. This is decoded
text, not a promise of original wire-byte or encoding preservation. No other
response headers or request/authentication data are attached.

For compatibility, legacy `message`, `args`, `request_id`, class and status are
unchanged: for 401, `message` still contains the response request ID (or None),
`request_id` remains the empty string, and `args` remains `(message, 401, '')`.
The old `json.loads(exc.message)` limitation is intentionally not fixed. Migrate
401 body consumers to `exc.response_body` and ID consumers to
`exc.response_request_id`; parse JSON only when appropriate for the response.
These new attributes apply to decoder-produced 401 errors, not manually created
AuthError instances or other status codes. Authentication, retries and exception
formatting are unchanged. Raw error bodies may contain sensitive data: the SDK
does not newly log them; callers should not log these fields indiscriminately.

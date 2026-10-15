# Populated singleton fixtures (synthetic composition, not cloud captures)

Authority: https://docs.cloudsigma.com/en/latest/networking.html#get-single-ip
and https://docs.cloudsigma.com/en/latest/networking.html#get-single-vlan
(singleton examples: owner resource_uri/uuid, subscription integer id/resource_uri,
IP nameservers/netmask/server:null; VLAN bottom_vlan_tag:null). These are the page's IP/VLAN singleton sections.

https://docs.cloudsigma.com/en/latest/acls.html#finding-what-permissions-are-granted-to-you-on-a-resource
says *each resource* has effective string permissions; owner view has empty permissions.
Its preceding resource applicability table explicitly includes IP/VLAN LIST EDIT ATTACH.
https://docs.cloudsigma.com/en/latest/acls.html#finding-what-permissions-you-have-granted-on-a-resource
specifies each resource's grantees as user references plus permissions; example user
contains email:null, resource_uri and uuid. These are resource-level grantees, NOT
ACL-object grantees (whose example has a different resource_uri shape).

IP fixture is a shared-resource view with populated effective permissions. VLAN
fixture is an owner view with two distinct synthetic grantees, neither equal to
owner. IDs/combination/counts are synthetic, derived from documented member shapes.
Tag uuid/resource_uri references follow the same ACL resource example and networking
schema's “list of individually nested resource data”; tags.html is also inspected.
Two tags exercise preservation of wire order, NOT a server-side ordering guarantee.

https://docs.cloudsigma.com/en/latest/meta.html says keys <=32 characters and values
strings. Only string metadata (including empty and Unicode) is used; no invented
boolean/numeric metadata. Subscription/owner shape is the networking embedded
reference, not an expanded subscriptions.html resource. network_interfaces.html
explains attachment but does not settle expanded IP server/VLAN servers response
member shape; populated server members remain UNRESOLVED and are not invented.

Six tests, ten SDK reads, two stored fixtures. Complete strict comparison is
supplemented by independently literal field expectations and negative oracle
controls (types, order, missing null including nested email). Ownership is decoded
object/fixture/sibling/re-read isolation, not authorization enforcement or a claim
that the SDK implements deep copying. Existing routes/errors/empty collections are
adopted, not newly claimed coverage. IPv4 only; contested IPv6 remains outside scope.

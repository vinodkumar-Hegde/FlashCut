def handler(event, context):
    attributes = (
        event
        .get(
            "request",
            {},
        )
        .get(
            "userAttributes",
            {},
        )
    )

    tenant_id = attributes.get(
        "custom:tenant_id"
    )

    if not tenant_id:
        return event

    response = event.setdefault(
        "response",
        {},
    )

    response[
        "claimsAndScopeOverrideDetails"
    ] = {
        "accessTokenGeneration": {
            "claimsToAddOrOverride": {
                "custom:tenant_id":
                    tenant_id
            }
        }
    }

    return event

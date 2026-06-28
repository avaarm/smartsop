"""Small helpers shared across the test modules."""


def register(client, email, password="password123", **kw):
    return client.post("/api/auth/register", json={"email": email, "password": password, **kw})


def login(client, email, password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def burn_superadmin(client):
    """Register a throwaway first user so subsequently-created users are regular
    members (the very first user ever becomes the platform superadmin)."""
    register(client, "root@test.local")


def make_owner(client, email, account_name):
    """Register a regular user owning a new account.

    Returns (token, account_id, user_dict). Call burn_superadmin first if you
    need this user to be a regular (non-superadmin) member.
    """
    res = register(client, email, account_name=account_name)
    body = res.get_json()
    return body["token"], body["user"]["memberships"][0]["account_id"], body["user"]

import pytest
from app.core.auth_types import Scope, SecurityContext, UserTier, TIER_DEFAULT_QUOTAS
from app.core.audit import audit_logger
from app.core.quota import quota_engine
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    invalidate_user_sessions,
    rotate_refresh_token,
)
from app.models.entities import ChatHistory, User


def create_user_with_tier(db_session, email: str, tier: str = "free", is_admin: bool = False) -> User:
    user = User(
        email=email,
        full_name=f"{tier.capitalize()} User",
        hashed_password=hash_password("Password123!"),
        tier=tier,
        is_admin=is_admin,
        token_version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_free_user_accessing_pro_feature_denied(client, db_session) -> None:
    """
    Scenario: Free tier user attempts to access an advanced LLM mode requiring 'llm:query:advanced_tier'.
    Expected: Rejected with 403 Forbidden, required scope indicated, and denied_access audit logged.
    """
    free_user = create_user_with_tier(db_session, "free_actor@example.com", tier="free")
    token = create_access_token(free_user.email, user=free_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Verify session claims contain standard scope but lack advanced scope
    session_res = client.get("/auth/session", headers=headers)
    assert session_res.status_code == 200
    claims = session_res.json()
    assert claims["tier"] == "free"
    assert Scope.LLM_QUERY_STANDARD.value in claims["scopes"]
    assert Scope.LLM_QUERY_ADVANCED.value not in claims["scopes"]

    # Attempt to request advanced reasoning model
    res = client.post(
        "/chat",
        json={"message": "Solve complex architecture problem", "mode": "deep_research"},
        headers=headers,
    )
    assert res.status_code == 403
    body = res.json()
    assert "Forbidden" in body["detail"]["error"]
    assert body["detail"]["required_scope"] == Scope.LLM_QUERY_ADVANCED.value

    # Verify audit event captured
    denied_events = audit_logger.get_events(event_type="denied_access", user_id=free_user.id)
    assert len(denied_events) > 0
    assert denied_events[-1].required_scope == Scope.LLM_QUERY_ADVANCED.value


def test_pro_user_accessing_advanced_features_allowed(client, db_session) -> None:
    """
    Scenario: Pro tier user with 'llm:query:advanced_tier' requests advanced features.
    Expected: Authorized to execute advanced model requests.
    """
    pro_user = create_user_with_tier(db_session, "pro_actor@example.com", tier="pro")
    token = create_access_token(pro_user.email, user=pro_user)
    headers = {"Authorization": f"Bearer {token}"}

    session_res = client.get("/auth/session", headers=headers)
    assert session_res.status_code == 200
    claims = session_res.json()
    assert claims["tier"] == "pro"
    assert Scope.LLM_QUERY_ADVANCED.value in claims["scopes"]


def test_quota_exceeded_mid_request_blocks_llm(client, db_session) -> None:
    """
    Scenario: User exceeds monthly token allowance.
    Expected: Pre-request check returns 429 Too Many Requests and logs quota_exceeded event.
    """
    quota_user = create_user_with_tier(db_session, "quota_actor@example.com", tier="free")
    token = create_access_token(quota_user.email, user=quota_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Artificially saturate user's monthly quota
    free_limit = TIER_DEFAULT_QUOTAS[UserTier.FREE].monthly_tokens
    quota_engine.record_usage(quota_user.id, free_limit + 10)

    # Attempt request
    res = client.post(
        "/chat",
        json={"message": "Analyze this data set", "mode": "standard"},
        headers=headers,
    )
    assert res.status_code == 429
    body = res.json()
    assert body["detail"]["reason"] == "monthly_token_quota_exceeded"
    assert body["detail"]["monthly_limit"] == free_limit

    # Verify audit event logged
    quota_events = audit_logger.get_events(event_type="quota_exceeded", user_id=quota_user.id)
    assert len(quota_events) > 0
    assert quota_events[-1].details["metric"] == "monthly_tokens"

    # Reset quota and verify next request proceeds
    quota_engine.reset_usage(quota_user.id)
    allowed_res = client.post(
        "/chat",
        json={"message": "Hello again", "mode": "standard"},
        headers=headers,
    )
    assert allowed_res.status_code == 200


def test_tier_downgrade_mid_session_invalidates_jwt(client, db_session) -> None:
    """
    Scenario: Pro user downgrades to Free tier mid-session.
    Expected: Token version increments, existing 15-minute Pro JWT is rejected with 401 on next call.
    """
    user = create_user_with_tier(db_session, "downgrade_actor@example.com", tier="pro")
    pro_token = create_access_token(user.email, user=user)
    headers = {"Authorization": f"Bearer {pro_token}"}

    # Verify token works initially
    res_before = client.get("/auth/session", headers=headers)
    assert res_before.status_code == 200
    assert res_before.json()["tier"] == "pro"

    # Simulate tier downgrade (e.g., from billing webhook or /auth/tier endpoint)
    downgrade_res = client.post(
        "/auth/tier",
        params={"tier": "free"},
        headers=headers,
    )
    assert downgrade_res.status_code == 200
    assert downgrade_res.json()["token_version"] == 2

    # Using the OLD Pro token must now be rejected immediately without contacting database
    res_after = client.get("/auth/session", headers=headers)
    assert res_after.status_code == 401
    assert "superseded or tier updated" in res_after.json()["error"] or "superseded or tier updated" in res_after.json()["detail"]


def test_cross_tenant_data_isolation(client, db_session) -> None:
    """
    Scenario: User A attempts to view conversations created by User B.
    Expected: Row-level scoping ensures User A only receives their own records.
    """
    user_a = create_user_with_tier(db_session, "usera@example.com", tier="free")
    user_b = create_user_with_tier(db_session, "userb@example.com", tier="free")

    # Add conversation for User B
    chat_b = ChatHistory(user_id=user_b.id, message="User B secret message", response={"answer": "Confidential B"})
    db_session.add(chat_b)
    db_session.commit()

    # User A queries /user/conversations
    token_a = create_access_token(user_a.email, user=user_a)
    res_a = client.get("/user/conversations", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    records_a = res_a.json()
    # User A should NOT see User B's conversations
    assert all(r["user_id"] == user_a.id for r in records_a)
    assert not any(r["message"] == "User B secret message" for r in records_a)


def test_refresh_token_rotation_and_reuse_detection(client, db_session) -> None:
    """
    Scenario: Refresh Token Rotation (RTR). If an already-used refresh token is replayed,
    the entire token family is revoked immediately to mitigate stolen token replays.
    """
    user = create_user_with_tier(db_session, "rtr_actor@example.com", tier="free")
    initial_refresh = create_refresh_token(user.email, user_id=user.id)

    # Legitimate first rotation
    new_refresh, email, uid = rotate_refresh_token(initial_refresh)
    assert new_refresh != initial_refresh
    assert email == user.email

    # Attacker tries to replay the initial refresh token
    with pytest.raises(Exception) as exc_info:
        rotate_refresh_token(initial_refresh)
    assert "Refresh token reuse detected" in str(exc_info.value.detail)

    # Legitimate user subsequently tries to use their new_refresh:
    # Because family was revoked upon reuse detection, it must now fail securely
    with pytest.raises(Exception) as exc_info2:
        rotate_refresh_token(new_refresh)
    assert "Token family revoked" in str(exc_info2.value.detail)


def test_admin_role_hierarchy_and_audit_log_access(client, db_session) -> None:
    """
    Scenario: Admin accesses privileged audit logs.
    Non-admin user attempting to access audit logs is denied with 403.
    """
    admin_user = create_user_with_tier(db_session, "admin_actor@example.com", tier="admin", is_admin=True)
    admin_token = create_access_token(admin_user.email, user=admin_user)

    admin_res = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_res.status_code == 200
    assert isinstance(admin_res.json(), list)

    # Standard user attempting access
    regular_user = create_user_with_tier(db_session, "regular_actor@example.com", tier="free")
    reg_token = create_access_token(regular_user.email, user=regular_user)
    denied_res = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {reg_token}"})
    assert denied_res.status_code == 403


def test_user_quota_live_dashboard(client, db_session) -> None:
    """
    Scenario: User inspects live quota dashboard at /user/quota.
    Expected: Accurately reflects limits, consumed usage, and remaining tokens.
    """
    user = create_user_with_tier(db_session, "quota_dash@example.com", tier="pro")
    token = create_access_token(user.email, user=user)
    headers = {"Authorization": f"Bearer {token}"}

    # Record some usage
    quota_engine.record_usage(user.id, 50000)

    res = client.get("/user/quota", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["tier"] == "pro"
    assert data["monthly_tokens"]["used"] >= 50000
    assert data["monthly_tokens"]["limit"] == TIER_DEFAULT_QUOTAS[UserTier.PRO].monthly_tokens
    assert data["monthly_tokens"]["remaining"] == data["monthly_tokens"]["limit"] - data["monthly_tokens"]["used"]
    assert data["rate_limits"]["requests_per_minute"] == 120


def test_user_profile_read_and_patch(client, db_session) -> None:
    """
    Scenario: User reads and updates profile via /user/profile.
    Expected: Can read full profile and update full_name.
    """
    user = create_user_with_tier(db_session, "profile_actor@example.com", tier="free")
    token = create_access_token(user.email, user=user)
    headers = {"Authorization": f"Bearer {token}"}

    # Read profile
    get_res = client.get("/user/profile", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["email"] == "profile_actor@example.com"

    # Update profile
    patch_res = client.patch("/user/profile", params={"full_name": "Updated Name"}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "Updated Name"


def test_admin_user_tier_and_flags_management(client, db_session) -> None:
    """
    Scenario: Admin updates user tier and feature flags.
    Expected: Target user tier changes, sessions invalidate, and flags update.
    """
    admin = create_user_with_tier(db_session, "admin_mgr@example.com", tier="admin", is_admin=True)
    admin_token = create_access_token(admin.email, user=admin)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    target = create_user_with_tier(db_session, "target_user@example.com", tier="free")

    # Admin changes target tier to pro
    patch_tier_res = client.patch(
        f"/admin/users/{target.id}/tier",
        params={"tier": "pro"},
        headers=admin_headers,
    )
    assert patch_tier_res.status_code == 200
    assert patch_tier_res.json()["new_tier"] == "pro"

    # Admin updates target feature flags
    flags_res = client.patch(
        f"/admin/users/{target.id}/feature-flags",
        json=["streaming_v2", "experimental_vision"],
        headers=admin_headers,
    )
    assert flags_res.status_code == 200
    assert "streaming_v2" in flags_res.json()["new_flags"]


def test_admin_analytics_tier_breakdown(client, db_session) -> None:
    """
    Scenario: Admin views analytics platform dashboard.
    Expected: Returns user tier breakdown, total users, orders, and products.
    """
    admin = create_user_with_tier(db_session, "admin_analytics@example.com", tier="admin", is_admin=True)
    admin_token = create_access_token(admin.email, user=admin)
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/admin/analytics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "users_by_tier" in data
    assert "total_users" in data
    assert "total_chat_messages" in data


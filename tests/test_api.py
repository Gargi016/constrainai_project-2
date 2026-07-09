import pytest
from fastapi.testclient import TestClient

import api.main as main_module
from constrainai import persistence


def make_client(tmp_path, name="test_api.db"):
    db_path = str(tmp_path / name)

    def override_get_db():
        session = persistence.get_session(db_path)
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    return TestClient(main_module.app)


def test_full_conversation_over_http(tmp_path):
    client = make_client(tmp_path)
    conv = "conv-http-1"

    turns = [
        "Budget must stay under ₹20k",
        "GPU costs at least ₹14k",
        "RAM costs at least ₹8k",
        "Reserve ₹2k for storage",
    ]
    for text in turns:
        resp = client.post(f"/conversations/{conv}/turns", json={"text": text})
        assert resp.status_code == 200
        body = resp.json()
        assert body["outcome"]["kind"] == "add", body

    # No relation constraint yet -> still SAT (nothing ties the sum to budget).
    check = client.get(f"/conversations/{conv}/check").json()
    assert check["result"] == "sat"

    # Add a 5th bound-style statement that DOES trigger UNSAT once we
    # manually insert the cross-variable relation via a raw retract/ADD
    # cycle isn't available over HTTP (relations aren't NL-extractable in
    # this MVP) -- so directly hit the constraints listing to confirm state,
    # then use the constraint-store API's building blocks by adding the
    # relation the same way demo.py does, through a direct DB round trip.
    from constrainai.constraints import Constraint, ConstraintKind, Operator
    from constrainai.expressions import var, add as expr_add

    session = persistence.get_session(str(tmp_path / "test_api.db"))
    store = persistence.load_store(session, conv)
    store.add(Constraint(
        kind=ConstraintKind.RELATION,
        lhs=expr_add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE, rhs=var("budget"),
        source_turn=5, source_text="(implicit) gpu + ram + storage <= budget",
    ))
    persistence.save_store(session, conv, store)
    session.close()

    check2 = client.get(f"/conversations/{conv}/check").json()
    assert check2["result"] == "unsat"
    assert len(check2["minimal_core"]) == 5
    assert check2["minimal_core_verified"] is True

    repairs = client.get(f"/conversations/{conv}/repairs").json()
    assert repairs["repairs_needed"] is True
    budget_repair = next(r for r in repairs["repairs"] if r["variable_name"] == "budget")
    assert budget_repair["direction"] == "increase"
    assert budget_repair["new_value"] == pytest.approx(24000)
    assert budget_repair["verified_sat"] is True

    # Resolve via retraction over HTTP.
    constraints = client.get(f"/conversations/{conv}/constraints", params={"status": "active"}).json()
    ram_constraint = next(c for c in constraints if c["lhs"].get("name") == "ram_cost" and c["kind"] == "bound")
    retract_resp = client.post(f"/conversations/{conv}/constraints/{ram_constraint['id']}/retract")
    assert retract_resp.status_code == 200
    assert retract_resp.json()["sat_status"]["result"] == "sat"

    # Final NL turn: revise-style message on a now-fresh conversation to
    # confirm the revise pathway also works cleanly over HTTP.
    conv2 = "conv-http-2"
    client.post(f"/conversations/{conv2}/turns", json={"text": "Budget must stay under ₹20k"})
    revise_resp = client.post(f"/conversations/{conv2}/turns", json={"text": "Actually increase budget to ₹27k"})
    assert revise_resp.status_code == 200
    assert revise_resp.json()["outcome"]["kind"] == "revise"


def test_retract_unknown_constraint_returns_404(tmp_path):
    client = make_client(tmp_path, "test_api_404.db")
    resp = client.post("/conversations/conv-x/constraints/does-not-exist/retract")
    assert resp.status_code == 404


def test_persistence_across_client_instances(tmp_path):
    """Confirms conversation state genuinely persists to disk, not just
    in-process memory, by tearing down and recreating the TestClient."""
    db_name = "test_api_persist.db"
    client1 = make_client(tmp_path, db_name)
    client1.post(
        "/conversations/conv-persist/turns",
        json={"text": "Budget must stay under ₹20k"},
    )
    del client1

    client2 = make_client(tmp_path, db_name)
    constraints = client2.get(
        "/conversations/conv-persist/constraints", params={"status": "active"}
    ).json()
    assert len(constraints) == 1
    assert constraints[0]["source_text"] == "Budget must stay under ₹20k"


def test_list_and_delete_conversation(tmp_path):
    client = make_client(tmp_path, "test_api_list.db")
    client.post("/conversations/conv-a/turns", json={"text": "Budget must stay under ₹20k"})
    client.post("/conversations/conv-b/turns", json={"text": "GPU costs at least ₹14k"})

    ids = client.get("/conversations").json()["conversation_ids"]
    assert "conv-a" in ids and "conv-b" in ids

    del_resp = client.delete("/conversations/conv-a")
    assert del_resp.status_code == 200

    remaining = client.get("/conversations/conv-a/constraints", params={"status": "all"}).json()
    assert remaining == []


def test_invalid_status_query_param_returns_400(tmp_path):
    client = make_client(tmp_path, "test_api_badstatus.db")
    client.post("/conversations/conv-z/turns", json={"text": "Budget must stay under ₹20k"})
    resp = client.get("/conversations/conv-z/constraints", params={"status": "nonsense"})
    assert resp.status_code == 400


def test_relation_endpoint_triggers_conflict_entirely_over_http(tmp_path):
    """
    This is the scenario that previously required dropping to a direct DB
    round trip (see test_full_conversation_over_http): now the relation
    constraint can be added through a dedicated endpoint, so the whole
    UNSAT -> minimal core -> repair flow is reachable purely via HTTP,
    exactly as the frontend's "add relation" form will call it.
    """
    client = make_client(tmp_path, "test_api_relation.db")
    conv = "conv-relation"

    for text in [
        "Budget must stay under ₹20k",
        "GPU costs at least ₹14k",
        "RAM costs at least ₹8k",
        "Reserve ₹2k for storage",
    ]:
        resp = client.post(f"/conversations/{conv}/turns", json={"text": text})
        assert resp.status_code == 200
        assert resp.json()["sat_status"]["result"] == "sat"  # not tied together yet

    relation_resp = client.post(
        f"/conversations/{conv}/constraints/relation",
        json={
            "lhs_variables": ["gpu_cost", "ram_cost", "storage_cost"],
            "operator": "<=",
            "rhs_variables": ["budget"],
        },
    )
    assert relation_resp.status_code == 200
    body = relation_resp.json()
    assert body["constraint"]["kind"] == "relation"
    assert body["sat_status"]["result"] == "unsat"

    check = client.get(f"/conversations/{conv}/check").json()
    assert check["result"] == "unsat"
    assert len(check["minimal_core"]) == 5

    repairs = client.get(f"/conversations/{conv}/repairs").json()
    assert repairs["repairs_needed"] is True
    assert len(repairs["repairs"]) == 4
    assert all(r["verified_sat"] for r in repairs["repairs"])


def test_relation_endpoint_rejects_invalid_operator(tmp_path):
    client = make_client(tmp_path, "test_api_relation_bad_op.db")
    resp = client.post(
        "/conversations/conv-bad/constraints/relation",
        json={"lhs_variables": ["a"], "operator": "==", "rhs_variables": ["b"]},
    )
    assert resp.status_code == 422  # pydantic validation error


def test_relation_endpoint_rejects_empty_variable_list(tmp_path):
    client = make_client(tmp_path, "test_api_relation_empty.db")
    resp = client.post(
        "/conversations/conv-empty/constraints/relation",
        json={"lhs_variables": [], "operator": "<=", "rhs_variables": ["b"]},
    )
    assert resp.status_code == 422

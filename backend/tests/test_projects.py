def create_project(client, headers, name="Demo"):
    r = client.post("/projects", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_requires_login(client):
    assert client.get("/projects").status_code == 401


def test_project_crud(client, auth):
    p = create_project(client, auth)
    assert [x["id"] for x in client.get("/projects", headers=auth).json()] == [p["id"]]

    r = client.put(f"/projects/{p['id']}", json={"name": "Renamed"}, headers=auth)
    assert r.status_code == 200 and r.json()["name"] == "Renamed"

    assert client.delete(f"/projects/{p['id']}", headers=auth).status_code == 204
    assert client.get(f"/projects/{p['id']}", headers=auth).status_code == 404


def test_empty_name_rejected(client, auth):
    r = client.post("/projects", json={"name": "   "}, headers=auth)
    assert r.status_code == 400


def test_file_crud(client, auth):
    p = create_project(client, auth)
    base = f"/projects/{p['id']}/files"

    r = client.post(
        base,
        json={"filename": "main.py", "language": "python", "content": "print(1)"},
        headers=auth,
    )
    assert r.status_code == 201
    f = r.json()

    r = client.put(f"{base}/{f['id']}", json={"content": "print(2)"}, headers=auth)
    assert r.status_code == 200 and r.json()["content"] == "print(2)"

    assert len(client.get(base, headers=auth).json()) == 1
    assert client.delete(f"{base}/{f['id']}", headers=auth).status_code == 204
    assert client.get(f"{base}/{f['id']}", headers=auth).status_code == 404


def test_users_cannot_see_each_others_projects(client, auth, other_auth):
    p = create_project(client, auth)
    pid = p["id"]

    assert client.get(f"/projects/{pid}", headers=other_auth).status_code == 404
    assert client.get(f"/projects/{pid}/files", headers=other_auth).status_code == 404
    assert client.put(f"/projects/{pid}", json={"name": "x"}, headers=other_auth).status_code == 404
    assert client.delete(f"/projects/{pid}", headers=other_auth).status_code == 404
    assert client.get("/projects", headers=other_auth).json() == []
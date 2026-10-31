import base64

import app as backend


def test_face_detection_accepts_a_camera_jpeg():
    encoded_ok, image = backend.cv2.imencode(
        ".jpg", backend.np.zeros((48, 64, 3), dtype=backend.np.uint8)
    )
    assert encoded_ok
    image_data = base64.b64encode(image).decode("ascii")

    response = backend.app.test_client().post(
        "/api/detect_faces",
        json={"image": f"data:image/jpeg;base64,{image_data}"},
    )

    assert response.status_code == 200
    assert response.json["width"] == 64
    assert response.json["height"] == 48
    assert response.json["faces"] == []


def test_frontend_assets_are_served_with_matching_paths():
    client = backend.app.test_client()

    home = client.get("/")
    assert home.status_code == 200
    assert b'href="./style.css"' in home.data
    assert b'src="./index.js"' in home.data

    stylesheet = client.get("/style.css")
    assert stylesheet.status_code == 200
    assert b"body" in stylesheet.data

    script = client.get("/index.js")
    assert script.status_code == 200
    assert script.mimetype == "text/javascript"

    config = client.get("/config.js")
    assert config.status_code == 200
    assert "window.KAREN_API_ENABLED = true;" in config.get_data(as_text=True)


def test_news_endpoint_returns_structured_current_affairs(monkeypatch):
    expected = {
        "date": "2026-10-30",
        "date_label": "Friday, 30 October 2026",
        "total": 1,
        "categories": [
            {
                "key": "national",
                "label": "National · India",
                "articles": [{"title": "India news", "source": "Test Wire"}],
            }
        ],
        "message": "",
        "summary": "Current affairs for 30 October 2026. Found 1 headline(s).",
        "feeds": [],
    }
    monkeypatch.setattr(
        backend,
        "fetch_current_affairs",
        lambda query, date_override=None: (expected, 200),
    )

    response = backend.app.test_client().post(
        "/api/news",
        json={
            "query": "30 October 2026 current affairs international and national India",
            "date": "2026-10-30",
        },
    )

    assert response.status_code == 200
    assert response.json["date"] == "2026-10-30"
    assert response.json["categories"][0]["articles"][0]["title"] == "India news"


def test_news_endpoint_rejects_empty_query():
    response = backend.app.test_client().post("/api/news", json={"query": "  "})
    assert response.status_code == 400
    assert response.json["error"] is True
class TestMetrics:
    def test_placeholder(self, client):  # This is just here to keep coverage happy
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.data.decode("UTF-8") == "OK"

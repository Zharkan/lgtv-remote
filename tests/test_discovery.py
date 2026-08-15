from lgtv_remote.discovery import parse_ip_neigh_line, parse_ssdp_response


class TestParseSsdpResponse:
    def test_basic(self):
        raw = (
            "HTTP/1.1 200 OK\r\n"
            "CACHE-CONTROL: max-age=1800\r\n"
            "LOCATION: http://192.168.10.42:1780/\r\n"
            "SERVER: WebOS/1.0 UPnP/1.0\r\n"
            "ST: urn:lge-com:service:webos-second-screen:1\r\n"
            "\r\n"
        )
        headers = parse_ssdp_response(raw)
        assert headers["LOCATION"] == "http://192.168.10.42:1780/"
        assert headers["ST"] == "urn:lge-com:service:webos-second-screen:1"
        assert "WebOS" in headers["SERVER"]

    def test_empty(self):
        assert parse_ssdp_response("") == {}

    def test_no_http_line_in_result(self):
        raw = "HTTP/1.1 200 OK\r\nFoo: bar\r\n"
        headers = parse_ssdp_response(raw)
        assert "HTTP/1.1 200 OK" not in headers
        assert headers["FOO"] == "bar"


class TestParseIpNeighLine:
    def test_reachable(self):
        line = "192.168.10.42 dev enp3s0 lladdr f8:01:b4:a5:d8:b2 REACHABLE"
        result = parse_ip_neigh_line(line)
        assert result == ("192.168.10.42", "f8:01:b4:a5:d8:b2")

    def test_stale(self):
        line = "192.168.10.42 dev enp3s0 lladdr f8:01:b4:a5:d8:b2 STALE"
        result = parse_ip_neigh_line(line)
        assert result == ("192.168.10.42", "f8:01:b4:a5:d8:b2")

    def test_incomplete(self):
        line = "192.168.10.42 dev enp3s0 INCOMPLETE"
        result = parse_ip_neigh_line(line)
        assert result is None

    def test_empty(self):
        assert parse_ip_neigh_line("") is None

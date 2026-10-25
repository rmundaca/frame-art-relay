import io
import json
import unittest

import httpx
from PIL import Image as PILImage

from app.services import source_icloud
from app.services.source_icloud import ICloudError

TOKEN = "B0z5qAGN1JIFd3y"
URL = f"https://www.icloud.com/sharedalbum/#{TOKEN}"


def jpeg_bytes():
    buf = io.BytesIO()
    PILImage.new("RGB", (32, 18), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


def photo(guid, checksum, video=False):
    return {
        "photoGuid": guid,
        "mediaAssetType": "video" if video else None,
        "derivatives": {
            "342": {"checksum": f"small-{checksum}", "width": "456", "height": "342"},
            "2048": {"checksum": checksum, "width": "2730", "height": "2048"},
        },
    }


class FakeICloud:
    def __init__(self, photos, location="cvws.icloud-content.com"):
        self.photos = photos
        self.location = location
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        host, path = request.url.host, request.url.path
        if path.endswith("/webstream"):
            if host == "p61-sharedstreams.icloud.com":
                return httpx.Response(330, json={"X-Apple-MMe-Host": "p99-sharedstreams.icloud.com"})
            return httpx.Response(200, json={"streamName": "Viaje", "photos": self.photos})
        if path.endswith("/webasseturls"):
            guids = json.loads(request.content)["photoGuids"]
            items = {p["derivatives"]["2048"]["checksum"]: {"url_location": self.location,
                                                            "url_path": f"/S/{p['photoGuid']}.jpg"}
                     for p in self.photos if p["photoGuid"] in guids}
            return httpx.Response(200, json={"items": items})
        if path.startswith("/S/"):
            return httpx.Response(200, content=jpeg_bytes())
        return httpx.Response(404)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handler))


class ICloudTest(unittest.TestCase):
    def test_parse_token(self):
        self.assertEqual(source_icloud.parse_token(URL), TOKEN)
        self.assertEqual(source_icloud.parse_token(f"https://www.icloud.com/sharedalbum/es-es/#{TOKEN};x"), TOKEN)
        for bad in ("", f"http://www.icloud.com/sharedalbum/#{TOKEN}", f"https://evil.com/sharedalbum/#{TOKEN}",
                    "https://www.icloud.com/sharedalbum/"):
            with self.assertRaises(ICloudError):
                source_icloud.parse_token(bad)

    def test_partition(self):
        # "0z" en base 62 = 61
        self.assertTrue(source_icloud.base_url(TOKEN).startswith("https://p61-sharedstreams.icloud.com/"))
        self.assertTrue(source_icloud.base_url("Ab" + TOKEN[2:]).startswith("https://p37-"))

    def test_refresh_follows_redirect_and_downloads_new_only(self):
        fake = FakeICloud([photo("G1", "c1"), photo("G2", "c2"), photo("V1", "cv", video=True)])
        with fake.client() as client:
            name, found = source_icloud.refresh(9001, URL, client)
        self.assertEqual(name, "Viaje")
        self.assertEqual([k for k, _, _ in found], ["G1.jpg", "G2.jpg"])
        self.assertTrue(any("p99-sharedstreams" in u for u in fake.requests))
        self.assertTrue(source_icloud.file_path(9001, "G1.jpg").is_file())

        fake.photos = [photo("G2", "c2"), photo("G3", "c3")]
        fake.requests.clear()
        with fake.client() as client:
            _, found = source_icloud.refresh(9001, URL, client)
        self.assertEqual([k for k, _, _ in found], ["G2.jpg", "G3.jpg"])
        self.assertEqual([u for u in fake.requests if "/S/" in u], ["https://cvws.icloud-content.com/S/G3.jpg"])
        with self.assertRaises(ValueError):
            source_icloud.file_path(9001, "G1.jpg")
        source_icloud.remove_cache(9001)

    def test_rejects_download_hosts_outside_apple(self):
        fake = FakeICloud([photo("G1", "c1")], location="evil.example.com")
        with fake.client() as client, self.assertRaises(ICloudError) as ctx:
            source_icloud.refresh(9002, URL, client)
        self.assertEqual(str(ctx.exception), "icloud_unreachable")
        self.assertFalse(any("evil" in u for u in fake.requests))
        source_icloud.remove_cache(9002)

    def test_private_album(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
        with client, self.assertRaises(ICloudError) as ctx:
            source_icloud.fetch_stream(client, TOKEN)
        self.assertEqual(str(ctx.exception), "icloud_album_not_public")

    def test_file_path_rejects_traversal(self):
        with self.assertRaises(ValueError):
            source_icloud.file_path(9001, "../app.db")


if __name__ == "__main__":
    unittest.main()

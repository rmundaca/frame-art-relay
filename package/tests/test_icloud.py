import io
import json
import unittest
from unittest.mock import patch

import httpx
from PIL import Image as PILImage

from app.services import source_icloud
from app.services.source_icloud import ICloudError

TOKEN = "B0z5qAGN1JIFd3y"
URL = f"https://www.icloud.com/sharedalbum/#{TOKEN}"
CLOUD_TOKEN = "06aExamplePublicAlbumLink"
CLOUD_URL = f"https://photos.icloud.com/shared/album/{CLOUD_TOKEN}"


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


class FakeCloud:
    def __init__(self):
        self.requests = []
        self.private = False
        self.partition = "https://p142-ckdatabasews.icloud.com:443"
        self.location = "cvws-h2.icloud-content.com"
        self.total = 3
        self.empty_page = False
        self.jpeg = True
        self.video_ranks = set()
        self.hidden_ranks = set()

    def handler(self, request):
        self.requests.append(request)
        if request.url.host == self.location:
            return httpx.Response(200, content=jpeg_bytes())
        body = json.loads(request.content)
        if request.url.path.endswith("/resolve"):
            result = {"requireAppleLogin": self.private,
                      "anonymousPublicAccess": {"token": "temporary-token", "databasePartition": self.partition},
                      "zoneID": {"zoneName": "test-zone", "ownerRecordName": "test-owner"},
                      "share": {"fields": {"cloudkit.title": {"value": "Cloud album"}}}}
            return httpx.Response(200, json={"results": [result]})
        if request.url.path.endswith("/query"):
            assert request.url.params["remapEnums"] == "true"
            assert request.url.params["publicAccessAuthToken"] == "temporary-token"
            if body["query"]["recordType"] == "HyperionIndexCountLookup":
                return httpx.Response(200, json={"records": [
                    {"fields": {"itemCount": {"value": self.total}}}]})
            rank = body["query"]["filterBy"][1]["fieldValue"]["value"]
            records = []
            if not self.empty_page:
                # Una foto por pagina aunque se hayan pedido mas resultados.
                fields = {"dataClassType": {"value": 2 if rank in self.video_ranks else 1}}
                for prefix, width in (("resJPEGThumb", 480), ("resJPEGMed", 2048)):
                    fields.update({
                        prefix + "FileType": {"value": "public.jpeg" if self.jpeg else "public.heic"},
                        prefix + "Width": {"value": width}, prefix + "Height": {"value": width},
                        prefix + "Res": {"value": {"downloadURL":
                            f"https://{self.location}/{rank}/{width}.jpg"}},
                    })
                records = [
                    {"recordType": "CPLMaster", "recordName": f"master/{rank}", "fields": fields},
                    {"recordType": "CPLAsset", "recordName": f"asset/{rank}", "fields": {
                        "isHidden": {"value": int(rank in self.hidden_ranks)},
                        "masterRef": {"value": {"recordName": f"master/{rank}"}}}},
                ]
            return httpx.Response(200, json={"records": records})
        return httpx.Response(404)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handler))


class CloudICloudTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCloud()
        self.source_id = 9010
        self.addCleanup(source_icloud.remove_cache, self.source_id)

    def test_parse_and_normalize_both_formats(self):
        self.assertEqual(source_icloud.parse_token(CLOUD_URL), CLOUD_TOKEN)
        self.assertEqual(source_icloud.canonical_url(f" {CLOUD_URL}/?tracking=x "), CLOUD_URL)
        self.assertEqual(source_icloud.canonical_url(f"https://icloud.com/sharedalbum/en/#{TOKEN};x"), URL)
        for url in (CLOUD_URL.replace("https:", "http:"),
                    CLOUD_URL.replace("photos.icloud.com", "photos.icloud.com.evil.example"),
                    CLOUD_URL + "/extra", "https://photos.icloud.com/shared/album/",
                    "https://[invalid/shared/album/example", CLOUD_URL.replace("/album/", "/other/")):
            with self.subTest(url=url), self.assertRaisesRegex(ICloudError, "invalid_icloud_url"):
                source_icloud.parse_token(url)

    def test_metadata_does_not_download(self):
        with self.fake.client() as client:
            self.assertEqual(source_icloud.album_name(client, CLOUD_URL), "Cloud album")
        self.assertEqual(len(self.fake.requests), 1)

    def test_refresh_paginates_and_reuses_cache(self):
        with self.fake.client() as client:
            name, found = source_icloud.refresh(self.source_id, CLOUD_URL, client)
        self.assertEqual(name, "Cloud album")
        self.assertEqual(len(found), 3)
        for key, _, _ in found:
            self.assertTrue(source_icloud.file_path(self.source_id, key).is_file())
        downloads = [r.url.path for r in self.fake.requests if r.url.host == self.fake.location]
        self.assertEqual(downloads, [f"/{rank}/2048.jpg" for rank in range(3)])
        self.fake.requests.clear()
        self.fake.total = 2
        with self.fake.client() as client:
            _, found = source_icloud.refresh(self.source_id, CLOUD_URL, client)
        self.assertEqual(len(found), 2)
        self.assertFalse(any(r.url.host == self.fake.location for r in self.fake.requests))
        self.assertEqual(len(list(source_icloud.cache_dir(self.source_id).iterdir())), 2)

    def test_limit(self):
        with patch.dict(source_icloud.settings, {"icloud": {"max_photos": 1}}):
            with self.fake.client() as client:
                _, found = source_icloud.refresh(self.source_id, CLOUD_URL, client)
        self.assertEqual(len(found), 1)

    def test_skips_videos_and_hidden_images(self):
        self.fake.video_ranks = {0}
        self.fake.hidden_ranks = {1}
        with self.fake.client() as client:
            _, found = source_icloud.refresh(self.source_id, CLOUD_URL, client)
        self.assertEqual(len(found), 1)
        downloads = [r.url.path for r in self.fake.requests if r.url.host == self.fake.location]
        self.assertEqual(downloads, ["/2/2048.jpg"])

    def test_empty_album(self):
        self.fake.total = 0
        with self.fake.client() as client:
            _, found = source_icloud.refresh(self.source_id, CLOUD_URL, client)
        self.assertEqual(found, [])

    def test_private_album(self):
        self.fake.private = True
        with self.fake.client() as client, self.assertRaisesRegex(ICloudError, "icloud_album_not_public"):
            source_icloud.album_name(client, CLOUD_URL)

    def test_rejects_non_apple_partition_and_download(self):
        for attribute in ("partition", "location"):
            with self.subTest(attribute=attribute):
                fake = FakeCloud()
                setattr(fake, attribute, "https://evil.example" if attribute == "partition" else "evil.example")
                with fake.client() as client, self.assertRaisesRegex(ICloudError, "icloud_unreachable"):
                    source_icloud.refresh(self.source_id, CLOUD_URL, client)
                self.assertFalse(any(r.url.host == "evil.example" for r in fake.requests))

    def test_incomplete_or_unsupported_results_do_not_clear_cache(self):
        folder = source_icloud.cache_dir(self.source_id)
        folder.mkdir(parents=True, exist_ok=True)
        existing = folder / "existing.jpg"
        existing.write_bytes(jpeg_bytes())
        for attribute in ("empty_page", "jpeg"):
            fake = FakeCloud()
            setattr(fake, attribute, attribute == "empty_page")
            with self.subTest(attribute=attribute), fake.client() as client:
                with self.assertRaisesRegex(ICloudError, "icloud_unreachable"):
                    source_icloud.refresh(self.source_id, CLOUD_URL, client)
            self.assertTrue(existing.exists())

    def test_malformed_and_failed_responses(self):
        responses = (httpx.Response(200, text="not json"), httpx.Response(200, json={}),
                     httpx.Response(200, json={"results": []}), httpx.Response(500),
                     httpx.Response(200, json={"results": [None]}),
                     httpx.Response(200, json={"serverErrorCode": "BAD_REQUEST"}))
        for response in responses:
            with self.subTest(response=response), httpx.Client(
                    transport=httpx.MockTransport(lambda r: response)) as client:
                with self.assertRaisesRegex(ICloudError, "icloud_unreachable"):
                    source_icloud.album_name(client, CLOUD_URL)

    def test_expired_link_and_transport_error(self):
        for status in (200, 403, 404):
            with self.subTest(status=status), httpx.Client(transport=httpx.MockTransport(
                    lambda r: httpx.Response(status, json={"serverErrorCode": "NOT_FOUND"}))) as client:
                with self.assertRaisesRegex(ICloudError, "icloud_album_not_public"):
                    source_icloud.album_name(client, CLOUD_URL)

        def timeout(request):
            raise httpx.ReadTimeout("timed out", request=request)

        with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
            with self.assertRaisesRegex(ICloudError, "icloud_unreachable"):
                source_icloud.album_name(client, CLOUD_URL)


if __name__ == "__main__":
    unittest.main()

import unittest
import types
import hmac
import hashlib


class _FakeRedis:
    def __init__(self):
        self._set = set()
    def set(self, key, value, nx=False, ex=None):
        if nx:
            if key in self._set:
                return False
            self._set.add(key)
            return True
        self._set.add(key)
        return True


class DeviceSignatureTests(unittest.TestCase):
    def test_verify_device_signature_ok(self):
        import cloud_server.server.app as appmod

        appmod.redis_client = _FakeRedis()
        device_id = 'dev1'
        token = 'a' * 64

        payload = b'{"device_id":"dev1"}'
        body_hash = hashlib.sha256(payload).hexdigest()
        ts = str(int(appmod.datetime.now().timestamp()))
        nonce = 'n1'
        msg = f"{device_id}|{ts}|{nonce}|{body_hash}".encode('utf-8')
        sig = hmac.new(token.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        with appmod.app.test_request_context(
            '/api/device/heartbeat',
            method='POST',
            data=payload,
            headers={
                'X-Device-Id': device_id,
                'X-Device-Timestamp': ts,
                'X-Device-Nonce': nonce,
                'X-Device-Signature': sig,
                'Content-Type': 'application/json'
            }
        ):
            err = appmod._verify_device_signature(device_id, token)
            self.assertIsNone(err)

    def test_verify_device_signature_replay(self):
        import cloud_server.server.app as appmod

        fake = _FakeRedis()
        appmod.redis_client = fake
        device_id = 'dev1'
        token = 'a' * 64

        payload = b'{}'
        body_hash = hashlib.sha256(payload).hexdigest()
        ts = str(int(appmod.datetime.now().timestamp()))
        nonce = 'same'
        msg = f"{device_id}|{ts}|{nonce}|{body_hash}".encode('utf-8')
        sig = hmac.new(token.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        headers = {
            'X-Device-Id': device_id,
            'X-Device-Timestamp': ts,
            'X-Device-Nonce': nonce,
            'X-Device-Signature': sig
        }

        with appmod.app.test_request_context('/x', method='POST', data=payload, headers=headers):
            self.assertIsNone(appmod._verify_device_signature(device_id, token))
        with appmod.app.test_request_context('/x', method='POST', data=payload, headers=headers):
            self.assertEqual(appmod._verify_device_signature(device_id, token), '设备请求重复')


if __name__ == '__main__':
    unittest.main()


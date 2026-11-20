import json
import unittest

import server


class ChatRequestLimitTests(unittest.TestCase):
    def test_chat_request_limit_is_192000_bytes(self):
        self.assertEqual(server.CHAT_REQUEST_MAX_BYTES, 192000)

    def test_ten_maximum_length_unicode_messages_fit(self):
        messages = [
            {"role": "user", "content": "\U0001F600" * 4000}
            for _ in range(10)
        ]
        payload = json.dumps(
            {"messages": messages}, ensure_ascii=False
        ).encode("utf-8")

        self.assertGreater(len(payload), 16000)
        self.assertLessEqual(len(payload), server.CHAT_REQUEST_MAX_BYTES)

    def test_request_limit_has_headroom_over_old_limit(self):
        self.assertGreater(server.CHAT_REQUEST_MAX_BYTES, 16000)


if __name__ == "__main__":
    unittest.main()

"""Exercise the real Flask boundary without external data or Telegram calls."""
import contextlib
import io
import threading
import unittest
from unittest.mock import Mock, patch

import requests
import main


class HttpSecurityTests(unittest.TestCase):
    def setUp(self):
        main.app.config['TESTING'] = True
        self.client = main.app.test_client()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for key, value in {
            'JOB_TOKEN': 'synthetic-job-token-' + 'x' * 32,
            'BOT_TOKEN': 'synthetic-bot-token',
            'CHAT_ID': 'synthetic-chat',
            '_last_send_attempt': None,
            '_send_lock': threading.Lock(),
        }.items():
            self.stack.enter_context(patch.object(main, key, value))
        self.get = self.stack.enter_context(patch.object(requests, 'get', side_effect=AssertionError('No live GET')))
        self.post = self.stack.enter_context(patch.object(requests, 'post'))
        self.scores = self.stack.enter_context(patch.object(main, 'get_fng_scores', return_value=(50, 50)))
        self.stack.enter_context(patch.object(main, 'get_market_data', return_value={}))
        self.stack.enter_context(patch.object(main, 'get_kospi_investor_data', return_value=None))
        self.response = Mock()
        self.response.json.return_value = {'ok': True}
        self.post.return_value = self.response

    def send(self, token=None):
        return self.client.post('/send', headers={'X-JOB-TOKEN': token if token is not None else main.JOB_TOKEN})

    def assert_no_calls(self):
        self.scores.assert_not_called()
        self.get.assert_not_called()
        self.post.assert_not_called()

    def test_health_and_old_routes_have_no_side_effects(self):
        for method, path, status in [('get', '/', 200), ('get', '/healthz', 200), ('head', '/', 200), ('post', '/', 405), ('get', '/send', 405)]:
            with self.subTest(method=method, path=path):
                self.assertEqual(getattr(self.client, method)(path).status_code, status)
        self.assert_no_calls()

    def test_missing_wrong_unicode_and_oversized_tokens_rejected(self):
        for token in ['', 'wrong', '잘못된인증', 'x' * 300]:
            with self.subTest(token_length=len(token)):
                self.assertEqual(self.send(token).status_code, 401)
        self.assert_no_calls()

    def test_query_token_is_not_authentication(self):
        self.assertEqual(self.client.post('/send?token=' + main.JOB_TOKEN).status_code, 401)
        self.assert_no_calls()

    def test_absent_or_weak_configuration_fails_closed(self):
        for value in [None, '', 'short']:
            with patch.object(main, 'JOB_TOKEN', value):
                self.assertEqual(self.send('wrong').status_code, 503)
        self.assert_no_calls()

    def test_missing_telegram_configuration_fails_before_collection(self):
        for key in ['BOT_TOKEN', 'CHAT_ID']:
            with patch.object(main, key, None):
                self.assertEqual(self.send().status_code, 503)
        self.assert_no_calls()

    def test_authenticated_send_checks_telegram_success(self):
        self.assertEqual(self.send().status_code, 200)
        self.post.assert_called_once()
        self.response.raise_for_status.assert_called_once()
        self.assertEqual(self.post.call_args.kwargs['json']['chat_id'], main.CHAT_ID)

    def test_telegram_false_is_failure(self):
        self.response.json.return_value = {'ok': False, 'description': 'synthetic-bot-token'}
        self.assertEqual(self.send().status_code, 502)

    def test_exception_url_and_telegram_body_not_in_response_or_logs(self):
        secret = main.BOT_TOKEN
        self.post.side_effect = requests.ConnectionError('https://api.telegram.org/bot' + secret + '/sendMessage')
        stdout = io.StringIO()
        with self.assertLogs(main.app.logger, level='ERROR') as logs, contextlib.redirect_stdout(stdout):
            result = self.send()
        self.assertEqual(result.status_code, 502)
        self.assertNotIn(secret, result.get_data(as_text=True) + ''.join(logs.output) + stdout.getvalue())
        self.assertNotIn('api.telegram.org', ''.join(logs.output))
        self.assertFalse(main._send_lock.locked())

    def test_http_error_does_not_claim_success(self):
        self.response.raise_for_status.side_effect = requests.HTTPError('synthetic-bot-token')
        self.assertEqual(self.send().status_code, 502)

    def test_repeated_send_is_throttled_then_allowed_after_cooldown(self):
        with patch.object(main.time, 'monotonic', side_effect=[100, 101, 161]):
            self.assertEqual(self.send().status_code, 200)
            limited = self.send()
            self.assertEqual(limited.status_code, 429)
            self.assertIn('Retry-After', limited.headers)
            self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.post.call_count, 2)

    def test_concurrent_send_is_rejected_before_collection(self):
        main._send_lock.acquire()
        try:
            self.assertEqual(self.send().status_code, 429)
            self.assert_no_calls()
        finally:
            main._send_lock.release()

    def test_ambiguous_delivery_failure_still_throttles_retry(self):
        self.post.side_effect = requests.Timeout('synthetic-bot-token')
        self.assertEqual(self.send().status_code, 502)
        self.assertEqual(self.send().status_code, 429)
        self.post.assert_called_once()


if __name__ == '__main__':
    unittest.main()

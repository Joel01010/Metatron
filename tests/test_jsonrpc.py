import sys, time, unittest
from pathlib import Path
from metatron.jsonrpc import JsonRpcProcess


class RpcTests(unittest.TestCase):
    def test_rpc_events_and_server_requests_are_bounded(self):
        p = JsonRpcProcess([sys.executable, str(Path(__file__).with_name('mock_rpc_worker.py'))])
        try:
            p.request('initialize', {})
            self.assertEqual(p.request('thread/start', {})['thread']['id'], 'th1')
            self.assertEqual(p.request('turn/start', {})['turn']['id'], 'tu1')
            deadline=time.time()+1
            while time.time()<deadline and not p.server_requests(): time.sleep(.01)
            self.assertEqual(p.events()[0]['method'], 'item/agentMessage/delta')
            self.assertEqual(p.server_requests()[0]['id'], 999)
        finally:
            p.stop()


if __name__=='__main__': unittest.main()

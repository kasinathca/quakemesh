from simulator.transports import AwsIotTransport


class FakeFuture:
    def __init__(self):
        self.timeout = None

    def result(self, *, timeout):
        self.timeout = timeout
        return "done"


def test_wait_supports_bare_future_and_sdk_tuple_shapes():
    bare = FakeFuture()
    paired = FakeFuture()
    assert AwsIotTransport._wait(bare, 3) == "done"
    assert bare.timeout == 3
    assert AwsIotTransport._wait((paired, 42), 7) == "done"
    assert paired.timeout == 7

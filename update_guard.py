"""Reserve an idle desktop service before replacing the application bundle."""
from development import DevelopmentRefresh


class UpdateGuard:
    def __init__(self):
        self.reserved = False

    def status(self, engine, prepare=False):
        with engine.lock:
            busy = DevelopmentRefresh.busy(engine)
            if prepare and not busy:
                self.reserved = True
            return {'busy': busy, 'ready': self.reserved and not busy}

    def cancel(self):
        self.reserved = False
        return {'busy': True, 'ready': False}

    def check(self, path):
        # The native transport can drain while quitting; new user requests cannot
        # start a recording between the idle check and replacement of the bundle.
        if self.reserved and path not in ('updates/status', 'updates/prepare', 'updates/cancel', 'bluetooth_native', 'state'):
            raise ValueError('Bandstand is installing an update. Please wait for it to reopen.')

import threading
import unittest
from types import SimpleNamespace
from update_guard import UpdateGuard


class UpdateSafetyTests(unittest.TestCase):
    def engine(self):
        return SimpleNamespace(lock=threading.RLock(), session=None,
            typing=SimpleNamespace(running=False, fitting=False),
            personal=SimpleNamespace(current=None), developer=SimpleNamespace(current=None))

    def test_each_recording_and_training_mode_prevents_installation(self):
        for mode in ('erp', 'typing', 'training', 'personal', 'developer'):
            with self.subTest(mode=mode):
                engine = self.engine()
                if mode == 'erp': engine.session = {'running': True}
                if mode == 'typing': engine.typing.running = True
                if mode == 'training': engine.typing.fitting = True
                if mode == 'personal': engine.personal.current = {'active': True}
                if mode == 'developer': engine.developer.current = {'active': True}
                guard = UpdateGuard()
                self.assertEqual(guard.status(engine, prepare=True), {'busy': True, 'ready': False})
                guard.check('start')

    def test_idle_reservation_blocks_late_start_and_cancel_restores_access(self):
        guard = UpdateGuard()
        self.assertTrue(guard.status(self.engine(), prepare=True)['ready'])
        for path in ('start', 'personal/start', 'typing/start', 'developer/start', 'speller'):
            with self.assertRaises(ValueError): guard.check(path)
        guard.check('bluetooth_native')
        guard.cancel()
        guard.check('start')

    def test_status_does_not_reserve(self):
        guard = UpdateGuard()
        self.assertEqual(guard.status(self.engine()), {'busy': False, 'ready': False})
        guard.check('start')

import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from windows_bluetooth import MuseBluetooth, decode_eeg, BASE

class BluetoothTests(unittest.TestCase):
 def test_decode_counter_scale_and_channel(self):
  # Pair of ADC endpoints, repeated six times.
  p=decode_eeg(bytes([255,255])+bytes([0,15,255])*6,'AF7')
  self.assertEqual(p['counter'],65535);self.assertEqual(p['channel'],'AF7')
  self.assertEqual(p['values'],[-1000,999.51171875]*6)
  with self.assertRaises(ValueError):decode_eeg(b'bad','AF7')
 def transport(self):
  packets=[]
  engine=SimpleNamespace(lock=threading.RLock(),source='live',assembler=SimpleNamespace(add=packets.append))
  return MuseBluetooth(engine),packets
 def test_subscriptions_commands_packets_and_disconnect(self):
  transport,packets=self.transport();writes=[];subscribed=[]
  class Scanner:
   @staticmethod
   async def discover(**kwargs):return {'x':(SimpleNamespace(name='Muse-test'),SimpleNamespace(local_name='Muse-test'))}
  class Client:
   def __init__(self,*a,**k):self.is_connected=True;self.services=SimpleNamespace(get_characteristic=lambda uuid:SimpleNamespace(properties=['write-without-response']))
   async def __aenter__(self):return self
   async def __aexit__(self,*a):self.is_connected=False
   async def write_gatt_char(self,ch,payload,**kwargs):
    writes.append(payload)
    if payload==b'\x02d\n':transport.cancel.set()
   async def start_notify(self,uuid,callback):
    subscribed.append(uuid);callback(None,bytes([0,1])+bytes([128,8,0])*6)
  with patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakScanner=Scanner,BleakClient=Client)}):asyncio.run(transport.run())
  self.assertEqual([p['channel'] for p in packets],['TP9','AF7','AF8','TP10'])
  self.assertEqual(len(subscribed),4);self.assertEqual(writes,[b'\x02h\n',b'\x04p21\n',b'\x02d\n',b'\x02h\n'])
 def test_missing_device_reports_actionable_error(self):
  transport,_=self.transport()
  class Scanner:
   @staticmethod
   async def discover(**kwargs):return {}
  with patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakScanner=Scanner,BleakClient=None)}):transport.worker()
  self.assertEqual(transport.engine.status['state'],'bluetooth_error')
  self.assertIn('No Muse found',transport.engine.status['message'])

"""Store only a refresh token in macOS Keychain, never the account password."""
import ctypes as C
import sys
from private_storage import DATA_ROOT
import hashlib

def _operation(action, value=None):
 if sys.platform!='darwin':raise ValueError('Secure session storage requires macOS Keychain.')
 cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
 sec=C.CDLL('/System/Library/Frameworks/Security.framework/Security')
 P=C.c_void_p; L=C.c_long
 cf.CFStringCreateWithCString.argtypes=[P,C.c_char_p,C.c_uint32];cf.CFStringCreateWithCString.restype=P
 cf.CFDataCreate.argtypes=[P,C.c_char_p,L];cf.CFDataCreate.restype=P
 cf.CFDictionaryCreate.argtypes=[P,P,P,L,P,P];cf.CFDictionaryCreate.restype=P
 cf.CFDataGetLength.argtypes=[P];cf.CFDataGetLength.restype=L
 cf.CFDataGetBytePtr.argtypes=[P];cf.CFDataGetBytePtr.restype=P
 cf.CFRelease.argtypes=[P]
 owned=[]
 def string(x):
  p=cf.CFStringCreateWithCString(None,x.encode(),0x08000100);owned.append(p);return p
 def symbol(lib,name):return P.in_dll(lib,name).value
 def dictionary(items):
  k=(P*len(items))(*[x[0] for x in items]);v=(P*len(items))(*[x[1] for x in items]);p=cf.CFDictionaryCreate(None,k,v,len(items),None,None);owned.append(p);return p
 base=[(symbol(sec,'kSecClass'),symbol(sec,'kSecClassGenericPassword')),(symbol(sec,'kSecAttrService'),string('org.bandstand.session')),(symbol(sec,'kSecAttrAccount'),string(hashlib.sha256(str(DATA_ROOT).encode()).hexdigest()))]
 try:
  query=dictionary(base)
  sec.SecItemDelete.argtypes=[P];sec.SecItemDelete.restype=C.c_int
  if action=='delete':
   result=sec.SecItemDelete(query)
  elif action=='save':
   data=cf.CFDataCreate(None,value.encode(),len(value.encode()));owned.append(data)
   attributes=dictionary([(symbol(sec,'kSecValueData'),data)])
   sec.SecItemUpdate.argtypes=[P,P];sec.SecItemUpdate.restype=C.c_int
   result=sec.SecItemUpdate(query,attributes)
   if result==-25300:
    sec.SecItemAdd.argtypes=[P,P];sec.SecItemAdd.restype=C.c_int
    result=sec.SecItemAdd(dictionary(base+[(symbol(sec,'kSecValueData'),data)]),None)
  else:
   sec.SecItemCopyMatching.argtypes=[P,C.POINTER(P)];sec.SecItemCopyMatching.restype=C.c_int
   out=P();result=sec.SecItemCopyMatching(dictionary(base+[(symbol(sec,'kSecReturnData'),symbol(cf,'kCFBooleanTrue'))]),C.byref(out))
   if result==0:
    try:return C.string_at(cf.CFDataGetBytePtr(out),cf.CFDataGetLength(out)).decode()
    finally:cf.CFRelease(out)
  if result not in (0,-25300):raise ValueError('macOS Keychain was unavailable. Sign in again or allow Keychain access.')
  return None
 finally:
  for p in reversed(owned):cf.CFRelease(p)

def load():return _operation('load')
def save(token):return _operation('save',token)
def clear():return _operation('delete')

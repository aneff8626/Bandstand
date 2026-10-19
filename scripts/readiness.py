"""Run local release checks; external acceptance gates never pass by inference."""
import argparse, datetime, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXTERNAL=['github_collaborator_accepted','clean_mac_install_and_gatekeeper','remembered_account_restart',
          'stable_permissions_across_update','real_headset_and_typing','production_signup_email_received',
          'staging_two_account_isolation','production_erp_delivery','protected_federation_security_review']

def run(command, env):
 try:
  result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=300)
  # Do not copy arbitrary test output into a report that may be shared.
  return {'command':command,'passed':result.returncode==0,'exit_code':result.returncode}
 except subprocess.TimeoutExpired:return {'command':command,'passed':False,'error':'timeout'}
 except OSError:return {'command':command,'passed':False,'error':'runtime unavailable'}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--node',default=shutil.which('node') or 'node');args=parser.parse_args()
 with tempfile.TemporaryDirectory(prefix='bandstand-readiness-') as directory:
  env=dict(os.environ,BANDSTAND_DATA_DIR=directory,PYTHONDONTWRITEBYTECODE='1')
  checks=[run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],env)]
  for path in sorted((ROOT/'tests').glob('*.cjs')):
   checks.append(run([args.node,str(path.relative_to(ROOT))],env))
  report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'automated_passed':all(x['passed'] for x in checks),'checks':checks,
          'external_gates':{name:'NOT VERIFIED' for name in EXTERNAL},'release_ready':False}
  out=ROOT/'.audit/readiness.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2))
  print(json.dumps({'automated_passed':report['automated_passed'],'checks':len(checks),'failed':sum(not x['passed'] for x in checks),'external_gates':'NOT VERIFIED','report':str(out)}))
  return 0 if report['automated_passed'] else 1
if __name__=='__main__':sys.exit(main())

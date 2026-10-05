from __future__ import annotations
import argparse,json,py_compile,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=["README.md","NEXT_STEPS.md","NEW_REPO_SETUP_AND_PUSH.md","requirements.txt","src/quakemesh_core/correlation.py","local_runtime/app.py","simulator/cli.py","aws/infrastructure/stack.py","aws/lambdas/ingress.py","dashboard/index.html","android/app/src/main/AndroidManifest.xml","docs/QM-TRC-001_TRACEABILITY.md"]

def compile_python():
    bad=[]
    for p in ROOT.rglob('*.py'):
        if any(x in p.parts for x in ('.venv','.venv-cdk','artifacts','cdk.out')):continue
        try:py_compile.compile(str(p),doraise=True)
        except Exception as e:bad.append((p,e))
    if bad:raise RuntimeError("Python compilation failed: "+"; ".join(f"{p}: {e}" for p,e in bad))
    print("Python compilation: clean")

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();compile_python()
    if a.compile_only:return
    missing=[x for x in REQUIRED if not (ROOT/x).exists()]
    if missing:raise RuntimeError("Missing required files: "+", ".join(missing))
    for p in list((ROOT/'schemas').glob('*.json'))+[ROOT/'experiments/scenarios.json']:json.loads(p.read_text())
    for p in (ROOT/'android/app/src/main').rglob('*.xml'):ET.parse(p)
    if (ROOT/'dashboard/app.js').exists():
        try:subprocess.run(['node','--check',str(ROOT/'dashboard/app.js')],check=True,capture_output=True,text=True)
        except FileNotFoundError:print('Node unavailable: dashboard JS syntax check skipped')
    print("Repository structural audit: clean")
if __name__=='__main__':main()

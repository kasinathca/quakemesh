from pathlib import Path
import shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];out=ROOT/"artifacts"/"lambda-layer"/"python"
if out.parent.exists():shutil.rmtree(out.parent)
out.mkdir(parents=True)
cmd=[sys.executable,"-m","pip","install","--disable-pip-version-check","--platform","manylinux2014_x86_64","--implementation","cp","--python-version","3.12","--only-binary=:all:","--target",str(out),"h3==4.5.0"]
print(" ".join(cmd));subprocess.check_call(cmd);print(f"Built Lambda layer at {out.parent}")

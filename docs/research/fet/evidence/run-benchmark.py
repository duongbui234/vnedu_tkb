"""Reproduce local FET CLI measurements; no product/solver implementation."""
from pathlib import Path
import hashlib, json, re, subprocess, time, platform
ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "research/fet/fet-7.12.0"
BIN = ROOT / "reverse-engineering/fet/fet-cl"
OUT = ROOT / "reverse-engineering/fet/benchmark"
EVIDENCE = Path(__file__).parent
DATASETS = [
 ("german589", "official/by-Volker-Dirr/German_subact_constr.fet", 10),
 ("standby", "official/by-xdv/standby.fet", 10),
 ("pocht", "official/by-Alexey-Chernous/PochtSchool_default.fet", 10),
 ("ma582", "mornings-afternoons/Algeria/7-by-Benahmed-Abdelkrim/Test_View_Time_H_With_0_Gaps.fet", 10),
]
SEEDS = [[1,2,3,4,5,6], [11,12,13,14,15,16], [21,22,23,24,25,26]]
assert all(len(s)==6 and all(v>0 for v in s) for s in SEEDS)
assert BIN.is_file()
rows=json.loads((EVIDENCE/"benchmark-results.json").read_text()) if (EVIDENCE/"benchmark-results.json").exists() else []
for label, relative, limit in DATASETS + [("impossible5", "tests/2026-03-16-exams/test-liviu-2-impossible.fet", 2), ("large1517", "official/by-Eric-Carolus/MHS_July2.fet", 2)]:
 for ix, seed in enumerate(SEEDS if label in {"standby","pocht","ma582","german589"} else SEEDS[:1], 1):
  if any(row['label']==label and row['repeat']==ix for row in rows):
   continue
  source=SRC/"examples"/relative
  assert source.is_file()
  run=OUT/(label+"-s"+str(ix))
  run.mkdir(parents=True,exist_ok=False)
  cmd=[str(BIN), "--inputfile="+str(source), "--outputdir="+str(run), "--timelimitseconds="+str(limit), "--language=en", "--writetimetablesdayshorizontal=false", "--writetimetablesdaysvertical=false", "--writetimetablestimehorizontal=false", "--writetimetablestimevertical=false", "--writetimetableconflicts=true", "--writetimetablesxml=true", "--exportcsv=true"]
  cmd += ["--randomseed"+name+"="+str(value) for name,value in zip(["s10","s11","s12","s20","s21","s22"],seed)]
  (run/"command.json").write_text(json.dumps(cmd,indent=2))
  start=time.perf_counter()
  with (run/"stdout.txt").open("w") as stdout, (run/"stderr.txt").open("w") as stderr:
   result=subprocess.run(["/usr/bin/time","-v","-o",str(run/"resources.txt")]+cmd,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=45)
  duration=time.perf_counter()-start
  text=(run/"stdout.txt").read_text(errors="replace");res=(run/"resources.txt").read_text()
  def metric(key):
   m=re.search(re.escape(key)+r":\s*([0-9.]+)",res)
   return float(m[1]) if m else None
  row={"label":label,"repeat":ix,"input":str(source.relative_to(ROOT)),"sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"seed":seed,"limit_s":limit,"exit_code":result.returncode,"wall_s":round(duration,6),"user_s":metric("User time (seconds)"),"system_s":metric("System time (seconds)"),"max_rss_kib":metric("Maximum resident set size (kbytes)"),"output":str(run.relative_to(ROOT)),"tail":text[-1800:]}
  rows.append(row)
  (EVIDENCE/"benchmark-results.json").write_text(json.dumps(rows,indent=2))
  print(json.dumps({k:row[k] for k in ["label","repeat","exit_code","wall_s","user_s","max_rss_kib"]}),flush=True)

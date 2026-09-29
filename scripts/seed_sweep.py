"""Robustness: regenerate SimSOC with N different seeds and benchmark each (isolated dirs)."""
import os, sys, shutil, json, importlib
from pathlib import Path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
seeds = [int(s) for s in sys.argv[1:]] or [1, 2, 3, 4, 5]
base = Path(os.environ.get("SWEEP_DIR", "/tmp/socrix_sweep"))
rows = []
for s in seeds:
    home = base / str(s)
    shutil.rmtree(home, ignore_errors=True); (home / "data" / "reference").mkdir(parents=True)
    src = Path(__file__).resolve().parent.parent / "data" / "reference"
    for f in src.iterdir(): shutil.copy(f, home / "data" / "reference" / f.name)
    os.environ["SOCRIX_HOME"] = str(home)
    import socrix.config as C; importlib.reload(C)
    import socrix.attack, socrix.audit, socrix.simsoc, socrix.intake, socrix.indicators, socrix.scoring, socrix.prioritise, socrix.pipeline, socrix.benchmark
    for m in (socrix.attack, socrix.audit, socrix.simsoc, socrix.intake, socrix.indicators, socrix.scoring, socrix.prioritise, socrix.pipeline, socrix.benchmark):
        importlib.reload(m)
    socrix.simsoc.generate(C.SUBMISSIONS, seed=s)
    socrix.intake.ingest(C.SUBMISSIONS, C.DB_PATH)
    socrix.pipeline.run(C.DB_PATH)
    b = socrix.benchmark.run(C.DB_PATH, C.DATA / "ground_truth.json")
    rows.append((s, b["detected"], b["planted"], b["false_positives"], b["clean_entity_false_positives"], b["missed_list"], b["fp_list"]))
    print(s, f"recall {b['detected']}/{b['planted']}", f"FP {b['false_positives']} (clean {b['clean_entity_false_positives']})",
          "missed:", b["missed_list"], "fp:", b["fp_list"], flush=True)
tot_d = sum(r[1] for r in rows); tot_p = sum(r[2] for r in rows); tot_fp = sum(r[3] for r in rows)
print(f"TOTAL recall {tot_d}/{tot_p} = {tot_d/tot_p:.1%}; FP {tot_fp}; precision {tot_d/(tot_d+tot_fp):.1%}")

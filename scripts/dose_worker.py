"""One detection-limit run: SOCRIX_HOME/SOCRIX_DOSE set by caller. Prints JSON."""
import json, os, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
home = Path(os.environ["SOCRIX_HOME"]); ref = Path(__file__).resolve().parent.parent / "data" / "reference"
(home / "data" / "reference").mkdir(parents=True, exist_ok=True)
for f in ref.iterdir(): shutil.copy(f, home / "data" / "reference" / f.name)
from socrix import config as C, simsoc, intake, pipeline, benchmark
import duckdb
seed = int(sys.argv[1])
simsoc.generate(C.SUBMISSIONS, seed=seed); intake.ingest(C.SUBMISSIONS, C.DB_PATH); pipeline.run(C.DB_PATH)
b = benchmark.run(C.DB_PATH, C.DATA / "ground_truth.json")
con = duckdb.connect(str(C.DB_PATH), read_only=True)
sha = sorted(r[0] for r in con.execute("select sha256 from receipts").fetchall())
print(json.dumps(dict(seed=seed, dose=simsoc.DOSE, archetypes=b["archetypes"], fp=b["false_positives"],
                      clean_fp=b["clean_entity_false_positives"], fp_list=b["fp_list"], sha=sha)))

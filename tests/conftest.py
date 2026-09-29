"""Tests run the real pipeline once in an isolated SOCRIX_HOME (never touches ./data).
TZ is set to Asia/Kolkata on purpose: it reproduces the DuckDB 'Asia/Calcutta' timezone failure seen during the build."""
import os, shutil, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(tempfile.mkdtemp(prefix="socrix_test_"))
(HOME / "data" / "reference").mkdir(parents=True)
for f in (ROOT / "data" / "reference").iterdir():
    shutil.copy(f, HOME / "data" / "reference" / f.name)
os.environ["SOCRIX_HOME"] = str(HOME)
os.environ["TZ"] = "Asia/Kolkata"
os.environ["SOCRIX_PSEUDONYM_KEY"] = "test-key"


@pytest.fixture(scope="session")
def built():
    from socrix import config as C, simsoc, intake, pipeline, benchmark
    simsoc.generate(C.SUBMISSIONS, seed=C.RANDOM_SEED)
    summary = intake.ingest(C.SUBMISSIONS, C.DB_PATH)
    results = pipeline.run(C.DB_PATH)
    bench = benchmark.run(C.DB_PATH, C.DATA / "ground_truth.json")
    return dict(summary=summary, results=results, bench=bench, C=C)

import os


# The Makefile turns both off; a run that forgot would send data out.
def test_telemetry_is_off():
    assert os.environ.get("DEEPEVAL_TELEMETRY_OPT_OUT") == "YES"
    assert os.environ.get("ANONYMIZED_TELEMETRY") == "False"

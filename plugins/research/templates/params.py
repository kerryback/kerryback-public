"""The frozen method spec, as code.

`project/global/method_spec.md` pins the choices that could move a result. This
file is that pin in executable form: every implementer imports the same values
instead of transcribing them, so a number can never differ because someone typed
the wrong year.

    import sys; sys.path.insert(0, str(REPO_ROOT / "workspaces" / "global"))
    from params import SAMPLE_YEARS, SEED

CHANGING THIS FILE IS A SPEC CHANGE. It goes through the same gate as
method_spec.md.

WHAT BELONGS HERE
  IN   what the spec freezes — sample window, screens, feature list, estimator
       hyperparameters, seeds, fold count. Both implementers are REQUIRED to use
       identical values; a difference is a spec violation, not evidence.
  OUT  how a build is written — column names, dataframe layout, helper
       structure. That difference is the point of having two builds.
  OUT  paths. Those come from DATA_ROOT / GLOBAL_DATA / WORK_ROOT / REPO_ROOT.

When this file changes, re-check each value against the code it came from.
Writing it from memory is how a wrong feature list gets in, and nothing errors —
the numbers just come out different.
"""

# --- sample -------------------------------------------------------------------
# SAMPLE_YEARS = list(range(2000, 2026))

# --- estimator ----------------------------------------------------------------
# SEED = 42

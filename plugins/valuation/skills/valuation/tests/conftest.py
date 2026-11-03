"""Put the skill directory and the tests directory on the path.

The skill's scripts sit beside SKILL.md rather than in a package, because that
is how a skill is laid out and how Claude will invoke them. The tests import
them directly, and import each other's fixtures.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

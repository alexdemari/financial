from joblib import Memory

import os

location = os.path.join(os.path.dirname(__file__), "../../cache/joblib")
memory = Memory(location=location, verbose=0)

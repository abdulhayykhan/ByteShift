# Compatibility shim for pydub on Python 3.13+
# pydub tries to import pyaudioop, but we have audioop-lts installed as audioop
from audioop import *

#!/usr/bin/env python
"""
Import this code to set up your interactive repl
"""
from sqlalchemy import select
from sqlalchemy.sql import func

def format_json(o):
    return _format_json(o, handler=_handler)

from models import *

try:
    import IPython
    IPython.embed()
except:
    import code
    code.InteractiveConsole(locals=locals()).interact()


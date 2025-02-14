import logging
import json
import sys
import os

logger = None

def use_logginghandler():
    global logger
    if logger is not None:
        return logger
        
    l = logging.getLogger()
    l.setLevel("INFO")
    handler = logging.StreamHandler(sys.stdout)
    l.addHandler(handler)
    logger = l
    return logger
    
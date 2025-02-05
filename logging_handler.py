import logging
import json
import sys
import os

def use_logginghandler():
    logger = logging.getLogger()
    logger.setLevel("INFO")
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    return logger
    
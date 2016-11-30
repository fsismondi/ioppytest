# -*- coding: utf-8 -*-
#!/usr/bin/env python3

import logging
import os.path
import sys


def initialize_logger(output_dir, component_id):

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(component_id)
    logger.propagate = False
    #logger.setLevel(logging.DEBUG)

    # create console handler and set level to info
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("[ %(module)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # create error file handler and set level to error
    handler = logging.FileHandler(os.path.join(output_dir, "%s.error.log"%component_id), "w")
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter("[ %(module)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # create debug file handler and set level to debug
    handler = logging.FileHandler(os.path.join(output_dir, "%s.all.log"%component_id), "w")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[ %(module)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
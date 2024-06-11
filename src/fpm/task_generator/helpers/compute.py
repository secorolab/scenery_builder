#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later

import rdflib
import json
import os
from pyld import jsonld
from pprint import pprint
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

import numpy as np

def load_json(path):
    with open(path, "r") as file:
        return json.load(file)

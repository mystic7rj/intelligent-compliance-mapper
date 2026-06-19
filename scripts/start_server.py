#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Startup script for the FastAPI compliance mapper server."""

import os
import sys

# Ensure the project root (parent of scripts/) is on sys.path and is the cwd
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)

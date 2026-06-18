#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Startup script for the FastAPI compliance mapper server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)

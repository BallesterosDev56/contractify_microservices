#!/bin/bash
cd contract_service
uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}

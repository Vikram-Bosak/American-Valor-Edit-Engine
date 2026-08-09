#!/bin/bash
echo "Starting American Valor Automation Pipeline in Production Mode..."
nohup ./venv/bin/python daemon.py > daemon.log 2>&1 &
echo "Pipeline is now running in the background!"
echo "To view logs, run: tail -f daemon.log"
echo "To stop the pipeline, run: pkill -f daemon.py"

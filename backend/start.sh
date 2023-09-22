#!/bin/bash

thisFileDir="$( cd "$( dirname "${BASH_SOURCE[0]}")" && pwd )"

cd $thisFileDir
nohup uvicorn web:app --reload --host 0.0.0.0 --port 5007 --limit-max-requests 10485760 >> nohup.out &
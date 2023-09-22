
conda activate /opt/disk2/env-embedchain/

Depends:
    pip install fastapi uvicorn apscheduler python-multipart aiohttp request
    pip install embedchain

cd /opt/disk2/github/embedchain
nohup uvicorn web:app --reload --port 5007 >> nohup.out &

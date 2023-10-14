
conda activate /opt/disk2/env-embedchain-v1/

Depends:
    pip install fastapi uvicorn apscheduler python-multipart aiohttp request sseclient
    pip install embedchain==0.0.69

v1 = 0.0.69

cd /opt/disk2/github/embedchain
nohup uvicorn web:app --reload --port 5007 >> nohup.out &

import config
URL = f'{config.PROXY_HOST_PORT}/openai-api-proxy/chat'

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import aiohttp
import logging

async def proxy(user, prompt, model) -> StreamingResponse:
    generator = proxy_generator(user, prompt, model)
    return StreamingResponse(generator)

async def proxy_generator(user: str, prompt: str, model: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(URL, json={"prompt":prompt, "user": user, "user_group": "marvin", "model": model}) as response:
                s = ''
                async for data in response.content.iter_any():
                    yield data
                    try:
                        s += str(data.decode('utf-8'))
                    except:
                        logging.exception('ops')
                        
                logging.info('========start reply========')
                logging.info(s)
                logging.info('========end of reply========')
        except Exception as e:
            yield f'Exception: {e}'

async def proxy_sync(user: str, prompt: str, model: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(URL, json={"prompt":prompt, "user": user, "user_group": "marvin", "model": model}) as response:
            return await response.text()

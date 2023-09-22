async function streamPostRequest(url, body, headers) {
    const response = await fetch(url, {
        method: 'POST',
        body: JSON.stringify(body),
        headers,
    });
    const reader = response.body.getReader();
    return new ReadableStream({
        async start(controller) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }
                controller.enqueue(value);
            }
            controller.close();
        }
    });
}

export async function handleStream(url, bodyObject, headerObject, handleOutput) {
    const stream = await streamPostRequest(url, bodyObject, headerObject);
    const decoder = new TextDecoder();
    const reader = stream.getReader();
    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            break;
        }
        const text = decoder.decode(value);
        console.log(text);
        handleOutput(text)
    }
    handleOutput(null)
}
